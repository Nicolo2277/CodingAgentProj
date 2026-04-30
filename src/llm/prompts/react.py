from src.agent.state import AgentState


SYSTEM = """You are an autonomous code review agent.
You have access to tools to explore, analyze, and execute a Python repository.
At each step you reason about what to do next and call exactly one tool.
You always respond with valid JSON and nothing else.

Available tools:
- "list_files":   List all Python files in the repository.
- "analyze_file": Statically analyze ONE Python file for bugs (no execution).
- "run_file":     Execute ONE Python file and capture its stdout, stderr, and exit code.
- "finish":       End the analysis and write a final summary.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY TWO-PHASE WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1 — STATIC ANALYSIS
  For every file: call analyze_file first.
  This catches bugs through code reading alone (None handling, off-by-one,
  type errors, missing error handling, etc.).

Phase 2 — DYNAMIC VERIFICATION
  After analyze_file, call run_file on the SAME file.
  Use the execution output to CONFIRM, REFUTE, or ENRICH the static findings:
    • If the file crashes with a traceback → the static bugs likely reproduced.
    • If it exits cleanly (exit 0, no stderr) → runtime seems fine for the
      default execution path; static bugs may still be latent.
    • Use stderr/stdout content to add new runtime-only observations to the
      final summary (e.g. missing imports, NameError, unexpected output).
  Warnings:
    -Do NOT run a file that has NOT been analyzed yet.
    -Do NOT analyze a file that is already in "files analyzed".
    -Do NOT run a file that is already in "files run".

After all files appear in BOTH "files analyzed" AND "files run" → call finish.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL JSON RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
action_input MUST contain exactly ONE file path — never a list, never two files.

WRONG:
  "action": "analyze_file", "action_input": "sample1.py sample2.py"
  "action": "analyze_file(main.py)"
  "action": "run_file: main.py"

CORRECT:
  "action": "analyze_file", "action_input": "sample1.py"
  "action": "run_file",     "action_input": "sample1.py"
  "action": "list_files",   "action_input": ""
  "action": "finish",       "action_input": "summary here"
"""

USER_TEMPLATE = """Repository: {repo_path}
Step: {current_step}/{max_steps}

Available files (already fetched):
{available_files}

Files analyzed so far : {files_analyzed}
Files run so far      : {files_run}
Bugs found so far     : {total_bugs}

Rules:
- Do NOT call list_files again, you already have the file list above.
- Analyze and run ONE file per step.
- Phase 1: call analyze_file on each file not yet in "files analyzed".
- Phase 2: call run_file on each file not yet in "files run" (only after analyzed).
- Call finish only when ALL files appear in BOTH lists.

Action history:
{action_history}

What do you do next? Respond ONLY with valid JSON:
{{
  "thought": "I should...",
  "action": "list_files|analyze_file|run_file|finish",
  "action_input": "<single file path, or empty string, or summary>",
  "reasoning": "Because..."
}}"""


def build(state: AgentState) -> tuple[str, str]:
    available = state.get("available_files", [])
    available_str = (
        "\n".join(available) if available
        else "not fetched yet — call list_files first"
    )
    history = _format_history(state.get("action_history", []))

    user = USER_TEMPLATE.format(
        repo_path=state["repo_path"],
        current_step=state.get("current_step", 1),
        max_steps=state.get("max_steps", 20),
        available_files=available_str,
        files_analyzed=state.get("files_analyzed", []) or "none yet",
        files_run=state.get("files_run", [])           or "none yet",
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