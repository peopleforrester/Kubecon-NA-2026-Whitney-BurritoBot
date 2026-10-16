# ABOUTME: Static cross-manifest reference checks — resolves every backendRef, parentRef and targetRef
# ABOUTME: across the repo's Kubernetes manifests, then follows Service -> pod -> containerPort.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yaml


# Directories holding Kubernetes manifests that ArgoCD syncs. YAML without
# apiVersion + kind + metadata (Helm values, app config, Kustomizations) is
# not a cluster object and is skipped.
MANIFEST_ROOTS = ("ai-gateway", "apps", "deploy", "gitops", "security", "observability")

GATEWAY_API = "gateway.networking.k8s.io"
AI_GATEWAY = "aigateway.envoyproxy.io"

# Gateway API route kinds: a listener's allowedRoutes governs their parentRefs.
ROUTE_KINDS = {"HTTPRoute", "GRPCRoute", "TLSRoute", "TCPRoute", "UDPRoute"}

# Kinds whose spec.template is a pod template a Service selector can match.
POD_TEMPLATE_KINDS = {
    ("apps", "Deployment"),
    ("apps", "StatefulSet"),
    ("apps", "DaemonSet"),
    ("apps", "ReplicaSet"),
    ("batch", "Job"),
}


@dataclass(frozen=True)
class Manifest:
    path: str  # repo-relative
    doc: dict

    @property
    def group(self) -> str:
        api = self.doc["apiVersion"]
        return api.split("/", 1)[0] if "/" in api else ""

    @property
    def kind(self) -> str:
        return self.doc["kind"]

    @property
    def name(self) -> str:
        return self.doc["metadata"]["name"]

    @property
    def namespace(self) -> str | None:
        return self.doc["metadata"].get("namespace")

    @property
    def label(self) -> str:
        return f"{self.kind} {self.namespace}/{self.name} ({self.path})"


@dataclass(frozen=True)
class Ref:
    """One reference from a manifest to another object, with its defaults applied."""

    source: Manifest
    field: str  # backendRef | parentRef | targetRef
    group: str
    kind: str
    namespace: str | None
    name: str
    port: int | None
    section: str | None = None

    @property
    def target(self) -> str:
        grp = f"{self.group}/" if self.group else ""
        port = f":{self.port}" if self.port is not None else ""
        return f"{grp}{self.kind} {self.namespace}/{self.name}{port}"

    @property
    def key(self) -> str:
        """Stable identity used by known-open registries in the tests."""
        src = self.source
        return f"{src.kind} {src.namespace}/{src.name} {self.field} -> {self.target}"


def load_manifests(root: Path) -> list[Manifest]:
    """Parse every Kubernetes manifest under MANIFEST_ROOTS. Parse errors raise."""
    manifests: list[Manifest] = []
    for top in MANIFEST_ROOTS:
        for path in sorted((root / top).rglob("*.y*ml")):
            with path.open(encoding="utf-8") as fh:
                for doc in yaml.safe_load_all(fh):
                    if isinstance(doc, dict) and {"apiVersion", "kind", "metadata"} <= doc.keys():
                        manifests.append(Manifest(str(path.relative_to(root)), doc))
    return manifests


