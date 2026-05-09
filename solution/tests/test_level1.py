"""Level 1 tests: deterministic unit tests with stubbed LLM and search tool.

These tests exercise orchestration, error handling, and DI seams without
making real API calls. The Anthropic client is monkeypatched at the
``anthropic.Anthropic`` symbol used inside ``agent.agent``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent import agent as agent_module
from agent.agent import summarize
from agent.models import SummaryResult
from agent.tools import NoResultsError, SearchResult, SearchToolError, StubSearchTool


# ---------- helpers ----------------------------------------------------------


_VALID_TOOL_INPUT = {
    "topic": "photosynthesis",
    "synopsis": "Photosynthesis converts light into chemical energy.",
    "key_findings": ["Plants use chlorophyll.", "Oxygen is a byproduct."],
    "citations": [
        {
            "title": "Photosynthesis",
            "url": "https://example.com/photo",
            "snippet": "An overview.",
        }
    ],
}


def _tool_use_response(tool_input: dict | None = None, name: str = "return_summary"):
    """Build a fake Anthropic response containing one tool_use block."""
    block = SimpleNamespace(
        type="tool_use",
        name=name,
        input=tool_input if tool_input is not None else _VALID_TOOL_INPUT,
    )
    return SimpleNamespace(content=[block])


def _no_tool_use_response():
    """Fake Anthropic response with only a text block (no tool_use)."""
    block = SimpleNamespace(type="text", text="hello")
    return SimpleNamespace(content=[block])


class _FakeAnthropic:
    """Stand-in for ``anthropic.Anthropic`` that records the create() call."""

    def __init__(self, response, recorder: dict | None = None) -> None:
        self._response = response
        self._recorder = recorder if recorder is not None else {}
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self._recorder.update(kwargs)
        return self._response


@pytest.fixture
def patch_anthropic(monkeypatch):
    """Return a function that installs a fake Anthropic client.

    Usage: ``recorder = patch_anthropic(response)`` — the returned dict
    captures the kwargs passed to ``messages.create``.
    """

    def _install(response):
        recorder: dict = {}
        monkeypatch.setattr(
            agent_module.anthropic,
            "Anthropic",
            lambda *a, **kw: _FakeAnthropic(response, recorder),
        )
        return recorder

    return _install


def _stub_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Photosynthesis",
            url="https://example.com/photo",
            snippet="An overview.",
        )
    ]


# ---------- tests ------------------------------------------------------------


@pytest.mark.parametrize("topic", ["", "   ", "\t\n"])
def test_empty_topic_raises_value_error_without_calling_apis(topic, monkeypatch):
    """Test 1: empty/whitespace topic must raise before any API call."""

    def _explode(*_a, **_kw):  # pragma: no cover - must not be called
        raise AssertionError("Anthropic client should not be constructed")

    monkeypatch.setattr(agent_module.anthropic, "Anthropic", _explode)

    class _ExplodingSearch:
        def search(self, *_a, **_kw):  # pragma: no cover - must not be called
            raise AssertionError("Search tool should not be invoked")

    with pytest.raises(ValueError):
        summarize(topic, search_tool=_ExplodingSearch())


def test_empty_search_results_raise_no_results_error(patch_anthropic):
    """Test 2: when search returns [], the agent must raise NoResultsError.

    Exposes the ``# TODO: handle empty results`` gap in agent.py.
    """
    # Anthropic should never be called; if it is, fail loudly.
    patch_anthropic(_tool_use_response())

    with pytest.raises(NoResultsError):
        summarize("photosynthesis", search_tool=StubSearchTool(results=[]))


def test_search_tool_error_propagates(patch_anthropic):
    """Test 3: SearchToolError from the tool propagates unchanged."""
    patch_anthropic(_tool_use_response())

    class _FailingSearch:
        def search(self, query, max_results=5):
            raise SearchToolError("boom")

    with pytest.raises(SearchToolError, match="boom"):
        summarize("photosynthesis", search_tool=_FailingSearch())


def test_happy_path_returns_summary_result(patch_anthropic):
    """Test 4: stubbed search + stubbed tool_use returns a valid SummaryResult."""
    patch_anthropic(_tool_use_response())

    result = summarize(
        "photosynthesis", search_tool=StubSearchTool(results=_stub_results())
    )

    assert isinstance(result, SummaryResult)
    assert result.topic == "photosynthesis"
    assert result.synopsis.startswith("Photosynthesis")
    assert len(result.key_findings) == 2
    assert result.citations[0].url == "https://example.com/photo"


def test_response_without_tool_use_raises_runtime_error(patch_anthropic):
    """Test 5: Anthropic response missing a tool_use block → RuntimeError."""
    patch_anthropic(_no_tool_use_response())

    with pytest.raises(RuntimeError, match="return_summary"):
        summarize(
            "photosynthesis", search_tool=StubSearchTool(results=_stub_results())
        )


def test_agent_requests_five_search_results(patch_anthropic):
    """Test 6: orchestration check — agent calls search with max_results=5."""
    patch_anthropic(_tool_use_response())

    captured: dict = {}

    class _RecordingSearch:
        def search(self, query, max_results=5):
            captured["query"] = query
            captured["max_results"] = max_results
            return _stub_results()

    summarize("photosynthesis", search_tool=_RecordingSearch())

    assert captured["query"] == "photosynthesis"
    assert captured["max_results"] == 5


def test_injected_search_tool_used_instead_of_default(patch_anthropic, monkeypatch):
    """Test 7: DI seam — injected search_tool wins over the default factory."""
    # Make the default factory explode if it is ever called.
    def _explode():  # pragma: no cover - must not be called
        raise AssertionError("_default_search_tool should not be invoked")

    monkeypatch.setattr(agent_module, "_default_search_tool", _explode)
    patch_anthropic(_tool_use_response())

    called = {"n": 0}

    class _CountingSearch:
        def search(self, query, max_results=5):
            called["n"] += 1
            return _stub_results()

    result = summarize("photosynthesis", search_tool=_CountingSearch())

    assert called["n"] == 1
    assert isinstance(result, SummaryResult)
