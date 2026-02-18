"""
GOVY - Pipeline de Extracao de Jurisprudencia
SPEC 1.2 - Knowledge Base Juridica

Pipeline 2-pass:
1. Passo A: GPT-4o extrai todos os elementos (function-calling)
2. Passo B: Claude Sonnet audita campos criticos (function-calling)

Auto-aprovacao: agree == true AND confidence >= 0.90
Caso contrario: fila do juridico
"""

import os
import json
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime
import uuid

# OpenAI e Anthropic
from openai import OpenAI
import anthropic

# Modulos locais
from .juris_regex import has_fundamento_legal
from .juris_constants import (
    PROCEDURAL_STAGES, HOLDING_OUTCOMES, REMEDY_TYPES, EFFECTS,
    PISTAS_PROCEDURAL_STAGE,
    CONFIDENCE_THRESHOLD, UF_TO_REGION
)

logger = logging.getLogger(__name__)

# =============================================================================
# SCHEMAS PARA FUNCTION-CALLING
# =============================================================================

# Schema GPT-4o (Extracao) - COM fundamento_legal
EXTRACTION_SCHEMA_FULL = {
    "name": "extract_jurisprudencia",
    "description": "Extrai informacoes estruturadas de jurisprudencia de licitacoes",
    "parameters": {
        "type": "object",
        "properties": {
            "tese": {
                "type": "string",
                "description": "Enunciado/regra principal do caso (1-2 frases)"
            },
            "vital": {
                "type": "string",
                "description": "Trecho operacional com comando do tribunal, copiavel para peca juridica (ate 200 palavras)"
            },
            "fundamento_legal": {
                "type": ["string", "null"],
                "description": "Artigos/leis citados no texto. NULL se nao houver referencia legal explicita"
            },
            "limites": {
                "type": ["string", "null"],
                "description": "Condicoes, ressalvas ou excecoes ('desde que...', 'salvo...'). NULL se nao houver"
            },
            "contexto_minimo": {
                "type": ["string", "null"],
                "description": "Fatos essenciais do caso (ate 100 palavras). NULL se nao for relevante"
            },
            "procedural_stage": {
                "type": "string",
                "enum": PROCEDURAL_STAGES,
                "description": "Fase do processo licitatorio"
            },
            "holding_outcome": {
                "type": "string",
                "enum": HOLDING_OUTCOMES,
                "description": "Resultado/decisao do caso"
            },
            "remedy_type": {
                "type": "string",
                "enum": REMEDY_TYPES,
                "description": "Tipo de remedio/instrumento processual"
            },
            "effect": {
                "type": "string",
                "enum": EFFECTS,
                "description": "Efeito da decisao: FLEXIBILIZA (favorece licitante), RIGORIZA (favorece administracao), CONDICIONAL (depende), NAO_CLARO"
            },
            "key_facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 fatos-chave do caso"
            },
            "claim_pattern": {
                "type": "string",
                "description": "Padrao de tese em 1 frase (ex: 'exigencia de atestado com quantitativo minimo')"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confianca geral na extracao (0.0 a 1.0)"
            }
        },
        "required": ["tese", "vital", "procedural_stage", "holding_outcome", "remedy_type", "effect", "claim_pattern", "confidence"]
    }
}

# Schema GPT-4o (Extracao) - SEM fundamento_legal (regex nao disparou)
EXTRACTION_SCHEMA_NO_LEGAL = {
    "name": "extract_jurisprudencia",
    "description": "Extrai informacoes estruturadas de jurisprudencia de licitacoes (sem fundamento legal)",
    "parameters": {
        "type": "object",
        "properties": {
            "tese": {
                "type": "string",
                "description": "Enunciado/regra principal do caso (1-2 frases)"
            },
            "vital": {
                "type": "string",
                "description": "Trecho operacional com comando do tribunal, copiavel para peca juridica (ate 200 palavras)"
            },
            "limites": {
                "type": ["string", "null"],
                "description": "Condicoes, ressalvas ou excecoes ('desde que...', 'salvo...'). NULL se nao houver"
            },
            "contexto_minimo": {
                "type": ["string", "null"],
                "description": "Fatos essenciais do caso (ate 100 palavras). NULL se nao for relevante"
            },
            "procedural_stage": {
                "type": "string",
                "enum": PROCEDURAL_STAGES,
                "description": "Fase do processo licitatorio"
            },
            "holding_outcome": {
                "type": "string",
                "enum": HOLDING_OUTCOMES,
                "description": "Resultado/decisao do caso"
            },
            "remedy_type": {
                "type": "string",
                "enum": REMEDY_TYPES,
                "description": "Tipo de remedio/instrumento processual"
            },
            "effect": {
                "type": "string",
                "enum": EFFECTS,
                "description": "Efeito da decisao: FLEXIBILIZA (favorece licitante), RIGORIZA (favorece administracao), CONDICIONAL (depende), NAO_CLARO"
            },
            "key_facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 fatos-chave do caso"
            },
            "claim_pattern": {
                "type": "string",
                "description": "Padrao de tese em 1 frase (ex: 'exigencia de atestado com quantitativo minimo')"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confianca geral na extracao (0.0 a 1.0)"
            }
        },
        "required": ["tese", "vital", "procedural_stage", "holding_outcome", "remedy_type", "effect", "claim_pattern", "confidence"]
    }
}

