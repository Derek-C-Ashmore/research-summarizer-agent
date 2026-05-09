"""Level 2 tests: constrained model tests against a real Anthropic API.

These tests exercise prompt effectiveness and structured-output compliance.
The search side is stubbed with a curated payload so assertions target only
the model/prompt — not live web variability. Temperature is pinned to 0 via
the ``SUMMARIZER_TEMPERATURE`` env override.

The whole module skips when ``ANTHROPIC_API_KEY`` is not set, so attendees
can run Level 1 freely without burning Anthropic credits.
"""

from __future__ import annotations

import os
import re

import pytest

from agent.agent import summarize
from agent.models import SummaryResult
from agent.tools import SearchResult, StubSearchTool


pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set; Level 2 requires a live Anthropic key",
)


_TOPIC = "photosynthesis"

_STUB_RESULTS: list[SearchResult] = [
    SearchResult(
        title="Photosynthesis - Wikipedia",
        url="https://en.wikipedia.org/wiki/Photosynthesis",
        snippet=(
            "Photosynthesis is the biological process by which plants, algae, "
            "and some bacteria use light energy to convert carbon dioxide and "
            "water into glucose and oxygen. The pigment chlorophyll absorbs "
            "light primarily in the blue and red portions of the spectrum."
        ),
    ),
    SearchResult(
        title="Photosynthesis | Definition, Equation, Steps | Britannica",
        url="https://www.britannica.com/science/photosynthesis",
        snippet=(
            "Photosynthesis takes place in the chloroplasts of plant cells. "
            "The light-dependent reactions split water molecules, releasing "
            "oxygen as a byproduct, while the Calvin cycle fixes carbon "
            "dioxide into sugars."
        ),
    ),
    SearchResult(
        title="What Is Photosynthesis? - NASA Climate Kids",
        url="https://climatekids.nasa.gov/photosynthesis/",
        snippet=(
            "Through photosynthesis, plants take in sunlight, water, and "
            "carbon dioxide and produce energy-rich sugars along with the "
            "oxygen that animals breathe."
        ),
    ),
]

_STUB_URLS = {r.url for r in _STUB_RESULTS}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@pytest.fixture(autouse=True)
def _pin_temperature_to_zero(monkeypatch):
    """Level 2 calls the real model at temperature=0 for minimum variance."""
    monkeypatch.setenv("SUMMARIZER_TEMPERATURE", "0")


def _count_sentences(text: str) -> int:
    pieces = [p for p in _SENTENCE_SPLIT_RE.split(text.strip()) if p.strip()]
    return len(pieces)


@pytest.mark.parametrize("run_index", [0, 1, 2])
def test_level2_summarize_photosynthesis(run_index):
    """Run the agent against the canonical fixture and assert all four
    Level 2 dimensions: structured-output compliance, synopsis bounds,
    citation provenance, and topic fidelity. Three independent runs give a
    crude reliability signal at moderate cost.
    """
    result = summarize(_TOPIC, search_tool=StubSearchTool(results=list(_STUB_RESULTS)))

    # 1. Structured output compliance — summarize() returns a validated model.
    assert isinstance(result, SummaryResult), (
        f"run {run_index}: expected SummaryResult, got {type(result).__name__}"
    )

    # 2. Synopsis bounds — the prompt mandates 2-4 sentences.
    sentence_count = _count_sentences(result.synopsis)
    assert 2 <= sentence_count <= 4, (
        f"run {run_index}: synopsis has {sentence_count} sentences, expected 2-4. "
        f"Synopsis: {result.synopsis!r}"
    )

    # 3. Citation provenance — every cited URL was in the stubbed payload.
    assert result.citations, f"run {run_index}: no citations returned"
    for citation in result.citations:
        assert citation.url in _STUB_URLS, (
            f"run {run_index}: citation URL {citation.url!r} was not in the "
            f"provided search results {_STUB_URLS}"
        )

    # 4. Topic fidelity — the returned topic matches the input.
    assert result.topic.strip().lower() == _TOPIC, (
        f"run {run_index}: expected topic {_TOPIC!r}, got {result.topic!r}"
    )
