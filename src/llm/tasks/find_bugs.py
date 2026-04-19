from src.llm.client import BaseLLMClient
from src.llm.prompts.find_bugs import FindBugsPrompt
from src.models.schemas import BugReport
from src.logger import get_logger

logger = get_logger(__name__)


def find_bugs(code: str, client: BaseLLMClient) -> BugReport:
    system, user = FindBugsPrompt.build(code=code)

    logger.info("Bug analysis started (%d chars of code)", len(code))
    response = client.complete(user, system=system, json_mode=True)
    
    logger.debug("Raw response: %s", response.content) 

    data = response.as_json()
    report = BugReport(**data)

    logger.info(
        "Analysis completed — %d bugs found in %dms",
        len(report.bugs),
        response.duration_ms,
    )
    return report