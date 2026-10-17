# ABOUTME: Who installs the Gateway API CRDs: an ArgoCD-synced Envoy Gateway chart or GKE (gateway_api_config),
# ABOUTME: and which Gateway API bundle GKE installs at the cluster's minimum GKE version.

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import yaml


Files = dict[str, str]  # repo-relative path -> text

# GKE installs this Gateway API release with gateway_api_config, by GKE
# version, newest first ("New clusters and cluster upgrades" table,
# https://docs.cloud.google.com/kubernetes-engine/docs/how-to/gatewayclass-capabilities,
# read 2026-10-17). It serves the standard channel only.
GKE_GATEWAY_API_BUNDLES: tuple[tuple[str, str], ...] = (
    ("1.35.2-gke.1842000", "1.5"),
    ("1.34.1-gke.1822000", "1.4"),
    ("1.33.2-gke.1335000", "1.3"),
    ("1.32.2-gke.1475000", "1.2"),
    ("1.30.2-gke.1783000", "1.1"),
)


def load_files(root: Path) -> Files:
    paths = [
        *sorted((root / "infrastructure" / "terraform").glob("*.tf")),
        *sorted((root / "gitops" / "apps").glob("*.yaml")),
    ]
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8") for p in paths}


def terraform_text(files: Files) -> str:
    """All Terraform in one string, with # comments removed."""
    return "\n".join(
        line.split("#", 1)[0]
        for path, text in files.items()
        if path.endswith(".tf")
        for line in text.splitlines()
    )


def applications(files: Files) -> Iterator[tuple[str, dict]]:
    """(path, Application) for every ArgoCD Application under gitops/apps."""
    for path, text in files.items():
        if not path.startswith("gitops/apps/"):
            continue
        for doc in yaml.safe_load_all(text):
            if doc and doc.get("kind") == "Application":
                yield path, doc


def _values(app: dict) -> dict:
    return ((app["spec"].get("source") or {}).get("helm") or {}).get("valuesObject") or {}


def gateway_api_chart_owners(files: Files) -> list[str]:
    """Applications whose chart renders the Gateway API CRDs, with the chart defaults applied:
    gateway-helm's crds subchart is on unless crds.enabled is false, gateway-crds-helm's
    Gateway API CRDs are off unless crds.gatewayAPI.enabled is true."""
    owners = []
    for path, app in applications(files):
        chart = (app["spec"].get("source") or {}).get("chart")
        crds = _values(app).get("crds") or {}
        if chart == "gateway-helm" and crds.get("enabled", True):
            owners.append(f"{path} (gateway-helm crds.enabled)")
        if chart == "gateway-crds-helm" and (crds.get("gatewayAPI") or {}).get("enabled", False):
            owners.append(f"{path} (gateway-crds-helm crds.gatewayAPI.enabled)")
    return owners


def gke_manages_gateway_api(files: Files) -> bool:
    """gateway_api_config with a channel other than CHANNEL_DISABLED."""
    return bool(re.search(r'gateway_api_config\s*{[^}]*channel\s*=\s*"CHANNEL_(?!DISABLED")', terraform_text(files)))


def gke_min_master_version(files: Files) -> str | None:
    match = re.search(r'min_master_version\s*=\s*"([^"]+)"', terraform_text(files))
    return match.group(1) if match else None


def gke_version_key(version: str) -> tuple[int, ...]:
    """1.34.1-gke.1822000 -> (1, 34, 1, 1822000). A short version such as
    "1.34" lets GKE pick any 1.34 patch, so its missing parts count as 0."""
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?(?:-gke\.(\d+))?", version)
    assert match, f"not a GKE version: {version!r}"
    return tuple(int(p or 0) for p in match.groups())


def gke_bundle_for(version: str) -> str | None:
    """The Gateway API release GKE installs at this GKE version, or None below the table."""
    for since, bundle in GKE_GATEWAY_API_BUNDLES:
        if gke_version_key(version) >= gke_version_key(since):
            return bundle
    return None


def gke_floor_for(release: str) -> str:
    """The oldest GKE version whose Gateway API bundle is at least this release."""
    key = tuple(int(p) for p in release.split("."))
    eligible = [since for since, bundle in GKE_GATEWAY_API_BUNDLES if tuple(int(p) for p in bundle.split(".")) >= key]
    assert eligible, f"no GKE version in the table installs Gateway API v{release}+"
    return min(eligible, key=gke_version_key)


def owner_problems(files: Files, floor: str) -> list[str]:
    """Empty when exactly one party installs the Gateway API CRDs, and, when it is GKE,
    the cluster's minimum GKE version installs a bundle at or above `floor`."""
    owners = gateway_api_chart_owners(files)
    gke = gke_manages_gateway_api(files)
    if gke:
        owners.append("infrastructure/terraform (gateway_api_config)")
    if len(owners) != 1:
        return [f"Gateway API CRDs need exactly one owner, found {len(owners)}: {owners}"]
    if not gke:
        return []
    version = gke_min_master_version(files)
    if version is None:
        return [
            "GKE installs the Gateway API CRDs but min_master_version is unset; the bundle follows "
            f"the GKE version, and the manifests need v{floor}+ (GKE {gke_floor_for(floor)}+)"
        ]
    bundle = gke_bundle_for(version)
    if bundle is None or tuple(int(p) for p in bundle.split(".")) < tuple(int(p) for p in floor.split(".")):
        served = f"Gateway API v{bundle}" if bundle else "a Gateway API release older than the table"
        return [f"min_master_version {version} installs {served}, the manifests need v{floor}+ (GKE {gke_floor_for(floor)}+)"]
    return []
