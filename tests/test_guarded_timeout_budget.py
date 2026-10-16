# ABOUTME: Each timeout on the guarded path outlasts every hop inside it (#92): the frontend's guarded
# ABOUTME: timeout, the burritbot-audience route timeout, BurritBot's gateway timeout and the Vertex route timeout.

from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from conftest import PROJECT_ROOT


GATEWAY_FILE = PROJECT_ROOT / "ai-gateway" / "envoy" / "gateway.yaml"
FRONTEND_MAIN = PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "main.py"
BURRITBOT_APP = PROJECT_ROOT / "apps" / "burritbot" / "app.py"

AUDIENCE_ROUTE = "burritbot-audience"
AI_ROUTE = "burritbot-gemini-route"
EXTPROC_POLICY = "burritbot-guardrails"

# The guarded path, outermost first. Phone -> frontend (guarded timeout) ->
# gateway: the guardrails ext_proc on the request -> burritbot-audience route
# (route timeout) -> guarded BurritBot (gateway timeout) -> gateway again: the
# guardrails ext_proc on the request -> AIGatewayRoute (route timeout) ->
# Vertex -> the guardrails ext_proc on the response -> BurritBot -> the
# guardrails ext_proc on the response -> frontend.
#
# Envoy starts a route timeout once the request has passed every decoder
# filter, and stops it when the upstream response is complete, before the
# encoder filters run. So a route timeout covers neither direction of the
# guardrails ext_proc on its own pass, and the caller of each pass must.
# Each ext_proc message is held to its messageTimeout, whatever the
# adapter does inside it.
#
# Without timeouts.request, Envoy Gateway leaves Envoy's 15s route default
# on an HTTPRoute, and Envoy AI Gateway sets 60s on an AIGatewayRoute rule
# (api/v1beta1/ai_gateway_route.go, v1.2.0).


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _find(docs: list[dict], kind: str, name: str) -> dict:
    for doc in docs:
        if doc["kind"] == kind and doc["metadata"]["name"] == name:
            return doc
    raise AssertionError(f"{kind} {name} not found in {GATEWAY_FILE}")


def _seconds(duration: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m)", duration)
    assert match, f"unparseable duration {duration!r}"
    value, unit = float(match.group(1)), match.group(2)
    return value * {"ms": 0.001, "s": 1, "m": 60}[unit]


def _load(path: Path, name: str) -> ModuleType:
    """Import a fresh copy of a module, so it reads the environment as it is now."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _route_request_timeouts(route: dict) -> list[float | None]:
    """Each rule's timeouts.request in seconds, or None where the rule sets none."""
    out: list[float | None] = []
    for rule in route["spec"]["rules"]:
        request = (rule.get("timeouts") or {}).get("request")
        out.append(_seconds(request) if request else None)
    return out


def budget_violations(docs: list[dict], gateway_timeout: float, frontend_timeout: float) -> list[str]:
    """Every timeout on the guarded path that would fire before the hops inside it finish."""
    out: list[str] = []
    policy = _find(docs, "EnvoyExtensionPolicy", EXTPROC_POLICY)
    # One pass through the gateway: every ext_proc entry on the request, then on the response.
    scans = 2 * sum(_seconds(ext["messageTimeout"]) for ext in policy["spec"]["extProc"])

    vertex = _route_request_timeouts(_find(docs, "AIGatewayRoute", AI_ROUTE))
    if None in vertex:
        out.append(f"AIGatewayRoute {AI_ROUTE} leaves a rule on the 60s AI Gateway default; set timeouts.request")
    model_call = scans + max((t for t in vertex if t is not None), default=60.0)
    if gateway_timeout <= model_call:
        out.append(
            f"BurritBot GATEWAY_TIMEOUT_SECONDS {gateway_timeout:g} is not above its gateway pass "
            f"({scans:g}s of ext_proc plus the {AI_ROUTE} route timeout = {model_call:g}s)"
        )

    audience = _route_request_timeouts(_find(docs, "HTTPRoute", AUDIENCE_ROUTE))
    if None in audience:
        out.append(f"HTTPRoute {AUDIENCE_ROUTE} leaves a rule on Envoy's 15s route default; set timeouts.request")
    for seconds in (t if t is not None else 15.0 for t in audience):
        if seconds <= gateway_timeout:
            out.append(
                f"HTTPRoute {AUDIENCE_ROUTE} route timeout {seconds:g}s is not above BurritBot's "
                f"GATEWAY_TIMEOUT_SECONDS {gateway_timeout:g}"
            )
    audience_pass = scans + max(t if t is not None else 15.0 for t in audience)
    if frontend_timeout <= audience_pass:
        out.append(
            f"frontend GUARDED_TIMEOUT_SECONDS {frontend_timeout:g} is not above its gateway pass "
            f"({scans:g}s of ext_proc plus the {AUDIENCE_ROUTE} route timeout = {audience_pass:g}s)"
        )
    return out


