# Interaction log with Claude to create level 4 tests

> Initial Prompt
```
I want to write Level 4 tests for this agent as defined in the `Level4` section of the testing pyramid described in file `requirements/Testing-Pyramid.md`. Place the driver for level 4 tests in file `tests/test_level4.py` so that I can independently decide when those tests run. Tests in tests in files `tests/test_level1.py`, `tests/test_level2.py`, and `tests/test_level3.py` are green and need to remain so. Please interview me for any additional information you need. Ask your questions one at a time. Don't write the tests yet until we agree on the plan.
```

> Response
```
Level 4 in the pyramid is human evaluation — preference testing, expert review, red-teaming. That's inherently a
  human-in-the-loop activity, so I need to understand how you want to encode it as a pytest driver.

  Question 1: Which Level 4 shape do you want tests/test_level4.py to take?

  - (A) Artifact generator: the test runs the agent against a curated set of inputs (including adversarial/red-team
  prompts) and writes outputs to a review file (e.g. sample_outputs/level4_review.json or markdown). The pytest itself
  passes if generation succeeds; a human later reads the file and renders judgment out-of-band.
  - (B) Recorded human verdicts: a checked-in file holds prior human pass/fail verdicts keyed by input. The test re-runs
   the agent and asserts the output still matches (or is judged equivalent to) the human-approved baseline — failing if
  it drifts.
  - (C) Interactive prompt: the test runs the agent and then prompts you (stdin/y-n) to approve each output, recording
  your verdicts. Pass = you typed "pass".
  - (D) A/B preference harness: runs two agent variants (e.g. current vs. a baseline output saved in sample_outputs/)
  and writes a side-by-side artifact for human preference judgment.

  Which one (or combination) matches your intent?
```

> Answer
```
A
```

Chosen for simplcity for the workshop. In a production application, I would usually choose B.

> Response
```
Question 2: What input set should the artifact generator run against?

  - (A) Red-team / adversarial only: prompts designed to stress safety, hallucination, and edge cases (e.g. empty-ish
  topic, extremely niche topic with sparse sources, a known-controversial topic, a topic that invites fabrication, a
  prompt-injection attempt embedded in the topic string).
  - (B) Subjective-quality sample: a handful of "normal" topics across domains (science, history, current-ish tech) so a
   human reviewer can judge genuine helpfulness and tone.
  - (C) Both — one curated list mixing ~3 normal topics and ~3 adversarial ones, each tagged with its category in the
  artifact.
  - (D) Reuse sample_outputs/ topics (penicillin, photosynthesis, quantum computing, etc.) so the human can compare new
  runs against the curated baselines.

  And: should the search side be live Tavily (real variability, matches production) or stubbed from pinned payloads
  (reproducible, matches Level 3's approach)?
```

> Answer
```
D
```

> Response
```
Question 3: What search source should the Level 4 run use?

  - (A) Live Tavily — matches real production behavior; the human reviewer sees what users would actually get.
  Variability is part of what's being reviewed.
  - (B) Pinned stub from judge_eval_run.json-style traces — fully reproducible; the human always reviews against a fixed
   search payload (only penicillin currently has a recorded trace, so we'd either need to record traces for the other
  two now, or restrict Level 4 to penicillin).
  - (C) Hybrid — live Tavily, but the artifact also embeds the search results that were fed in, so the reviewer can see
  whether weak outputs are caused by weak sources vs. agent failure.
```

> Answer
```
C
```

> Response
```
Question 4: What should the artifact contain and where should it land?

  Proposal — confirm or amend:

  - Path: sample_outputs/level4_review.json (single file, overwritten each run) plus a sibling
  sample_outputs/level4_review.md rendered for easy human reading. Or do you prefer timestamped runs (e.g.
  sample_outputs/level4/2026-05-09T….json) so reviews accumulate?
  - Per-topic record: topic, run timestamp, model + temperature used, the live search results fed to the agent, the full
   SummaryResult (synopsis, findings, citations), and a side-by-side reference to the curated baseline in
  sample_outputs/<topic>.json so the reviewer can compare new vs. baseline.
  - Reviewer fields left blank for human fill-in: reviewer, verdict (pass/fail), notes, per-dimension scores
  (helpfulness, accuracy, tone, hallucination, safety) — or do you want a different rubric?

  Two sub-questions to pick from:

  - (A) Single overwritten file (json + md), rubric = the four Level 3 dimensions plus a free-form notes field.
  - (B) Timestamped per-run directory, same rubric.
  - (C) Single overwritten file, but a different rubric you'll specify.
```

> Answer
```
(B) Timestamped per-run directory, same rubric.
```

