"""Tests for govy.doctrine.chunker — paragraph grouping into chunks."""

from __future__ import annotations

from govy.doctrine.chunker import chunk_paragraphs


class TestChunkParagraphs:
    def test_single_small_paragraph(self):
        chunks = chunk_paragraphs(["Short paragraph."])
        assert len(chunks) == 1
        assert chunks[0].order == 0
        assert chunks[0].content_raw == "Short paragraph."
        assert chunks[0].content_hash  # non-empty sha256

    def test_empty_input(self):
        assert chunk_paragraphs([]) == []

    def test_blank_paragraphs_skipped(self):
        chunks = chunk_paragraphs(["Hello", "", "  ", "World"])
        assert len(chunks) == 1
        assert "Hello" in chunks[0].content_raw
        assert "World" in chunks[0].content_raw

    def test_chunk_id_format(self):
        chunks = chunk_paragraphs(["Some text here."])
        assert chunks[0].chunk_id.startswith("doctrine_0_")

    def test_multiple_chunks_when_exceeding_max(self):
        paragraphs = [chr(ord("A") + i) * 1000 for i in range(5)]  # 5 distinct paragraphs
        chunks = chunk_paragraphs(paragraphs, max_chars=2500, min_chars=900)
        assert len(chunks) >= 2
        for i, ch in enumerate(chunks):
            assert ch.order == i

    def test_respects_min_chars(self):
        paragraphs = ["A" * 500, "B" * 500, "C" * 500]
        chunks = chunk_paragraphs(paragraphs, max_chars=600, min_chars=400)
        # First chunk: 500+1=501 chars in buffer, then second para would push to 1002 > 600
        # and 501 >= 400 (min), so flush happens. Result: at least 2 chunks
        assert len(chunks) >= 2

    def test_content_hash_is_deterministic(self):
        c1 = chunk_paragraphs(["Deterministic test"])
        c2 = chunk_paragraphs(["Deterministic test"])
        assert c1[0].content_hash == c2[0].content_hash

    def test_different_content_different_hash(self):
        c1 = chunk_paragraphs(["Content A"])
        c2 = chunk_paragraphs(["Content B"])
        assert c1[0].content_hash != c2[0].content_hash

    def test_dataclass_is_frozen(self):
        chunks = chunk_paragraphs(["Frozen test"])
        import dataclasses

        assert dataclasses.fields(chunks[0])  # it's a dataclass
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            chunks[0].order = 99  # type: ignore[misc]
