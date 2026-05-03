from src.agent.state import AgentState

SYSTEM = """"You are an autonomous code review agent executing a pre-built analysis plan.
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

── PLAN ──────────────────────────────────────────────────────────────────
{plan_steps}

── PROGRESS ──────────────────────────────────────────────────────────────
Analyzed : {files_analyzed}
Failed   : {files_failed}
Remaining: {files_remaining}
Bugs so far: {total_bugs}
Files run: {files_run}

── RULES ─────────────────────────────────────────────────────────────────
- Follow the plan order: analyze the FIRST file in "Remaining".
- Do NOT call list_files — you already have the file list.
- Call finish ONLY when "Remaining" is empty.
- If a file fails, move to the next one.

── HISTORY ───────────────────────────────────────────────────────────────
{action_history}

What do you do next? Respond ONLY with valid JSON:
{{
  "thought":      "I should...",
  "action":       "analyze_file|run_file|finish|list_files",
  "action_input": "...",
  "reasoning":    "Because..."
}}"""


def _format_plan_steps(state: AgentState) -> str:
    plan = state.get("plan")
    if not plan:
        return "  (no plan. call list_files to fetch files)"

    analyzed = set(state.get("files_analyzed", []))
    failed   = set(state.get("files_failed", []))
    lines = []
    for step in plan.steps:
        if step.file in analyzed:
            status = "Ok"
        elif step.file in failed:
            status = "Error:"
        else:
            status = "·"
        lines.append(f"  [{status}] [{step.priority:6}] {step.file}  — {step.reason}")
    return "\n".join(lines)


def build(state: AgentState) -> tuple[str, str]:
    plan = state.get("plan")
    analyzed = set(state.get("files_analyzed", []))
    failed   = set(state.get("files_failed",   []))
    run = set(state.get("files_run", []))

    if plan:
        all_files = [s.file for s in plan.steps]
    else:
        all_files = state.get("available_files", [])

    remaining = [f for f in all_files if f not in failed and not (f in analyzed and f in run)]

    user = USER_TEMPLATE.format(
        repo_path      = state["repo_path"],
        current_step   = state.get("current_step", 1),
        max_steps      = state.get("max_steps", 20),
        plan_steps     = _format_plan_steps(state),
        files_analyzed = ", ".join(analyzed) or "none yet",
        files_failed   = ", ".join(failed)   or "none",
        files_run      = ", ".join(run)      or "none yet",
        files_remaining= ", ".join(remaining) or "none — call finish",
        total_bugs     = state.get("total_bugs", 0),
        action_history = _format_history(state.get("action_history", [])),
    )
    return SYSTEM, user

def _format_history(history: list) -> str:
    if not history:
        return ""
    lines = []
    for i, record in enumerate(history[-5:], 1): #We consider the last 5 entries
        lines.append(
            f"  [{i}] {record['action']}({record['action_input']!r})\n"
            f"       → {record['result']}"
        )
    return "\n".join(lines)