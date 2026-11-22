"""F5 - The document collection: reading the PDFs and dividing them into passages (lead: Mohamed Alradhi).

Method (as in Lab 3.3, "Splitting the Laws into Chunks"):
  1. Read each document page by page, so every passage keeps its page numbers for citations.
     Six PDFs have a text layer (read with pypdf). D1a and D3a are scans: their text is the
     group's checked OCR text in documents/ocr/.
  2. Split each page into paragraphs: a new paragraph starts at a blank line, a heading
     (Article (10), Section 5, 5.4.5 ...) or a list item.
  3. Group whole paragraphs into passages of at most `chunk_words` words (200 in v1, as in the lab),
     recording the document, the pages and the articles/sections each passage covers.
     A new article or section starts a new passage once the current one is at least half full,
     so most passages hold one rule.
  4. Give each passage an id, P1, P2, ... which the model cites as [P12].

The PDFs are stored unchanged in documents/; their official URLs and SHA-256 are in data/documents_manifest.json.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from app.config import DOCS_DIR, DOCS_MANIFEST, OCR_DIR

# Short names and currency notes shown with every passage, so the model (and the reader)
# knows which document a rule comes from and whether a newer text replaces it.
DOC_INFO = {
    "D1": ("Legislative Decree No. (27) of 2015 concerning the Commercial Register (MOIC)",
           "Articles 20(a)(1)-(3) and 27 were amended by D1a in 2018. A definition in Article 1 was amended "
           "by Law No. (9) of 2022, which has no English text."),
    "D1a": ("Legislative Decree No. (52) of 2018 amending the Commercial Register law (MOIC)",
            "Current text of the fines and penalties it replaces in D1."),
    "D2": ("Order No. (126) of 2016, Implementing Regulation of the Commercial Register law (MOIC)",
           "Article 14 was amended by Decision No. (68) of 2018, and Articles 6 (paragraph 2), 16, 20 (paragraph 1) "
           "and 21 (paragraph 1) by Decision No. (62) of 2024. Neither amendment has an English text, so these "
           "articles may not be the current rule."),
    "D3": ("MOIC Procedures Guide for Establishments and Commercial Companies",
           "Guide file from 2022; its limited liability company (WLL) section predates D3a and is out of date."),
    "D3a": ("Decree-Law No. (28) of 2020 amending the Commercial Companies Law (MOIC)",
            "Current text for the articles it replaces, including one-person WLL companies."),
    "D4": ("MOH Food Safety Guideline in Food Premises (FCS/3, Version 4)", ""),
    "D5": ("MOIC Virtual Store 'Sijili' Guide (summary of Order No. (51) of 2024)",
           "Its count of available activities is out of date (amended in 2026)."),
    "D6": ("MOIC notice 'Food Truck Activity Licensing'", ""),
}

HEADING = re.compile(
    r"^(Article\s*\(\s*\d+[^)]*\)"                      # Article (10), Article (18 bis)
    r"|Article\s+(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)\b"   # amendment decrees
    r"|Section\s+\d+"                                     # D4: Section 5 - ...
    r"|\d+\.\d+(\.\d+)*\s+[A-Z])"                         # D4: 5.4.5 Temperature control
)
LIST_ITEM = re.compile(r"^([▪•\-–]|\d+[.)-]\s|[a-z][.)]\s|\(\w\)\s)")
D4_HEADER = re.compile(r"^\d+\s*\|\s*Food Safety Guideline in Food Premises", re.I)
ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")


@dataclass
class Page:
    doc: str          # D1, D1a, ...
    file: str
    page: int         # PDF page number, from 1
    text: str


@dataclass
class Chunk:
    id: str                       # P1, P2, ...
    doc: str
    pages: list[int]
    sections: list[str] = field(default_factory=list)
    text: str = ""

    @property
    def words(self) -> int:
        return len(self.text.split())

    def page_label(self) -> str:
        a, b = self.pages[0], self.pages[-1]
        return f"p. {a}" if a == b else f"pp. {a}–{b}"

    def title(self) -> str:
        """Document code, short name, sections and pages: used for embedding and in every citation."""
        name = DOC_INFO.get(self.doc, (self.doc, ""))[0]
        secs = ", ".join(self.sections)
        return f"{self.doc} · {name}" + (f" · {secs}" if secs else "") + f" · {self.page_label()}"

    def as_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ 1. read the pages
def manifest() -> dict:
    return json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))


def _clean_line(doc: str, line: str) -> str | None:
    line = line.replace(" ", " ").strip()
    if not line:
        return ""
    if doc == "D4" and D4_HEADER.match(line):          # running page header of the guideline
        return None
    if re.fullmatch(r"\d{1,3}", line):                  # a page number on its own
        return None
    if ARABIC.search(line) and len(ARABIC.findall(line)) > len(LATIN.findall(line)):
        return None                                     # D5 prints Arabic and English side by side: keep the English
    return re.sub(r"\s+", " ", line)


def ocr_file_for(name: str) -> str:
    return name.replace(".pdf", " (OCR).txt")


def load_pages() -> list[Page]:
    """Every page of every document, in manifest order. Raises FileNotFoundError if a file is missing."""
    from pypdf import PdfReader

    pages: list[Page] = []
    for name, info in manifest().items():
        doc = info["code"]
        ocr = OCR_DIR / ocr_file_for(name)
        if info.get("scanned"):
            if not ocr.exists():
                raise FileNotFoundError(f"OCR text missing for {doc}: {ocr}. Run python scripts/setup_sources.py")
            raw = ocr.read_text(encoding="utf-8")
            parts = re.split(r"=== PAGE (\d+) ===", raw)
            for num, text in zip(parts[1::2], parts[2::2]):
                pages.append(Page(doc, name, int(num), text))
        else:
            reader = PdfReader(str(DOCS_DIR / name))
            for i, p in enumerate(reader.pages, start=1):
                pages.append(Page(doc, name, i, p.extract_text() or ""))
    return pages


def page_text(page: Page) -> str:
    """The cleaned text of a page (used for the baseline run, where whole documents go in the prompt)."""
    lines = [_clean_line(page.doc, l) for l in page.text.splitlines()]
    return "\n".join(l for l in lines if l)


# ------------------------------------------------------------------ 2. paragraphs
def paragraphs(page: Page) -> list[tuple[str, str | None]]:
    """(paragraph text, heading if the paragraph starts a new article/section) for one page."""
    out: list[tuple[str, str | None]] = []
    current: list[str] = []
    heading: str | None = None

    def close():
        nonlocal current, heading
        if current:
            out.append((" ".join(current), heading))
        current, heading = [], None

    for raw in page.text.splitlines():
        line = _clean_line(page.doc, raw)
        if line is None:
            continue
        if line == "":
            close()
            continue
        if HEADING.match(line):
            close()
            heading = line if len(line) < 90 else line[:90]
        elif LIST_ITEM.match(line):
            close()
        current.append(line)
    close()
    return out


# ------------------------------------------------------------------ 3. passages (chunks)
def split_into_chunks(pages: list[Page], chunk_words: int) -> list[Chunk]:
    """Group whole paragraphs into passages of at most chunk_words words, one document at a time."""
    chunks: list[Chunk] = []
    for doc in dict.fromkeys(p.doc for p in pages):
        current: list[str] = []
        count = 0
        pages_in: list[int] = []
        sections: list[str] = []
        section_now: str | None = None          # the article/section the current paragraph belongs to

        def close():
            nonlocal current, count, pages_in, sections
            if current:
                chunks.append(Chunk(id="", doc=doc, pages=sorted(set(pages_in)), sections=list(sections),
                                    text="\n".join(current)))
            current, count, pages_in, sections = [], 0, [], []

        for page in (p for p in pages if p.doc == doc):
            for text, heading in paragraphs(page):
                if heading is not None:
                    # a new article/section starts a new passage once the current one is at least half full
                    if current and count >= chunk_words // 2:
                        close()
                    section_now = _short(heading)
                # a paragraph longer than the limit is split at sentence ends
                for piece in _split_long(text, chunk_words):
                    n = len(piece.split())
                    if current and count + n > chunk_words:
                        close()
                    current.append(piece)
                    count += n
                    pages_in.append(page.page)
                    if section_now and section_now not in sections:
                        sections.append(section_now)   # the articles/sections this passage covers (as in Lab 3.3)
        close()
    for i, c in enumerate(chunks, start=1):
        c.id = f"P{i}"
    return chunks


def _short(heading: str) -> str:
    """'Article (10)' or '5.4.5 Temperature control' (first few words only)."""
    m = re.match(r"(Article\s*\(\s*[^)]*\)|Article\s+\w+|Section\s+\d+)", heading)
    if m:
        return re.sub(r"\s+", " ", m.group(1))
    return " ".join(heading.split()[:5])


def _split_long(text: str, limit: int) -> list[str]:
    if len(text.split()) <= limit:
        return [text]
    sentences = re.split(r"(?<=[.;:])\s+", text)
    pieces, cur = [], []
    for s in sentences:
        if cur and len(" ".join(cur + [s]).split()) > limit:
            pieces.append(" ".join(cur))
            cur = []
        cur.append(s)
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def build_chunks(chunk_words: int) -> list[Chunk]:
    return split_into_chunks(load_pages(), chunk_words)