# Alias para compatibilidade
EXTRACTION_SCHEMA = EXTRACTION_SCHEMA_FULL

# Schema Claude Sonnet (Auditoria)
AUDIT_SCHEMA = {
    "name": "audit_jurisprudencia",
    "description": "Audita extracao de jurisprudencia para garantir qualidade",
    "input_schema": {
        "type": "object",
        "properties": {
            "audits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "campo": {
                            "type": "string",
                            "description": "Nome do campo auditado"
                        },
                        "agree": {
                            "type": "boolean",
                            "description": "Concorda com a extracao?"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confianca na avaliacao (0.0 a 1.0)"
                        },
                        "correction": {
                            "type": ["string", "null"],
                            "description": "Correcao sugerida se agree=false"
                        },
                        "evidence_quote": {
                            "type": "string",
                            "description": "Trecho do texto original que suporta a decisao"
                        },
                        "justificativa": {
                            "type": "string",
                            "description": "Justificativa da avaliacao"
                        }
                    },
                    "required": ["campo", "agree", "confidence", "evidence_quote", "justificativa"]
                }
            },
            "overall_confidence": {
                "type": "number",
                "description": "Confianca geral na extracao auditada"
            },
            "recommend_human_review": {
                "type": "boolean",
                "description": "Recomenda revisao humana?"
            },
            "review_reason": {
                "type": ["string", "null"],
                "description": "Motivo da recomendacao de revisao"
            }
        },
        "required": ["audits", "overall_confidence", "recommend_human_review"]
    }
}


# =============================================================================
# PROMPTS
# =============================================================================

def build_extraction_prompt(full_text: str, has_legal_refs: bool, legal_refs: List[str]) -> str:
    """Constroi prompt para GPT-4o."""
    
    # Formata pistas
    pistas_text = ""
    for stage, keywords in PISTAS_PROCEDURAL_STAGE.items():
        pistas_text += f"  {stage}: {', '.join(keywords[:5])}...\n"
    
    fundamento_instruction = ""
    fundamento_field_instruction = ""
    if has_legal_refs:
        fundamento_instruction = f"""
FUNDAMENTO LEGAL DETECTADO:
Referencias encontradas: {', '.join(legal_refs[:10])}
Extraia o fundamento_legal com os artigos/leis relevantes para a tese.
"""
        fundamento_field_instruction = "3. FUNDAMENTO_LEGAL: Artigos/leis citados (null se nao detectado)\n\n"
    else:
        fundamento_instruction = """
FUNDAMENTO LEGAL NAO DETECTADO:
Nao foram encontradas referencias explicitas a artigos ou leis.
NAO extraia fundamento_legal. Este campo NAO esta no schema.
"""

    return f"""Voce e um especialista em jurisprudencia de licitacoes publicas brasileiras.

TAREFA: Extrair informacoes estruturadas do texto juridico abaixo.

{fundamento_instruction}

TEXTO:
{full_text}

INSTRUCOES:

1. TESE:
   Enunciado/regra principal (1-2 frases objetivas).
   O que o tribunal ENTENDE como regra abstrata.

2. VITAL:
   Extraia o trecho mais forte e OPERACIONAL da decisao, que possa ser COPIADO E COLADO diretamente em uma peca juridica.
   O trecho deve, sempre que possivel:
   - conter a CONSEQUENCIA PRATICA ou COMANDO do tribunal (ex.: "determinou a anulacao...", "afastou a exigencia...", "nao e suficiente para inabilitar...");
   - refletir a aplicacao concreta da tese ao caso;
   - ser DISTINTO da TESE, ainda que ambos tratem do mesmo tema.
   Se o texto nao contiver consequencia pratica clara, retorne vital=null e confidence baixa.
   NAO usar vital como simples reescrita da tese.

{fundamento_field_instruction}3. LIMITES: Ressalvas ou condicoes ("desde que...", "salvo...") - null se nao houver

4. CONTEXTO_MINIMO: Fatos essenciais do caso (ate 100 palavras) - null se generico

5. CLASSIFICACOES: Use as pistas abaixo para maior precisao

PISTAS PARA PROCEDURAL_STAGE:
{pistas_text}

PISTAS PARA EFFECT:
  FLEXIBILIZA: nao e suficiente para inabilitar, saneamento, falha formal sanavel, exigencia restritiva
  RIGORIZA: manteve inabilitacao, nao cabe saneamento, exigencia legitima, vinculacao ao edital
  CONDICIONAL: desde que, a depender, em regra... salvo, se justificado tecnicamente

REGRAS:
- Se nao tiver certeza de um campo, retorne null ou NAO_CLARO
- Nunca invente informacoes que nao estao no texto
- confidence deve refletir sua confianca real na extracao

Retorne via ferramenta/schema estruturado."""


