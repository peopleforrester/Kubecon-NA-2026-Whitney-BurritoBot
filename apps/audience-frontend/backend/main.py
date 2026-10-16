# ABOUTME: Audience frontend — the phone page, its QR landing, and a 10/minute per-IP /chat proxy.
# ABOUTME: Routes to burritbot-unguarded (Act 1) or burritbot-guarded via the gateway (Act 2).

from __future__ import annotations

import html
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import qrcode
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
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

# The page lives in apps/audience-frontend/static/, beside backend/. The
# image keeps the same layout (/app/backend/main.py, /app/static/).
STATIC_DIR: Path = Path(__file__).resolve().parent.parent / "static"
STATIC_ASSETS = ("app.js", "styles.css")

# Page settings, read per request so a `kubectl set env` takes effect on the
# next page load. Unset or non-http(s) values fail the page with a 503 that
# names the variable; /healthz and /chat keep working.
FEEDBACK_URL_ENV = "FEEDBACK_URL"  # where the page's Feedback button goes
PUBLIC_URL_ENV = "AUDIENCE_PUBLIC_URL"  # what the projected QR code encodes

QR_BORDER = 4  # quiet zone, in modules, that QR readers expect


class PageConfigError(Exception):
    """A page setting is missing or is not an absolute http(s) URL."""


def _page_url(env_name: str) -> str:
    """Return the absolute http(s) URL in env_name, or raise PageConfigError."""
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise PageConfigError(f"{env_name} is not set on the audience-frontend Deployment")
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise PageConfigError(f"{env_name} must be an absolute http(s) URL, got {value!r}")
    return value


def _qr_svg(text: str) -> str:
    """Render text as a QR code: one SVG path, black on a white quiet zone."""
    qr = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    size = len(matrix) + 2 * QR_BORDER
    cells = "".join(
        f"M{x + QR_BORDER},{y + QR_BORDER}h1v1h-1z"
        for y, row in enumerate(matrix)
        for x, dark in enumerate(row)
        if dark
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'shape-rendering="crispEdges" role="img" '
        f'aria-label="QR code for {html.escape(text)}">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>'
        f'<path d="{cells}" fill="#000"/></svg>'
    )


def _render(template: str, **values: str) -> str:
    """Fill {{name}} placeholders in a page template with pre-escaped values."""
    for name, value in values.items():
        template = template.replace("{{" + name + "}}", value)
    return template


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

    # Read the templates once; a missing file stops the app at startup.
    index_template = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    qr_template = (STATIC_DIR / "qr.html").read_text(encoding="utf-8")
    for asset in STATIC_ASSETS:
        if not (STATIC_DIR / asset).is_file():
            raise FileNotFoundError(f"audience page asset missing: {STATIC_DIR / asset}")

    @app.exception_handler(PageConfigError)
    async def page_config_error(_: Request, exc: PageConfigError) -> PlainTextResponse:
        logger.error("Audience page misconfigured: %s", exc)
        return PlainTextResponse(
            f"Audience page is not configured: {exc}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
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
            "feedback_url": os.environ.get(FEEDBACK_URL_ENV),
            "public_url": os.environ.get(PUBLIC_URL_ENV),
        }

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        feedback_url = _page_url(FEEDBACK_URL_ENV)
        return HTMLResponse(
            _render(index_template, feedback_url=html.escape(feedback_url)),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/qr", response_class=HTMLResponse)
    def qr_landing() -> HTMLResponse:
        public_url = _page_url(PUBLIC_URL_ENV)
        return HTMLResponse(
            _render(qr_template, qr_svg=_qr_svg(public_url), public_url=html.escape(public_url)),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/qr.svg")
    def qr_svg() -> Response:
        return Response(
            _qr_svg(_page_url(PUBLIC_URL_ENV)),
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/static/{asset}")
    def static_asset(asset: str) -> FileResponse:
        # Only the page's own assets; the HTML templates are not served raw.
        if asset not in STATIC_ASSETS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return FileResponse(STATIC_DIR / asset)

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
