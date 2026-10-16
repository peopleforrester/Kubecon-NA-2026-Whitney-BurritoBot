# ABOUTME: The container images built from this repo and the uv.lock groups their requirements export from (#78).
# ABOUTME: Parses the exported, hashed requirements.txt format into name -> version pins.

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Image:
    """One image: its Dockerfile, the requirements file it installs, and the uv group behind it."""

    name: str
    dockerfile: Path
    requirements: Path
    group: str


IMAGES = (
    Image(
        "burritbot",
        PROJECT_ROOT / "apps" / "burritbot" / "Dockerfile",
        PROJECT_ROOT / "apps" / "burritbot" / "requirements.txt",
        "image-burritbot",
    ),
    Image(
        "audience-frontend",
        PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "Dockerfile",
        PROJECT_ROOT / "apps" / "audience-frontend" / "backend" / "requirements.txt",
        "image-audience-frontend",
    ),
    Image(
        "burritbot-extproc",
        PROJECT_ROOT / "ai-gateway" / "extproc" / "Dockerfile",
        PROJECT_ROOT / "ai-gateway" / "extproc" / "requirements.txt",
        "image-extproc",
    ),
)

# A requirement line in `uv export` output: `name==version`, an optional
# `; marker`, then the `\` continuation into the --hash lines.
_PIN = re.compile(r"([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;\\]+)")


def export_command(group: str) -> list[str]:
    """The `uv export` call that writes an image's requirements.txt from uv.lock."""
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH; the image requirements are exported from uv.lock with it"
    return [uv, "export", "--frozen", "--only-group", group, "--no-emit-project"]


def export(group: str) -> str:
    """Run `uv export` for one image group and return the requirements text."""
    result = subprocess.run(
        export_command(group),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"uv export --only-group {group} failed:\n{result.stderr}"
    return result.stdout


def requirement_pins(path: Path) -> dict[str, str]:
    """Exact pins in a requirements file, keyed by lower-cased package name."""
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _PIN.match(line)
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins
