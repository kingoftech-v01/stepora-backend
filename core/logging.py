"""
Structured JSON log formatter for production (ECS / CloudWatch).

Emits one JSON object per log line so that CloudWatch Logs Insights can
parse fields like ``level``, ``logger``, ``module``, ``message``, and
``exc_info`` without custom parsing rules.

Security audit references: V-571 (No SIEM), V-587 (No dashboard).
Structured logs are a prerequisite for both.
"""

import json
import logging
import traceback
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exc_type"] = record.exc_info[0].__name__
            log_entry["exc_message"] = str(record.exc_info[1])
            log_entry["exc_traceback"] = traceback.format_exception(*record.exc_info)

        # Include extra fields passed via ``extra={}`` in log calls
        # (e.g., from core.audit module)
        _standard_attrs = logging.LogRecord(
            "", 0, "", 0, "", (), None
        ).__dict__.keys()
        for key, value in record.__dict__.items():
            if key not in _standard_attrs and key not in log_entry:
                try:
                    json.dumps(value)  # Ensure serializable
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        return json.dumps(log_entry, default=str, ensure_ascii=False)
