# govy/legal/govbr_parser.py
"""
Parser para listas de legislacao do portal gov.br/compras.

Funcoes:
  - parse_list_page: extrai itens (caption + link) de uma pagina de lista
  - caption_to_doc_id: converte titulo em doc_id deterministico
  - parse_detail_page: extrai texto normativo de pagina de detalhe
  - extract_revocation_from_title: extrai referencia de revogacao do titulo
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class ListItem:
    """Um item extraido de uma lista gov.br."""
    caption_raw: str
    detail_url: str
    doc_id: Optional[str] = None
    kind: Optional[str] = None
    number: Optional[str] = None
    year: Optional[int] = None


@dataclass
class ListPageResult:
    """Resultado do parse de uma pagina de lista."""
    items: List[ListItem] = field(default_factory=list)
    next_page_url: Optional[str] = None


@dataclass
class DetailResult:
    """Resultado do parse de uma pagina de detalhe."""
    text: str
    title: Optional[str] = None
    dou_url: Optional[str] = None
    revoked_by_refs: List[str] = field(default_factory=list)


# ── Constantes ───────────────────────────────────────────────────────────────

GOVBR_LISTS = [
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas",
        "kind": "instrucao_normativa",
        "status_hint": "vigente",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas-revogadas",
        "kind": "instrucao_normativa",
        "status_hint": "revogada",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/portarias",
        "kind": "portaria",
        "status_hint": "vigente",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/portarias-revogadas",
        "kind": "portaria",
        "status_hint": "revogada",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/resolucoes",
        "kind": "resolucao",
        "status_hint": "vigente",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/resolucoes-revogadas",
        "kind": "resolucao",
        "status_hint": "revogada",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/orientacoes-normativas",
        "kind": "orientacao_normativa",
        "status_hint": "vigente",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/orientacoes-normativas-revogadas",
        "kind": "orientacao_normativa",
        "status_hint": "revogada",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/leis",
        "kind": "lei",
        "status_hint": "vigente",
    },
    {
        "url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/decretos-vigentes",
        "kind": "decreto",
        "status_hint": "vigente",
    },
]


# ── Tipo map para doc_id ─────────────────────────────────────────────────────

# Caption tipo textual → (prefixo_doc_id, kind)
# Compativel com pipeline.py / relation_extractor.py
# Ordem importa: compostos ANTES dos simples (para match correto)
_CAPTION_TYPE_MAP = {
    # Compostos — portaria
    "portaria normativa": ("portaria", "portaria"),
    "portaria interministerial": ("portaria", "portaria"),
    "portaria conjunta": ("portaria", "portaria"),
    "portaria de pessoal": ("portaria", "portaria"),
    # Compostos — instrução normativa
    "instrução normativa conjunta": ("in", "instrucao_normativa"),
    "instrucao normativa conjunta": ("in", "instrucao_normativa"),
    "instrução normativa": ("in", "instrucao_normativa"),
    "instrucao normativa": ("in", "instrucao_normativa"),
    # Compostos — resolução
    "resolução conjunta": ("resolucao", "resolucao"),
    "resolucao conjunta": ("resolucao", "resolucao"),
    "resolução": ("resolucao", "resolucao"),
    "resolucao": ("resolucao", "resolucao"),
    # Compostos — lei / decreto
    "lei complementar": ("lc", "lei_complementar"),
    "decreto lei": ("decreto_lei", "decreto_lei"),
    "decreto-lei": ("decreto_lei", "decreto_lei"),
    # Simples
    "portaria": ("portaria", "portaria"),
    "orientação normativa": ("on", "orientacao_normativa"),
    "orientacao normativa": ("on", "orientacao_normativa"),
    "lei": ("lei", "lei"),
    "decreto": ("decreto", "decreto"),
}

# Regex para extrair tipo, numero e ano de um caption
# Exemplos:
#   "INSTRUÇÃO NORMATIVA SEGES/MGI Nº 512, DE 3 DE DEZEMBRO DE 2025"
#   "PORTARIA Nº 75 DE 22 DE JULHO DE 2014"          (sem virgula)
#   "DECRETO Nº 5.992 , DE 19 DE DEZEMBRO DE 2006"   (espaço antes virgula)
#   "ORIENTAÇÃO NORMATIVA/SLTI Nº 1, DE 20 DE AGOSTO DE 2015"  (barra no orgao)
#   "PORTARIA Nº 36, DE 13 DE DEZEMBRO 2010"          (sem 2o "DE" antes do ano)
#   "INSTRUÇÃO NORMATIVA N° 01 , DE 08 DE AGOSTO DE 2002."
#
# Grupo 1: tipo normativo (com modificadores: NORMATIVA, INTERMINISTERIAL, etc.)
# Grupo 2: numero (pode ter pontos: 1.962)
# Grupo 3: ano (4 digitos)
_TIPO_BASE = (
    r"INSTRU[ÇC][ÃA]O\s+NORMATIVA(?:\s+CONJUNTA)?"
    r"|PORTARIA(?:\s+(?:NORMATIVA|INTERMINISTERIAL|CONJUNTA|DE\s+PESSOAL))?"
    r"|RESOLU[ÇC][ÃA]O(?:\s+CONJUNTA)?"
    r"|ORIENTA[ÇC][ÃA]O\s+NORMATIVA"
    r"|LEI\s+COMPLEMENTAR"
    r"|DECRETO[\s\-]+LEI"
    r"|LEI"
    r"|DECRETO"
)
RE_CAPTION = re.compile(
    rf"^({_TIPO_BASE})"
    r"[\s/]+(?:[\w/\-\.]+\s+)*?N[ºo°\s\.]+\s*([\d\.]+)"
    r"(?:\s*,?\s*(?:DE\s+)?\d{1,2}[ºo°]?\s+(?:DE\s+)?\w+\s+(?:DE\s+)?(\d{4}))?",
    re.IGNORECASE,
)

# Regex para revogacao no titulo: "(Revogada pela IN nº 90, de 2022)"
RE_REVOGACAO_TITULO = re.compile(
    r"\(Revogad[ao]\s+pel[ao]\s+(.+?)\)",
    re.IGNORECASE,
)


# ── Funcoes de parse ─────────────────────────────────────────────────────────

def parse_list_page(html: str, list_url: str) -> ListPageResult:
    """
    Extrai itens de uma pagina de lista gov.br/compras.

    Itens podem estar em <h2><a>...</a></h2> ou <h3><a>...</a></h3>
    (leis e decretos usam h3 no portal gov.br).

    Args:
        html: HTML da pagina de lista
        list_url: URL da pagina (para resolver links relativos e paginacao)

    Returns:
        ListPageResult com items e next_page_url
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    items: List[ListItem] = []
    seen_urls = set()

    # Busca em h2 e h3 (leis/decretos usam h3)
    for heading in soup.find_all(["h2", "h3"]):
        a = heading.find("a", href=True)
        if not a:
            continue

        caption = a.get_text(strip=True)
        if not caption:
            continue

        href = a["href"]
        detail_url = urljoin(list_url, href)

        # Dedup (h2 e h3 podem duplicar)
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)

        # Tenta parsear doc_id do caption
        parsed = caption_to_doc_id(caption)
        if parsed:
            doc_id, kind, number, year = parsed
        else:
            doc_id, kind, number, year = None, None, None, None

        items.append(ListItem(
            caption_raw=caption,
            detail_url=detail_url,
            doc_id=doc_id,
            kind=kind,
            number=number,
            year=year,
        ))

    # Paginacao: procura link "Próximo" ou "Next"
    next_page_url = None
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if "próximo" in text or "proximo" in text or "next" in text:
            next_page_url = urljoin(list_url, a["href"])
            break

    return ListPageResult(items=items, next_page_url=next_page_url)


