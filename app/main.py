import logging
import sys
import uvicorn
from .api import app
from .config import APP_NAME

# simple JSON logger
class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        payload = {"ts": self.formatTime(record), "level": record.levelname, "msg": record.getMessage()}
        if record.__dict__.get("extra"):
            payload.update(record.__dict__["extra"])
        return json_dump(payload)

def json_dump(d):
    import json
    return json.dumps(d, default=str)

root = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":%(message)s}'))
root.setLevel(logging.INFO)
root.handlers = [handler]

if __name__ == "__main__":
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False)
