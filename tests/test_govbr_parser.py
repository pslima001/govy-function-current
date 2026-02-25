# tests/test_govbr_parser.py
"""
Testes unitarios para govy.legal.govbr_parser e govy.legal.html_extractor.
"""
from __future__ import annotations

import pytest

from govy.legal.govbr_parser import (
    ListItem,
    caption_to_doc_id,
    extract_revocation_from_title,
    parse_detail_page,
    parse_list_page,
)
from govy.legal.html_extractor import extract_html


# ── caption_to_doc_id ────────────────────────────────────────────────────────

class TestCaptionToDocId:
    def test_instrucao_normativa_basica(self):
        caption = "INSTRUÇÃO NORMATIVA SEGES/MGI Nº 512, DE 3 DE DEZEMBRO DE 2025"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_512_2025_federal_br"
        assert kind == "instrucao_normativa"
        assert number == "512"
        assert year == 2025

    def test_instrucao_normativa_numero_com_ponto(self):
        caption = "INSTRUÇÃO NORMATIVA Nº 1.962, DE 26 DE ABRIL DE 2024"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_1962_2024_federal_br"
        assert number == "1962"

    def test_lei(self):
        caption = "LEI Nº 14.133, DE 1º DE ABRIL DE 2021"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "lei_14133_2021_federal_br"
        assert kind == "lei"
        assert year == 2021

    def test_portaria(self):
        caption = "PORTARIA SEGES/MGI Nº 1.962, DE 26 DE ABRIL DE 2024"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_1962_2024_federal_br"
        assert kind == "portaria"

    def test_decreto(self):
        caption = "DECRETO Nº 12.102, DE 2 DE JULHO DE 2024"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "decreto_12102_2024_federal_br"
        assert kind == "decreto"

    def test_resolucao(self):
        caption = "RESOLUÇÃO Nº 58, DE 12 DE MARÇO DE 2019"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "resolucao_58_2019_federal_br"
        assert kind == "resolucao"

    def test_orientacao_normativa(self):
        caption = "ORIENTAÇÃO NORMATIVA Nº 3, DE 8 DE OUTUBRO DE 2009"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "on_3_2009_federal_br"
        assert kind == "orientacao_normativa"

    def test_com_parentetico_revogacao(self):
        caption = "INSTRUÇÃO NORMATIVA SEGES/ME Nº 75, DE 13 DE AGOSTO DE 2021 (Revogada pela IN nº 90, de 2022)"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_75_2021_federal_br"
        assert kind == "instrucao_normativa"
        assert year == 2021

    def test_numero_com_leading_zeros(self):
        caption = "INSTRUÇÃO NORMATIVA Nº 01, DE 5 DE JANEIRO DE 2010"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, _, number, _ = result
        assert number == "1"
        assert doc_id == "in_1_2010_federal_br"

    def test_sem_ano_retorna_none(self):
        caption = "INSTRUÇÃO NORMATIVA Nº 512"
        result = caption_to_doc_id(caption)
        assert result is None

    def test_texto_invalido(self):
        result = caption_to_doc_id("Algum texto qualquer")
        assert result is None

    # ── Variantes compostas (encontradas no portal) ──

    def test_portaria_normativa(self):
        caption = "PORTARIA NORMATIVA MF Nº 1.344, DE 31 DE OUTUBRO DE 2023"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_1344_2023_federal_br"
        assert kind == "portaria"

    def test_portaria_interministerial(self):
        caption = "Portaria Interministerial MJ/MP nº 2.162, DE 24 DE DEZEMBRO DE 2015"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_2162_2015_federal_br"
        assert kind == "portaria"

    def test_portaria_conjunta(self):
        caption = "PORTARIA CONJUNTA Nº 3, DE 16 DE DEZEMBRO DE 2014"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_3_2014_federal_br"
        assert kind == "portaria"

    def test_portaria_de_pessoal(self):
        caption = "PORTARIA DE PESSOAL Nº 9.728, DE 24 DE AGOSTO DE 2021"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_9728_2021_federal_br"
        assert kind == "portaria"

    def test_instrucao_normativa_conjunta(self):
        caption = "INSTRUÇÃO NORMATIVA CONJUNTA N° 4, DE 18 DE AGOSTO DE 1997"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_4_1997_federal_br"
        assert kind == "instrucao_normativa"

    def test_decreto_lei(self):
        caption = "DECRETO LEI Nº 200, DE 25 DE FEVEREIRO DE 1967"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "decreto_lei_200_1967_federal_br"
        assert kind == "decreto_lei"

    def test_lei_complementar(self):
        caption = "LEI COMPLEMENTAR Nº 123, DE 14 DE DEZEMBRO DE 2006"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "lc_123_2006_federal_br"
        assert kind == "lei_complementar"

    def test_portaria_normativa_sem_orgao(self):
        caption = "PORTARIA NORMATIVA Nº 2, DE 30 DE JANEIRO DE 2018"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_2_2018_federal_br"

    def test_portaria_interministerial_sem_orgao(self):
        caption = "PORTARIA INTERMINISTERIAL Nº 11, DE 25 DE NOVEMBRO DE 2019"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_11_2019_federal_br"

    # ── Variantes de formatação (sem vírgula, espaço extra, barra no orgao) ──

    def test_sem_virgula_antes_de(self):
        caption = "PORTARIA Nº 75 DE 22 DE JULHO DE 2014"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_75_2014_federal_br"

    def test_espaco_antes_da_virgula(self):
        caption = "DECRETO Nº 5.992 , DE 19 DE DEZEMBRO DE 2006"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "decreto_5992_2006_federal_br"

    def test_barra_orgao_slti(self):
        caption = "ORIENTAÇÃO NORMATIVA/SLTI Nº 1, DE 20 DE AGOSTO DE 2015"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "on_1_2015_federal_br"
        assert kind == "orientacao_normativa"

    def test_barra_orgao_seges_mp(self):
        caption = "INSTRUÇÃO NORMATIVA/SEGES/MP Nº 1, DE 29 DE MARÇO DE 2016 (Revogada pela IN nº 102, de 2020)"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_1_2016_federal_br"

    def test_sem_segundo_de_antes_ano(self):
        caption = "PORTARIA Nº 36, DE 13 DE DEZEMBRO 2010"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_36_2010_federal_br"

    def test_n_grau_espaco_virgula(self):
        caption = "INSTRUÇÃO NORMATIVA N° 01 , DE 08 DE AGOSTO DE 2002. (Revogada pela IN nº 2, de 2011)"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_1_2002_federal_br"

    def test_portaria_minuscula_nro(self):
        caption = "PORTARIA nº 1.591 , DE 15 DE JUNHO DE 1998 (revogada pela Portaria nº 406, de 2019)"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_1591_1998_federal_br"

    def test_in_sem_virgula(self):
        caption = "INSTRUÇÃO NORMATIVA Nº 10 DE 23 DE NOVEMBRO DE 2018 (Revogada pela IN nº412, de 2025)"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_10_2018_federal_br"

    def test_sem_de_antes_dia(self):
        """Nº 04, 11 DE NOVEMBRO DE 2009 — missing 'DE' before day number."""
        caption = "INSTRUÇÃO NORMATIVA Nº 04, 11 DE NOVEMBRO DE 2009"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_4_2009_federal_br"

    def test_sem_de_entre_dia_e_mes(self):
        """Nº 03, DE 15 OUTUBRO DE 2009 — missing 'DE' between day and month."""
        caption = "INSTRUÇÃO NORMATIVA Nº 03, DE 15 OUTUBRO DE 2009"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "in_3_2009_federal_br"

    def test_dia_com_grau_degree_sign(self):
        """DE 1° DE ABRIL — degree sign (U+00B0) after day number."""
        caption = "PORTARIA Nº 25, DE 1\u00b0 DE ABRIL DE 2014"
        result = caption_to_doc_id(caption)
        assert result is not None
        doc_id, kind, number, year = result
        assert doc_id == "portaria_25_2014_federal_br"

    def test_itens_nao_normativos_retornam_none(self):
        for caption in ["Vídeo", "Formulário de Sugestões", "Manuais", "Webinários"]:
            assert caption_to_doc_id(caption) is None


