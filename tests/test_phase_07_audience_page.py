# ABOUTME: Phase 7 audience phone page tests (#56) — index.html, app.js, styles.css, QR landing.
# ABOUTME: Drives the real FastAPI app in-process; /chat upstream calls are left to the live suite.

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
import qrcode
from fastapi.testclient import TestClient

from conftest import PROJECT_ROOT
from helpers.image_requirements import requirement_pins
from helpers.static_assets import file_has_aboutme


pytestmark = pytest.mark.phase7

FRONTEND_DIR = PROJECT_ROOT / "apps" / "audience-frontend"
BACKEND_FILE = FRONTEND_DIR / "backend" / "main.py"
STATIC_DIR = FRONTEND_DIR / "static"
PAGE_FILES = ("index.html", "qr.html", "app.js", "styles.css")
DOCKERFILE = FRONTEND_DIR / "backend" / "Dockerfile"
REQUIREMENTS = FRONTEND_DIR / "backend" / "requirements.txt"

FEEDBACK_URL = "https://feedback.example/burritbot?session=1"
PUBLIC_URL = "https://burritbot.example/"
CANONICAL_PROMPTS = (
    "teach me some salsa dance moves",
    "how do I throw a hot dog party",
    "recommend karaoke songs for a wedding",
)


@pytest.fixture(autouse=True)
def _limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """The delivery overlay's /chat limits (question 157); the app refuses to start without them."""
    monkeypatch.setenv("AUDIENCE_TOKEN_LIMIT", "10/minute")
    monkeypatch.setenv("AUDIENCE_ADDRESS_LIMIT", "300/minute")


def _load_backend() -> ModuleType:
    """Import apps/audience-frontend/backend/main.py under a private name."""
    spec = importlib.util.spec_from_file_location("audience_frontend_main", BACKEND_FILE)
    assert spec and spec.loader, f"cannot load {BACKEND_FILE}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FEEDBACK_URL", FEEDBACK_URL)
    monkeypatch.setenv("AUDIENCE_PUBLIC_URL", PUBLIC_URL)
    return TestClient(_load_backend().create_app())


