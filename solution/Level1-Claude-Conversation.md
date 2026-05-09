# Interaction log with Claude to create level 1 tests

> Initial Prompt
```
I want to write Level 1 tests for this agent as defined in the `Level1` section of the testing pyramid described in file `requirements/testing-Pyramid.md`. Place the driver for level 1 tests in file `tests/test_level1.py` so that I can independently decide when those tests run. Please interview me for any additional information you need. Ask your questions one at a time. Don't write the tests yet until we agree on the plan. 
```

> Response

```
 Question 1 of N: Which scenarios do you want Level 1 to cover? Here's my proposed set — tell me to add, drop, or
  modify:

  1. Empty / whitespace-only topic → ValueError (no API calls made)
  2. Search tool returns [] → NoResultsError (will fail today; exposes the TODO)
  3. Search tool raises SearchToolError → propagates unchanged
  4. Happy path: stubbed search results + stubbed Anthropic tool_use response → returns a valid SummaryResult
  5. Anthropic returns a response with no tool_use block → RuntimeError
  6. Agent passes max_results=5 to the search tool (orchestration check)
  7. Injected search_tool is used instead of the default (DI seam check)

  Which of these do you want in, and is there anything missing (e.g., verifying the user message contains the topic, or
  that SUMMARIZER_MODEL env override is honored)?
  ```

  > Answer

```
  Implement all 7 tests
```

> Response

I was prompted if I wanted the TODO implemented in agent.py

> Answer
```
  fix the TODO in agent.py
```

  > Epilog

  Exited Claude and executed this command to make sure that all tests are green: `python -m pytest tests/test_level1.py -v`.