# ── extract_revocation_from_title ────────────────────────────────────────────

class TestExtractRevocationFromTitle:
    def test_revogacao_in(self):
        caption = "INSTRUÇÃO NORMATIVA SEGES/ME Nº 75, DE 13 DE AGOSTO DE 2021 (Revogada pela IN nº 90, de 2022)"
        result = extract_revocation_from_title(caption)
        assert result == "IN nº 90, de 2022"

    def test_revogado_decreto(self):
        caption = "DECRETO Nº 5.450, DE 31 DE MAIO DE 2005 (Revogado pelo Decreto nº 10.024, de 2019)"
        result = extract_revocation_from_title(caption)
        assert result == "Decreto nº 10.024, de 2019"

    def test_sem_revogacao(self):
        caption = "INSTRUÇÃO NORMATIVA SEGES/MGI Nº 512, DE 3 DE DEZEMBRO DE 2025"
        result = extract_revocation_from_title(caption)
        assert result is None


# ── parse_list_page ──────────────────────────────────────────────────────────

class TestParseListPage:
    def test_extrai_itens_h2_a(self):
        html = """
        <html><body>
            <h2><a href="https://www.gov.br/compras/pt-br/legislacao/in-512">
                INSTRUÇÃO NORMATIVA SEGES/MGI Nº 512, DE 3 DE DEZEMBRO DE 2025
            </a></h2>
            <p>Regulamenta o art. 32...</p>
            <h2><a href="https://www.gov.br/compras/pt-br/legislacao/in-460">
                INSTRUÇÃO NORMATIVA SEGES/MGI Nº 460, DE 31 DE OUTUBRO DE 2025
            </a></h2>
        </body></html>
        """
        result = parse_list_page(html, "https://www.gov.br/compras/pt-br/legislacao/ins")
        assert len(result.items) == 2
        assert result.items[0].doc_id == "in_512_2025_federal_br"
        assert result.items[1].doc_id == "in_460_2025_federal_br"
        assert result.next_page_url is None

    def test_detecta_paginacao(self):
        html = """
        <html><body>
            <h2><a href="/legislacao/in-1">IN Nº 1, DE 1 DE JANEIRO DE 2020</a></h2>
            <a href="?b_start:int=30">Próximo »</a>
        </body></html>
        """
        result = parse_list_page(html, "https://www.gov.br/compras/pt-br/legislacao/ins")
        assert result.next_page_url is not None
        assert "b_start:int=30" in result.next_page_url

    def test_sem_itens(self):
        html = "<html><body><p>Pagina vazia</p></body></html>"
        result = parse_list_page(html, "https://example.com")
        assert len(result.items) == 0

    def test_extrai_itens_h3_a(self):
        """Leis e decretos usam h3 no portal."""
        html = """
        <html><body>
            <h3><a href="http://www.planalto.gov.br/lei-14133">
                LEI Nº 14.133, DE 1º DE ABRIL DE 2021
            </a></h3>
            <h3><a href="http://www.planalto.gov.br/lc-123">
                LEI COMPLEMENTAR Nº 123, DE 14 DE DEZEMBRO DE 2006
            </a></h3>
        </body></html>
        """
        result = parse_list_page(html, "https://www.gov.br/compras/pt-br/legislacao/leis")
        assert len(result.items) == 2
        assert result.items[0].doc_id == "lei_14133_2021_federal_br"
        assert result.items[1].doc_id == "lc_123_2006_federal_br"

    def test_h2_h3_dedup(self):
        """Se mesmo link aparece em h2 e h3, nao duplica."""
        html = """
        <html><body>
            <h2><a href="/lei-1">LEI Nº 1, DE 1 DE JANEIRO DE 2020</a></h2>
            <h3><a href="/lei-1">LEI Nº 1, DE 1 DE JANEIRO DE 2020</a></h3>
        </body></html>
        """
        result = parse_list_page(html, "https://example.com")
        assert len(result.items) == 1

    def test_links_relativos_sao_resolvidos(self):
        html = """
        <html><body>
            <h2><a href="../legislacao/in-512">
                INSTRUÇÃO NORMATIVA Nº 512, DE 3 DE DEZEMBRO DE 2025
            </a></h2>
        </body></html>
        """
        result = parse_list_page(html, "https://www.gov.br/compras/pt-br/legislacao/lista")
        assert result.items[0].detail_url.startswith("https://www.gov.br/")