def _gateway_timeout() -> float:
    return _load(BURRITBOT_APP, "burritbot_app_timeout_budget").GATEWAY_TIMEOUT_SECONDS


def _frontend() -> ModuleType:
    return _load(FRONTEND_MAIN, "audience_frontend_main_timeout_budget")


@pytest.mark.static
def test_guarded_timeouts_outlast_the_hops_inside_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    violations = budget_violations(_docs(GATEWAY_FILE), _gateway_timeout(), _frontend().GUARDED_TIMEOUT_SECONDS)
    assert not violations, "\n".join(violations)


@pytest.mark.static
def test_frontend_uses_the_guarded_timeout_on_the_guarded_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BURRITBOT_TARGET", "burritbot-guarded")
    frontend = _frontend()
    _, _, timeout = frontend._resolve_target()
    assert timeout == frontend.GUARDED_TIMEOUT_SECONDS


@pytest.mark.static
def test_frontend_keeps_the_unguarded_timeout_on_the_unguarded_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BURRITBOT_TARGET", "burritbot-unguarded")
    frontend = _frontend()
    _, _, timeout = frontend._resolve_target()
    assert timeout == frontend.UNGUARDED_TIMEOUT_SECONDS


def _drop_timeouts(docs: list[dict], kind: str, name: str) -> None:
    for rule in _find(docs, kind, name)["spec"]["rules"]:
        rule.pop("timeouts", None)


def _raise_message_timeouts(docs: list[dict]) -> None:
    for ext in _find(docs, "EnvoyExtensionPolicy", EXTPROC_POLICY)["spec"]["extProc"]:
        ext["messageTimeout"] = "30s"


@pytest.mark.static
@pytest.mark.parametrize(
    ("mutate", "gateway_delta", "frontend_timeout", "expected"),
    [
        (lambda docs: None, 0.0, 10.0, "frontend GUARDED_TIMEOUT_SECONDS 10"),
        (lambda docs: _drop_timeouts(docs, "HTTPRoute", AUDIENCE_ROUTE), 0.0, None, "Envoy's 15s route default"),
        (lambda docs: _drop_timeouts(docs, "AIGatewayRoute", AI_ROUTE), 0.0, None, "60s AI Gateway default"),
        (lambda docs: None, -1000.0, None, "is not above its gateway pass"),
        (lambda docs: None, 1000.0, None, "is not above BurritBot's"),
        (_raise_message_timeouts, 0.0, None, "is not above its gateway pass"),
    ],
    ids=[
        "frontend-10s",
        "audience-route-default",
        "vertex-route-default",
        "gateway-timeout-short",
        "audience-route-short",
        "message-timeouts-raised",
    ],
)
def test_mutation_short_timeout_is_caught(
    monkeypatch: pytest.MonkeyPatch, mutate, gateway_delta: float, frontend_timeout: float | None, expected: str
) -> None:
    monkeypatch.delenv("BURRITBOT_GUARDED", raising=False)
    docs = copy.deepcopy(_docs(GATEWAY_FILE))
    mutate(docs)
    gateway_timeout = max(_gateway_timeout() + gateway_delta, 1.0)
    frontend = frontend_timeout if frontend_timeout is not None else _frontend().GUARDED_TIMEOUT_SECONDS
    violations = budget_violations(docs, gateway_timeout, frontend)
    assert any(expected in v for v in violations), violations
