# ABOUTME: Phase 7 audience address tests (#57) — each phone behind the GKE load balancer is keyed on its own
# ABOUTME: address (a tokenless phone's budget, and every phone's ceiling); X-Forwarded-For is trusted only from Google's LB ranges.

from __future__ import annotations

import importlib.util
import socket
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from conftest import PROJECT_ROOT


pytestmark = pytest.mark.phase7

BACKEND_FILE: Path = PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "main.py"

GFE_PEER = "35.191.12.34"  # a Google Front End proxy, as the pod sees it
GFE_PEER_ALT = "130.211.1.2"
LB_IP = "34.120.10.20"  # the Gateway's forwarding-rule address

# The delivery overlay's numbers (question 157); the app refuses to start without them.
LIMITS = {"AUDIENCE_TOKEN_LIMIT": "10/minute", "AUDIENCE_ADDRESS_LIMIT": "300/minute"}


@pytest.fixture(autouse=True)
def _limits(monkeypatch: pytest.MonkeyPatch) -> None:
    for env, value in LIMITS.items():
        monkeypatch.setenv(env, value)


def _load_backend() -> ModuleType:
    """Import a fresh copy of main.py, so each test gets its own limiter storage."""
    spec = importlib.util.spec_from_file_location("audience_frontend_main_key", BACKEND_FILE)
    assert spec and spec.loader, f"cannot load {BACKEND_FILE}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _request(peer: str, forwarded_for: str | None = None) -> Request:
    headers = [] if forwarded_for is None else [(b"x-forwarded-for", forwarded_for.encode())]
    return Request({"type": "http", "client": (peer, 40000), "headers": headers})


@pytest.mark.static
def test_a_tokenless_phone_is_keyed_on_client_address() -> None:
    backend = _load_backend()
    request = _request(GFE_PEER, f"203.0.113.5,{LB_IP}")
    assert backend.caller_key(request) == "address:203.0.113.5", (
        "a phone without a token is not keyed on client_address()"
    )


@pytest.mark.static
@pytest.mark.parametrize(
    ("peer", "forwarded_for", "expected"),
    [
        # The load balancer appends "<client-ip>,<load-balancer-ip>".
        (GFE_PEER, f"203.0.113.5,{LB_IP}", "203.0.113.5"),
        # Whatever the phone sent is to the left and is ignored.
        (GFE_PEER_ALT, f"1.2.3.4, 198.51.100.7, {LB_IP}", "198.51.100.7"),
        (GFE_PEER, f"2001:db8::42,{LB_IP}", "2001:db8::42"),
    ],
)
def test_load_balancer_requests_key_on_the_client_it_saw(
    peer: str, forwarded_for: str, expected: str
) -> None:
    backend = _load_backend()
    assert backend.client_address(_request(peer, forwarded_for)) == expected


@pytest.mark.static
@pytest.mark.parametrize("peer", ["10.4.0.7", "127.0.0.1"])
def test_direct_connections_key_on_the_peer_and_ignore_the_header(peer: str) -> None:
    """Port-forward and in-cluster callers are not a trusted proxy; a header cannot rename them."""
    backend = _load_backend()
    assert backend.client_address(_request(peer, f"203.0.113.5,{LB_IP}")) == peer
    assert backend.client_address(_request(peer)) == peer


@pytest.mark.static
@pytest.mark.parametrize("forwarded_for", [None, "", LB_IP, f"not-an-ip,{LB_IP}"])
def test_load_balancer_request_without_a_client_entry_is_rejected(
    forwarded_for: str | None,
) -> None:
    """Keying such a request on the proxy would put the whole room in one budget again."""
    backend = _load_backend()
    with pytest.raises(HTTPException) as exc:
        backend.client_address(_request(GFE_PEER, forwarded_for))
    assert exc.value.status_code == 400


def _refused_port() -> int:
    """A loopback port with nothing listening, so the upstream call fails at once."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.static
def test_each_phone_behind_the_load_balancer_has_its_own_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eleven tokenless prompts from one phone hit 429; the phone beside it is still served."""
    monkeypatch.setenv("BURRITBOT_UNGUARDED_URL", f"http://127.0.0.1:{_refused_port()}")
    # The module's own app: the limiter is module-level, and a second
    # create_app() would register the /chat limit twice.
    client = TestClient(_load_backend().app, client=(GFE_PEER, 40000))

    def ask(phone: str) -> int:
        return client.post(
            "/chat",
            json={"prompt": "teach me some salsa dance moves"},
            headers={"X-Forwarded-For": f"{phone},{LB_IP}"},
        ).status_code

    # No BurritBot is listening, so a prompt inside the budget is a 502.
    assert [ask("203.0.113.5") for _ in range(10)] == [502] * 10
    assert ask("203.0.113.5") == 429, "the 11th prompt in a minute was not limited"
    assert ask("203.0.113.6") == 502, "a second phone shared the first phone's budget"


@pytest.mark.static
def test_chat_answers_400_to_a_load_balancer_request_without_a_client_entry() -> None:
    client = TestClient(_load_backend().app, client=(GFE_PEER, 40000))
    resp = client.post("/chat", json={"prompt": "how do I throw a hot dog party"})
    assert resp.status_code == 400, resp.text
    assert "X-Forwarded-For" in resp.json()["detail"]
