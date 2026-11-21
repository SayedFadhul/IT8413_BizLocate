"""Tests for F5: passages (chunks), keyword search and the citation-ready titles.
Skipped when the documents have not been downloaded (python scripts/setup_sources.py)."""
import numpy as np
import pytest

from app.config import DOCS_DIR
from app.documents import Chunk, split_into_chunks, Page
from app.retrieval import Index, keyword_search, passage_input, question_input


def test_chunking_keeps_whole_paragraphs_and_pages():
    text = "Article (1)\nDefinitions\n" + "word " * 120 + "\n\nArticle (2)\nScope\n" + "more " * 150
    pages = [Page("D9", "x.pdf", 1, text), Page("D9", "x.pdf", 2, "Article (3)\nEnd\n" + "last " * 30)]
    chunks = split_into_chunks(pages, chunk_words=200)
    assert [c.id for c in chunks] == [f"P{i}" for i in range(1, len(chunks) + 1)]
    assert all(c.words <= 200 for c in chunks)
    assert chunks[0].sections[0] == "Article (1)"
    assert chunks[-1].pages[-1] == 2
    assert "p." in chunks[0].title()


def test_long_paragraph_is_split_at_sentences():
    text = " ".join(f"Sentence number {i} has five words." for i in range(100))
    chunks = split_into_chunks([Page("D9", "x.pdf", 1, text)], chunk_words=60)
    assert all(c.words <= 60 for c in chunks)
    assert sum(c.words for c in chunks) == len(text.split())


def test_embedding_inputs_use_the_lab_prefixes():
    c = Chunk(id="P1", doc="D2", pages=[5], sections=["Article (10)"], text="Obtain licences within one year.")
    assert passage_input(c).startswith("title: D2")
    assert question_input("How long?") == "task: search result | query: How long?"


def test_cosine_search_ranks_the_closest_passage_first():
    chunks = [Chunk(id=f"P{i}", doc="D9", pages=[1], text=t) for i, t in enumerate(["a", "b", "c"], start=1)]
    idx = Index(chunks=chunks, vectors=np.array([[1, 0, 0], [0.7, 0.7, 0], [0, 0, 1]], dtype=float), info={})
    res = idx.search([0.9, 0.1, 0], k=2)
    assert [c.id for _, c in res] == ["P1", "P2"]
    assert res[0][0] > res[1][0]
    assert idx.by_id("P3").text == "c" and idx.by_id("P9") is None


def test_keyword_search():
    chunks = [Chunk(id="P1", doc="D9", pages=[1], text="The licence for food premises is valid for one year."),
              Chunk(id="P2", doc="D9", pages=[1], text="Shareholders of a joint stock company.")]
    assert keyword_search(chunks, "food premises licence")[0][1].id == "P1"


@pytest.mark.skipif(not (DOCS_DIR / "D4_MOH_Food_Safety_Guideline_FCS3_v4.pdf").exists(),
                    reason="documents not downloaded")
def test_real_collection():
    from app.documents import build_chunks
    chunks = build_chunks(200)
    docs = {c.doc for c in chunks}
    assert docs == {"D1", "D1a", "D2", "D3", "D3a", "D4", "D5", "D6"}
    assert all(1 <= c.words <= 200 for c in chunks)
    assert not any("| Food Safety Guideline in Food Premises" in c.text for c in chunks)   # page headers removed
    assert any("Article (10)" in c.sections for c in chunks if c.doc == "D2")
