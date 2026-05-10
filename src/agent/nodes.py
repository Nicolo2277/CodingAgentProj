from __future__ import annotations

from typing import cast
from src.agent.state import AgentState
from src.agent.tools import (
    tool_analyze_file,
    tool_list_files,
    tool_run_file,
    tool_verify_file,
)
from src.llm.factory import get_client
from src.llm.tasks.plan import create_plan
from src.logger import get_logger
from src.tools.output_writer import save_final_report

logger = get_logger(__name__)
client = get_client()


# plan 

def node_plan(state: AgentState) -> dict:
    """Run once at start: build a prioritised file plan."""
    plan, available_files = create_plan(state, client)
    return {
        "plan":            plan,
        "available_files": available_files,
    }


# think_act

def node_think_act(state: AgentState) -> dict:
    from src.llm.tasks.think import think  # local import avoids circular deps

    action = think(state, client)

    result_text:   str  = ""
    state_updates: dict = {}

    if action.action == "list_files":
        result_text, state_updates = tool_list_files(state)

    elif action.action == "analyze_file":
        result_text, state_updates = tool_analyze_file(
            state, action.action_input, client
        )

    elif action.action == "run_file":
        result_text, state_updates = tool_run_file(state, action.action_input)

        # Auto-trigger verifier 
        # Once run_file succeeds we have both a BugReport and execution context
        # for this file, so we can generate and run targeted tests immediately.
        # This is transparent to the agent — it never needs to call verify itself.
        file_key = action.action_input.strip()
        merged_state = cast(AgentState, {**state, **state_updates})  # reflect run_results in state

        if file_key in merged_state.get("reports", {}):
            verify_text, verify_updates = tool_verify_file(
                merged_state, file_key, client
            )
            # Append verification summary to the result the agent will see
            result_text = f"{result_text}\n\n[Verifier] {verify_text}"
            state_updates = {**state_updates, **verify_updates}
        else:
            logger.debug(
                "Skipping auto-verification for %s — no bug report found yet.", file_key
            )

    elif action.action == "finish":
        result_text   = "Agent finished."
        state_updates = {
            "finished": True,
            "summary":  action.action_input,
        }

    record = {
        "thought":      action.thought,
        "action":       action.action,
        "action_input": action.action_input,
        "result":       result_text,
    }

    return {
        "current_step":   state.get("current_step", 0) + 1,
        "action_history": [record],
        **state_updates,
    }  # type: ignore[return-value]


# save_results

def node_save_results(state: AgentState) -> dict:
    save_final_report(
        state["repo_path"],
        state.get("reports", {}),
        state.get("verified_reports", {}),
    )
    logger.info(
        "Done — %d files analyzed | %d run | %d verified | %d bugs (%d confirmed)",
        len(state.get("files_analyzed",  [])),
        len(state.get("files_run",       [])),
        len(state.get("files_verified",  [])),
        state.get("total_bugs",     0),
        state.get("confirmed_bugs", 0),
    )
    return {}