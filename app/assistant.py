"""F6-F8 - Answering a question: data and documents together, refusal, follow-ups (lead: Sayed Fadhul Hashem).

How one question is answered (the three course techniques together):
  1. Retrieval (F5): the question is embedded and the k most similar passages are found.
     For a follow-up ("And how many ...?") the previous question is added to the search text,
     so the search knows what "it" or "that" refers to (F8).
  2. Prompting: the system instruction sets the rules (sources only, cite ids, refuse when the
     sources do not answer). The request holds the earlier questions and answers of the session (F8),
     the retrieved passages with their ids, and the question (as in Lab 3.3: "Passages: ... Question: ...").
  3. Tool use (F4): the model may call the data functions in app/data_tools.py. Our code runs them and
     sends the computed figures back with an id such as [T1]. At most 3 generation calls per question;
     the last call is sent without the function list, so it must write the answer.
  4. Checks: the citations in the answer are matched with the passages and results the model received,
     and a refusal is detected from the fixed opening sentence (F7).
Everything about the question (answer, citations, passages, function calls, tokens, time) is returned
in an Answer, which the app shows and the query log saves (F10).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from google.genai import types

from app.config import Settings, cost_usd
from app.documents import DOC_INFO
from app.gemini import Gemini, Usage, failure_tag
from app.retrieval import Index, question_input

REFUSAL = "This is not available in the sources."

SYSTEM_INSTRUCTION = f"""You are BizLocate BH, a tool used by advisors at a government business support centre in Bahrain during consultations with people who plan to open a small business.

You answer only from two kinds of sources given in this conversation:
1. FUNCTION RESULTS: figures computed in code from six published datasets: business locations of restaurants and cafes [RC], other shops [OS] and supermarkets and hypermarkets [SH]; population [POP]; land use [LU]; area [AR]. Each result has an id such as T1.
2. PASSAGES: extracts of eight official documents: the Commercial Register law (D1) and its 2018 amendment (D1a), its implementing regulation (D2), the MOIC procedures guide (D3), the 2020 amendment of the Commercial Companies Law (D3a), the MOH food-safety guideline (D4), the Sijili virtual-store guide (D5) and the food-truck licensing notice (D6). Each passage has an id such as P12.