def build_audit_prompt(extraction: Dict, full_text: str) -> str:
    """Constroi prompt para Claude Sonnet."""
    
    extraction_json = json.dumps(extraction, ensure_ascii=False, indent=2)
    
    return f"""Voce e um auditor de qualidade para jurisprudencia de licitacoes publicas brasileiras.

TAREFA: Auditar a extracao abaixo e garantir que esta correta.

PROPOSTA DO EXTRATOR:
{extraction_json}

TEXTO ORIGINAL:
{full_text}

CAMPOS A AUDITAR (em ordem de prioridade):

1. effect - CRITICO: impacta diretamente o matching de cenario. Esta correto?

2. vital - ESSENCIAL: 
   - Verifique se o trecho e OPERACIONAL/copiar-colar, e NAO apenas uma repeticao conceitual da tese.
   - Se vital e tese forem essencialmente iguais, DISCORDAR do vital.
   - O vital DEVE conter consequencia pratica ou comando do tribunal (determinou, afastou, anulou, manteve, nao e suficiente para...).
   - Se o vital for apenas a regra abstrata sem comando/consequencia, discordar.

3. fundamento_legal - Se preenchido: existe no texto ou e invencao?

4. limites - Se preenchido: existem ressalvas nao capturadas?

5. procedural_stage / holding_outcome / remedy_type - Classificacoes corretas?

REGRAS DE AUDITORIA:
- Para CADA campo auditado, forneca evidence_quote (trecho literal do texto)
- Se agree=false, forneca correction com o valor correto
- confidence deve refletir sua certeza na avaliacao
- recommend_human_review=true se houver ambiguidade significativa

ATENCAO ESPECIAL:
- effect: Nao confundir FLEXIBILIZA (favorece licitante) com RIGORIZA (favorece administracao)
- vital: Deve ser um trecho OPERACIONAL com comando/consequencia, NAO um resumo ou reescrita da tese
- fundamento_legal: Se nao ha artigos/leis explicitos, deve ser null

Retorne via ferramenta/schema estruturado."""


# =============================================================================
# PIPELINE PRINCIPAL
# =============================================================================

