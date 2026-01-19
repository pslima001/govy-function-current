import re
import unicodedata
from typing import List

def normalizar_para_comparacao(texto: str) -> str:
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r'[^\w\s]', ' ', texto)
    texto = re.sub(r'\d+', '', texto)
    stopwords = {'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'da', 'do', 'das', 'dos', 'em', 'na', 'no', 'para', 'por', 'com', 'e', 'ou', 'que', 'se', 'prazo', 'dias', 'dia', 'uteis', 'corridos'}
    palavras = [p for p in texto.split() if p not in stopwords and len(p) > 2]
    return ' '.join(palavras).strip()

def calcular_similaridade(texto1: str, texto2: str) -> float:
    norm1 = normalizar_para_comparacao(texto1)
    norm2 = normalizar_para_comparacao(texto2)
    if not norm1 or not norm2:
        return 0.0
    palavras1 = set(norm1.split())
    palavras2 = set(norm2.split())
    if not palavras1 or not palavras2:
        return 0.0
    intersecao = len(palavras1 & palavras2)
    uniao = len(palavras1 | palavras2)
    return intersecao / uniao if uniao > 0 else 0.0

def filtrar_candidatos_similares(candidatos: List[dict], threshold_similaridade: float = 0.75, max_candidatos: int = 3) -> List[dict]:
    if not candidatos:
        return []
    candidatos_ordenados = sorted(candidatos, key=lambda x: x.get('score', 0), reverse=True)
    selecionados = []
    for candidato in candidatos_ordenados:
        texto_candidato = candidato.get('context') or candidato.get('evidence') or ''
        if not texto_candidato:
            continue
        eh_similar = False
        for selecionado in selecionados:
            texto_selecionado = selecionado.get('context') or selecionado.get('evidence') or ''
            if calcular_similaridade(texto_candidato, texto_selecionado) >= threshold_similaridade:
                eh_similar = True
                break
        if not eh_similar:
            selecionados.append(candidato)
        if len(selecionados) >= max_candidatos:
            break
    return selecionados