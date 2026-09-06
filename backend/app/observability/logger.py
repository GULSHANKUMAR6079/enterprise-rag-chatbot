"""
Structured JSON Logging System.
Formats logs as JSON objects and automatically scrubs credentials, passwords, and tokens.
"""
import json
import logging
import re
import sys
from typing import Any, Dict

# Redaction patterns for sensitive headers and keys
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(authorization|bearer|api[_-]?key|secret|password|token|cookie|set-cookie)"
)


class SanitizedJsonFormatter(logging.Formatter):
    """Formats log records as JSON and sanitizes sensitive fields."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom extra fields if provided
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName"
            ):
                if SENSITIVE_KEY_PATTERN.search(key):
                    log_obj[key] = "[REDACTED]"
                elif isinstance(value, str) and len(value) > 500:
                    log_obj[key] = value[:500] + "...[TRUNCATED]"
                else:
                    log_obj[key] = value

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logger(name: str = "app", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(SanitizedJsonFormatter())
        logger.addHandler(handler)
    logger.propagate = False
    return logger


app_logger = setup_logger("enterprise_assistant")