def caption_to_doc_id(caption: str) -> Optional[Tuple[str, str, str, int]]:
    """
    Converte caption de lista em doc_id deterministico.

    Args:
        caption: titulo original (ex: "INSTRUÇÃO NORMATIVA SEGES/MGI Nº 512, DE 3 DE DEZEMBRO DE 2025")

    Returns:
        (doc_id, kind, number, year) ou None se nao conseguir parsear
        Ex: ("in_512_2025_federal_br", "instrucao_normativa", "512", 2025)
    """
    # Remove parentetico de revogacao antes do parse
    clean_caption = RE_REVOGACAO_TITULO.sub("", caption).strip()

    m = RE_CAPTION.match(clean_caption)
    if not m:
        logger.debug("caption_to_doc_id: nao casou regex para '%s'", caption[:80])
        return None

    tipo_raw = m.group(1).strip()
    numero_raw = m.group(2).strip()
    ano_raw = m.group(3)

    # Normalizar tipo
    tipo_lower = tipo_raw.lower()
    tipo_lower = re.sub(r"[\-–]", " ", tipo_lower)         # decreto-lei → decreto lei
    tipo_lower = re.sub(r"\s+", " ", tipo_lower).strip()
    # Normalizar acentos para lookup
    _ACCENT_MAP = str.maketrans("çãõéáíóúê", "caoeaioue")
    tipo_norm = tipo_lower.translate(_ACCENT_MAP)

    lookup = _CAPTION_TYPE_MAP.get(tipo_lower)
    if not lookup:
        # Tenta sem acentos
        for key, val in _CAPTION_TYPE_MAP.items():
            if key.translate(_ACCENT_MAP) == tipo_norm:
                lookup = val
                break
    if not lookup:
        logger.debug("caption_to_doc_id: tipo desconhecido '%s'", tipo_raw)
        return None

    prefix, kind = lookup

    # Normalizar numero: remove pontos (1.962 → 1962), strip leading zeros
    number = numero_raw.replace(".", "").lstrip("0") or "0"

    if not ano_raw:
        logger.debug("caption_to_doc_id: sem ano para '%s'", caption[:80])
        return None

    year = int(ano_raw)
    doc_id = f"{prefix}_{number}_{year}_federal_br"

    return doc_id, kind, number, year


