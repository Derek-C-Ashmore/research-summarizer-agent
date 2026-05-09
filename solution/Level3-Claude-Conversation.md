# Interaction log with Claude to create level 3 tests

> Initial Prompt
```
I want to write Level 3 tests for this agent as defined in the `Level3` section of the testing pyramid described in file `requirements/Testing-Pyramid.md`. Place the driver for level 3 tests in file `tests/test_level3.py` so that I can independently decide when those tests run. Tests in tests in files `tests/test_level1.py` and `tests/test_level2.py` are green and need to remain so. Please interview me for any additional information you need. Ask your questions one at a time. Don't write the tests yet until we agree on the plan.
```

> Response
```
1. Rubric eval only (4 dims)
     Reuse the existing rubric (factual_accuracy, citation_integrity, synopsis_quality, findings_count) from
     evals/judge_eval.py across multiple topics. Simplest, mirrors what's already there.
  2. Rubric + transaction replay
     Add a second test that replays a previously recorded run (e.g. sample_outputs/judge_eval_run.json) and asks the
     judge whether differences from the recorded baseline are material/improvement/degradation.
  3. Rubric + hallucination probe
     Add an adversarial topic (e.g. nonsense or sparse-results) and assert the judge confirms the agent didn't fabricate
      citations or facts.
  4. All of the above
     Rubric across topics + transaction replay + hallucination probe. Most thorough but more code and more API spend.
  5. Type something.
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  6. Chat about this
```

> Answer
```
  1
```

  Chosen to keep cost down for attendees.

> Response
```
Which topics should the Level 3 test run the rubric against?

❯ 1. Just the existing topic (penicillin)
     Reuse 'the discovery of penicillin' from judge_eval.py. One parametrized case. Cheapest (~2 API calls per run).
  2. 3 curated topics
     E.g. penicillin, photosynthesis, quantum computing — diverse, well-covered topics with stable sources. ~6 API calls
      per run.
  3. Topics from sample_outputs/*.json
     Drive the test from the hand-curated SummaryResult fixtures in sample_outputs/ so topic list lives next to the
     fixtures. Adds discovery code.
  4. Type something.
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  5. Chat about this
```

> Answer
```
  1
```

  Chosen to keep cost down for attendees.

  > Response
```
  Should the Level 3 test use live Tavily search, or stubbed search results?

❯ 1. Stubbed (recommended)
     Use a fixed StubSearchTool payload (or replay sample_outputs/judge_eval_run.json's search_results). Test only
     varies on agent+judge models, not web flux. More deterministic; only ANTHROPIC_API_KEY needed.
  2. Live Tavily
     Mirror evals/judge_eval.py exactly — hit Tavily, then feed the same results into the agent and judge. Requires both
      API keys; results drift as the web changes.
  3. Type something.
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  4. Chat about this
```

> Answer
```
  1
```

> Response
```
  Pass criteria for the test — how strict?

❯ 1. All 4 dimensions must pass
     Strict. Any 'fail' verdict from the judge fails the test. Highest signal but more flake risk if the model wobbles.
  2. At least 3 of 4 must pass
     Lenient threshold tolerates one judge 'fail' to reduce flakiness. Less strict, but can mask regressions.
  3. All 4 must pass, parametrized over N runs
     Run e.g. 2-3 times like Level 2 does; each run must pass all 4 dimensions. Higher cost, gives reliability signal.
  4. Type something.
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  5. Chat about this
```

> Answer
```
  1
```

> Response
```
Where should the rubric/judge logic live so test_level3.py can import it?

❯ 1. Refactor judge_eval.py to expose helpers
     Extract _build_judge_prompt, _parse_judge_verdicts, JUDGE_SYSTEM_PROMPT, JUDGE_RUBRIC_INSTRUCTIONS, JUDGE_MODEL
     into importable names. test_level3.py imports them. judge_eval.py's main() still works. DRY.
  2. Duplicate inline in test_level3.py
     Copy the prompt + parsing logic into the test file. Keeps judge_eval.py untouched but duplicates ~30 lines.
  3. Move shared bits to a new evals/judge.py module
     Create evals/judge.py with the shared rubric+judge helpers; both judge_eval.py and test_level3.py import from it.
  4. Type something.
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  5. Chat about this
```
> Answer
```
  3
```

