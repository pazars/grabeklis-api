from __future__ import annotations

import loguru
from loguru import logger
import sys
import json
import os


logger.remove()
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()


def cloud_logging_sink(message: loguru.Message):
    record = message.record

    gcp_severity_map = {
        "TRACE": "DEBUG",
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "SUCCESS": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    log_entry = {
        "message": record["message"],
        "severity": gcp_severity_map.get(record["level"].name, "INFO"),
        "timestamp": record["time"].isoformat(),
        "file": record["file"].name,
        "line": record["line"],
        "function": record["function"],
        **record["extra"],
    }

    print(json.dumps(log_entry), file=sys.stdout)


logger.add(cloud_logging_sink, level=LOG_LEVEL, enqueue=True)

if os.getenv("ENVIRONMENT", "development").lower() == "development":
    logger.add(
        sys.stderr,
        format="{time} {level} {message}",
        level="DEBUG",
        colorize=True,
        filter=lambda record: record["level"].name != "INFO"
        or "uvicorn." not in record["name"],
    )
