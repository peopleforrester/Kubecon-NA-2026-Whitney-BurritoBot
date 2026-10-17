# ABOUTME: Checks that every image installs a hashed requirements file exported from uv.lock (#78).
# ABOUTME: Transitive packages are pinned by the lock, not resolved by pip at docker build time.

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT
from helpers.image_requirements import (
    DERIVED_IMAGES,
    IMAGES,
    Image,
    export,
    export_command,
    requirement_pins,
)


PYPROJECT = PROJECT_ROOT / "pyproject.toml"
UV_LOCK = PROJECT_ROOT / "uv.lock"

# The transitive packages issue #78 names, per image that pulls them in.
NAMED_TRANSITIVES = {
    "burritbot": ("starlette", "anyio", "urllib3", "protobuf"),
    "audience-frontend": ("starlette", "anyio"),
}


def _image_id(image: Image) -> str:
    return image.name


def _locked_versions() -> dict[str, str]:
    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    versions: dict[str, list[str]] = {}
    for package in lock["package"]:
        versions.setdefault(package["name"], []).append(package["version"])
    # The image groups resolve with the dev group, so each package has one version.
    split = {name: v for name, v in versions.items() if len(v) > 1}
    assert not split, f"uv.lock forks these packages across groups: {split}"
    return {name: v[0] for name, v in versions.items()}


def _pip_installs(dockerfile: Path) -> list[str]:
    text = dockerfile.read_text(encoding="utf-8").replace("\\\n", " ")
    return [line for line in text.splitlines() if re.search(r"\bpip\b.*\binstall\b", line)]


@pytest.mark.static
def test_every_dockerfile_is_a_known_image() -> None:
    """A new Dockerfile has to join IMAGES (or DERIVED_IMAGES), so its pins are checked."""
    found = {
        path
        for path in PROJECT_ROOT.rglob("Dockerfile")
        if not any(part.startswith(".") for part in path.relative_to(PROJECT_ROOT).parts)
    }
    known = {image.dockerfile for image in IMAGES} | {image.dockerfile for image in DERIVED_IMAGES}
    assert found == known, (
        f"Dockerfiles not in helpers.image_requirements IMAGES or DERIVED_IMAGES: "
        f"{sorted(str(p.relative_to(PROJECT_ROOT)) for p in found ^ known)}"
    )


@pytest.mark.static
@pytest.mark.parametrize("image", IMAGES, ids=_image_id)
def test_image_group_is_declared(image: Image) -> None:
    """Each image's top-level packages live in their own pyproject.toml dependency group."""
    groups = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["dependency-groups"]
    assert groups.get(image.group), f"pyproject.toml has no [dependency-groups] {image.group}"


@pytest.mark.static
@pytest.mark.parametrize("image", IMAGES, ids=_image_id)
def test_requirements_are_the_uv_export(image: Image) -> None:
    """The checked-in requirements.txt is exactly `uv export` of the image group."""
    expected = export(image.group)
    actual = image.requirements.read_text(encoding="utf-8")
    assert actual == expected, (
        f"{image.requirements.relative_to(PROJECT_ROOT)} is stale against uv.lock; "
        "regenerate it with scripts/export-image-requirements.sh"
    )


@pytest.mark.static
@pytest.mark.parametrize("image", IMAGES, ids=_image_id)
def test_every_installed_package_is_locked(image: Image) -> None:
    """Each package the image installs is in uv.lock at the same version, so #39 covers it."""
    locked = _locked_versions()
    pins = requirement_pins(image.requirements)
    assert pins, f"{image.requirements.relative_to(PROJECT_ROOT)} pins nothing"
    drift = {name: (v, locked.get(name)) for name, v in pins.items() if locked.get(name) != v}
    assert not drift, f"{image.name} installs versions uv.lock does not hold: {drift}"


@pytest.mark.static
@pytest.mark.parametrize("image", IMAGES, ids=_image_id)
def test_every_requirement_is_hashed(image: Image) -> None:
    """Every requirement carries at least one sha256, so pip runs in hash-checking mode."""
    text = image.requirements.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9])", text)
    unhashed = [
        block.split()[0]
        for block in blocks
        if re.match(r"[A-Za-z0-9]", block) and "--hash=sha256:" not in block
    ]
    assert not unhashed, f"{image.name} requirements without a hash: {unhashed}"


@pytest.mark.static
@pytest.mark.parametrize(
    ("image", "name"),
    [(image, name) for image in IMAGES for name in NAMED_TRANSITIVES.get(image.name, ())],
    ids=lambda value: value.name if isinstance(value, Image) else value,
)
def test_named_transitives_are_pinned(image: Image, name: str) -> None:
    """The transitive packages the issue names are pinned in the image, not left to pip."""
    assert name in requirement_pins(image.requirements), (
        f"{image.name} does not pin {name}; pip would resolve it at build time"
    )


@pytest.mark.static
@pytest.mark.parametrize("image", IMAGES, ids=_image_id)
def test_dockerfile_installs_with_hash_checking_and_no_resolution(image: Image) -> None:
    """The one pip install takes the exported file with --require-hashes and --no-deps."""
    installs = _pip_installs(image.dockerfile)
    assert len(installs) == 1, f"{image.name} Dockerfile has {len(installs)} pip installs: {installs}"
    (install,) = installs
    for flag in ("--require-hashes", "--no-deps"):
        assert flag in install, f"{image.name} Dockerfile pip install lacks {flag}: {install}"
    assert re.search(r"-r \S*requirements\.txt\b", install), (
        f"{image.name} Dockerfile pip install does not read requirements.txt: {install}"
    )


@pytest.mark.live
@pytest.mark.timeout(900)
@pytest.mark.parametrize("image", IMAGES, ids=_image_id)
def test_requirements_install_without_resolution(image: Image, tmp_path: Path) -> None:
    """The image's pip install, run in a clean Python 3.13 venv from PyPI, gives a consistent set."""
    uv = export_command(image.group)[0]
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", "--python", "3.13", "--seed", str(venv)], check=True)
    pip = str(venv / "bin" / "pip")
    install = subprocess.run(
        [pip, "install", "--no-cache-dir", "--no-deps", "--require-hashes", "-r", str(image.requirements)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, f"{image.name} install failed:\n{install.stdout}\n{install.stderr}"
    check = subprocess.run([pip, "check"], capture_output=True, text=True, check=False)
    assert check.returncode == 0, f"{image.name} is missing dependencies:\n{check.stdout}{check.stderr}"
