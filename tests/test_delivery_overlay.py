# ABOUTME: The active delivery's overlay writes its slug into every Vertex AI call's cost labels (#82, question 152):
# ABOUTME: unguarded BurritBot's env and the AI gateway's labels bodyMutation; NeMo has no model to label (#112).

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from conftest import PROJECT_ROOT
from helpers.cost_labels import (
    DELIVERY_LABEL,
    PRESENTATIONS,
    event_of,
    runbook_slug,
    terraform_cost_labels,
)
from helpers.manifest_graph import kustomization_files, load_manifests


GITOPS_APPS = PROJECT_ROOT / "gitops" / "apps"
BURRITBOT_APP = PROJECT_ROOT / "apps" / "burritbot" / "app.py"
BASE_UNGUARDED = PROJECT_ROOT / "apps" / "burritbot" / "k8s" / "deployment-unguarded.yaml"

# Application name → the platform kustomization its delivery overlay wraps.
LABELLED_APPS = {"burritbot": "deploy/burritbot", "ai-gateway": "deploy/ai-gateway"}

# What the base carries where a manifest needs a literal. Longer than a label
# value may be, so a sync without an overlay is refused, never mislabelled.
PLACEHOLDER = "unset-the-delivery-overlay-under-presentations-sets-burritbot-io-delivery"
DELIVERY_ENV = "BURRITBOT_DELIVERY"


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _application(name: str) -> dict:
    for path in sorted(GITOPS_APPS.glob("*.yaml")):
        for doc in _docs(path):
            if doc.get("kind") == "Application" and doc["metadata"]["name"] == name:
                return doc
    raise AssertionError(f"no Application {name} in gitops/apps")


def _overlay(name: str) -> Path:
    return PROJECT_ROOT / _application(name)["spec"]["source"]["path"]


def _patch(name: str, kind: str) -> dict:
    """The one patch of kind the overlay synced by Application name lists."""
    directory = _overlay(name)
    kustomization = yaml.safe_load((directory / "kustomization.yaml").read_text(encoding="utf-8"))
    found = [
        doc
        for entry in kustomization.get("patches") or []
        for doc in _docs(directory / entry["path"])
        if doc["kind"] == kind
    ]
    assert len(found) == 1, f"{directory} has {len(found)} {kind} patches, expected one"
    return found[0]


def _slug(name: str) -> str:
    return runbook_slug(event_of(_overlay(name)))


def _gateway_labels(backend: dict) -> dict[str, str]:
    sets = [s for s in backend["spec"]["bodyMutation"]["set"] if s["path"] == "labels"]
    assert len(sets) == 1, f"expected one labels bodyMutation, got {sets}"
    return json.loads(sets[0]["value"])