# ── parse_detail_page ────────────────────────────────────────────────────────

class TestParseDetailPage:
    def test_extrai_texto_basico(self):
        html = """
        <html><head><title>IN 512/2025</title></head>
        <body>
            <nav>Menu principal</nav>
            <h1>INSTRUÇÃO NORMATIVA SEGES/MGI Nº 512, DE 3 DE DEZEMBRO DE 2025</h1>
            <article>
                <p>Art. 1º Esta Instrução Normativa regulamenta o art. 32 da Lei nº 14.133.</p>
                <p>Art. 2º Para os fins desta Instrução Normativa considera-se:</p>
            </article>
            <footer>Rodape</footer>
        </body></html>
        """
        result = parse_detail_page(html)
        assert "Art. 1" in result.text
        assert "Art. 2" in result.text
        assert "Menu principal" not in result.text
        assert "Rodape" not in result.text
        assert result.title is not None

    def test_detecta_link_dou(self):
        html = """
        <html><body>
            <article>
                <p>Texto normativo</p>
                <a href="https://www.in.gov.br/web/dou/-/instrucao-normativa-123">DOU</a>
            </article>
        </body></html>
        """
        result = parse_detail_page(html)
        assert result.dou_url is not None
        assert "in.gov.br/web/dou" in result.dou_url

    def test_detecta_revogacao_no_texto(self):
        html = """
        <html><body>
            <article>
                <p>Art. 50. Fica revogada pela Instrução Normativa nº 90, de 2022.</p>
            </article>
        </body></html>
        """
        result = parse_detail_page(html)
        assert len(result.revoked_by_refs) >= 1


