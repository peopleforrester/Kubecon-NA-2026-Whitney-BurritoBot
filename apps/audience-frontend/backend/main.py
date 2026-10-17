# ABOUTME: Audience frontend — the phone page, its QR landing, and a /chat proxy limited per browser token.
# ABOUTME: Routes to burritbot-unguarded (Act 1) or burritbot-guarded via the gateway (Act 2).

from __future__ import annotations

import html
import ipaddress
import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import qrcode
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)
from limits import parse_many
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


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
# The guarded path enters the AI gateway's proxy Service. Envoy Gateway runs
# the proxy in its controller namespace; the burritbot-ai-gateway EnvoyProxy
# pins the Service name (ai-gateway/envoy/vertex-ai-backend.yaml).
BURRITBOT_GUARDED_URL: str = os.environ.get(
    "BURRITBOT_GUARDED_URL",
    "http://burritbot-ai-gateway.envoy-gateway-system.svc.cluster.local:8080",
)
# The gateway picks the route by Host. The burritbot-audience HTTPRoute
# matches only this hostname; any other Host (the Service name included)
# falls to the route generated from the AIGatewayRoute, which expects an
# OpenAI-shaped body, not {"prompt": ...}.
BURRITBOT_GUARDED_HOST: str = os.environ.get(
    "BURRITBOT_GUARDED_HOST", "burritbot.burritbot.local"
)

# How long /chat waits on each target. Guarded traffic passes the guardrails
# ext_proc on the request and on the response (2 x 2 x 10s messageTimeout),
# around the burritbot-audience route's 80s timeout, which itself covers
# BurritBot's own gateway pass to Vertex (tests/test_guarded_timeout_budget.py).
# A GKE Gateway in front of this Service needs a GCPBackendPolicy whose
# timeoutSec sits above GUARDED_TIMEOUT_SECONDS; the load balancer's own
# default is 30s (#109).
UNGUARDED_TIMEOUT_SECONDS = 10.0
GUARDED_TIMEOUT_SECONDS = 125.0

# /chat limits, read once at startup from the delivery overlay
# (presentations/<event>/deploy/audience). Each browser keeps a random token
# in localStorage and sends it in TOKEN_HEADER; the token gets TOKEN_LIMIT_ENV
# (the spec's per-person budget, 10/minute). A phone with no token is held
# to the same number on its address. ADDRESS_LIMIT_ENV caps one address
# however many tokens it sends, so clearing the token cannot mint budget
# (question 157). Unset or unparseable, the app refuses to start.
TOKEN_LIMIT_ENV = "AUDIENCE_TOKEN_LIMIT"
ADDRESS_LIMIT_ENV = "AUDIENCE_ADDRESS_LIMIT"
TOKEN_HEADER = "X-Audience-Token"
TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")  # app.js: 16 random bytes as hex

# Phones reach the pod through a GKE Gateway (global external Application
# Load Balancer, NEG backends), so every request arrives from a Google Front
# End in these ranges. The load balancer appends "<client-ip>,<lb-ip>" to
# X-Forwarded-For; anything left of that came from the phone and is not
# trusted. Source:
# https://docs.cloud.google.com/load-balancing/docs/https (firewall rules,
# X-Forwarded-For header).
GOOGLE_LB_RANGES = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("35.191.0.0/16", "130.211.0.0/22", "2600:2d00:1:1::/64")
)

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


def _resolve_target() -> tuple[str, dict[str, str], float]:
    """Return the upstream URL, extra headers and timeout for the selected target."""
    if BURRITBOT_TARGET == "burritbot-guarded":
        return BURRITBOT_GUARDED_URL, {"Host": BURRITBOT_GUARDED_HOST}, GUARDED_TIMEOUT_SECONDS
    return BURRITBOT_UNGUARDED_URL, {}, UNGUARDED_TIMEOUT_SECONDS


def guardrails_refusal(status_code: int, content: bytes) -> dict[str, Any] | None:
    """The net's refusal of a guarded prompt or reply, or None when the answer is something else.

    The burritbot-guardrails ext_proc answers a block with a 403 whose JSON names
    the scanner in "blocked_by" and says why in "detail"
    (ai-gateway/extproc/adapter.py); guarded BurritBot relays a block on its
    model hop in the same shape (#94).
    """
    if status_code != status.HTTP_403_FORBIDDEN:
        return None
    try:
        body = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (
        isinstance(body, dict)
        and isinstance(body.get("blocked_by"), str)
        and isinstance(body.get("detail"), str)
    ):
        return body
    return None


