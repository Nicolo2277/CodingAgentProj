from src.agent.state import AgentState


def should_continue(state: AgentState) -> str:
    """If there are file not analyzed yet, we continue, otherwise we stop"""
    if state["files_to_analyze"]:
        return "analyze"
    return "done"