def _load_app(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, BURRITBOT_APP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the overlay is what syncs, and it sits with its delivery ---------------


@pytest.mark.static
@pytest.mark.parametrize("name,base", sorted(LABELLED_APPS.items()))
def test_application_syncs_a_delivery_overlay_of_the_platform(name: str, base: str) -> None:
    overlay = _overlay(name)
    assert overlay.resolve().is_relative_to(PRESENTATIONS.resolve()), (
        f"Application {name} syncs {overlay}, not a delivery overlay under presentations/<event>/deploy/"
    )
    assert overlay.relative_to(PRESENTATIONS / event_of(overlay)).parts == ("deploy", name)
    kustomization = yaml.safe_load((overlay / "kustomization.yaml").read_text(encoding="utf-8"))
    resources = [(overlay / r).resolve() for r in kustomization.get("resources") or []]
    assert resources == [(PROJECT_ROOT / base).resolve()], (
        f"{overlay} must wrap {base} and nothing else; it lists {kustomization.get('resources')}"
    )


@pytest.mark.static
def test_ai_gateway_overlay_patches_only_the_gateway_backend() -> None:
    """No NeMo model is left to label (#112, question 207), so the overlay patches the gateway alone."""
    kustomization = yaml.safe_load((_overlay("ai-gateway") / "kustomization.yaml").read_text(encoding="utf-8"))
    assert [entry["path"] for entry in kustomization["patches"]] == ["delivery-vertex-backend.yaml"]


@pytest.mark.static
@pytest.mark.parametrize("name", sorted(LABELLED_APPS))
def test_every_patch_targets_an_object_the_base_renders(name: str) -> None:
    """kustomize fails the build on a patch that matches nothing; catch it before ArgoCD does."""
    overlay = _overlay(name)
    rendered = kustomization_files(PROJECT_ROOT, PROJECT_ROOT / LABELLED_APPS[name])
    objects = {
        (m.kind, m.namespace, m.name) for m in load_manifests(PROJECT_ROOT) if m.path in rendered
    }
    kustomization = yaml.safe_load((overlay / "kustomization.yaml").read_text(encoding="utf-8"))
    for entry in kustomization["patches"]:
        for doc in _docs(overlay / entry["path"]):
            key = (doc["kind"], doc["metadata"].get("namespace"), doc["metadata"]["name"])
            assert key in objects, f"{overlay / entry['path']} patches {key}, which {LABELLED_APPS[name]} does not render"


# --- the two call sites carry the runbook's slug -----------------------------


@pytest.mark.static
def test_unguarded_burritbot_gets_the_delivery_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    patch = _patch("burritbot", "Deployment")
    assert patch["metadata"]["namespace"] == "burritbot-unguarded"
    containers = {c["name"]: c for c in patch["spec"]["template"]["spec"]["containers"]}
    env = {e["name"]: e.get("value") for e in containers["burritbot"]["env"]}
    slug = _slug("burritbot")
    assert env.get(DELIVERY_ENV) == slug, f"{DELIVERY_ENV} is {env.get(DELIVERY_ENV)!r}, the runbook applies {slug!r}"

    monkeypatch.setenv(DELIVERY_ENV, slug)
    assert _load_app("burritbot_app_overlay_slug").request_labels() == terraform_cost_labels(slug)


@pytest.mark.static
def test_gateway_vertex_calls_get_the_delivery_labels() -> None:
    labels = _gateway_labels(_patch("ai-gateway", "AIServiceBackend"))
    assert labels == terraform_cost_labels(_slug("ai-gateway"))


# --- without an overlay, model calls are refused, never mislabelled ----------


@pytest.mark.static
def test_base_carries_a_placeholder_no_label_accepts(monkeypatch: pytest.MonkeyPatch) -> None:
    assert len(PLACEHOLDER) > 63, "the placeholder must be too long for a GCP label value"
    expected = terraform_cost_labels(PLACEHOLDER)
    backend = next(d for d in _docs(PROJECT_ROOT / "ai-gateway" / "envoy" / "vertex-ai-backend.yaml")
                   if d["kind"] == "AIServiceBackend")
    assert _gateway_labels(backend) == expected

    monkeypatch.setenv(DELIVERY_ENV, PLACEHOLDER)
    with pytest.raises(RuntimeError, match="not a GCP label value"):
        _load_app("burritbot_app_placeholder").request_labels()


@pytest.mark.static
def test_base_unguarded_deployment_leaves_the_delivery_to_the_overlay() -> None:
    container = _docs(BASE_UNGUARDED)[0]["spec"]["template"]["spec"]["containers"][0]
    assert DELIVERY_ENV not in {e["name"] for e in container.get("env", [])}


@pytest.mark.static
def test_platform_tree_names_no_delivery_slug() -> None:
    """The slug lives in the overlay; the platform manifests stay event-neutral."""
    slug = _slug("burritbot")
    for top in ("ai-gateway", "apps", "deploy"):
        for path in sorted((PROJECT_ROOT / top).rglob("*.y*ml")):
            assert slug not in path.read_text(encoding="utf-8"), f"{path} names the delivery slug {slug}"


# --- live: kustomize renders the labels the way the patches claim ------------


@pytest.mark.live
@pytest.mark.parametrize("name", sorted(LABELLED_APPS))
def test_kustomize_renders_the_delivery_labels(name: str) -> None:
    kubectl = shutil.which("kubectl")
    assert kubectl, "kubectl is not on PATH; this check renders the overlay with `kubectl kustomize`"
    result = subprocess.run(
        [kubectl, "kustomize", str(_overlay(name))], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"kubectl kustomize {_overlay(name)} failed: {result.stderr}"
    docs = [d for d in yaml.safe_load_all(result.stdout) if d]
    slug = _slug(name)
    assert PLACEHOLDER not in result.stdout, f"the rendered {name} overlay still carries the placeholder"
    if name == "burritbot":
        deployment = next(d for d in docs if d["kind"] == "Deployment"
                          and d["metadata"]["namespace"] == "burritbot-unguarded")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        env = {e["name"]: e.get("value") for e in container["env"]}
        assert env[DELIVERY_ENV] == slug
        assert "MODEL_NAME" in env, "the patch replaced the base env instead of merging into it"
    else:
        backend = next(d for d in docs if d["kind"] == "AIServiceBackend")
        assert _gateway_labels(backend)[DELIVERY_LABEL] == slug