def upstream_failure(status_code: int, content: bytes, target: str) -> JSONResponse:
    """Answer an upstream error: the net's refusal as JSON the page shows as a reply, else an error.

    A refusal is BurritBot sticking to burritos (Act 2), so the phone gets the
    net's own body plus the target that answered. Anything else keeps its
    status, with the upstream body as the detail.
    """
    refused = guardrails_refusal(status_code, content)
    if refused is None:
        raise HTTPException(status_code=status_code, detail=content.decode("utf-8", "replace"))
    return JSONResponse({**refused, "target": target}, status_code=status_code)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    model: str
    guarded: bool
    target: str


def _limit_setting(env_name: str) -> str:
    """Return the rate limit in env_name (e.g. "10/minute"), or raise RuntimeError."""
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise RuntimeError(
            f"{env_name} is not set on the audience-frontend Deployment; "
            "the delivery overlay under presentations/<event>/deploy/audience sets it"
        )
    try:
        parse_many(value)
    except ValueError as exc:
        raise RuntimeError(f"{env_name} is not a rate limit like '10/minute': {value!r}") from exc
    return value


def client_address(request: Request) -> str:
    """Return the phone's address: the load balancer's client entry, or the direct peer.

    A request from Google's load-balancer ranges is keyed on the client the
    load balancer saw. Keying it on the proxy would put the whole room in one
    budget, so one without that entry gets a 400. Any other peer (a
    port-forward, an in-cluster caller) is keyed on itself and its
    X-Forwarded-For is ignored.
    """
    peer = request.client.host if request.client else ""
    try:
        from_load_balancer = any(
            ipaddress.ip_address(peer) in network for network in GOOGLE_LB_RANGES
        )
    except ValueError:
        from_load_balancer = False
    if not from_load_balancer:
        return peer

    entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",")]
    if len(entries) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="load balancer request has no client entry in X-Forwarded-For",
        )
    try:
        return str(ipaddress.ip_address(entries[-2]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"X-Forwarded-For client entry is not an IP address: {entries[-2]!r}",
        ) from exc


def caller_key(request: Request) -> str:
    """Return the per-phone budget key: the browser's token, or its address when it sends none."""
    token = request.headers.get(TOKEN_HEADER)
    if token is None:
        return f"address:{client_address(request)}"
    if not TOKEN_PATTERN.fullmatch(token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{TOKEN_HEADER} must be 32 lowercase hex characters",
        )
    return f"token:{token}"


def create_app() -> FastAPI:
    """Factory for the audience frontend backend."""
    app = FastAPI(
        title="burritbot Audience Frontend",
        description="Lightweight front-end that proxies audience prompts to BurritBot.",
        version="0.1.0",
    )
    token_limit = _limit_setting(TOKEN_LIMIT_ENV)
    address_limit = _limit_setting(ADDRESS_LIMIT_ENV)
    # One limiter per app: its storage is the budget, and the /chat limits
    # below register on it.
    limiter = Limiter(key_func=caller_key)
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        # exc.detail is the error_message of the limit that was hit; the page
        # words a "network" 429 differently from a "phone" one.
        return JSONResponse(
            {"detail": f"{exc.detail} limit exceeded: {exc.limit.limit}", "limit": exc.detail},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

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
            "guarded_host": BURRITBOT_GUARDED_HOST,
            "token_limit": token_limit,
            "address_limit": address_limit,
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
    # The inner limit registers, and is checked, first: a prompt the phone's
    # own budget refuses never counts against its address's ceiling.
    @limiter.limit(address_limit, key_func=client_address, error_message="network")
    @limiter.limit(token_limit, error_message="phone")
    async def chat(request: Request, payload: ChatRequest) -> ChatResponse | JSONResponse:
        target_url, headers, timeout = _resolve_target()
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(
                    f"{target_url}/chat",
                    json={"prompt": payload.prompt},
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                logger.exception("Upstream call failed")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"BurritBot unreachable: {exc}",
                ) from exc

        if resp.status_code >= 400:
            return upstream_failure(resp.status_code, resp.content, BURRITBOT_TARGET)
        body = resp.json()
        return ChatResponse(
            reply=body.get("reply", ""),
            model=body.get("model", "unknown"),
            guarded=body.get("guarded", BURRITBOT_TARGET == "burritbot-guarded"),
            target=BURRITBOT_TARGET,
        )

    return app


app = create_app()
