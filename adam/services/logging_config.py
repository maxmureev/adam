import logging
import sys
from logging.handlers import RotatingFileHandler
from fastapi import Request
from config import config

# Dictionary for storing already created loggers
_loggers = {}


def get_logger(name: str) -> logging.Logger:
    """Returns the configured logger with the specified name"""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.log.level.upper(), logging.INFO))
    logger.propagate = False  # Prevent duplicate logs

    # Check if the handlers have already been added to avoid duplicates
    if not logger.handlers:
        # Logs format
        log_format = logging.Formatter(
            "[%(asctime)s] [%(name)s] %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Handler for stdout/stderr
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

        # Handler for file
        if config.log.file:
            file_handler = RotatingFileHandler(
                config.log.file, maxBytes=10 * 1024 * 1024, backupCount=5
            )
            file_handler.setFormatter(log_format)
            logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


async def log_requests_middleware(request: Request, call_next):
    """Middleware for logging HTTP requests"""
    logger = get_logger("http")
    client_ip = request.client.host
    method = request.method
    path = request.url.path

    excluded_paths = [
        "/static",
    ]
    excluded_files = [
        "/favicon.ico",
        "/openapi.json",
    ]

    should_log = not (
        any(path.startswith(excluded_path) for excluded_path in excluded_paths)
        or path in excluded_files
    )

    try:
        response = await call_next(request)
        if should_log:
            status_code = response.status_code
            logger.info(f'{client_ip} "{method} {path} HTTP/1.1" {status_code}')
        return response
    except Exception as e:
        if should_log:
            logger.error(f'{client_ip} "{method} {path} HTTP/1.1" 500 - {str(e)}')
        raise


def setup_logging():
    """Configures centralized logging for the application"""
    get_logger("root")

    # Disable logs from other libraries
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").propagate = False
    logging.getLogger("gunicorn").propagate = False
