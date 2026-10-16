# ABOUTME: Static checks that uv.lock holds no version affected by a known Dependabot advisory (#39).
# ABOUTME: Each locked package must sit at or above the first patched release for its advisory.

from __future__ import annotations

import tomllib

import pytest
from packaging.version import Version

from conftest import PROJECT_ROOT


UV_LOCK = PROJECT_ROOT / "uv.lock"

# First patched release per package, from the advisories in issue #39.
# anyio: TLSStream IDNA 2003 host name encoding (critical).
# urllib3: unbounded chunk-size line; HTTPS proxy TLS config ignored (high).
# oauthlib, fsspec, multidict: the medium advisories.
PATCHED = {
    "anyio": "4.14.2",
    "urllib3": "2.8.0",
    "oauthlib": "4.0.0",
    "fsspec": "2026.6.0",
    "multidict": "6.9.1",
}


def _locked_versions() -> dict[str, list[str]]:
    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    versions: dict[str, list[str]] = {}
    for package in lock["package"]:
        versions.setdefault(package["name"], []).append(package["version"])
    return versions


@pytest.mark.static
@pytest.mark.parametrize(("name", "patched"), sorted(PATCHED.items()))
def test_locked_version_is_patched(name: str, patched: str) -> None:
    """Every locked copy of the package is at or above its first patched release."""
    locked = _locked_versions().get(name)
    assert locked, f"{name} is not in uv.lock; drop it from PATCHED if it left the tree"
    stale = [v for v in locked if Version(v) < Version(patched)]
    assert not stale, f"uv.lock pins {name} {stale}; the advisory is fixed in {patched}"
