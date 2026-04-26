from src.llm.prompts.base import BasePrompt


class FindBugsPrompt(BasePrompt):
    SYSTEM = """You are an expert Python code reviewer.
You analyze code and identify bugs with surgical precision.
You never add explanations outside the JSON structure.
Focus ONLY on edge cases and runtime errors.
Consider empty lists, None values, invalid inputs."""

    USER_TEMPLATE = """Analyze the following Python code and find all bugs.
Return ONLY valid JSON, no text outside the JSON.

Code:
{code}

Expected JSON format:
{{
  "bugs": [
    {{
      "line": <int>,
      "description": "<str>",
      "severity": "low|medium|high",
      "fix": "<str>"
    }}
  ],
  "summary": "<str>"
}}"""