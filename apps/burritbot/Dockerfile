# ABOUTME: Dockerfile for BurritBot — python:3.13-slim base with uv and uvicorn.
# ABOUTME: Runs as non-root (burritbot:1001) and serves on port 8080.
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 burritbot \
    && useradd --system --uid 1001 --gid burritbot --home /app burritbot

WORKDIR /app

COPY --chown=burritbot:burritbot requirements.txt /app/requirements.txt
# requirements.txt is uv.lock exported with hashes (scripts/export-image-requirements.sh):
# every transitive package is pinned there, so pip checks hashes and resolves nothing.
RUN pip install --no-cache-dir --no-deps --require-hashes -r /app/requirements.txt

COPY --chown=burritbot:burritbot app.py /app/app.py

USER burritbot:burritbot
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
