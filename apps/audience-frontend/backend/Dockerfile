# ABOUTME: Dockerfile for the audience-frontend FastAPI proxy — python:3.13-slim + uvicorn.
# ABOUTME: Runs as non-root (audience:1001) and serves on port 8080.
# Build context is apps/audience-frontend, so the image carries the page too:
#   docker build -f apps/audience-frontend/backend/Dockerfile apps/audience-frontend
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 audience \
    && useradd --system --uid 1001 --gid audience --home /app audience

WORKDIR /app/backend

COPY --chown=audience:audience backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# main.py finds the page at ../static, the same layout as the repo.
COPY --chown=audience:audience backend/main.py /app/backend/main.py
COPY --chown=audience:audience static /app/static

USER audience:audience
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
