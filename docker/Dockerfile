# Countertop server in a container (Unraid, Synology, a Pi, any Docker host).
# Build from the project root:   docker build -f docker/Dockerfile -t countertop .
FROM python:3.12-slim

# tzdata: the server turns calendar times into *local* time, so the container needs real time zones
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir python-dateutil

WORKDIR /app
# app code (read-only at runtime); everything the server writes goes to /app/work
COPY tools/ /app/tools/
RUN rm -f /app/tools/*.backup* /app/tools/*backup-*.html \
    && mkdir -p /app/work && chmod 777 /app/work

ENV TZ=America/Chicago \
    PYTHONUNBUFFERED=1
VOLUME /app/work
EXPOSE 8090

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/version', timeout=4)" || exit 1

CMD ["python", "tools/silk_probe.py", "--port", "8090"]
