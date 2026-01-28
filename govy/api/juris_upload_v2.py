# govy/api/juris_upload.py
# Endpoint: POST /api/juris/upload
# Aceita RTF, PDF, TXT, DOCX via base64 ou texto direto

import azure.functions as func
import json
import logging
import os
import base64
import re
import psycopg2
import openai
from anthropic import Anthropic

# Configuracao
PG_HOST = "postgresqlgovy-kb.postgres.database.azure.com"
PG_DB = "govy_kb"
PG_USER = "pgadmin"

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        database=PG_DB,
        user=PG_USER,
        password=os.environ.get("PG_PASSWORD"),
        sslmode="require"
    )


def extract_text_from_rtf(rtf_content):
    """Extrai texto puro de conteudo RTF."""
    try:
        # Decodificar se for bytes
        if isinstance(rtf_content, bytes):
            rtf_content = rtf_content.decode('latin-1', errors='ignore')
        
        # Remover grupos RTF de controle
        text = rtf_content
        
        # Remover header RTF
        text = re.sub(r'\\rtf1.*?\\viewkind4', '', text, flags=re.DOTALL)
        
        # Converter caracteres especiais RTF
        replacements = {
            r"\\'e1": "a", r"\\'e9": "e", r"\\'ed": "i", r"\\'f3": "o", r"\\'fa": "u",
            r"\\'e0": "a", r"\\'e8": "e", r"\\'ec": "i", r"\\'f2": "o", r"\\'f9": "u",
            r"\\'e2": "a", r"\\'ea": "e", r"\\'ee": "i", r"\\'f4": "o", r"\\'fb": "u",
            r"\\'e3": "a", r"\\'f5": "o", r"\\'e7": "c", r"\\'c7": "C",
            r"\\'c1": "A", r"\\'c9": "E", r"\\'cd": "I", r"\\'d3": "O", r"\\'da": "U",
            r"\\'c0": "A", r"\\'c8": "E", r"\\'cc": "I", r"\\'d2": "O", r"\\'d9": "U",
            r"\\'c2": "A", r"\\'ca": "E", r"\\'ce": "I", r"\\'d4": "O", r"\\'db": "U",
            r"\\'c3": "A", r"\\'d5": "O",
            r"\\'ba": "o", r"\\'aa": "a",  # ordinals
            r"\\'b0": " graus ",
            r"\\'a7": " paragrafo ",
            r"\\'93": '"', r"\\'94": '"',
            r"\\'91": "'", r"\\'92": "'",
            r"\\'96": "-", r"\\'97": "-",
            r"\\'85": "...",
        }
        
        for rtf_code, char in replacements.items():
            text = text.replace(rtf_code, char)
        
        # Remover comandos RTF restantes
        text = re.sub(r'\\[a-z]+\d*\s?', ' ', text)
        text = re.sub(r'\\[*]', '', text)
        text = re.sub(r'\{|\}', '', text)
        
        # Limpar espacos extras
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    except Exception as e:
        logging.error(f"Erro ao extrair texto RTF: {str(e)}")
        return ""


def extract_text_from_pdf_simple(pdf_bytes):
    """Extrai texto de PDF usando metodo simples (sem dependencias externas)."""
    try:
        # Tentar extrair texto diretamente do PDF
        text = ""
        content = pdf_bytes.decode('latin-1', errors='ignore')
        
        # Procurar por streams de texto
        streams = re.findall(r'stream(.*?)endstream', content, re.DOTALL)
        
        for stream in streams:
            # Extrair texto visivel
            text_parts = re.findall(r'\((.*?)\)', stream)
            text += ' '.join(text_parts)
        
        # Se nao encontrou texto, pode ser PDF com encoding diferente
        if len(text) < 100:
            # Tentar outro metodo - BT/ET blocks
            bt_blocks = re.findall(r'BT(.*?)ET', content, re.DOTALL)
            for block in bt_blocks:
                tj_texts = re.findall(r'\[(.*?)\]TJ', block)
                for tj in tj_texts:
                    parts = re.findall(r'\((.*?)\)', tj)
                    text += ' '.join(parts)
        
        return text.strip() if text else None
        
    except Exception as e:
        logging.error(f"Erro ao extrair texto PDF: {str(e)}")
        return None


def extract_text_from_docx(docx_bytes):
    """Extrai texto de DOCX (ZIP com XML)."""
    try:
        import zipfile
        import io
        
        # DOCX e um ZIP
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
            # Ler document.xml
            if 'word/document.xml' in zf.namelist():
                xml_content = zf.read('word/document.xml').decode('utf-8')
                # Extrair texto entre tags
                text = re.sub(r'<[^>]+>', ' ', xml_content)
                text = re.sub(r'\s+', ' ', text)
                return text.strip()
        return None
    except Exception as e:
        logging.error(f"Erro ao extrair texto DOCX: {str(e)}")
        return None


