"""Gemini API client, written the way the course labs do it (Labs 2.2-3.3).

  - One `genai.Client` with the key from the environment (never written in code).
  - `send()` retries a request twice when the service is busy (503) or a free-tier rate limit is
    reached (429): 30 and 60 seconds later by default, as in Lab 3.3 (evaluation runs). The app passes
    shorter pauses so a person is not left waiting, and shows each wait on screen (`on_wait`).
  - Instead of a fixed pause after every request, the client waits only when the next request
    would go over the per-minute limit (15 generation requests, 100 embedding requests). The time
    spent waiting is recorded, so latency can be reported with and without it.
  - Token counts come from `usage_metadata`; thinking tokens are billed as output tokens (Lab 4.1).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from google import genai
from google.genai import errors, types

from app.config import EMBEDDING_REQUESTS_PER_MINUTE, GENERATION_REQUESTS_PER_MINUTE, Settings

logging.getLogger("google_genai").setLevel(logging.ERROR)


def failure_tag(err: Exception) -> str:
    """Name a failed request plainly, so it is never read as a result (Labs 2.2-2.8)."""
    code = getattr(err, "code", None)
    if code == 429:
        return "FAILED: RATE LIMIT (429)"
    if code == 503:
        return "FAILED: SERVER BUSY (503)"
    return f"FAILED: {type(err).__name__} {code or ''}".strip()


def is_busy(err: Exception) -> bool:
    """True for the two errors that usually pass: server busy (503) and rate limit (429)."""
    return getattr(err, "code", None) in (429, 503)


def busy_text(code) -> str:
    return ("Google's server is busy (503)." if code == 503
            else "The free-tier request limit was reached (429).")


class RateLimiter:
    """Wait before a request only if the last minute already holds `per_minute` requests."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.sent: deque[float] = deque()

    def wait(self) -> float:
        now = time.monotonic()
        while self.sent and now - self.sent[0] > 60:
            self.sent.popleft()
        waited = 0.0
        if len(self.sent) >= self.per_minute:
            waited = 60 - (now - self.sent[0]) + 0.5
            time.sleep(max(0.0, waited))
            self.sent.popleft()
        self.sent.append(time.monotonic())
        return waited


@dataclass
class Usage:
    """Tokens and requests used for one question (all calls added together)."""

    input_tokens: int = 0
    output_tokens: int = 0          # includes thinking tokens
    thinking_tokens: int = 0
    embed_tokens: int = 0
    generation_calls: int = 0
    embedding_calls: int = 0
    wait_seconds: float = 0.0       # time spent waiting for rate limits or retries
    finish_reasons: list[str] = field(default_factory=list)

    def add_response(self, response) -> None:
        u = response.usage_metadata
        if u is not None:
            thoughts = u.thoughts_token_count or 0
            self.input_tokens += u.prompt_token_count or 0
            self.output_tokens += (u.candidates_token_count or 0) + thoughts
            self.thinking_tokens += thoughts
        self.generation_calls += 1
        try:
            self.finish_reasons.append(str(response.candidates[0].finish_reason.name))
        except Exception:
            pass


class Gemini:
    """The model calls of the app: generate (with or without tools) and embed."""

    _gen_limiter = RateLimiter(GENERATION_REQUESTS_PER_MINUTE)     # shared by every Gemini object in the process
    _emb_limiter = RateLimiter(EMBEDDING_REQUESTS_PER_MINUTE)

    def __init__(self, api_key: str, settings: Settings, retry_pauses: tuple[float, ...] = (30.0, 60.0),
                 on_wait: Callable[[str], None] | None = None):
        if not api_key:
            raise ValueError("No Gemini API key. Put GEMINI_API_KEY in a .env file (README, step 4).")
        self.client = genai.Client(api_key=api_key)
        self.settings = settings
        self.model = settings.model             # generation model (the app may switch to settings.fallback_model)
        self.retry_pauses = tuple(retry_pauses)
        self.on_wait = on_wait

    def notify(self, message: str) -> None:
        """Tell the person waiting what is happening (the app shows it; scripts pass nothing)."""
        if self.on_wait is not None:
            self.on_wait(message)

    # ----------------------------------------------------------------- retries (Lab 3.3)
    def send(self, request, limiter: RateLimiter, usage: Usage | None = None):
        """Submit a request. If the service is busy (503) or the rate limit is reached (429),
        wait and try again, once for each pause in `retry_pauses`."""
        attempts = len(self.retry_pauses) + 1
        for attempt in range(attempts):
            waited = limiter.wait()
            if usage:
                usage.wait_seconds += waited
            try:
                return request()
            except errors.APIError as err:
                if not is_busy(err) or attempt == attempts - 1:
                    raise
                pause = self.retry_pauses[attempt]
                if usage:
                    usage.wait_seconds += pause
                self.notify(f"{busy_text(err.code)} Trying again in {pause:g} seconds "
                            f"(attempt {attempt + 2} of {attempts}).")
                time.sleep(pause)

    # ----------------------------------------------------------------- generation
    def config(self, system_instruction: str | None = None, tools: list | None = None,
               tool_mode: str | None = None) -> types.GenerateContentConfig:
        s = self.settings
        kwargs: dict = dict(temperature=s.temperature, max_output_tokens=s.max_output_tokens)
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        if s.thinking_level and s.thinking_level != "default":
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=s.thinking_level)
        if tools:
            kwargs["tools"] = [types.Tool(function_declarations=tools)]
            # We run the functions ourselves (manual loop), so every call can be logged and checked.
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
            if tool_mode:
                kwargs["tool_config"] = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode=tool_mode))
        return types.GenerateContentConfig(**kwargs)

    def generate(self, contents, usage: Usage, system_instruction: str | None = None,
                 tools: list | None = None, tool_mode: str | None = None):
        cfg = self.config(system_instruction, tools, tool_mode)
        try:
            response = self.send(lambda: self.client.models.generate_content(
                model=self.model, contents=contents, config=cfg), self._gen_limiter, usage)
        except errors.APIError as err:
            err.stage = "generation"            # lets the app tell a busy model from a busy embedding service
            raise
        usage.add_response(response)
        return response

    # ----------------------------------------------------------------- embeddings (Labs 3.1 and 3.3)
    def embed(self, texts: list[str], usage: Usage | None = None) -> list[list[float]]:
        """One request for a list of texts; each text gets its own vector.

        Each text is sent as a separate input (its own Content). With gemini-embedding-2, texts placed
        together in one input produce ONE combined embedding (Week 8 lecture), which would mix passages."""
        inputs = [types.Content(parts=[types.Part(text=t)]) for t in texts]
        response = self.send(lambda: self.client.models.embed_content(
            model=self.settings.embedding_model, contents=inputs), self._emb_limiter, usage)
        vectors = [e.values for e in response.embeddings]
        if len(vectors) != len(texts):
            raise RuntimeError(f"Expected {len(texts)} embeddings, got {len(vectors)}")
        if usage is not None:
            usage.embedding_calls += 1
            usage.embed_tokens += embed_token_count(response)
        return vectors


def embed_token_count(response) -> int:
    """Tokens of an embedding request, when the API reports them (0 otherwise)."""
    um = getattr(response, "usage_metadata", None)
    for name in ("prompt_token_count", "total_token_count"):
        value = getattr(um, name, None) if um is not None else None
        if value:
            return int(value)
    total = 0
    for e in response.embeddings or []:
        stats = getattr(e, "statistics", None)
        total += int(getattr(stats, "token_count", 0) or 0) if stats else 0
    return total
