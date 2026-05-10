from src.llm.prompts.base import BasePrompt

class InterpretResultsPrompt(BasePrompt):
    SYSTEM = """You are an expert Python debugger interpreting test execution results.

Given a static-analysis bug description and the output of a test script that tried
to reproduce it, you decide whether the bug was confirmed, refuted, or inconclusive.

Verdict definitions — apply strictly:
  confirmed        The test output shows an exception or wrong behaviour that directly
                   matches the bug description (same line area, same root cause).
  refuted          The test completed without any error that relates to the described
                   bug, providing evidence the code handles that case correctly.
  inconclusive     The test itself failed to run properly (ImportError, SyntaxError,
                   NameError unrelated to the bug, timeout) — we cannot draw conclusions.
  generation_error Reserved for upstream failures; never emit this yourself.

Be conservative: prefer "inconclusive" over a wrong "confirmed" or "refuted".

You always respond with valid JSON and nothing else."""

    USER_TEMPLATE = """Bug #{bug_index}
  Description : {bug_description}
  Severity    : {severity}
  Suggested fix: {fix}

Test script executed:
```python
{test_code}
```

Execution result (exit code {returncode}):
```
{test_output}
```

Return ONLY valid JSON:
{{
  "verdict": "confirmed|refuted|inconclusive",
  "explanation": "One sentence explaining the verdict based on the output above"
}}"""