def processar_informativo(texto: str, fonte: str) -> list:
    """Processa texto do informativo TCU e extrai fichas com Claude."""
    
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    prompt = f"""Analise este Informativo de Licitacoes e Contratos do TCU e extraia as jurisprudencias.

Para cada acordao encontrado, retorne um JSON com:
- id: "TCU-[numero]-[ano]" (ex: "TCU-2351-2023")
- acordao: numero completo (ex: "2351/2023-Plenario")
- relator: nome do ministro
- data: mes/ano
- colegiado: Plenario, Primeira Camara ou Segunda Camara
- tema_principal: um tema (ex: "Formalismo moderado", "Vistoria tecnica", "Habilitacao")
- temas_secundarios: lista de temas relacionados
- palavras_chave: lista de 5-10 termos para busca
- ementa: resumo da decisao (o texto em negrito no inicio)
- entendimento: lista de regras extraidas (o que o TCU decidiu)
- contexto: breve descricao do caso
- citacao_direta: trecho importante para citar em peticoes
- quando_usar: lista de situacoes praticas de aplicacao
- quando_nao_usar: lista de situacoes em que NAO se aplica
- link: URL do acordao se presente no texto

TEXTO DO INFORMATIVO:
{texto[:15000]}

Responda APENAS com JSON valido no formato:
{{"fichas": [...]}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    resp_text = response.content[0].text
    resp_text = resp_text.replace("```json", "").replace("```", "").strip()
    
    result = json.loads(resp_text)
    fichas = result.get("fichas", [])
    
    # Gerar embeddings e salvar no banco
    openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    conn = get_db_connection()
    cur = conn.cursor()
    
    fichas_salvas = []
    
    for ficha in fichas:
        try:
            ficha["fonte"] = fonte
            ficha["status"] = "pendente"
            
            # Gerar embedding da ementa + entendimento
            texto_emb = ficha.get("ementa", "") + " " + " ".join(ficha.get("entendimento", []))
            
            emb_response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texto_emb[:8000]
            )
            embedding = emb_response.data[0].embedding
            
            # Inserir no banco
            cur.execute("""
                INSERT INTO kb_jurisprudencia 
                (id, acordao, relator, data, tipo_processo, colegiado, fonte,
                 tema_principal, temas_secundarios, palavras_chave,
                 ementa, entendimento, contexto, citacao_direta,
                 quando_usar, quando_nao_usar, acordaos_relacionados,
                 status, link, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    tema_principal = EXCLUDED.tema_principal,
                    ementa = EXCLUDED.ementa,
                    entendimento = EXCLUDED.entendimento,
                    atualizado_em = CURRENT_TIMESTAMP
            """, (
                ficha.get("id"),
                ficha.get("acordao"),
                ficha.get("relator"),
                ficha.get("data"),
                ficha.get("tipo_processo"),
                ficha.get("colegiado"),
                ficha.get("fonte"),
                ficha.get("tema_principal"),
                ficha.get("temas_secundarios", []),
                ficha.get("palavras_chave", []),
                ficha.get("ementa"),
                ficha.get("entendimento", []),
                ficha.get("contexto"),
                ficha.get("citacao_direta"),
                ficha.get("quando_usar", []),
                ficha.get("quando_nao_usar", []),
                ficha.get("acordaos_relacionados", []),
                ficha.get("status", "pendente"),
                ficha.get("link"),
                embedding
            ))
            
            fichas_salvas.append(ficha)
            
        except Exception as e:
            logging.error(f"Erro ao salvar ficha {ficha.get('id')}: {str(e)}")
    
    conn.commit()
    cur.close()
    conn.close()
    
    return fichas_salvas


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handler principal do endpoint."""
    
    logging.info("juris_upload chamado")
    
    try:
        body = req.get_json()
        
        texto = body.get("texto", "")
        arquivo_base64 = body.get("arquivo_base64", "")
        filename = body.get("filename", "documento")
        fonte = body.get("fonte", "Informativo TCU")
        
        # Se recebeu arquivo em base64, extrair texto
        if arquivo_base64:
            try:
                file_bytes = base64.b64decode(arquivo_base64)
                filename_lower = filename.lower()
                
                if filename_lower.endswith('.rtf'):
                    texto = extract_text_from_rtf(file_bytes)
                    logging.info(f"RTF extraido: {len(texto)} caracteres")
                    
                elif filename_lower.endswith('.pdf'):
                    texto = extract_text_from_pdf_simple(file_bytes)
                    if not texto:
                        return func.HttpResponse(
                            json.dumps({"error": "Nao foi possivel extrair texto do PDF. Use RTF ou TXT."}),
                            status_code=400,
                            mimetype="application/json"
                        )
                    logging.info(f"PDF extraido: {len(texto)} caracteres")
                    
                elif filename_lower.endswith('.docx'):
                    texto = extract_text_from_docx(file_bytes)
                    if not texto:
                        return func.HttpResponse(
                            json.dumps({"error": "Nao foi possivel extrair texto do DOCX."}),
                            status_code=400,
                            mimetype="application/json"
                        )
                    logging.info(f"DOCX extraido: {len(texto)} caracteres")
                    
                elif filename_lower.endswith('.txt'):
                    texto = file_bytes.decode('utf-8', errors='ignore')
                    logging.info(f"TXT lido: {len(texto)} caracteres")
                    
                else:
                    # Tentar como texto
                    texto = file_bytes.decode('utf-8', errors='ignore')
                    
            except Exception as e:
                logging.error(f"Erro ao processar arquivo: {str(e)}")
                return func.HttpResponse(
                    json.dumps({"error": f"Erro ao processar arquivo: {str(e)}"}),
                    status_code=400,
                    mimetype="application/json"
                )
        
        if not texto:
            return func.HttpResponse(
                json.dumps({"error": "Campo 'texto' ou 'arquivo_base64' obrigatorio"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if len(texto) < 100:
            return func.HttpResponse(
                json.dumps({"error": f"Texto muito curto ({len(texto)} chars). Verifique o arquivo."}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Processar com IA
        fichas = processar_informativo(texto, fonte)
        
        # Remover embeddings do retorno
        for ficha in fichas:
            ficha.pop("embedding", None)
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "fichas_extraidas": len(fichas),
                "texto_extraido_chars": len(texto),
                "fichas": fichas
            }, ensure_ascii=False),
            mimetype="application/json"
        )
        
    except json.JSONDecodeError:
        return func.HttpResponse(
            json.dumps({"error": "JSON invalido"}),
            status_code=400,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Erro em juris_upload: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
