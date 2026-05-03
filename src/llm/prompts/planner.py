from src.llm.prompts.base import BasePrompt


class PlannerPrompt(BasePrompt):
    SYSTEM = """You are a strategic Python code-review planner.
Given a list of files, you create a prioritized analysis plan.
You always respond with valid JSON and nothing else.

Priority rules — apply in order:
  high   → entry points (main.py), core domain logic, files with many dependants
  medium → utilities, helpers, standalone modules
  low    → configuration, __init__.py stubs, test files

If you are unsure, default to "medium"."""

    USER_TEMPLATE = """Repository: {repo_path}

Files to plan (name · size in bytes):
{file_list}

Return ONLY valid JSON — no text outside the structure:
{{
  "reasoning": "Brief explanation of your prioritization strategy",
  "steps": [
    {{
      "file": "relative/path/to/file.py",
      "reason": "One-sentence rationale for this file's priority",
      "priority": "high|medium|low"
    }}
  ]
}}

Rules:
- Every file must appear exactly once in "steps".
- Order steps from most important to least important.
- "file" must match exactly one entry from the input list."""