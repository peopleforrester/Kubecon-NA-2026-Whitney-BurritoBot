# ABOUTME: Static checks that the BurritBot runtime pins agree everywhere they are recorded (#55).
# ABOUTME: A partial bump of fastapi, google-genai or OpenTelemetry fails here before it ships.

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT
from helpers.image_requirements import requirement_pins


BURRITBOT_REQUIREMENTS = PROJECT_ROOT / "apps" / "burritbot" / "requirements.txt"
AUDIENCE_REQUIREMENTS = PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "requirements.txt"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
UV_LOCK = PROJECT_ROOT / "uv.lock"
AGENTS_MD = PROJECT_ROOT / "AGENTS.md"
PHASE_06_SPEC = PROJECT_ROOT / "spec" / "phases" / "phase-06-burritbot.md"

# The image installs apps/burritbot/requirements.txt, so it is the reference.
PINNED = (
    "fastapi",
    "google-genai",
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-instrumentation-fastapi",
)


def _exact_pins(lines: list[str]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==(\S+)\s*", line)
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def _requirements(path: Path) -> dict[str, str]:
    # The image files are `uv export` output (#78): pins carry hashes and markers.
    return requirement_pins(path)


def _image_pins() -> dict[str, str]:
    pins = _requirements(BURRITBOT_REQUIREMENTS)
    missing = [name for name in PINNED if name not in pins]
    assert not missing, f"apps/burritbot/requirements.txt has no exact pin for {missing}"
    return pins


@pytest.mark.static
@pytest.mark.parametrize("name", PINNED)
def test_dev_group_matches_image(name: str) -> None:
    """pyproject.toml's dev group pins the same version the image installs."""
    dev = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    assert _exact_pins(dev).get(name) == _image_pins()[name], (
        f"pyproject.toml pins {name} {_exact_pins(dev).get(name)}, "
        f"the image pins {_image_pins()[name]}"
    )


@pytest.mark.static
@pytest.mark.parametrize("name", PINNED)
def test_lock_matches_image(name: str) -> None:
    """uv.lock resolves the same version the image installs."""
    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    locked = [p["version"] for p in lock["package"] if p["name"] == name]
    assert locked == [_image_pins()[name]], (
        f"uv.lock has {name} {locked}, the image pins {_image_pins()[name]}"
    )


@pytest.mark.static
def test_otlp_exporter_matches_otel_api() -> None:
    """The OTLP exporter moves in lockstep with opentelemetry-api."""
    pins = _image_pins()
    assert pins.get("opentelemetry-exporter-otlp") == pins["opentelemetry-api"], (
        "opentelemetry-exporter-otlp and opentelemetry-api are pinned to different releases"
    )


@pytest.mark.static
def test_audience_backend_fastapi_matches_image() -> None:
    """Both FastAPI services ship the same fastapi release."""
    assert _requirements(AUDIENCE_REQUIREMENTS).get("fastapi") == _image_pins()["fastapi"]


@pytest.mark.static
def test_critical_versions_match_image() -> None:
    """AGENTS.md Critical Versions record the versions the image installs."""
    pins = _image_pins()
    text = AGENTS_MD.read_text(encoding="utf-8")
    otel = (
        f"OTel Python (`opentelemetry-api`/`sdk`): {pins['opentelemetry-api']} "
        f"(`-instrumentation-*`: {pins['opentelemetry-instrumentation-fastapi']})"
    )
    assert otel in text, f"AGENTS.md Critical Versions do not say: {otel}"
    genai = f"via `google-genai` {pins['google-genai']}"
    assert genai in text, f"AGENTS.md Critical Versions do not say: {genai}"


@pytest.mark.static
def test_phase_06_spec_matches_image() -> None:
    """The phase-06 spec names the google-genai and FastAPI lines the image installs."""
    pins = _image_pins()
    text = PHASE_06_SPEC.read_text(encoding="utf-8")
    assert f"`google-genai` {pins['google-genai']}" in text, (
        f"spec/phases/phase-06-burritbot.md does not name google-genai {pins['google-genai']}"
    )
    minor = ".".join(pins["fastapi"].split(".")[:2])
    assert f"FastAPI {minor}.x" in text, (
        f"spec/phases/phase-06-burritbot.md does not name FastAPI {minor}.x"
    )
