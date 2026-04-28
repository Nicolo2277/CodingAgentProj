from src.agent.state import AgentState


# src/llm/prompts/react.py

SYSTEM = """You are an autonomous code review agent.
You have access to tools to explore and analyze a Python repository.
At each step you reason about what to do next and call exactly one tool.
You always respond with valid JSON and nothing else.

Available tools:
- "list_files": List all Python files in the repository.
- "analyze_file": Analyze a specific Python file for bugs.
- "finish": End the analysis and write a final summary.

IMPORTANT: The JSON fields must be exactly:
- "action": must be exactly one of these three values: "list_files", "analyze_file", "finish"
- "action_input": the file path string if action is "analyze_file", empty string "" otherwise

WRONG format examples (never do this):
  "action": "analyze_file(main.py)"
  "action": "analyze_file: main.py"

CORRECT format examples:
  "action": "analyze_file", "action_input": "main.py"
  "action": "list_files", "action_input": ""
  "action": "finish", "action_input": "summary here"
"""

USER_TEMPLATE = """Repository: {repo_path}
Step: {current_step}/{max_steps}

Available files (already fetched):
{available_files}

Files analyzed so far: {files_analyzed}
Bugs found so far: {total_bugs}

Rules:
- Do NOT call list_files again, you already have the file list above.
- Analyze files not yet in "files analyzed" list.
- Call finish when all files are analyzed.

Action history:
{action_history}

What do you do next? Respond ONLY with valid JSON:
{{
  "thought": "I should...",
  "action": "list_files|analyze_file|finish",
  "action_input": "...",
  "reasoning": "Because..."
}}"""


def build(state: AgentState) -> tuple[str, str]:
    available = state.get("available_files", [])
    available_str = "\n".join(available) if available else "not fetched yet — call list_files first"
    history = _format_history(state.get("action_history", []))
    user = USER_TEMPLATE.format(
        repo_path=state["repo_path"],
        current_step=state.get("current_step", 1),
        max_steps=state.get("max_steps", 20),
        available_files=available_str,
        files_analyzed=state.get("files_analyzed", []) or "none yet",
        total_bugs=state.get("total_bugs", 0),
        action_history=history or "none yet",
    )
    return SYSTEM, user


def _format_history(history: list) -> str:
    if not history:
        return ""
    lines = []
    for i, record in enumerate(history, 1):
        lines.append(
            f"[{i}] thought: {record['thought']}\n"
            f"    action: {record['action']}({record['action_input']})\n"
            f"    result: {record['result']}"
        )
    return "\n".join(lines)