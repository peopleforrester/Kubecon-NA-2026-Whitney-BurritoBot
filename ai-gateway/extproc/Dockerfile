# ABOUTME: Dockerfile for the burritbot-extproc sidecar — python:3.13-slim running the gRPC ext_proc adapter.
# ABOUTME: Runs as non-root (burritbot:1001) and serves envoy.service.ext_proc.v3 on EXTPROC_PORT.
#   docker build -t burritbot-extproc ai-gateway/extproc
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 burritbot \
    && useradd --system --uid 1001 --gid burritbot --home /app burritbot

WORKDIR /app

COPY --chown=burritbot:burritbot requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=burritbot:burritbot adapter.py /app/adapter.py

USER burritbot:burritbot
EXPOSE 50051

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "/app/adapter.py"]
