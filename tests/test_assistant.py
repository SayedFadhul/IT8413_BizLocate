"""Tests for F6-F8 with a fake model (no API key, no network): the tool loop, citations,
refusal detection, follow-ups and the query-log record. No test-set question is used."""
import numpy as np
import pytest
from google.genai import types

from app.assistant import REFUSAL, Assistant, is_follow_up, parse_citations
from app.config import get_settings
from app.data_prep import load_all
from app.data_tools import DataTools
from app.documents import Chunk
from app.retrieval import Index


def text_response(text, tokens=(100, 20)):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]),
                                    finish_reason="STOP")],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=tokens[0],
                                                                  candidates_token_count=tokens[1]))


def call_response(name, args):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name=name, args=args))]), finish_reason="STOP")],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=80, candidates_token_count=10))


class FakeGemini:
    """Plays back scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.embedded = []

    def embed(self, texts, usage=None):
        self.embedded += texts
        if usage is not None:
            usage.embedding_calls += 1
            usage.embed_tokens += 7
        return [[1.0, 0.0, 0.0] for _ in texts]

    def generate(self, contents, usage, system_instruction=None, tools=None, tool_mode=None):
        self.requests.append({"contents": list(contents), "tools": tools, "tool_mode": tool_mode})
        r = self.responses.pop(0)
        usage.add_response(r)
        return r


@pytest.fixture(scope="module")
def tools():
    return DataTools(load_all())


@pytest.fixture
def index():
    chunks = [Chunk(id="P1", doc="D4", pages=[9], sections=["Section 4"], text="A food premises needs a licence."),
              Chunk(id="P2", doc="D6", pages=[1], text="The applicant shall be a Bahraini national.")]
    return Index(chunks=chunks, vectors=np.array([[1.0, 0, 0], [0, 1.0, 0]]), info={"passages": 2})


def test_combined_question_uses_a_function_and_a_passage(tools, index):
    fake = FakeGemini([call_response("count_businesses", {"business_types": ["PIZZA"], "governorates": ["Capital"]}),
                       text_response("There are N pizza places [T1]. A licence is needed [P1].")])
    a = Assistant(fake, get_settings("v1"), tools=tools, index=index).ask("Pizza places in the Capital and the licence?")
    assert a.error is None
    assert a.tool_results[0]["id"] == "T1" and a.tool_results[0]["function"] == "count_businesses"
    assert a.cited == ["T1", "P1"] and a.unknown_citations == []
    assert a.passages[0]["id"] == "P1"                       # closest passage first
    assert a.usage.generation_calls == 2 and a.usage.embedding_calls == 1
    assert a.usage.input_tokens == 180 and a.usage.output_tokens == 30
    # the function result went back to the model
    last = fake.requests[1]["contents"][-1].parts[0].function_response
    assert last.name == "count_businesses" and last.response["output"]["id"] == "T1"


def test_last_call_cannot_call_functions(tools, index):
    s = get_settings("v1")
    responses = [call_response("get_area", {"year": 2024})] * (s.max_generation_calls - 1) + [text_response("Done [T1].")]
    fake = FakeGemini(responses)
    a = Assistant(fake, s, tools=tools, index=index).ask("Area?")
    modes = [r["tool_mode"] for r in fake.requests]
    assert fake.requests[-1]["tools"] is None and modes[-1] is None      # no function list on the last call
    assert all(m == "AUTO" for m in modes[:-1]) and all(r["tools"] for r in fake.requests[:-1])
    assert len(fake.requests) == s.max_generation_calls and a.text == "Done [T1]."


def test_refusal_is_detected(tools, index):
    fake = FakeGemini([text_response(f"{REFUSAL} The sources have no rents.")])
    a = Assistant(fake, get_settings("v1"), tools=tools, index=index).ask("What is the rent in block 1?")
    assert a.refused and a.says_not_available


def test_unknown_citation_is_flagged(tools, index):
    fake = FakeGemini([text_response("Claim [P9].")])
    a = Assistant(fake, get_settings("v1"), tools=tools, index=index).ask("Question?")
    assert a.unknown_citations == ["P9"]


def test_follow_up_sends_history_and_searches_with_the_previous_question(tools, index):
    s = get_settings("v1")
    first = Assistant(FakeGemini([text_response("67 stores [T1].")]), s, tools=tools, index=index).ask(
        "How many supermarkets are in the Southern Governorate?")
    fake = FakeGemini([text_response("About 4,810 [T2].")])
    second = Assistant(fake, s, tools=tools, index=index).ask("And per resident?", [first])
    assert second.follow_up
    assert "Southern Governorate" in fake.embedded[0]          # the search knows what 'it' refers to
    roles = [c.role for c in fake.requests[0]["contents"]]
    assert roles == ["user", "model", "user"]                  # previous question, previous answer, new question
    assert fake.requests[0]["contents"][1].parts[0].text == "67 stores."   # sent back without its citation


def test_follow_up_cannot_cite_an_earlier_result(tools, index):
    s = get_settings("v1")
    first = Assistant(FakeGemini([call_response("count_businesses", {"governorates": ["Capital"]}),
                                  text_response("There are N [T1].")]), s, tools=tools, index=index).ask("How many?")
    second = Assistant(FakeGemini([text_response("There are 7 [T1].")]), s, tools=tools, index=index).ask(
        "And in Muharraq?", [first])
    assert second.unknown_citations == ["T1"]                  # T1 belongs to the earlier question


def test_without_citations():
    from app.assistant import without_citations
    assert without_citations("A [T1]. B [P2, T3]. C [note].") == "A. B. C [note]."


def test_failed_request_is_recorded_not_answered(tools, index):
    class Broken(FakeGemini):
        def generate(self, *a, **k):
            raise RuntimeError("network down")
    a = Assistant(Broken([]), get_settings("v1"), tools=tools, index=index).ask("Anything?")
    assert a.error and "network down" in a.error and a.text == ""


def test_log_record_has_the_fields_the_brief_asks_for(tools, index):
    fake = FakeGemini([text_response("A licence is needed [P1].")])
    a = Assistant(fake, get_settings("v1"), tools=tools, index=index).ask("Licence?")
    rec = a.log_record(session_id="s1")
    for key in ("question", "answer", "citations", "latency_s", "input_tokens", "output_tokens", "model", "settings",
                "version", "timestamp"):
        assert key in rec
    assert rec["citations"][0]["id"] == "P1" and "D4" in rec["citations"][0]["title"]


def test_helpers():
    assert parse_citations("x [T1, P2] y [P2][P10] z [not an id]") == ["T1", "P2", "P10"]
    assert not is_follow_up("How many?", has_history=False)
    assert is_follow_up("And what about Muharraq?", has_history=True)
