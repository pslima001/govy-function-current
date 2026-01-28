# govy/api/dicionario_termos.py
"""
Dicionrio de termos para validao de itens extrados.
- Armazena nomes base de produtos (sem dosagem, tamanho, etc.)
- Atualiza automaticamente a cada extrao
- Persiste no Azure Blob Storage

Uso:
- Se descrio contm termo conhecido  aceita com 1 voto
- Melhora acurcia em editais diversos (sade, alimentos, construo, etc.)
"""

import os
import re
import json
import logging
from typing import Set, List, Dict, Optional
from datetime import datetime
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAO
# =============================================================================

DICIONARIO_CONTAINER = "govy-config"
DICIONARIO_BLOB = "dicionario/termos.json"

# Cache em memria (evita buscar blob a cada chamada)
_cache_termos: Set[str] = set()
_cache_loaded: bool = False

# =============================================================================
# NORMALIZAO DE TEXTO
# =============================================================================

def normalizar_texto(texto: str) -> str:
    """Remove acentos e converte para lowercase."""
    if not texto:
        return ""
    
    # Mapa de acentos
    acentos = {
        '': 'a', '': 'a', '': 'a', '': 'a', '': 'a',
        '': 'e', '': 'e', '': 'e', '': 'e',
        '': 'i', '': 'i', '': 'i', '': 'i',
        '': 'o', '': 'o', '': 'o', '': 'o', '': 'o',
        '': 'u', '': 'u', '': 'u', '': 'u',
        '': 'c', '': 'n',
        '': 'a', '': 'a', '': 'a', '': 'a', '': 'a',
        '': 'e', '': 'e', '': 'e', '': 'e',
        '': 'i', '': 'i', '': 'i', '': 'i',
        '': 'o', '': 'o', '': 'o', '': 'o', '': 'o',
        '': 'u', '': 'u', '': 'u', '': 'u',
        '': 'c', '': 'n',
    }
    
    resultado = texto.lower()
    for ac, sem in acentos.items():
        resultado = resultado.replace(ac, sem)
    
    return resultado

# =============================================================================
# EXTRAO DE NOME BASE
# =============================================================================

# Padres para REMOVER da descrio (ordem importa!)
PADROES_REMOVER = [
    # Dosagem e concentrao (mais completo)
    r'\d+[\.,]?\d*\s*/\s*(ml|mg|g|l)',  # ex: 0.5/ml, 500/ml
    r'\d+[\.,]?\d*\s*(mg|mcg|g|ml|l|ui|%|kg)\s*/\s*(ml|g|m|l)?',  # ex: 500mg/ml, 75g/m
    r'\d+[\.,]?\d*\s*(mg|mcg|g|ml|l|ui|%|kg)',  # ex: 500mg, 50kg
    
    # Forma farmacutica
    r'\b(cpr|comp|comprimido|caps|capsula|sol|solucao|susp|suspensao|injetavel|xarope|creme|gel|pomada|gotas|aerossol|spray|po|liquido|oral|topico|vaginal|retal)\b',
    
    # Tamanho e dimenses
    r'\d+[\.,]?\d*\s*x\s*\d+[\.,]?\d*',  # ex: 25x7, 30 x 8
    r'\d+[\.,]?\d*\s*(cm|mm|m)\b',
    r'\(\s*[^)]*\)',  # remove contedo entre parnteses
    
    # Nmero/tamanho
    r'\bn[]?\s*\d+\b',
    r'\bnumero\s*\d+\b',
    r'\btamanho\s*\w+\b',
    r'\b(pp|gg|eg)\b',  # s os extremos, P M G podem ser parte do nome
    
    # Caractersticas fsicas
    r'\b(descartavel|esteril|adulto|infantil|pediatrico|neonatal)\b',
    
    # Embalagem e quantidade
    r'\b(frasco|ampola|tubo|bisnaga|envelope|sache|blister|caixa|pacote|unid|unidade|resma|folhas|pecas)\b',
    r'\bc/\s*\d+\b',
    r'\bcom\s*\d+\b',
    r'\b\d+\s*(unid|folhas|pecas)\b',
    
    # Caracteres especiais sobrando
    r'[\-/]+',
    r'[]',
    
    # Nmeros soltos no final
    r'\b\d+\b',
]