def parse_detail_page(html: str) -> DetailResult:
    """
    Extrai texto normativo da pagina de detalhe gov.br.

    Remove nav, header, footer, breadcrumb, botoes de compartilhamento.
    Procura link do DOU (in.gov.br/web/dou).
    Tenta detectar "Revogada pela..." no texto.

    Args:
        html: HTML da pagina de detalhe

    Returns:
        DetailResult com texto, titulo, dou_url, revoked_by_refs
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Extrair titulo do h1 ou title
    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

    # Procurar link DOU
    dou_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "in.gov.br/web/dou" in href or "imprensanacional.gov.br" in href:
            dou_url = href
            break

    # Remover elementos indesejados
    for tag_name in ("nav", "header", "footer", "script", "style", "noscript"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remover breadcrumb
    for bc in soup.find_all(class_=re.compile(r"breadcrumb", re.I)):
        bc.decompose()

    # Remover botoes de compartilhamento
    for share in soup.find_all(class_=re.compile(r"share|social", re.I)):
        share.decompose()

    # Encontrar bloco principal de conteudo
    content_block = None
    for selector in ("article", "div#content-core", 'div[class*="content"]', "main"):
        content_block = soup.select_one(selector)
        if content_block:
            break
    if not content_block:
        content_block = soup.body or soup

    text = content_block.get_text(separator="\n")

    # Normalizar (reutiliza logica de text_extractor)
    from govy.legal.text_extractor import _normalize_text
    text = _normalize_text(text)

    # Detectar revogacoes no texto
    revoked_by_refs = []
    for m in re.finditer(
        r"revogad[ao]\s+pel[ao]\s+((?:instru[çc][ãa]o\s+normativa|portaria|resolu[çc][ãa]o|lei|decreto)\s+(?:[\w/\-]+\s+)?n[ºo°\s\.]+[\d\.]+(?:,?\s+de\s+\d{4})?)",
        text,
        re.IGNORECASE,
    ):
        revoked_by_refs.append(m.group(1).strip())

    return DetailResult(
        text=text,
        title=title,
        dou_url=dou_url,
        revoked_by_refs=revoked_by_refs,
    )


def extract_revocation_from_title(caption: str) -> Optional[str]:
    """
    Extrai referencia de revogacao do titulo de lista revogada.

    Ex: "INSTRUÇÃO NORMATIVA ... (Revogada pela IN nº 90, de 2022)"
        → "IN nº 90, de 2022"

    Args:
        caption: titulo completo da lista

    Returns:
        referencia textual ou None
    """
    m = RE_REVOGACAO_TITULO.search(caption)
    if m:
        return m.group(1).strip()
    return None
