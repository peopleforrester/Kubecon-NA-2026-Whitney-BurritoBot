# ABOUTME: Phase A3 test — audience-frontend must ship a Dockerfile + requirements.txt
# ABOUTME: matching the burritbot security pattern (non-root 1001, port 8080, ABOUTME header).

from __future__ import annotations

import pytest

from conftest import PROJECT_ROOT


BACKEND_DIR = PROJECT_ROOT / "apps" / "audience-frontend" / "backend"
DOCKERFILE = BACKEND_DIR / "Dockerfile"
REQUIREMENTS = BACKEND_DIR / "requirements.txt"


@pytest.mark.static
def test_audience_dockerfile_exists() -> None:
    """The audience-frontend image cannot be built without a Dockerfile."""
    assert DOCKERFILE.is_file(), f"missing Dockerfile at {DOCKERFILE}"


@pytest.mark.static
def test_audience_dockerfile_starts_with_aboutme() -> None:
    """All code files must start with two ABOUTME: comments."""
    lines = DOCKERFILE.read_text().splitlines()
    assert len(lines) >= 2, f"{DOCKERFILE} too short"
    assert lines[0].startswith("# ABOUTME:"), (
        f"{DOCKERFILE} line 1 must start with '# ABOUTME:'; got: {lines[0]!r}"
    )
    assert lines[1].startswith("# ABOUTME:"), (
        f"{DOCKERFILE} line 2 must start with '# ABOUTME:'; got: {lines[1]!r}"
    )


@pytest.mark.static
def test_audience_dockerfile_runs_non_root_1001() -> None:
    """Container must run as the non-root burritbot user (uid 1001) for parity."""
    content = DOCKERFILE.read_text()
    assert "1001" in content, "expected uid 1001 in Dockerfile"
    assert "USER " in content, "expected USER directive in Dockerfile"


@pytest.mark.static
def test_audience_dockerfile_exposes_8080() -> None:
    """Audience-frontend Service targets port 8080 — image must expose it."""
    content = DOCKERFILE.read_text()
    assert "EXPOSE 8080" in content, "expected EXPOSE 8080 in Dockerfile"


@pytest.mark.static
def test_audience_requirements_lists_runtime_deps() -> None:
    """requirements.txt must list the deps that backend/main.py actually imports."""
    assert REQUIREMENTS.is_file(), f"missing requirements.txt at {REQUIREMENTS}"
    content = REQUIREMENTS.read_text()
    for dep in ("fastapi", "uvicorn", "httpx", "pydantic", "slowapi"):
        assert dep in content, (
            f"requirements.txt missing '{dep}' (imported by backend/main.py)"
        )