Rules:
- For questions about businesses, residents, land use or area (including how a figure in a dataset changed), call the functions. For questions about registration, licensing or requirements, use the passages. A combined question needs both.
- Before you say that something is not available, call the functions that could hold the answer, unless the question asks for something the datasets do not record (listed below).
- Every number in your answer must be copied from a function result or a passage. Never calculate or estimate a number yourself: if you need a count, total, share, change or ratio, call the function that computes it.
- A follow-up question (for example "And in Muharraq?") asks for new figures: call the functions again with the new filters. Earlier answers in the conversation are shown without their citations and cannot be cited.
- Answer every part of the question, and give the figures behind each part (for example the values for each year or each governorate you compare). When you say that a figure rose, fell, jumped or differs, give the values with their years or places, copied from the function result.
- After each sentence, cite the ids it is based on in square brackets, for example [T1], [P12] or [T1, P12]. Cite only ids of function results and passages that appear in this conversation; never invent an id. A sentence that uses no function result or passage has no citation.
- If the function results and passages do not contain the answer, begin your reply with "{REFUSAL}" and then say in one or two sentences what the sources do cover. Do the same when asked whether a business would succeed, about the future, rents, prices, footfall, whether a named business is still open, or how many people live in a block (population is published only by governorate).
- If a function reports that the value asked for is missing in the source, begin with "{REFUSAL}" and explain that the record has no value in the source, which is not the same as zero.
- If one part of a question can be answered and another cannot, answer the first part and say which part is not available in the sources.
- When two documents differ, the newer amendment (D1a or D3a) is the current rule: say so.
- Do not rank areas or recommend where to open; give the evidence for the areas asked about.
- Mention a caveat from a function's notes only when it matters for the question.
- Write short, plain English: the direct answer first, then the details."""

FOLLOW_UP_WORDS = re.compile(r"\b(it|its|that|this|those|these|they|them|there|same|also|above|previous|instead)\b", re.I)
CITATION_GROUP = re.compile(r"\[([^\[\]]{1,80})\]")
CITATION_ID = re.compile(r"\b([PT]\d+)\b")
CITATION_MARKER = re.compile(r"\s*\[(?:[PT]\d+\s*,?\s*)+\]")


def without_citations(text: str) -> str:
    """An earlier answer as it is sent back for a follow-up: the text without [T1]/[P3] markers,
    so the model cannot cite an earlier result for a new figure (it must call the functions again)."""
    return CITATION_MARKER.sub("", text or "")


@dataclass
class Answer:
    question: str
    text: str = ""
    refused: bool = False                    # the answer opens with the refusal sentence (F7)
    says_not_available: bool = False         # the refusal sentence appears anywhere (e.g. one part declined)
    passages: list[dict] = field(default_factory=list)       # retrieved: id, doc, title, pages, score, text
    tool_results: list[dict] = field(default_factory=list)   # function calls: id, function, arguments, result, ...
    cited: list[str] = field(default_factory=list)            # ids cited in the answer, in order
    unknown_citations: list[str] = field(default_factory=list)  # cited ids the model was never given
    retrieval_query: str = ""
    follow_up: bool = False
    usage: Usage = field(default_factory=Usage)
    latency_s: float = 0.0                   # question sent -> answer ready (wall clock)
    error: str | None = None
    model: str = ""
    version: str = ""
    settings: dict = field(default_factory=dict)
    timestamp: str = ""

    @property
    def latency_without_waits_s(self) -> float:
        return round(max(0.0, self.latency_s - self.usage.wait_seconds), 2)

    @property
    def cited_passages(self) -> list[str]:
        return [c for c in self.cited if c.startswith("P")]

    @property
    def cited_results(self) -> list[str]:
        return [c for c in self.cited if c.startswith("T")]

    def cost(self) -> float:
        u = self.usage
        return cost_usd(u.input_tokens, u.output_tokens, u.embed_tokens)

    def log_record(self, session_id: str = "", run: str = "app") -> dict:
        """One row of the structured query log (F10)."""
        u = self.usage
        return {
            "timestamp": self.timestamp, "run": run, "session_id": session_id,
            "version": self.version, "model": self.model, "settings": self.settings,
            "question": self.question, "answer": self.text, "refused": self.refused,
            "says_not_available": self.says_not_available, "follow_up": self.follow_up,
            "citations": [{"id": c, "title": self._title(c)} for c in self.cited],
            "unknown_citations": self.unknown_citations,
            "retrieval_query": self.retrieval_query,
            "retrieved_passages": [{"id": p["id"], "title": p["title"], "score": p["score"]} for p in self.passages],
            "function_calls": [{"id": r.get("id"), "function": r.get("function"), "arguments": r.get("arguments"),
                                "source": r.get("source"), "result": r.get("result"), "error": r.get("error")}
                               for r in self.tool_results],
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens, "thinking_tokens": u.thinking_tokens,
            "embedding_tokens": u.embed_tokens, "generation_calls": u.generation_calls,
            "embedding_calls": u.embedding_calls, "finish_reasons": u.finish_reasons,
            "latency_s": round(self.latency_s, 2), "wait_s": round(u.wait_seconds, 2),
            "latency_without_waits_s": self.latency_without_waits_s,
            "cost_usd": round(self.cost(), 6), "error": self.error,
        }

    def _title(self, cid: str) -> str:
        for p in self.passages:
            if p["id"] == cid:
                return p["title"]
        for r in self.tool_results:
            if r.get("id") == cid:
                return f"{r.get('function')}: {r.get('source', '')}"
        return ""


# ---------------------------------------------------------------------------- helpers
def is_follow_up(question: str, has_history: bool) -> bool:
    """A very short question, or one that starts with 'And ...' or refers back ('it', 'that', 'there' ...),
    is treated as a follow-up."""
    if not has_history:
        return False
    q = question.strip().lower()
    return (len(q.split()) <= 4 or q.startswith(("and ", "what about", "how about", "and,"))
            or bool(FOLLOW_UP_WORDS.search(q)))


def parse_citations(text: str) -> list[str]:
    """Every id cited in square brackets, in order of first appearance: [P3], [T1, P12] ..."""
    found: list[str] = []
    for group in CITATION_GROUP.findall(text or ""):
        for cid in CITATION_ID.findall(group):
            if cid not in found:
                found.append(cid)
    return found


def passage_block(chunk, score: float) -> str:
    note = DOC_INFO.get(chunk.doc, ("", ""))[1]
    head = f"[{chunk.id}] {chunk.title()}" + (f"\nNote: {note}" if note else "")
    return f"{head}\n{chunk.text}"


def result_for_model(result: dict, max_rows: int = 25) -> dict:
    """What the model receives for one function call: its id, the figures, the source and the notes."""
    out = {k: result[k] for k in ("id", "error", "result", "source", "notes") if k in result}
    rows = result.get("rows") or []
    if rows:
        out["rows"] = rows[:max_rows]
        if len(rows) > max_rows:
            out["rows_note"] = f"{len(rows) - max_rows} more rows not shown"
    return out


def response_text(response) -> str:
    """The text parts of a response (ignores function-call parts)."""
    try:
        parts = response.candidates[0].content.parts or []
    except Exception:
        return ""
    return "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)).strip()


# ---------------------------------------------------------------------------- the assistant
class Assistant:
    def __init__(self, gemini: Gemini, settings: Settings, tools=None, index: Index | None = None):
        self.gemini = gemini
        self.settings = settings
        self.tools = tools          # app.data_tools.DataTools, or None (documents only)
        self.index = index          # app.retrieval.Index, or None (data only)

    def ask(self, question: str, history: list[Answer] | None = None) -> Answer:
        history = [h for h in (history or []) if not h.error]
        s = self.settings
        ans = Answer(question=question, model=s.model, version=s.version, settings=s.as_dict(),
                     timestamp=datetime.now().isoformat(timespec="seconds"))
        start = time.perf_counter()
        try:
            self._answer(ans, history)
        except Exception as err:            # a failed request is recorded plainly, never shown as an answer
            ans.error = f"{failure_tag(err)}: {err}"
            ans.text = ""
        ans.latency_s = time.perf_counter() - start
        return ans

    def _answer(self, ans: Answer, history: list[Answer]) -> None:
        s = self.settings
        recent = history[-s.history_turns:] if s.history_turns > 0 else []

        # 1. retrieval (F5), with the previous question added for a follow-up (F8)
        ans.follow_up = is_follow_up(ans.question, bool(recent))
        ans.retrieval_query = (recent[-1].question + " " + ans.question) if ans.follow_up else ans.question
        if self.index is not None:
            qv = self.gemini.embed([question_input(ans.retrieval_query)], ans.usage)[0]
            for score, chunk in self.index.search(qv, s.top_k):
                ans.passages.append({"id": chunk.id, "doc": chunk.doc, "title": chunk.title(), "pages": chunk.pages,
                                     "score": score, "text": chunk.text, "block": passage_block(chunk, score)})

        # 2. the request: earlier turns, then the passages and the question (Lab 3.3 layout)
        contents: list[types.Content] = []
        for h in recent:
            contents.append(types.Content(role="user", parts=[types.Part(text=h.question)]))
            contents.append(types.Content(role="model", parts=[types.Part(text=without_citations(h.text))]))
        passages = "\n\n".join(p["block"] for p in ans.passages) or "(no passages were retrieved)"
        prompt = f"Passages:\n{passages}\n\nQuestion: {ans.question}"
        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

        # 3. generation with tool use: at most max_generation_calls calls
        declarations = self.tools.declarations() if self.tools is not None else None
        next_id = 1 + sum(len(h.tool_results) for h in history)
        response = None
        for call_no in range(1, s.max_generation_calls + 1):
            last = call_no == s.max_generation_calls
            # The last call gets no function list at all, so it must write the answer
            # (with the list and mode NONE the model sometimes still asked for a function).
            use_tools = declarations if (declarations and not last) else None
            response = self.gemini.generate(contents, ans.usage, SYSTEM_INSTRUCTION, tools=use_tools,
                                            tool_mode="AUTO" if use_tools else None)
            calls = response.function_calls or []
            if not calls or last:
                break
            contents.append(response.candidates[0].content)      # keeps the model's turn (and its thought signatures)
            parts = []
            for fc in calls:
                result = self.tools.call(fc.name, dict(fc.args or {}))
                result = {"id": f"T{next_id}", **result}
                next_id += 1
                ans.tool_results.append(result)
                parts.append(types.Part.from_function_response(name=fc.name, response={"output": result_for_model(result)}))
            contents.append(types.Content(role="user", parts=parts))

        ans.text = response_text(response) if response is not None else ""
        if not ans.text:
            ans.error = "FAILED: NO TEXT (the model returned no answer text)"
            return

        # 4. checks: refusal (F7) and citations (F5)
        ans.refused = ans.text.lstrip("*_ ").lower().startswith(REFUSAL.lower().rstrip("."))
        ans.says_not_available = "not available in the sources" in ans.text.lower()
        ans.cited = parse_citations(ans.text)
        # Only the passages and results of THIS question can be cited (earlier answers are sent without ids).
        known = {p["id"] for p in ans.passages} | {r["id"] for r in ans.tool_results}
        ans.unknown_citations = [c for c in ans.cited if c not in known]


def answer_to_json(ans: Answer) -> str:
    d = asdict(ans)
    for p in d["passages"]:
        p.pop("block", None)
    return json.dumps(d, ensure_ascii=False)