# ── extract_html ─────────────────────────────────────────────────────────────

class TestExtractHtml:
    def test_extrai_texto_de_html_simples(self):
        html = b"""
        <html><body>
            <article>
                <p>Art. 1 Texto do artigo primeiro.</p>
                <p>Art. 2 Texto do artigo segundo.</p>
            </article>
        </body></html>
        """
        result = extract_html(html)
        assert result.source_format == "html"
        assert result.extractor == "beautifulsoup"
        assert "Art. 1" in result.text
        assert "Art. 2" in result.text
        assert result.char_count > 0
        assert len(result.sha256) == 64

    def test_remove_scripts_e_styles(self):
        html = b"""
        <html><body>
            <script>var x = 1;</script>
            <style>.nav { color: red; }</style>
            <p>Conteudo real</p>
        </body></html>
        """
        result = extract_html(html)
        assert "var x" not in result.text
        assert "color: red" not in result.text
        assert "Conteudo real" in result.text

    def test_encoding_latin1(self):
        html = "Instrução Normativa nº 1".encode("latin-1")
        result = extract_html(html, encoding="latin-1")
        assert "Instru" in result.text

    def test_html_vazio(self):
        result = extract_html(b"<html><body></body></html>")
        assert result.char_count == 0 or result.text == ""


# ── dispatch via text_extractor ──────────────────────────────────────────────

class TestTextExtractorHtmlDispatch:
    def test_dispatch_html(self):
        from govy.legal.text_extractor import extract
        html = b"<html><body><p>Texto de teste</p></body></html>"
        result = extract(html, "documento.html")
        assert result.source_format == "html"
        assert "Texto de teste" in result.text

    def test_dispatch_htm(self):
        from govy.legal.text_extractor import extract
        html = b"<html><body><p>Texto htm</p></body></html>"
        result = extract(html, "arquivo.htm")
        assert result.source_format == "html"
