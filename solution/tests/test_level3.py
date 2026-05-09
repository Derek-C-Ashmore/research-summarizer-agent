"""Level 3 tests: LLM-as-judge evals against the rubric in evals/judge.py.

These tests run the real agent (Anthropic Haiku) against a pinned, stubbed
search payload and then ask a more capable judge model
(``claude-sonnet-4-6``) to grade the output on four pass/fail dimensions.
The search side is stubbed so the only sources of variance are the agent
and judge models themselves; temperature is pinned to 0.

The whole module is gated behind the ``level3`` pytest marker AND requires
``ANTHROPIC_API_KEY`` to be set. ``pytest.ini`` deselects ``level3`` by
default so Level 1/2 runs are unaffected. To run Level 3 explicitly::

    pytest -m level3
    pytest tests/test_level3.py -m level3
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent.agent import summarize
from agent.tools import SearchResult, StubSearchTool
from evals.judge import RUBRIC_DIMENSIONS, run_judge


pytestmark = [
    pytest.mark.level3,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set; Level 3 requires a live Anthropic key",
    ),
]


_REPO_ROOT = Path(__file__).resolve().parent.parent
_RECORDED_TRACE = _REPO_ROOT / "sample_outputs" / "judge_eval_run.json"

_TOPIC = "the discovery of penicillin"


def _load_recorded_search_results() -> list[SearchResult]:
    """Replay the search_results from the committed judge_eval trace.

    Pinning these inputs removes web variability so the test only measures
    agent + judge behaviour.
    """
    trace = json.loads(_RECORDED_TRACE.read_text(encoding="utf-8"))
    return [SearchResult(**r) for r in trace["search_results"]]


@pytest.fixture(autouse=True)
def _pin_temperature_to_zero(monkeypatch):
    """Match Level 2: pin temperature=0 for minimum agent variance."""
    monkeypatch.setenv("SUMMARIZER_TEMPERATURE", "0")


def test_level3_judge_rubric_all_pass():
    """Run the agent against the pinned penicillin payload and assert that
    the judge returns ``pass`` on every rubric dimension."""
    search_results = _load_recorded_search_results()

    agent_result = summarize(
        _TOPIC, search_tool=StubSearchTool(results=list(search_results))
    )
    agent_payload = agent_result.model_dump()
    search_payload = [r.model_dump() for r in search_results]

    verdicts, comments, _raw = run_judge(_TOPIC, search_payload, agent_payload)

    missing = [d for d in RUBRIC_DIMENSIONS if d not in verdicts]
    assert not missing, (
        f"Judge response missing dimensions {missing}; got verdicts={verdicts!r} "
        f"comments={comments!r}"
    )

    failures = {d: verdicts[d] for d in RUBRIC_DIMENSIONS if verdicts[d] != "pass"}
    assert not failures, (
        f"Judge returned non-pass verdicts: {failures}. "
        f"Comments: {comments}. Agent output: {agent_payload!r}"
    )
