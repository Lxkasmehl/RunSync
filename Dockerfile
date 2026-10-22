FROM python:3.13-slim
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN useradd -m -u 1000 app && mkdir /data && chown app /data
USER app
WORKDIR /app
COPY *.py shoes.json ./
# /data: strava_tokens.json, ledger.json, service-account.json
ENV DATA_DIR=/data STRAVA_TOKENS_FILE=/data/strava_tokens.json FILE_PATH=/data/service-account.json PYTHONUNBUFFERED=1
HEALTHCHECK --interval=1m --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/ping')"
CMD ["python", "server.py"]
