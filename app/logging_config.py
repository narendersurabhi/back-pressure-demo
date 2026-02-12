import logging
import json
import sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        # include exception info if present
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # include any extra attributes
        for k, v in record.__dict__.items():
            if k in ("name", "msg", "args", "levelname", "levelno", "exc_info", "exc_text", "stack_info", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process"):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except Exception:
                payload[k] = str(v)
        return json.dumps(payload, ensure_ascii=False)


def init_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
