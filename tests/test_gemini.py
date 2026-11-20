"""Tests for the Gemini client helpers (app/gemini.py), with made-up responses: no API key, no network."""
from google.genai import types

from app import gemini
from app.config import get_settings
from app.gemini import Gemini, RateLimiter, Usage, embed_token_count, failure_tag


class FakeError(Exception):
    def __init__(self, code):
        self.code = code


def test_failure_tags_name_the_problem_plainly():
    assert failure_tag(FakeError(429)) == "FAILED: RATE LIMIT (429)"
    assert failure_tag(FakeError(503)) == "FAILED: SERVER BUSY (503)"
    assert failure_tag(ValueError("x")).startswith("FAILED: ValueError")


def test_usage_adds_thinking_tokens_to_output():
    r = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="ok")]),
                                    finish_reason="STOP")],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20, thoughts_token_count=5))
    u = Usage()
    u.add_response(r)
    u.add_response(r)
    assert (u.input_tokens, u.output_tokens, u.thinking_tokens, u.generation_calls) == (200, 50, 10, 2)
    assert u.finish_reasons == ["STOP", "STOP"]


def test_rate_limiter_waits_only_when_the_minute_is_full(monkeypatch):
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    limiter = RateLimiter(per_minute=2)
    assert limiter.wait() == 0 and limiter.wait() == 0
    assert limiter.wait() > 0 and slept                         # the third request in a minute waits


def test_embedding_token_count():
    r = types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=[0.1])],
                                   usage_metadata=types.EmbedContentResponseUsageMetadata(prompt_token_count=24)) \
        if hasattr(types, "EmbedContentResponseUsageMetadata") else None
    if r is not None:
        assert embed_token_count(r) == 24
    empty = types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=[0.1])])
    assert embed_token_count(empty) == 0


def test_request_settings_come_from_config():
    g = Gemini("test-value-not-a-key", get_settings("v1"))
    cfg = g.config("instruction", tools=[types.FunctionDeclaration(name="f", description="d")], tool_mode="AUTO")
    assert cfg.temperature == 1.0 and cfg.max_output_tokens == 1024
    assert cfg.system_instruction == "instruction"
    assert cfg.automatic_function_calling.disable is True       # we run the functions ourselves
    assert cfg.tool_config.function_calling_config.mode == "AUTO"
    assert g.config().tools is None
