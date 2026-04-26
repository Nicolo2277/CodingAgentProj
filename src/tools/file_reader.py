from pathlib import Path
from src.logger import get_logger

logger = get_logger(__name__)


def read_python_file(path: str | Path) -> str:
    file_path = Path(path)

    if not file_path.exists():
        logger.error("File not found: %s", file_path)
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.suffix != ".py":
        logger.warning("File is not a python file: %s", file_path)
        raise ValueError(f"File is not a python file: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    logger.info("File read - %s (%d chars)", file_path.name, len(content))
    return content