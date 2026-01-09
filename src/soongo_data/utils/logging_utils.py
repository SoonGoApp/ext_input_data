import logging
import typing
from functools import lru_cache


def gen_logger(
    name: str,
    file_path: typing.Optional[str] = None,
    parent_logger: typing.Optional[logging.Logger] = None,
) -> logging.Logger:
    """
    Create a custom logger with optional file logging and inheritance from
        another logger.

    :params name: Name of the logger.
    :params file_path: Optional file path for logging to a file.
    :params parent_logger: Optional parent logger for inheritance.

    :returns: Logger instance.
    """

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create console handler and set level to debug
    logger.addHandler(gen_console_handler())

    # Create file handler if file_path is provided
    if file_path:
        logger.addHandler(gen_file_handler(file_path))

    # Inherit from parent logger if provided
    if parent_logger:
        logger.parent = parent_logger

    return logger


@lru_cache(maxsize=1)
def gen_logging_formatter():
    """ Gen logging formatter, cached to avoid duplication"""
    return logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@lru_cache(maxsize=1)
def gen_console_handler():
    """ Gen logging console handler, cached to avoid log duplication."""
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(gen_logging_formatter())
    return console_handler


@lru_cache
def gen_file_handler(file_path: str):
    """ Gen logging file handler, cached to avoid log duplication.

    :param file_path: string path to the file where to write logs.
    """
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(gen_logging_formatter())
    return file_handler