def _walk(node: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], str, Any]]:
    """Yield (path-to-parent, key, value) for every mapping entry in the tree."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key, value
            yield from _walk(value, path + (key,))
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, path)


def _backend_default(m: Manifest, path: tuple[str, ...]) -> tuple[str, str]:
    """Default (group, kind) for a backendRef that omits them.

    Gateway API's BackendObjectReference defaults to a core Service. The one
    exception in use here: AIGatewayRoute rule backendRefs name an
    AIServiceBackend.
    """
    if m.group == AI_GATEWAY and m.kind == "AIGatewayRoute" and "rules" in path:
        return AI_GATEWAY, "AIServiceBackend"
    return "", "Service"


def collect_refs(manifests: list[Manifest]) -> list[Ref]:
    """Every backendRef(s), parentRefs and targetRef(s) in every manifest."""
    refs: list[Ref] = []
    for m in manifests:
        spec = m.doc.get("spec")
        # ArgoCD Applications carry Helm values, whose keys are not references.
        if not isinstance(spec, dict) or m.group == "argoproj.io":
            continue
        for path, key, value in _walk(spec):
            if key in ("backendRef", "backendRefs"):
                field = "backendRef"
            elif key == "parentRefs":
                field = "parentRef"
            elif key in ("targetRef", "targetRefs"):
                field = "targetRef"
            else:
                continue
            items = value if isinstance(value, list) else [value]
            for ref in items:
                if field == "backendRef":
                    group, kind = _backend_default(m, path)
                elif field == "parentRef":
                    group, kind = GATEWAY_API, "Gateway"
                else:
                    # LocalPolicyTargetReference: group and kind are required.
                    group, kind = ref["group"], ref["kind"]
                refs.append(
                    Ref(
                        source=m,
                        field=field,
                        group=ref.get("group", group),
                        kind=ref.get("kind", kind),
                        # targetRefs are always local to the referrer.
                        namespace=m.namespace if field == "targetRef" else ref.get("namespace", m.namespace),
                        name=ref["name"],
                        port=ref.get("port"),
                        section=ref.get("sectionName"),
                    )
                )
    return refs


def _index(manifests: list[Manifest]) -> dict[tuple[str, str, str | None, str], Manifest]:
    return {(m.group, m.kind, m.namespace, m.name): m for m in manifests}


def unresolved_refs(manifests: list[Manifest]) -> dict[str, str]:
    """References whose target object is defined nowhere in the repo (#24's class)."""
    index = _index(manifests)
    out: dict[str, str] = {}
    for ref in collect_refs(manifests):
        if (ref.group, ref.kind, ref.namespace, ref.name) not in index:
            out[ref.key] = f"{ref.source.label}: {ref.field} {ref.target} resolves to nothing"
    return out


def port_mismatches(manifests: list[Manifest]) -> dict[str, str]:
    """backendRefs whose port is not one the named Service exposes (#23's class)."""
    index = _index(manifests)
    out: dict[str, str] = {}
    for ref in collect_refs(manifests):
        if ref.field != "backendRef" or ref.kind != "Service" or ref.group != "":
            continue
        svc = index.get(("", "Service", ref.namespace, ref.name))
        if svc is None:
            continue  # reported by unresolved_refs
        exposed = [p["port"] for p in svc.doc["spec"].get("ports", [])]
        if ref.port is None:
            out[ref.key] = f"{ref.source.label}: backendRef {ref.target} names no port; Service exposes {exposed}"
        elif ref.port not in exposed:
            out[ref.key] = f"{ref.source.label}: backendRef {ref.target} but the Service exposes {exposed}"
    return out


def _labels_match(selector: dict, labels: dict) -> bool:
    """Evaluate a LabelSelector (matchLabels + matchExpressions) against labels."""
    for k, v in (selector.get("matchLabels") or {}).items():
        if labels.get(k) != v:
            return False
    for expr in selector.get("matchExpressions") or []:
        key, op, values = expr["key"], expr["operator"], expr.get("values") or []
        if op == "In" and labels.get(key) not in values:
            return False
        if op == "NotIn" and key in labels and labels[key] in values:
            return False
        if op == "Exists" and key not in labels:
            return False
        if op == "DoesNotExist" and key in labels:
            return False
        if op not in ("In", "NotIn", "Exists", "DoesNotExist"):
            raise ValueError(f"unsupported LabelSelector operator {op!r}")
    return True


def service_backend_mismatches(manifests: list[Manifest]) -> dict[str, str]:
    """Services that select no pod template, or whose targetPort no selected container serves.

    The next hop after port_mismatches: a backendRef can match the Service's
    port while the Service forwards to a port nothing listens on. Ports are
    resolved from the selected containers, never from the Service itself.
    """
    out: dict[str, str] = {}
    workloads = [m for m in manifests if (m.group, m.kind) in POD_TEMPLATE_KINDS]
    for svc in (m for m in manifests if m.group == "" and m.kind == "Service"):
        selector = svc.doc["spec"].get("selector")
        if not selector:
            continue  # selectorless Services are backed by manual EndpointSlices
        selected = [
            w for w in workloads
            if w.namespace == svc.namespace
            and _labels_match({"matchLabels": selector}, w.doc["spec"]["template"]["metadata"].get("labels") or {})
        ]
        key = f"Service {svc.namespace}/{svc.name}"
        if not selected:
            out[key] = f"{svc.label}: selector {selector} matches no pod template in {svc.namespace}"
            continue
        ports = [
            p
            for w in selected
            for c in w.doc["spec"]["template"]["spec"]["containers"]
            for p in c.get("ports") or []
        ]
        for sp in svc.doc["spec"].get("ports", []):
            target = sp.get("targetPort", sp["port"])
            if isinstance(target, str):
                ok = any(p.get("name") == target for p in ports)
            else:
                ok = any(p.get("containerPort") == target for p in ports)
            if not ok:
                served = [(p.get("name"), p.get("containerPort")) for p in ports]
                out[f"{key}:{sp['port']}"] = (
                    f"{svc.label}: port {sp['port']} targets {target!r}, but the selected "
                    f"containers serve {served}"
                )
    return out


def missing_reference_grants(manifests: list[Manifest]) -> dict[str, str]:
    """Cross-namespace backendRefs with no ReferenceGrant in the target namespace.

    Gateway API refuses a backendRef into another namespace unless a
    ReferenceGrant there names the referrer's group/kind/namespace and the
    target's group/kind (and name, when set). Envoy then has no backend.
    """
    grants = [m for m in manifests if m.group == GATEWAY_API and m.kind == "ReferenceGrant"]
    out: dict[str, str] = {}
    for ref in collect_refs(manifests):
        if ref.field != "backendRef" or ref.namespace == ref.source.namespace:
            continue
        src = ref.source
        allowed = any(
            g.namespace == ref.namespace
            and any(
                f.get("group", "") == src.group and f["kind"] == src.kind and f["namespace"] == src.namespace
                for f in g.doc["spec"]["from"]
            )
            and any(
                t.get("group", "") == ref.group and t["kind"] == ref.kind and t.get("name", ref.name) == ref.name
                for t in g.doc["spec"]["to"]
            )
            for g in grants
        )
        if not allowed:
            out[ref.key] = (
                f"{src.label}: backendRef {ref.target} crosses namespaces with no "
                f"ReferenceGrant in {ref.namespace} permitting {src.kind} from {src.namespace}"
            )
    return out


def _default_route_kinds(protocol: str) -> set[str]:
    return {
        "HTTP": {"HTTPRoute"},
        "HTTPS": {"HTTPRoute"},
        "TLS": {"TLSRoute"},
        "TCP": {"TCPRoute"},
        "UDP": {"UDPRoute"},
    }.get(protocol, set())


def _listener_admits(listener: dict, gateway: Manifest, route: Manifest, namespaces: dict[str, dict]) -> bool:
    allowed = listener.get("allowedRoutes") or {}
    kinds = {k["kind"] for k in allowed.get("kinds") or []} or _default_route_kinds(listener["protocol"])
    if route.kind not in kinds:
        return False
    ns_rule = allowed.get("namespaces") or {}
    origin = ns_rule.get("from", "Same")
    if origin == "All":
        return True
    if origin == "Same":
        return route.namespace == gateway.namespace
    if origin == "Selector":
        ns = namespaces.get(route.namespace)
        if ns is None:
            return False
        return _labels_match(ns_rule["selector"], ns["metadata"].get("labels") or {})
    raise ValueError(f"unsupported allowedRoutes.namespaces.from {origin!r}")


def unattachable_routes(manifests: list[Manifest]) -> dict[str, str]:
    """Route parentRefs that no listener on the named Gateway admits.

    A listener's allowedRoutes (namespace origin + route kinds) decides which
    routes may attach. A route it refuses is never programmed into Envoy.
    """
    index = _index(manifests)
    namespaces = {m.name: m.doc for m in manifests if m.group == "" and m.kind == "Namespace"}
    out: dict[str, str] = {}
    for ref in collect_refs(manifests):
        if ref.field != "parentRef" or ref.source.kind not in ROUTE_KINDS or ref.kind != "Gateway":
            continue
        gw = index.get((GATEWAY_API, "Gateway", ref.namespace, ref.name))
        if gw is None:
            continue  # reported by unresolved_refs
        listeners = [
            ln for ln in gw.doc["spec"]["listeners"]
            if (ref.section is None or ln["name"] == ref.section)
            and (ref.port is None or ln["port"] == ref.port)
        ]
        if not any(_listener_admits(ln, gw, ref.source, namespaces) for ln in listeners):
            out[ref.key] = (
                f"{ref.source.label}: no listener on Gateway {ref.namespace}/{ref.name} "
                f"admits a {ref.source.kind} from namespace {ref.source.namespace}"
            )
    return out
