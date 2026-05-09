# Interaction log with Claude to create level 2 tests

> Initial Prompt
```
I want to write Level 2 tests for this agent as defined in the `Level2` section of the testing pyramid described in file `requirements/testing-Pyramid.md`. Place the driver for level 2 tests in file `tests/test_level2.py` so that I can independently decide when those tests run. Tests in tests in file `tests/test_level1.py` are green and need to remain so. Please interview me for any additional information you need. Ask your questions one at a time. Don't write the tests yet until we agree on the plan. 
```

> Response
```
Question 1: Search tool boundary for Level 2

  Level 2 is about testing the model/prompt under controlled conditions. The CLAUDE.md hint suggests Level 2 uses "real
  Anthropic + Tavily." But mixing in live Tavily adds web-flux noise that has nothing to do with prompt effectiveness,
  and makes assertions harder to write against "clear correct answers."

  Which approach do you want?

  1. Real Anthropic + stubbed search results — feed the model a curated, fixed StubSearchTool payload so we test only
  the prompt/model behavior. Most aligned with Level 2's intent.
  2. Real Anthropic + real Tavily — full end-to-end live call. More realistic, but assertions must tolerate live-web
  variability.
  3. Both — some tests use stubbed search (deterministic prompt assertions), some use live Tavily (smoke/integration
  coverage).
```

> Answer
```
Real Anthropic + stubbed search results
```

> Response
```
Question 2: Temperature override

  The pyramid spec calls for temperature=0 at Level 2, but the agent defaults to 1.0 (and reads SUMMARIZER_TEMPERATURE
  at call time). How do you want the tests to handle this?

  1. Set SUMMARIZER_TEMPERATURE=0 via monkeypatch in each test (or a fixture) — pins temperature to 0 for Level 2 only,
  leaves the agent's production default untouched.
  2. Leave temperature at the agent default (1.0) — tests reflect real production behavior; assertions must tolerate
  more variance.
  3. Change the agent's default to 0 — simplest, but alters production behavior outside the test scope.
```

>Answer
```
1
```

> Response
```
Question 3: What dimensions to cover

  Level 2 lists several testable dimensions. Given the agent's narrow surface (one pipeline, one tool-use schema), which
   of these do you want covered? (multi-select)

  1. Structured output compliance — model returns a valid SummaryResult via the forced return_summary tool (schema
  honored, required fields present).
  2. Prompt effectiveness — synopsis bounds — synopsis is 1–3 sentences (spec rule enforced only by prompt).
  3. Prompt effectiveness — findings bounds — key_findings count falls within whatever the prompt specifies (need to
  check prompts.py).
  4. Citation provenance — citations come only from the URLs we fed via the stubbed search results (no fabricated URLs).
  5. Topic fidelity — result.topic matches the input topic.
  6. On-topic synopsis — synopsis text actually relates to the topic / mentions key terms from the stubbed snippets.
  7. Tool selection — model uses return_summary rather than emitting plain text (already enforced by tool_choice, so
  arguably redundant).

  Which of these (one or several) should the Level 2 suite cover?
```

  > Answer
  ```
  1,2,4,5
  ```

  > Response
  ```
  Question 4: Test topic and stubbed search payload

  Level 2 wants "carefully crafted test inputs that have clear correct answers." I propose one canonical fixture and
  reuse it across the four test cases:

  - Topic: "photosynthesis"
  - Stubbed search results: 3 hand-written SearchResult entries with stable URLs (e.g.
  https://en.wikipedia.org/wiki/Photosynthesis, https://www.nature.com/..., https://www.britannica.com/...) and snippets
   containing concrete facts (chlorophyll, light → chemical energy, oxygen byproduct).

  Citation-provenance assertions then check that every returned citation.url is in the set of stubbed URLs.

  Acceptable? Or would you prefer:

  1. Use the proposed photosynthesis fixture as described.
  2. Use a different topic (which one?).
  3. Multiple topics / parametrized — run all four assertions across 2–3 different topic fixtures for breadth.
```

> Answer
```
1
```

> Response
```
Level 2 hits the real Anthropic API (cost + latency). Two related decisions:

  1. Skip guard — should the suite pytest.skip when ANTHROPIC_API_KEY is missing (matching the Level 1 description in
  CLAUDE.md that says Level 2 "auto-skips if keys missing")? I'd recommend a module-level skip via
  pytest.importorskip-style check.
  2. Call budget — to keep cost low, I can either:
    - (a) One real API call, multiple assertions — run summarize() once in a session-scoped fixture, then assert
  structured-output compliance, synopsis bounds, citation provenance, and topic fidelity all against that single result.
   Cheapest, but one flaky run fails everything.
    - (b) One real API call per test — four separate summarize() calls, one per assertion dimension. Clearer failure
  isolation, ~4× the cost.
    - (c) A small N (e.g. 3 runs) with all four assertions applied to each — gives a crude reliability signal at
  moderate cost.

  Which do you prefer for skip + budget?
```

  > Answer
  ```
  2 c
  ```

  > Response
  ```
  I have enough to draft the plan. Here it is — please confirm or redirect.

  Level 2 test plan — tests/test_level2.py

  Boundary
  - Real Anthropic API call; StubSearchTool injected for the search side.
  - Module-level skip if ANTHROPIC_API_KEY is missing (or if anthropic import/auth fails).
  - monkeypatch.setenv("SUMMARIZER_TEMPERATURE", "0") via an autouse fixture so all Level 2 calls run at temp 0.

  Fixture — canonical input
  - Topic: "photosynthesis"
  - Stubbed SearchResult list (3 entries) with stable URLs (Wikipedia, Britannica, a NIH/Nature page) and snippets
  containing concrete facts (chlorophyll, light → chemical energy, O₂ byproduct).
  - The set of stubbed URLs is exposed as a fixture for citation-provenance assertions.

  Reliability strategy — 3 runs, all assertions per run (option c)
  - Single test function parametrized with run_index ∈ {0, 1, 2} so each run is an independent pytest case (clear
  failure isolation in the report).
  - Each run calls summarize("photosynthesis", search_tool=StubSearchTool(results=fixture)) once, then asserts all four
  dimensions on that result.

  
  Assertions per run
  1. Structured output compliance — summarize() returns a SummaryResult instance without raising. (Schema validity is
  enforced inside summarize() via SummaryResult.model_validate; reaching the return is the assertion.)
  2. Synopsis bounds — synopsis splits into 2–4 sentences (use a simple regex/split on .!? and count non-empty pieces).
  3. Citation provenance — every citation.url is in the set of stubbed URLs (no fabricated URLs).
  4. Topic fidelity — result.topic.strip().lower() == "photosynthesis".

  Out of scope (per your earlier answers)
  - On-topic synopsis content checks, findings-count bounds, and tool-selection assertions are not included.

  Cost — 3 real Haiku calls per Level 2 run, all at temperature 0.

  Shall I proceed to write this?
```

  > Answer
```
  Yes, proceed
```

> Epilog

  Exited Claude and executed these commands to make sure that all tests are green: 
  - `python -m pytest tests/test_level1.py -v`.
  - `python -m pytest tests/test_level2.py -v`.