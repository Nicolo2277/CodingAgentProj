import logging
import os
from src.config import LOG_LEVEL, LOG_DIR

def get_logger(name: str) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    if not logger.handlers:
        # console
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        ))

        # file
        file = logging.FileHandler(f"{LOG_DIR}agent.log", encoding="utf-8")
        file.setLevel(logging.DEBUG)
        file.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))

        logger.addHandler(console)
        logger.addHandler(file)

    return logger
