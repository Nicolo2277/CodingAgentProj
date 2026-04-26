from src.config import EXCLUDED_DIRS
from pathlib import Path
from src.logger import get_logger

logger = get_logger(__name__)


def scan_python_files(repo_path: str | Path) -> list[Path]:
    root = Path(repo_path)

    if not root.exists():
        logger.error("Folder not found: %s", root)
        raise FileNotFoundError(f"Folder not found: {root}")

    if not root.is_dir():
        logger.error("Path is not a folder: %s", root)
        raise ValueError(f"Path is not a folder: {root}")

    files = [
        path for path in root.rglob("*.py")
        if not any(excluded in path.parts for excluded in EXCLUDED_DIRS)
    ]

    logger.info("Found %d Python files in '%s'", len(files), root.name)
    return sorted(files)