class JurisPipeline:
    """Pipeline de extracao de jurisprudencia."""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    def extract_with_gpt4o(self, full_text: str, has_legal_refs: bool, legal_refs: List[str]) -> Dict[str, Any]:
        """Passo A: Extracao com GPT-4o."""

        prompt = build_extraction_prompt(full_text, has_legal_refs, legal_refs)
        schema = EXTRACTION_SCHEMA_FULL if has_legal_refs else EXTRACTION_SCHEMA_NO_LEGAL

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                tools=[{"type": "function", "function": schema}],
                tool_choice={"type": "function", "function": {"name": "extract_jurisprudencia"}}
            )
            
            # Extrai resultado do function call
            tool_call = response.choices[0].message.tool_calls[0]
            result = json.loads(tool_call.function.arguments)
            
            return {
                "status": "success",
                "extraction": result,
                "model": "gpt-4o",
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Erro GPT-4o: {e}")
            return {
                "status": "error",
                "error": str(e),
                "model": "gpt-4o"
            }
    
    def audit_with_claude(self, extraction: Dict, full_text: str) -> Dict[str, Any]:
        """Passo B: Auditoria com Claude Sonnet."""
        
        prompt = build_audit_prompt(extraction, full_text)
        
        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                tools=[AUDIT_SCHEMA],
                tool_choice={"type": "tool", "name": "audit_jurisprudencia"},
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extrai resultado do tool use
            tool_use = next(
                (block for block in response.content if block.type == "tool_use"),
                None
            )
            
            if tool_use:
                result = tool_use.input
                return {
                    "status": "success",
                    "audit": result,
                    "model": "claude-sonnet-4-20250514",
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }
            else:
                return {
                    "status": "error",
                    "error": "No tool_use block in response",
                    "model": "claude-sonnet-4-20250514"
                }
                
        except Exception as e:
            logger.error(f"Erro Claude: {e}")
            return {
                "status": "error",
                "error": str(e),
                "model": "claude-sonnet-4-20250514"
            }
    
    def apply_corrections(self, extraction: Dict, audit: Dict) -> Dict:
        """Aplica correcoes do auditor a extracao."""
        
        corrected = extraction.copy()
        
        for audit_item in audit.get("audits", []):
            campo = audit_item.get("campo")
            if not audit_item.get("agree") and audit_item.get("correction"):
                if campo in corrected:
                    corrected[campo] = audit_item["correction"]
                    logger.info(f"Corrigido {campo}: {extraction.get(campo)} -> {audit_item['correction']}")
        
        return corrected
    
    def should_auto_approve(self, audit: Dict) -> Tuple[bool, str]:
        """Verifica se pode auto-aprovar baseado na auditoria."""
        
        # Se auditor recomenda revisao humana
        if audit.get("recommend_human_review"):
            return False, audit.get("review_reason", "Auditor recomendou revisao")
        
        # Verifica confianca geral
        overall_confidence = audit.get("overall_confidence", 0)
        if overall_confidence < CONFIDENCE_THRESHOLD:
            return False, f"Confianca geral baixa: {overall_confidence:.2f}"
        
        # Verifica cada campo critico
        critical_fields = ["effect", "vital"]
        for audit_item in audit.get("audits", []):
            campo = audit_item.get("campo")
            if campo in critical_fields:
                if not audit_item.get("agree"):
                    return False, f"Auditor discordou de {campo}"
                if audit_item.get("confidence", 0) < CONFIDENCE_THRESHOLD:
                    return False, f"Confianca baixa em {campo}: {audit_item.get('confidence'):.2f}"
        
        return True, "Auto-aprovado"
    
    def process(self, full_text: str, title: str, citation_base: str, doc_meta: Dict) -> Dict[str, Any]:
        """
        Processa jurisprudencia completa.
        
        Args:
            full_text: Texto completo
            title: Titulo do documento
            citation_base: Base da citacao (ex: "TCU, Acordao 2666/2025-Plenario")
            doc_meta: Metadados (tribunal, uf, year, source, is_current)
            
        Returns:
            Dict com chunks, metadados, status de aprovacao
        """
        
        process_id = str(uuid.uuid4())[:8]
        logger.info(f"[{process_id}] Iniciando processamento: {title}")
        
        result = {
            "process_id": process_id,
            "title": title,
            "citation_base": citation_base,
            "doc_meta": doc_meta,
            "timestamp": datetime.utcnow().isoformat(),
            "chunks": [],
            "meta": {},
            "status": "processing",
            "auto_approved": False,
            "review_reason": None,
            "errors": []
        }
        
        # 1. Verifica regex para fundamento_legal
        has_legal, legal_refs = has_fundamento_legal(full_text)
        result["has_fundamento_legal"] = has_legal
        result["legal_refs_found"] = legal_refs[:10] if legal_refs else []
        logger.info(f"[{process_id}] Regex fundamento_legal: {has_legal} ({len(legal_refs)} refs)")
        
        # 2. Passo A: Extracao com GPT-4o
        logger.info(f"[{process_id}] Passo A: GPT-4o extracao...")
        extraction_result = self.extract_with_gpt4o(full_text, has_legal, legal_refs)
        
        if extraction_result["status"] != "success":
            result["status"] = "error"
            result["errors"].append(f"GPT-4o: {extraction_result.get('error')}")
            return result
        
        extraction = extraction_result["extraction"]
        result["extraction_raw"] = extraction
        result["gpt4o_usage"] = extraction_result.get("usage")
        
        # Se regex nao disparou, forca fundamento_legal = null
        if not has_legal:
            extraction["fundamento_legal"] = None
            logger.info(f"[{process_id}] fundamento_legal forcado para null (regex nao disparou)")
        
        # 3. Passo B: Auditoria com Claude Sonnet
        logger.info(f"[{process_id}] Passo B: Claude auditoria...")
        audit_result = self.audit_with_claude(extraction, full_text)
        
        if audit_result["status"] != "success":
            result["status"] = "error"
            result["errors"].append(f"Claude: {audit_result.get('error')}")
            return result
        
        audit = audit_result["audit"]
        result["audit_raw"] = audit
        result["claude_usage"] = audit_result.get("usage")
        
        # 4. Aplica correcoes
        corrected = self.apply_corrections(extraction, audit)
        
        # 5. Verifica auto-aprovacao
        auto_approved, review_reason = self.should_auto_approve(audit)
        result["auto_approved"] = auto_approved
        result["review_reason"] = review_reason
        
        # 6. Monta chunks
        chunks = []
        
        # Chunk: tese
        if corrected.get("tese"):
            chunks.append({
                "chunk_id": f"{process_id}-tese",
                "secao": "tese",
                "content": corrected["tese"],
                "citation": f"{citation_base}, tese",
                "confidence": audit.get("overall_confidence", 0),
                "approved": auto_approved
            })
        
        # Chunk: vital
        if corrected.get("vital"):
            chunks.append({
                "chunk_id": f"{process_id}-vital",
                "secao": "vital",
                "content": corrected["vital"],
                "citation": f"{citation_base}, vital",
                "confidence": audit.get("overall_confidence", 0),
                "approved": auto_approved
            })
        
        # Chunk: fundamento_legal (so se existe)
        if corrected.get("fundamento_legal"):
            chunks.append({
                "chunk_id": f"{process_id}-fundamento",
                "secao": "fundamento_legal",
                "content": corrected["fundamento_legal"],
                "citation": f"{citation_base}, fundamento legal",
                "confidence": audit.get("overall_confidence", 0),
                "approved": auto_approved
            })
        
        # Chunk: limites (so se existe)
        if corrected.get("limites"):
            chunks.append({
                "chunk_id": f"{process_id}-limites",
                "secao": "limites",
                "content": corrected["limites"],
                "citation": f"{citation_base}, limites",
                "confidence": audit.get("overall_confidence", 0),
                "approved": auto_approved
            })
        
        # Chunk: contexto_minimo (so se existe)
        if corrected.get("contexto_minimo"):
            chunks.append({
                "chunk_id": f"{process_id}-contexto",
                "secao": "contexto_minimo",
                "content": corrected["contexto_minimo"],
                "citation": f"{citation_base}, contexto",
                "confidence": audit.get("overall_confidence", 0),
                "approved": auto_approved
            })
        
        # Adiciona metadados comuns a todos os chunks
        for chunk in chunks:
            chunk.update({
                "doc_type": "jurisprudencia",
                "tribunal": doc_meta.get("tribunal"),
                "uf": doc_meta.get("uf"),
                "region": UF_TO_REGION.get(doc_meta.get("uf")) if doc_meta.get("uf") else None,
                "year": doc_meta.get("year"),
                "source": doc_meta.get("source"),
                "is_current": doc_meta.get("is_current", True),
                "title": title,
                "effect": corrected.get("effect"),
                "procedural_stage": corrected.get("procedural_stage"),
                "holding_outcome": corrected.get("holding_outcome"),
                "remedy_type": corrected.get("remedy_type"),
                "claim_pattern": corrected.get("claim_pattern"),
            })
        
        result["chunks"] = chunks
        
        # 7. Monta metadados consolidados
        result["meta"] = {
            "effect": corrected.get("effect"),
            "procedural_stage": corrected.get("procedural_stage"),
            "holding_outcome": corrected.get("holding_outcome"),
            "remedy_type": corrected.get("remedy_type"),
            "key_facts": corrected.get("key_facts", []),
            "claim_pattern": corrected.get("claim_pattern"),
        }
        
        result["status"] = "approved" if auto_approved else "pending_review"
        
        logger.info(f"[{process_id}] Processamento concluido: {result['status']} ({len(chunks)} chunks)")
        
        return result