@pytest.fixture
def unconfigured(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("FEEDBACK_URL", raising=False)
    monkeypatch.delenv("AUDIENCE_PUBLIC_URL", raising=False)
    return TestClient(_load_backend().create_app())


# --- The files exist and follow the repo conventions --------------------


@pytest.mark.static
@pytest.mark.parametrize("name", PAGE_FILES)
def test_page_file_exists_with_aboutme(name: str) -> None:
    path = STATIC_DIR / name
    assert path.is_file(), f"apps/audience-frontend/static/{name} is missing"
    assert file_has_aboutme(path), f"{name} does not start with two ABOUTME lines"


@pytest.mark.static
def test_image_ships_the_static_page() -> None:
    """The Dockerfile copies static/ next to backend/, where main.py looks for it."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^COPY\b.*\bstatic\b.*/app/static", text, re.M), (
        "Dockerfile does not copy static/ to /app/static"
    )
    assert re.search(r"^COPY\b.*backend/main\.py.*/app/backend/", text, re.M), (
        "Dockerfile does not copy main.py to /app/backend/"
    )


@pytest.mark.static
def test_requirements_pin_qrcode() -> None:
    assert requirement_pins(REQUIREMENTS).get("qrcode"), (
        "requirements.txt has no exact qrcode pin (the QR landing imports it)"
    )


# --- The phone page ------------------------------------------------------


@pytest.mark.static
def test_index_is_served_at_root(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/html")
    html = resp.text
    assert '<meta name="viewport"' in html, "page has no mobile viewport meta tag"
    assert "/static/app.js" in html and "/static/styles.css" in html


@pytest.mark.static
def test_index_carries_the_feedback_link(client: TestClient) -> None:
    html = client.get("/").text
    link = re.search(r'<a\b[^>]*\bid="feedback"[^>]*>', html)
    assert link, "page has no <a id=\"feedback\"> link"
    assert 'href="https://feedback.example/burritbot?session=1"' in link.group(0)
    assert 'target="_blank"' in link.group(0) and "noopener" in link.group(0)


@pytest.mark.static
def test_index_has_prompt_form_and_canonical_asks(client: TestClient) -> None:
    html = client.get("/").text
    assert re.search(r"<form\b[^>]*\bid=\"prompt-form\"", html)
    assert re.search(r"<textarea\b[^>]*\bmaxlength=\"2000\"", html), (
        "prompt box does not match the backend's 2000-character limit"
    )
    for prompt in CANONICAL_PROMPTS:
        assert prompt in html, f"canonical Act 1 ask missing: {prompt!r}"


@pytest.mark.static
def test_index_fails_explicitly_without_feedback_url(unconfigured: TestClient) -> None:
    resp = unconfigured.get("/")
    assert resp.status_code == 503
    assert "FEEDBACK_URL" in resp.text


@pytest.mark.static
@pytest.mark.parametrize("bad", ["javascript:alert(1)", "feedback.example/form", "ftp://x.example/"])
def test_index_rejects_non_http_feedback_url(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    monkeypatch.setenv("FEEDBACK_URL", bad)
    resp = TestClient(_load_backend().create_app()).get("/")
    assert resp.status_code == 503
    assert "FEEDBACK_URL" in resp.text


@pytest.mark.static
def test_feedback_url_is_attribute_escaped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDBACK_URL", 'https://x.example/?a=1&b="2"')
    html = TestClient(_load_backend().create_app()).get("/").text
    assert 'href="https://x.example/?a=1&amp;b=&quot;2&quot;"' in html


@pytest.mark.static
@pytest.mark.parametrize("name", ["app.js", "styles.css"])
def test_assets_are_served(client: TestClient, name: str) -> None:
    resp = client.get(f"/static/{name}")
    assert resp.status_code == 200
    assert resp.text == (STATIC_DIR / name).read_text(encoding="utf-8")


@pytest.mark.static
def test_app_js_posts_to_chat_and_never_injects_html() -> None:
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert re.search(r"fetch\(\s*[\"']/chat[\"']", js), "app.js never POSTs to /chat"
    assert "innerHTML" not in js, "app.js must render replies with textContent, not innerHTML"
    assert "429" in js, "app.js does not tell the audience about the rate limit"


@pytest.mark.static
def test_config_reports_page_links(client: TestClient) -> None:
    body = client.get("/config").json()
    assert body["feedback_url"] == FEEDBACK_URL
    assert body["public_url"] == PUBLIC_URL


# --- The QR landing ------------------------------------------------------


def _svg_modules(svg: str) -> set[tuple[int, int]]:
    """Dark modules drawn by the SVG path, as (x, y) cells."""
    path = re.search(r'<path\b[^>]*\bd="([^"]+)"', svg)
    assert path, "QR SVG has no <path d=...>"
    return {(int(x), int(y)) for x, y in re.findall(r"M(\d+),(\d+)h1v1h-1z", path.group(1))}


def _expected_modules(text: str, border: int) -> set[tuple[int, int]]:
    qr = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    return {
        (x + border, y + border)
        for y, row in enumerate(qr.get_matrix())
        for x, dark in enumerate(row)
        if dark
    }


@pytest.mark.static
def test_qr_svg_encodes_the_public_url(client: TestClient) -> None:
    resp = client.get("/qr.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    svg = resp.text
    assert 'fill="#fff"' in svg, "QR has no white quiet-zone background"
    modules = _svg_modules(svg)
    assert modules == _expected_modules(PUBLIC_URL, border=4)
    assert modules != _expected_modules("https://other.example/", border=4)


@pytest.mark.static
def test_qr_landing_shows_code_url_and_feedback(client: TestClient) -> None:
    resp = client.get("/qr")
    assert resp.status_code == 200
    html = resp.text
    assert "<svg" in html, "QR landing does not inline the code"
    assert _svg_modules(html) == _expected_modules(PUBLIC_URL, border=4)
    assert "burritbot.example" in html, "QR landing does not print the URL for people who cannot scan"
    assert "feedback" in html.lower()


@pytest.mark.static
@pytest.mark.parametrize("path", ["/qr", "/qr.svg"])
def test_qr_fails_explicitly_without_public_url(unconfigured: TestClient, path: str) -> None:
    resp = unconfigured.get(path)
    assert resp.status_code == 503
    assert "AUDIENCE_PUBLIC_URL" in resp.text


@pytest.mark.static
def test_health_and_chat_routes_survive_missing_page_config(unconfigured: TestClient) -> None:
    """A missing page setting fails the page, not the probes or the API."""
    assert unconfigured.get("/healthz").status_code == 200
    assert unconfigured.post("/chat", json={"prompt": ""}).status_code == 422


@pytest.mark.static
def test_static_dir_resolves_beside_backend() -> None:
    module = _load_backend()
    assert Path(module.STATIC_DIR).resolve() == STATIC_DIR.resolve()


# --- Live: the deployed pod serves the page ------------------------------


@pytest.mark.live
def test_deployed_page_carries_feedback_link_and_qr(k8s_core_v1) -> None:
    """The running Service serves the page and the QR landing (needs both page URLs set)."""
    core = k8s_core_v1
    page = core.connect_get_namespaced_service_proxy_with_path(
        "audience-frontend:http", "audience", path=""
    )
    assert re.search(r'<a\b[^>]*\bid="feedback"[^>]*\bhref="https?://', page), (
        "deployed page has no Feedback link"
    )
    landing = core.connect_get_namespaced_service_proxy_with_path(
        "audience-frontend:http", "audience", path="qr"
    )
    assert "<svg" in landing, "deployed /qr does not render the code"
