"""Level 4 tests: human-evaluation artifact generator.

Level 4 of the testing pyramid is human evaluation -- subjective quality,
red-teaming, and expert review. A pytest cannot render that judgment, so
this module instead generates a review artifact for an out-of-band human
reviewer. The pytest itself only verifies that the agent ran end-to-end
on each curated topic and that both artifact files were written.

The run uses live Tavily search plus the real Anthropic agent, and embeds
the search results that were fed to the agent alongside the agent's
output so the reviewer can attribute weak outputs to weak sources vs.
agent failure.

Each run lands in its own UTC-timestamped directory under
``sample_outputs/level4/`` so reviews accumulate over time:

    sample_outputs/level4/<UTC-timestamp>/run.json
    sample_outputs/level4/<UTC-timestamp>/review.md

The whole module is gated behind the ``level4`` pytest marker AND requires
both ``ANTHROPIC_API_KEY`` and ``TAVILY_API_KEY``. ``pytest.ini`` deselects
``level4`` by default. To run explicitly::

    pytest -m level4
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent.agent import summarize
from agent.tools import SearchResult, SearchTool, TavilySearchTool


pytestmark = [
    pytest.mark.level4,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set; Level 4 requires a live Anthropic key",
    ),
    pytest.mark.skipif(
        not os.environ.get("TAVILY_API_KEY"),
        reason="TAVILY_API_KEY not set; Level 4 uses live Tavily search",
    ),
]


_REPO_ROOT = Path(__file__).resolve().parent.parent
_LEVEL4_DIR = _REPO_ROOT / "sample_outputs" / "level4"


_TOPICS = [
    {"topic": "photosynthesis", "baseline": "sample_outputs/photosynthesis.json"},
    {"topic": "quantum computing", "baseline": "sample_outputs/quantum_computing.json"},
    {"topic": "the discovery of penicillin", "baseline": "sample_outputs/judge_eval_run.json"},
]


_RUBRIC_DIMENSIONS = (
    "factual_accuracy",
    "citation_integrity",
    "synopsis_quality",
    "findings_count",
)


class _CapturingSearchTool:
    """Wraps a ``SearchTool`` and records the results returned for each query.

    The Level 4 artifact embeds the search results that were actually fed to
    the agent so the human reviewer can judge whether weak outputs reflect
    weak sources rather than agent failure.
    """

    def __init__(self, inner: SearchTool) -> None:
        self._inner = inner
        self.last_results: list[SearchResult] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        results = self._inner.search(query, max_results=max_results)
        self.last_results = list(results)
        return results


@pytest.fixture(autouse=True)
def _pin_temperature_to_zero(monkeypatch):
    """Match Level 2/3: pin temperature=0 for minimum agent variance."""
    monkeypatch.setenv("SUMMARIZER_TEMPERATURE", "0")


def _utc_timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _blank_review() -> dict:
    return {
        "reviewer": "",
        "verdict": "",
        "rubric": {dim: "" for dim in _RUBRIC_DIMENSIONS},
        "notes": "",
    }


def _render_markdown(run_record: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Level 4 Human Review — {run_record['run_timestamp']}")
    lines.append("")
    lines.append(f"- Model: `{run_record['model']}`")
    lines.append(f"- Temperature: `{run_record['temperature']}`")
    lines.append("")
    lines.append(
        "Fill in the `review` block in `run.json` for each topic. "
        "This markdown is a side-by-side reading aid only."
    )
    lines.append("")

    for entry in run_record["topics"]:
        topic = entry["topic"]
        agent_output = entry["agent_output"]
        baseline_path = entry["baseline_path"]
        baseline = entry.get("baseline")

        lines.append(f"## Topic: {topic}")
        lines.append("")
        lines.append(f"Baseline reference: `{baseline_path}`")
        lines.append("")

        lines.append("### New synopsis")
        lines.append("")
        lines.append(agent_output.get("synopsis", "").strip() or "_(empty)_")
        lines.append("")

        if baseline is not None:
            lines.append("### Baseline synopsis")
            lines.append("")
            lines.append(baseline.get("synopsis", "").strip() or "_(empty)_")
            lines.append("")

        lines.append("### New key findings")
        lines.append("")
        for finding in agent_output.get("key_findings", []):
            lines.append(f"- {finding}")
        lines.append("")

        if baseline is not None:
            lines.append("### Baseline key findings")
            lines.append("")
            for finding in baseline.get("key_findings", []):
                lines.append(f"- {finding}")
            lines.append("")

        lines.append("### New citations")
        lines.append("")
        for cite in agent_output.get("citations", []):
            lines.append(f"- [{cite.get('title', '')}]({cite.get('url', '')})")
        lines.append("")

        lines.append("### Search results fed to the agent")
        lines.append("")
        for src in entry.get("search_results", []):
            lines.append(f"- [{src.get('title', '')}]({src.get('url', '')})")
        lines.append("")

        lines.append("### Rubric (fill in `run.json`)")
        lines.append("")
        for dim in _RUBRIC_DIMENSIONS:
            lines.append(f"- [ ] {dim}")
        lines.append("- [ ] overall verdict")
        lines.append("")

    return "\n".join(lines) + "\n"


def _load_baseline(baseline_path: Path) -> dict | None:
    if not baseline_path.exists():
        return None
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    if "agent_output" in data and "search_results" in data:
        return data["agent_output"]
    return data


def test_level4_generate_review_artifact():
    """Run the agent against each curated topic with live Tavily search and
    write a timestamped human-review artifact.

    The pytest passes if every topic produced a structurally valid
    ``SummaryResult`` and both artifact files were written. Human verdicts
    are recorded into the artifact out-of-band; this test never reads them.
    """
    inner_tool = TavilySearchTool()

    run_dir = _LEVEL4_DIR / _utc_timestamp_slug()
    run_dir.mkdir(parents=True, exist_ok=True)

    run_record: dict = {
        "run_timestamp": run_dir.name,
        "model": os.environ.get("SUMMARIZER_MODEL", "claude-haiku-4-5-20251001"),
        "temperature": os.environ.get("SUMMARIZER_TEMPERATURE", "0"),
        "topics": [],
    }

    for entry in _TOPICS:
        topic = entry["topic"]
        baseline_rel = entry["baseline"]
        capturing = _CapturingSearchTool(inner_tool)

        agent_result = summarize(topic, search_tool=capturing)

        baseline = _load_baseline(_REPO_ROOT / baseline_rel)

        run_record["topics"].append(
            {
                "topic": topic,
                "baseline_path": baseline_rel,
                "baseline": baseline,
                "search_results": [r.model_dump() for r in capturing.last_results],
                "agent_output": agent_result.model_dump(),
                "review": _blank_review(),
            }
        )

    run_json_path = run_dir / "run.json"
    review_md_path = run_dir / "review.md"

    run_json_path.write_text(
        json.dumps(run_record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    review_md_path.write_text(_render_markdown(run_record), encoding="utf-8")

    assert run_json_path.exists(), f"run.json was not written to {run_json_path}"
    assert review_md_path.exists(), f"review.md was not written to {review_md_path}"
    assert len(run_record["topics"]) == len(_TOPICS)