# Stopwords para remover
STOPWORDS = {'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'com', 'sem', 'para', 'por', 'a', 'o', 'e', 'ou'}

def extrair_nome_base(descricao: str) -> Optional[str]:
    """
    Extrai apenas o nome base do produto, removendo dosagem, tamanho, etc.
    
    Exemplos:
    - "cido valproico 250mg comp"  "acido valproico"
    - "Sulfato de salbutamol 0.5mg/ml - soluo injetvel"  "sulfato de salbutamol"
    - "Tala moldvel aramada EVA de imobilizao pp (30 cm x 8 cm)"  "tala moldavel aramada eva imobilizacao"
    - "Sonda uretral descartvel n06"  "sonda uretral"
    """
    if not descricao:
        return None
    
    # Normaliza (lowercase, sem acentos)
    texto = normalizar_texto(descricao)
    
    # Remove padres indesejados
    for padrao in PADROES_REMOVER:
        texto = re.sub(padrao, ' ', texto, flags=re.IGNORECASE)
    
    # Limpa espaos mltiplos e extremidades
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    # Remove palavras muito curtas e stopwords
    palavras = texto.split()
    palavras_filtradas = [p for p in palavras if len(p) >= 3 and p not in STOPWORDS]
    
    texto = ' '.join(palavras_filtradas)
    
    # Mnimo 3 caracteres para ser vlido
    if len(texto) < 3:
        return None
    
    return texto

# =============================================================================
# ACESSO AO BLOB STORAGE
# =============================================================================

def _get_blob_service() -> BlobServiceClient:
    """Retorna cliente do Blob Storage."""
    conn_str = os.environ.get("AzureWebJobsStorage")
    if not conn_str:
        raise ValueError("AzureWebJobsStorage no configurado")
    return BlobServiceClient.from_connection_string(conn_str)

def carregar_dicionario() -> Set[str]:
    """Carrega dicionrio do Blob Storage (com cache)."""
    global _cache_termos, _cache_loaded
    
    if _cache_loaded:
        return _cache_termos
    
    try:
        blob_service = _get_blob_service()
        container = blob_service.get_container_client(DICIONARIO_CONTAINER)
        
        # Cria container se no existir
        try:
            container.create_container()
            logger.info(f"Container {DICIONARIO_CONTAINER} criado")
        except Exception:
            pass  # J existe
        
        blob = container.get_blob_client(DICIONARIO_BLOB)
        
        try:
            dados = json.loads(blob.download_blob().readall())
            _cache_termos = set(dados.get("termos", []))
            _cache_loaded = True
            logger.info(f"Dicionrio carregado: {len(_cache_termos)} termos")
        except Exception:
            # Blob no existe ainda
            _cache_termos = set()
            _cache_loaded = True
            logger.info("Dicionrio vazio (primeiro uso)")
        
        return _cache_termos
        
    except Exception as e:
        logger.error(f"Erro ao carregar dicionrio: {e}")
        return set()

def salvar_dicionario(termos: Set[str]) -> bool:
    """Salva dicionrio no Blob Storage."""
    global _cache_termos, _cache_loaded
    
    try:
        blob_service = _get_blob_service()
        container = blob_service.get_container_client(DICIONARIO_CONTAINER)
        
        # Cria container se no existir
        try:
            container.create_container()
        except Exception:
            pass
        
        blob = container.get_blob_client(DICIONARIO_BLOB)
        
        dados = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "total": len(termos),
            "termos": sorted(termos)
        }
        
        blob.upload_blob(
            json.dumps(dados, ensure_ascii=False, indent=2),
            overwrite=True
        )
        
        # Atualiza cache
        _cache_termos = termos
        _cache_loaded = True
        
        logger.info(f"Dicionrio salvo: {len(termos)} termos")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar dicionrio: {e}")
        return False

def atualizar_dicionario(novos_termos: List[str]) -> int:
    """
    Adiciona novos termos ao dicionrio.
    Retorna quantidade de termos novos adicionados.
    """
    if not novos_termos:
        return 0
    
    # Carrega atual
    termos_atuais = carregar_dicionario()
    
    # Filtra e normaliza novos termos
    termos_validos = set()
    for termo in novos_termos:
        nome_base = extrair_nome_base(termo) if len(termo) > 20 else normalizar_texto(termo)
        if nome_base and len(nome_base) >= 3:
            termos_validos.add(nome_base)
    
    # Conta novos
    novos = termos_validos - termos_atuais
    
    if novos:
        termos_atuais.update(novos)
        salvar_dicionario(termos_atuais)
        logger.info(f"Dicionrio atualizado: +{len(novos)} termos novos")
    
    return len(novos)

# =============================================================================
# VALIDAO DE ITENS
# =============================================================================

def contem_termo_conhecido(descricao: str) -> bool:
    """
    Verifica se a descrio contm algum termo do dicionrio.
    Busca por substring para pegar variaes.
    """
    if not descricao:
        return False
    
    termos = carregar_dicionario()
    if not termos:
        return False
    
    # Normaliza descrio
    desc_norm = normalizar_texto(descricao)
    
    # Busca por substring (termo est contido na descrio)
    for termo in termos:
        if termo in desc_norm:
            return True
    
    return False

def extrair_termos_de_itens(itens: List[Dict]) -> List[str]:
    """
    Extrai nomes base de uma lista de itens extrados.
    Usado para atualizar o dicionrio aps extrao bem-sucedida.
    """
    termos = []
    for item in itens:
        descricao = item.get("descricao", "")
        nome_base = extrair_nome_base(descricao)
        if nome_base:
            termos.append(nome_base)
    return termos

# =============================================================================
# FUNES DE UTILIDADE
# =============================================================================

def get_estatisticas() -> Dict:
    """Retorna estatsticas do dicionrio."""
    termos = carregar_dicionario()
    return {
        "total_termos": len(termos),
        "cache_loaded": _cache_loaded,
        "container": DICIONARIO_CONTAINER,
        "blob": DICIONARIO_BLOB
    }

def invalidar_cache():
    """Fora recarregamento do dicionrio na prxima chamada."""
    global _cache_termos, _cache_loaded
    _cache_termos = set()
    _cache_loaded = False

# =============================================================================
# TESTE LOCAL
# =============================================================================

if __name__ == "__main__":
    # Testes de extrao de nome base
    testes = [
        "cido valproico 250mg comp",
        "Sulfato de salbutamol 0.5mg/ml - soluo injetvel",
        "Tala moldvel aramada EVA de imobilizao pp (30 cm x 8 cm)",
        "Sonda uretral descartvel n06",
        "Cloridrato de metformina 500mg - cpr",
        "Dipirona 500 mg/ml - soluo injetvel",
        "Agulha hipodrmica descartvel 25x7",
        "Luva de procedimento ltex tamanho M caixa c/100",
        "Cimento Portland CP II 50kg",
        "Papel sulfite A4 75g/m resma 500 folhas",
    ]
    
    print("=== TESTE DE EXTRAO DE NOME BASE ===\n")
    for t in testes:
        base = extrair_nome_base(t)
        print(f"Original: {t}")
        print(f"Base:     {base}")
        print()
