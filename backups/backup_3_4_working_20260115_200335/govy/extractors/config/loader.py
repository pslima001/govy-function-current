# govy/extractors/config/loader.py
"""
Loader de configuração simplificado.
As configurações agora ficam diretamente nos arquivos de extractor.
Este módulo existe apenas para manter compatibilidade com imports existentes.
"""
from typing import Dict, Any


def get_extractor_config(extractor_id: str) -> Dict[str, Any]:
    """
    Retorna configuração vazia - extractors usam seus próprios defaults internos.
    Mantido para compatibilidade de imports.
    """
    return {}
