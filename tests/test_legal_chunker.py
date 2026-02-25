# tests/test_legal_chunker.py
"""
Testes para o chunker estrutural de legislacao.
14 test cases cobrindo artigos, paragrafos, incisos, alineas, fallback, etc.
"""
from __future__ import annotations

import os
import pytest

from govy.legal.legal_chunker import (
    chunk_legal_text,
    _split_into_articles,
    _find_hierarchy_context,
    RE_ARTIGO,
    RE_PARAGRAFO,
    RE_INCISO,
    RE_ALINEA,
    RE_TITULO,
    RE_CAPITULO,
    RE_SECAO,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── Regex tests ────────────────────────────────────────────────────────────────

class TestRegexPatterns:
    def test_artigo_pattern_basic(self):
        text = "Art. 1o Esta Lei estabelece"
        matches = list(RE_ARTIGO.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1) == "1"

    def test_artigo_pattern_numero_grande(self):
        text = "Art. 175 Fica revogado"
        matches = list(RE_ARTIGO.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1) == "175"

    def test_artigo_pattern_ponto(self):
        text = "Art. 10. A partir da data"
        matches = list(RE_ARTIGO.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1) == "10"

    def test_paragrafo_numerico(self):
        text = "§ 1o Nao sao abrangidas"
        matches = list(RE_PARAGRAFO.finditer(text))
        assert len(matches) == 1

    def test_paragrafo_unico(self):
        text = "Parágrafo único. Este é"
        matches = list(RE_PARAGRAFO.finditer(text))
        assert len(matches) == 1

    def test_paragrafo_unico_sem_acento(self):
        text = "Paragrafo unico. Este é"
        matches = list(RE_PARAGRAFO.finditer(text))
        assert len(matches) == 1

    def test_inciso_romano(self):
        text = "I - os órgãos dos Poderes"
        matches = list(RE_INCISO.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1) == "I"

    def test_inciso_romano_complexo(self):
        text = "XIII - contratações"
        matches = list(RE_INCISO.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1) == "XIII"

    def test_alinea(self):
        text = "a) condições decorrentes"
        matches = list(RE_ALINEA.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1) == "a"

    def test_titulo(self):
        text = "TÍTULO I\nDISPOSIÇÕES PRELIMINARES"
        matches = list(RE_TITULO.finditer(text))
        assert len(matches) == 1

    def test_capitulo(self):
        text = "CAPÍTULO II\nDAS DEFINIÇÕES"
        matches = list(RE_CAPITULO.finditer(text))
        assert len(matches) == 1

    def test_secao(self):
        text = "SEÇÃO I\nDAS DISPOSIÇÕES GERAIS"
        matches = list(RE_SECAO.finditer(text))
        assert len(matches) == 1


# ── Structural splitting tests ─────────────────────────────────────────────────

class TestSplitIntoArticles:
    def test_split_basic(self):
        text = (
            "Preambulo do documento.\n\n"
            "Art. 1o Primeiro artigo.\n\n"
            "Art. 2o Segundo artigo.\n\n"
            "Art. 3o Terceiro artigo.\n"
        )
        preamble, articles = _split_into_articles(text)
        assert "Preambulo" in preamble
        assert len(articles) == 3
        assert articles[0].art_num == 1
        assert articles[1].art_num == 2
        assert articles[2].art_num == 3

    def test_no_articles(self):
        text = "Este documento nao tem artigos. Apenas texto corrido."
        preamble, articles = _split_into_articles(text)
        assert preamble == text
        assert len(articles) == 0

    def test_article_text_includes_paragraphs(self):
        text = (
            "Art. 1o Texto do artigo.\n"
            "§ 1o Primeiro paragrafo.\n"
            "§ 2o Segundo paragrafo.\n\n"
            "Art. 2o Outro artigo.\n"
        )
        _, articles = _split_into_articles(text)
        assert len(articles) == 2
        # Art 1 deve incluir seus paragrafos
        assert "§ 1o" in articles[0].text
        assert "§ 2o" in articles[0].text


# ── chunk_legal_text full pipeline tests ────────────────────────────────────────

class TestChunkLegalText:
    def test_fixture_lei_14133(self):
        """Testa com trecho real da Lei 14.133/2021."""
        text = _load_fixture("sample_lei_14133_excerpt.txt")
        provisions, chunks = chunk_legal_text(text, "lei_14133_test", "Lei 14.133/2021")

        # Deve ter multiplos artigos
        art_provisions = [p for p in provisions if p.provision_type == "artigo"]
        assert len(art_provisions) >= 10, f"Esperado >=10 artigos, got {len(art_provisions)}"

        # Deve ter preambulo
        preamble = [p for p in provisions if p.provision_type == "preambulo"]
        assert len(preamble) == 1

        # Deve ter paragrafos
        pars = [p for p in provisions if p.provision_type == "paragrafo"]
        assert len(pars) >= 3, f"Esperado >=3 paragrafos, got {len(pars)}"

        # Deve ter incisos
        incisos = [p for p in provisions if p.provision_type == "inciso"]
        assert len(incisos) >= 5, f"Esperado >=5 incisos, got {len(incisos)}"

        # Deve ter alineas
        alineas = [p for p in provisions if p.provision_type == "alinea"]
        assert len(alineas) >= 1, f"Esperado >=1 alinea, got {len(alineas)}"

        # Chunks devem ter citation_short
        for chunk in chunks:
            assert chunk.citation_short, f"Chunk {chunk.chunk_id} sem citation_short"
            assert chunk.content, f"Chunk {chunk.chunk_id} sem content"
            assert chunk.content_hash, f"Chunk {chunk.chunk_id} sem content_hash"

    def test_provision_keys(self):
        """Verifica que provision_keys seguem o padrao esperado."""
        text = _load_fixture("sample_lei_14133_excerpt.txt")
        provisions, _ = chunk_legal_text(text, "test_keys", "Lei 14.133/2021")

        keys = {p.provision_key for p in provisions}
        assert "art_1" in keys
        assert "art_2" in keys
        assert "preambulo" in keys

        # Paragrafos do art_1
        par_keys = {p.provision_key for p in provisions if p.parent_key == "art_1" and p.provision_type == "paragrafo"}
        assert "art_1_par_1" in par_keys or "art_1_par_unico" in par_keys

    def test_hierarchy_path(self):
        """Verifica que hierarchy_path contem contexto de TITULO/CAPITULO."""
        text = _load_fixture("sample_lei_14133_excerpt.txt")
        provisions, _ = chunk_legal_text(text, "test_hier", "Lei 14.133/2021")

        # Art 1 esta dentro do Titulo I, Capitulo I
        art1 = next(p for p in provisions if p.provision_key == "art_1")
        assert any("Titulo" in h for h in art1.hierarchy_path), \
            f"Art 1 hierarchy deveria ter Titulo: {art1.hierarchy_path}"
        assert any("Capitulo" in h for h in art1.hierarchy_path), \
            f"Art 1 hierarchy deveria ter Capitulo: {art1.hierarchy_path}"

    def test_citation_short_format(self):
        """Verifica formato de citation_short."""
        text = (
            "Art. 1o Texto do artigo.\n\n"
            "Art. 2o Outro artigo.\n\n"
            "Art. 3o Terceiro artigo.\n"
        )
        _, chunks = chunk_legal_text(text, "test_cite", "Lei 14.133/2021")
        for chunk in chunks:
            assert "Lei 14.133/2021" in chunk.citation_short

    def test_fallback_when_few_articles(self):
        """Testa fallback para chunker de paragrafos com <3 artigos."""
        text = (
            "Este e um texto longo sem artigos.\n"
            "Paragrafo 1 do texto.\n"
            "Paragrafo 2 do texto.\n"
            "Art. 1o Unico artigo.\n"
            "Mais texto aqui."
        )
        provisions, chunks = chunk_legal_text(text, "test_fallback", "Doc X")
        # Deve usar fallback (provision_key = "corpo")
        assert any(p.provision_key == "corpo" for p in provisions)

    def test_empty_text(self):
        """Testa com texto vazio."""
        provisions, chunks = chunk_legal_text("", "test_empty", "Doc")
        assert provisions == []
        assert chunks == []

    def test_only_whitespace(self):
        """Testa com texto apenas whitespace."""
        provisions, chunks = chunk_legal_text("   \n\n  ", "test_ws", "Doc")
        assert provisions == []
        assert chunks == []

    def test_chunk_ids_unique(self):
        """Verifica que chunk_ids sao unicos."""
        text = _load_fixture("sample_lei_14133_excerpt.txt")
        _, chunks = chunk_legal_text(text, "test_unique", "Lei 14.133/2021")
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "chunk_ids duplicados detectados"

    def test_large_article_sub_chunked(self):
        """Testa que artigo grande (>5000 chars) e sub-dividido."""
        # Cria artigo artificialmente grande
        big_par = "Este e um paragrafo muito longo. " * 100  # ~3300 chars
        text = (
            "Art. 1o Texto curto.\n\n"
            "Art. 2o Texto curto.\n\n"
            f"Art. 3o Caput do artigo grande.\n"
            f"§ 1o {big_par}\n"
            f"§ 2o {big_par}\n\n"
            "Art. 4o Texto curto.\n"
        )
        _, chunks = chunk_legal_text(text, "test_big", "Lei X")
        # Art 3 deve gerar >1 chunk
        art3_chunks = [c for c in chunks if "art_3" in c.provision_key]
        assert len(art3_chunks) >= 2, f"Art 3 grande deveria ter >=2 chunks, got {len(art3_chunks)}"

    def test_paragrafo_unico_detected(self):
        """Testa que 'Paragrafo unico' e detectado corretamente."""
        text = _load_fixture("sample_lei_14133_excerpt.txt")
        provisions, _ = chunk_legal_text(text, "test_par_unico", "Lei 14.133/2021")

        par_unico = [p for p in provisions if "par_unico" in p.provision_key]
        assert len(par_unico) >= 1, "Deveria detectar pelo menos 1 Paragrafo unico"


# ── Hierarchy context tests ────────────────────────────────────────────────────

class TestHierarchyContext:
    def test_finds_titulo_before_position(self):
        text = "TÍTULO I\nDISPOSIÇÕES\n\nArt. 1o Texto."
        pos = text.index("Art.")
        ctx = _find_hierarchy_context(text, pos)
        assert any("Titulo" in c for c in ctx)

    def test_finds_capitulo_before_position(self):
        text = "CAPÍTULO III\nDAS COISAS\n\nArt. 50. Texto."
        pos = text.index("Art.")
        ctx = _find_hierarchy_context(text, pos)
        assert any("Capitulo" in c for c in ctx)

    def test_finds_secao_before_position(self):
        text = "SEÇÃO II\nDOS ITENS\n\nArt. 20. Texto."
        pos = text.index("Art.")
        ctx = _find_hierarchy_context(text, pos)
        assert any("Secao" in c for c in ctx)