> Response
```
Question 5: Pytest gating + pass criteria.

  - Gating: mirror Level 3 — register a level4 marker, deselect by default in pytest.ini, require ANTHROPIC_API_KEY and
  TAVILY_API_KEY (skip otherwise since we're using live Tavily). Run with pytest -m level4. OK?
  - Pass criteria for the pytest itself — pick one:
    - (i) Generation-only: test passes if it successfully ran the agent on all topics and wrote the artifact. Human
  verdicts are reviewed out-of-band; pytest never reads them back.
    - (ii) Generation + verdict gate: same as (i), but the test also scans prior timestamped runs in
  sample_outputs/level4/ and fails if the most recent fully-reviewed run had any fail verdict (catches "human said this
  regressed" the next time CI runs).
    - (iii) Generation + structural sanity: passes if generation succeeded AND the produced SummaryResult for each topic
   is structurally valid (parses as SummaryResult, non-empty fields, citation URLs all came from the search results that
   were fed in). No verdict reading.

  Which gating + which pass-criteria option?
```

> Answer
```
mirror Level 3 — register a level4 marker
```

>Response
```
Gating confirmed. I'll go with (i) generation-only as the reasonable default for an artifact-generator pattern with
  timestamped runs (verdicts live in the artifact for human review; pytest doesn't read them back). Here's the
  consolidated plan — confirm and I'll implement.

  Plan: tests/test_level4.py

  Purpose: Generate a human-review artifact for the three curated baseline topics, using live search + the real agent,
  with a blank rubric for offline expert review.

  Scope & inputs
  - Topics (reused from sample_outputs/): photosynthesis, quantum computing, the discovery of penicillin.
  - Search: live Tavily (TavilySearchTool), but each artifact record embeds the search results that were fed to the
  agent (hybrid per Q3) so the reviewer can attribute weak outputs to weak sources vs. agent failure.
  - Agent: real summarize(), temperature pinned to 0 via monkeypatch.setenv("SUMMARIZER_TEMPERATURE", "0") (matches
  Level 2/3 convention; surprise-only variance comes from the model).

  Gating
  - New level4 marker registered in pytest.ini, deselected by default (same pattern as level3).
  - Module-level pytestmark skips unless both ANTHROPIC_API_KEY and TAVILY_API_KEY are set.
  - Run with pytest -m level4.

  Artifact layout

  - Directory: sample_outputs/level4/<UTC-timestamp>/ (e.g. 2026-05-09T14-32-05Z/), created per run.
  - run.json — machine-readable record:
  {
    "model": "...",
    "temperature": "0",
    "topics": [
      {
        "topic": "...",
        "baseline_path": "sample_outputs/photosynthesis.json",
        "search_results": [...],          // what was fed to the agent
        "agent_output": {...},            // full SummaryResult
        "review": {
          "reviewer": "",
          "verdict": "",                  // "pass" | "fail"
          "rubric": {
            "factual_accuracy": "",
            "citation_integrity": "",
            "synopsis_quality": "",
            "findings_count": ""
          },
          "notes": ""
        }
      },
      ...
    ]
  }
  - review.md — human-friendly side-by-side rendering: per topic, the new synopsis/findings/citations next to the
  curated baseline from sample_outputs/<topic>.json, with a checklist for the four rubric dimensions and a notes block.

  Pytest body
  - A single test function test_level4_generate_review_artifact that loops the three topics, runs summarize() with a
  TavilySearchTool wrapped to capture the results that were returned (so the artifact can embed them), writes both
  files, and asserts only that:
    a. Each topic produced a structurally valid SummaryResult (parsed by Pydantic — failure here means the agent broke,
  which is worth surfacing even in a Level 4 run).
    b. Both artifact files were written.
  - No verdict reading; no comparison against the baseline beyond linking to it in the artifact.

  Files touched
  - New: tests/test_level4.py
  - Edit: pytest.ini — register level4 marker and add to default deselect list (same shape as level3).
  - New directory created at runtime: sample_outputs/level4/ (gitignored? — I'll leave that to you; by default I won't
  add a .gitignore entry, since you may want to commit reviewed runs as artifacts).

  Will not touch: tests/test_level1.py, tests/test_level2.py, tests/test_level3.py, agent/, solution/.

  Confirm and I'll implement, or amend any bullet.
```

> Answer
```
Confirmed
```

> Epilog

  Exited Claude and executed these commands to make sure that all tests are green: 
  - `python -m pytest tests/test_level1.py -v`
  - `python -m pytest tests/test_level2.py -v`
  - `pytest -m level3 -v`
  - `pytest -m level4 -v`
