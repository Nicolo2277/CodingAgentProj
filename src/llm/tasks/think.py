from src.agent.state import AgentState
from src.llm.client import BaseLLMClient
from src.llm.prompts import react as prompt
from src.models.schemas import AgentAction
from src.logger import get_logger

logger = get_logger(__name__)

def _sanitize_action(data: dict) -> dict:
    action = data.get("action", "")

    # handles "analyze_file(main.py)"
    if "(" in action:
        parts = action.split("(")
        data["action"] = parts[0].strip()
        data["action_input"] = parts[1].replace(")", "").strip()

    # handles "list_files|analyze_file" or any other garbage
    valid = {"list_files", "analyze_file", "finish"}
    if data["action"] not in valid:
        data["action"] = "finish"
        data["action_input"] = "Could not determine next action, stopping."

    return data

def think(state: AgentState, client: BaseLLMClient) -> AgentAction:
    system, user = prompt.build(state)

    logger.info(
        "Step %d/%d — thinking...",
        state.get("current_step", 1),
        state.get("max_steps", 20),
    )

    response = client.complete(user, system=system, json_mode=True)
    data = _sanitize_action(response.as_json())
    action = AgentAction(**data)

    logger.info("→ action: %s(%s)", action.action, action.action_input)
    logger.debug("→ thought: %s", action.thought)

    return action


