from src.agent.state import AgentState


def should_continue(state: AgentState) -> str:
    if state.get("finished"):
        return "done"
    if state.get("current_step", 0) >= state.get("max_steps", 20):
        return "done"
    return "continue"