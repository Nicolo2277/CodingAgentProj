from src.agent.state import AgentState
from src.agent.tools import tool_list_files, tool_analyze_file, tool_run_file
from src.llm.tasks.think import think
from src.llm.tasks.plan import create_plan
from src.llm.factory import get_client
from src.tools.output_writer import save_final_report
from src.models.schemas import AgentAction
from src.logger import get_logger

logger = get_logger(__name__)
client = get_client()


def node_plan(state: AgentState) -> dict:
    """Run once at start: build a prioritized file plan."""
    plan, available_files = create_plan(state, client)
    return {
        "plan":            plan,
        "available_files": available_files,
    }

def node_think_act(state: AgentState) -> dict:
    action = think(state, client)

    result_text = ""
    state_updates: dict = {}

    if action.action == "list_files":
        result_text, state_updates = tool_list_files(state)

    elif action.action == "analyze_file":
        result_text, state_updates = tool_analyze_file(
            state, action.action_input, client
        )

    elif action.action == "run_file":
        result_text, state_updates = tool_run_file(state, action.action_input)

    elif action.action == "finish":
        result_text  = "Agent finished."
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

    return {"current_step": state.get("current_step", 0) + 1,
            "action_history": [record], **state_updates}  # type: ignore


def node_save_results(state: AgentState) -> dict:
    save_final_report(state["repo_path"], state.get("reports", {}))
    logger.info(
        "Done — %d files analyzed, %d run, %d bugs found",
        len(state.get("files_analyzed", [])),
        len(state.get("files_run", [])),
        state.get("total_bugs", 0),
    )
    return {}