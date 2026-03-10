import logging
import os

APP_LOGGER_NAME = "unichatbot"


def configure_logging() -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        for handler in logger.handlers:
            handler.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)


def get_logger(module_name: str | None = None) -> logging.Logger:
    if not module_name:
        return logging.getLogger(APP_LOGGER_NAME)
    return logging.getLogger(f"{APP_LOGGER_NAME}.{module_name}")
