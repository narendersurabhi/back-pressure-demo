FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app

# Install deps if requirements.txt exists; ignore failure to keep build robust for minimal workspaces
RUN pip install --no-cache-dir -r requirements.txt || true

EXPOSE 8000
# simple healthcheck against /health (app should expose it)
HEALTHCHECK --interval=10s --timeout=3s CMD python -c "import urllib.request as u,sys;\
try: u.urlopen('http://127.0.0.1:8000/health', timeout=2); sys.exit(0)\
except: sys.exit(1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