> Response
```
Skip behavior — when should test_level3.py auto-skip vs run?

❯ 1. Skip unless ANTHROPIC_API_KEY set + opt-in env var
     Skip by default like an integration suite. Require e.g. RUN_LEVEL3=1 (or similar) to run, since it costs both API
     calls and judge calls. Cleanly separated from Level 1/2 default runs.
  2. Skip only when ANTHROPIC_API_KEY is missing
     Same gate as Level 2 — runs whenever the key is set. Simpler, but means anyone running 'pytest tests/' with a key
     burns extra credit on the judge model.
  3. Custom pytest marker (e.g. @pytest.mark.level3) + key check
     Mark tests so they only run with `pytest -m level3` (or equivalent). Skip when key missing. Gives you a clean
     independent toggle without env vars.
  4. Type something.
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  5. Chat about this
```

> Answer
```
  3
```

> Response
```
  Got everything I need. Let me check the project config so the marker setup proposal is grounded.

  Listed 1 directory (ctrl+o to expand)

● No pytest.ini / pyproject.toml. Here's the proposed plan:

  Plan

  1. New module evals/judge.py — shared judge logic, importable from both the CLI and tests:
  - Constants: JUDGE_MODEL = "claude-sonnet-4-6", JUDGE_SYSTEM_PROMPT, JUDGE_RUBRIC_INSTRUCTIONS
  - Helpers: build_judge_prompt(topic, search_results, agent_result), extract_text(response), parse_judge_verdicts(raw),
   and a small run_judge(topic, search_results, agent_result) -> (verdicts, comments, raw) that wraps the Anthropic
  call.

  2. Refactor evals/judge_eval.py — replace the inlined constants/helpers with imports from evals/judge.py. CLI
  behavior, stdout report, and sample_outputs/judge_eval_run.json trace shape stay identical. (Both Level 1/2 tests are
  unaffected — they don't import evals/.)

  3. New tests/test_level3.py — one test, stubbed search, real Anthropic + judge:
  - Module-level pytestmark = [pytest.mark.level3, pytest.mark.skipif(no ANTHROPIC_API_KEY)]
  - Topic: "the discovery of penicillin" (matches judge_eval.py)
  - Search results: reuse the recorded search_results from sample_outputs/judge_eval_run.json loaded into a
  StubSearchTool. This pins the inputs the judge already has seen behave well.
  - monkeypatch.setenv("SUMMARIZER_TEMPERATURE", "0") (same pattern as Level 2)
  - Call summarize(), then run_judge(...), then assert each of the four dimensions is "pass" with a per-dimension
  assertion message that includes the judge's comments for diagnostics.

   4. New pytest.ini at repo root to:
  - Register the level3 marker (avoids PytestUnknownMarkWarning)
  - Set addopts = -m "not level3" so the default pytest and existing Level 1/2 commands skip it. To run Level 3: pytest
  -m level3 or pytest tests/test_level3.py -m level3.

  Cost per run: 2 Anthropic calls (1 agent Haiku + 1 judge Sonnet). No Tavily. No web variability.

  What stays unchanged: agent/, Level 1/2 tests, judge_eval.py external behavior, sample outputs, conftest.py.

  Does this plan look right? Any tweaks before I implement?
```

> Answer
```
Yes, please implement
```

> Epilog

  Exited Claude and executed these commands to make sure that all tests are green: 
  - `python -m pytest tests/test_level1.py -v`
  - `python -m pytest tests/test_level2.py -v`
  - `pytest -m level3 -v`
