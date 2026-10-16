# ABOUTME: Audience frontend backend — FastAPI proxy with a 10/minute per-IP rate limit.
# ABOUTME: Routes to burritbot-unguarded (Act 1) or burritbot-guarded via the gateway (Act 2).

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


logger = logging.getLogger("audience-frontend")
logging.basicConfig(level=logging.INFO)

# Target is toggled by cast-net.sh at demo time. The script patches the
# BURRITBOT_TARGET env var on the audience Deployment (one of:
# "burritbot-unguarded" or "burritbot-guarded").
BURRITBOT_TARGET: str = os.environ.get("BURRITBOT_TARGET", "burritbot-unguarded")
BURRITBOT_UNGUARDED_URL: str = os.environ.get(
    "BURRITBOT_UNGUARDED_URL",
    "http://burritbot-unguarded.burritbot-unguarded.svc.cluster.local:8080",
)
BURRITBOT_GUARDED_URL: str = os.environ.get(
    "BURRITBOT_GUARDED_URL",
    "http://burritbot-ai-gateway.burritbot-net.svc.cluster.local:8080",
)

RATE_LIMIT = "10/minute"


def _resolve_target_url() -> str:
    """Return the upstream URL for the currently selected target."""
    if BURRITBOT_TARGET == "burritbot-guarded":
        return BURRITBOT_GUARDED_URL
    return BURRITBOT_UNGUARDED_URL


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    model: str
    guarded: bool
    target: str


limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT])


def create_app() -> FastAPI:
    """Factory for the audience frontend backend."""
    app = FastAPI(
        title="burritbot Audience Frontend",
        description="Lightweight front-end that proxies audience prompts to BurritBot.",
        version="0.1.0",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # audience-only demo, behind a private gateway
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "target": BURRITBOT_TARGET}

    @app.get("/config")
    def config() -> dict[str, Any]:
        return {
            "target": BURRITBOT_TARGET,
            "unguarded_url": BURRITBOT_UNGUARDED_URL,
            "guarded_url": BURRITBOT_GUARDED_URL,
            "rate_limit": RATE_LIMIT,
        }

    @app.post("/chat", response_model=ChatResponse)
    @limiter.limit(RATE_LIMIT)
    async def chat(request: Request, payload: ChatRequest) -> ChatResponse:
        target_url = _resolve_target_url()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{target_url}/chat",
                    json={"prompt": payload.prompt},
                )
            except httpx.HTTPError as exc:
                logger.exception("Upstream call failed: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"BurritBot unreachable: {exc}",
                ) from exc

        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        body = resp.json()
        return ChatResponse(
            reply=body.get("reply", ""),
            model=body.get("model", "unknown"),
            guarded=body.get("guarded", BURRITBOT_TARGET == "burritbot-guarded"),
            target=BURRITBOT_TARGET,
        )

    return app


app = create_app()
