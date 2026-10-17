# ABOUTME: Static cross-manifest reference checks — resolves every backendRef, parentRef and targetRef
# ABOUTME: across the repo's Kubernetes manifests, then follows Service -> pod -> containerPort.

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


# Directories holding Kubernetes manifests that ArgoCD syncs. YAML without
# apiVersion + kind + metadata (Helm values, app config, Kustomizations) is
# not a cluster object and is skipped.
MANIFEST_ROOTS = ("ai-gateway", "apps", "deploy", "gitops", "security", "observability")

GATEWAY_API = "gateway.networking.k8s.io"
AI_GATEWAY = "aigateway.envoyproxy.io"

# Gateway API route kinds: a listener's allowedRoutes governs their parentRefs.
ROUTE_KINDS = {"HTTPRoute", "GRPCRoute", "TLSRoute", "TCPRoute", "UDPRoute"}

# Kinds whose controller generates a route of another kind, with the same
# name, namespace and parentRefs. The listener admits the generated route.
GENERATED_ROUTE_KINDS = {(AI_GATEWAY, "AIGatewayRoute"): "HTTPRoute"}

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


# File names ArgoCD's tool detection takes as a Kustomize source.
KUSTOMIZATION_NAMES = ("kustomization.yaml", "kustomization.yml", "Kustomization")


def _kustomization_resources(directory: Path) -> Iterator[tuple[Path, str, Path]]:
    """(kustomization dir, resource entry, resolved target) for every resource, following nested ones.

    A resource that is a directory must hold its own kustomization.yaml, as
    kustomize requires. A resource that names nothing raises: kustomize build
    would fail the same way, and the sync with it.
    """
    with (directory / "kustomization.yaml").open(encoding="utf-8") as fh:
        kustomization = yaml.safe_load(fh)
    for resource in kustomization.get("resources") or []:
        target = (directory / resource).resolve()
        if not target.exists():
            raise FileNotFoundError(f"{directory / 'kustomization.yaml'}: resource {resource!r} does not exist")
        yield directory, resource, target
        if target.is_dir():
            yield from _kustomization_resources(target)


def _app_source_paths(manifests: list[Manifest]) -> Iterator[tuple[Manifest, dict]]:
    """(Application, source) for every source of every Application, single- or multi-source."""
    for app in manifests:
        if app.group != "argoproj.io" or app.kind != "Application":
            continue
        spec = app.doc["spec"]
        for source in [spec["source"]] if "source" in spec else spec.get("sources") or []:
            yield app, source


def _kustomize_roots(root: Path, manifests: list[Manifest]) -> Iterator[tuple[Manifest, dict, Path]]:
    """(Application, source, directory) for every source path that holds a kustomization.yaml."""
    for app, source in _app_source_paths(manifests):
        path = source.get("path")
        if path and (root / path / "kustomization.yaml").is_file():
            yield app, source, root / path


def kustomization_files(root: Path, directory: Path) -> set[str]:
    """Repo-relative files the kustomization in directory renders, nested kustomizations included."""
    resolved = root.resolve()
    return {
        str(target.relative_to(resolved))
        for _, _, target in _kustomization_resources(directory)
        if target.is_file()
    }


def kustomized_paths(root: Path, manifests: list[Manifest]) -> set[str]:
    """Repo-relative files that an ArgoCD Application syncs through a Kustomization.

    Applications whose source path holds a kustomization.yaml render exactly
    its resources; any other file in the repo is never applied by them.
    Helm-chart Applications (no path) contribute nothing. Directory sources
    are not counted here; synced_paths is everything ArgoCD applies.
    """
    resolved = root.resolve()
    return {
        path
        for _, _, directory in _kustomize_roots(resolved, manifests)
        for path in kustomization_files(resolved, directory)
    }


# File names a Directory source reads (reposerver manifestFile), and the
# marker that makes it pass a file over.
DIRECTORY_MANIFEST = re.compile(r"^.*\.(yaml|yml|json|jsonnet)$")
SKIP_RENDERING_MARKER = "+argocd:skip-file-rendering"

# Source blocks that set the type explicitly, as ArgoCD's ExplicitType reads them.
EXPLICIT_SOURCE_TYPES = {"directory": "Directory", "helm": "Helm", "kustomize": "Kustomize", "plugin": "Plugin"}


def _glob_regex(pattern: str) -> str:
    """Translate a gobwas/glob pattern compiled with no separators into a regex.

    ArgoCD's glob.Match(include, relPath) passes no separators, so `*` and
    `**` both match any run of characters, `/` included. A pattern that does
    not compile raises: ArgoCD would log it and match nothing.
    """
    out: list[str] = []
    depth = 0
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            if i + 1 == len(pattern):
                raise ValueError(f"glob {pattern!r} ends in an escape")
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if c == "*":
            out.append(".*")
        elif c == "?":
            out.append(".")
        elif c == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                raise ValueError(f"glob {pattern!r} has an unclosed [")
            body = pattern[i + 1:end]
            negate = body.startswith("!")
            body = body[1:] if negate else body
            if not body:
                raise ValueError(f"glob {pattern!r} has an empty character class")
            chars = "".join(ch if ch == "-" else re.escape(ch) for ch in body)
            out.append(f"[{'^' if negate else ''}{chars}]")
            i = end
        elif c == "{":
            out.append("(?:")
            depth += 1
        elif c == "," and depth:
            out.append("|")
        elif c == "}" and depth:
            out.append(")")
            depth -= 1
        else:
            out.append(re.escape(c))
        i += 1
    if depth:
        raise ValueError(f"glob {pattern!r} has an unclosed {{")
    return "".join(out)


def glob_match(pattern: str, text: str) -> bool:
    """ArgoCD's glob.Match(pattern, text) for a directory source's include or exclude."""
    return re.fullmatch(_glob_regex(pattern), text, re.DOTALL) is not None


def source_type(root: Path, source: dict) -> str | None:
    """The type ArgoCD gives an Application source, or None for a chart from a Helm repository.

    An explicit directory/helm/kustomize/plugin block wins; two of them is an
    error, as in ArgoCD. Otherwise the path is detected: a kustomization file
    makes it Kustomize, a Chart.yaml Helm, anything else Directory.
    """
    path = source.get("path")
    if "chart" in source or not path:
        return None
    explicit = [t for key, t in EXPLICIT_SOURCE_TYPES.items() if source.get(key) is not None]
    if len(explicit) > 1:
        raise ValueError(f"source {path!r} sets multiple application source types: {explicit}")
    if explicit:
        return explicit[0]
    directory = root / path
    if any((directory / n).is_file() for n in KUSTOMIZATION_NAMES):
        return "Kustomize"
    if (directory / "Chart.yaml").is_file():
        return "Helm"
    return "Directory"


def directory_files(root: Path, path: str, directory: dict) -> set[str]:
    """Repo-relative files a Directory source on path reads, as ArgoCD's reposerver walks it.

    Subdirectories only with recurse; only manifest extensions unless
    disableExtensionFilter; exclude and include are globs on the path
    relative to the source path; files carrying the skip marker are passed
    over. A path that names no directory raises, as the sync would fail.
    """
    resolved = root.resolve()
    top = resolved / path
    if not top.is_dir():
        raise FileNotFoundError(f"directory source path {path!r} does not exist under {resolved}")
    include = directory.get("include") or ""
    exclude = directory.get("exclude") or ""
    out: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(top):
        if not directory.get("recurse"):
            dirnames.clear()
        for name in filenames:
            if not directory.get("disableExtensionFilter") and not DIRECTORY_MANIFEST.match(name):
                continue
            file = Path(dirpath) / name
            rel = file.relative_to(top).as_posix()
            if exclude and glob_match(exclude, rel):
                continue
            if include and not glob_match(include, rel):
                continue
            if SKIP_RENDERING_MARKER in file.read_text(encoding="utf-8"):
                continue
            out.add(file.relative_to(resolved).as_posix())
    return out


def synced_paths(root: Path, manifests: list[Manifest]) -> set[str]:
    """Repo-relative files that some ArgoCD Application applies, Kustomize and Directory sources alike.

    A Kustomize source renders exactly its kustomization's resources; a
    Directory source reads the files directory_files finds. Helm sources,
    local charts included, contribute nothing: their templates are not
    cluster manifests until rendered. A plugin source raises, since what it
    renders cannot be read from the repo.
    """
    resolved = root.resolve()
    out: set[str] = set()
    for app, source in _app_source_paths(manifests):
        kind = source_type(resolved, source)
        if kind == "Kustomize":
            out |= kustomization_files(resolved, resolved / source["path"])
        elif kind == "Directory":
            out |= directory_files(resolved, source["path"], source.get("directory") or {})
        elif kind == "Plugin":
            raise ValueError(f"{app.label}: plugin sources are not modelled")
    return out


def unsynced_manifests(manifests: list[Manifest], synced: set[str]) -> dict[str, str]:
    """Cluster manifests in the repo that no ArgoCD Application applies, keyed "path: Kind namespace/name"."""
    return {
        f"{m.path}: {m.kind} {m.namespace}/{m.name}": f"{m.label}: no ArgoCD Application syncs {m.path}"
        for m in manifests
        if m.path not in synced
    }


def directory_typed_kustomizations(root: Path, manifests: list[Manifest]) -> dict[str, str]:
    """Applications that set source.directory on a path ArgoCD would otherwise build with kustomize (#76).

    ArgoCD takes an explicitly configured source type before detecting one, so
    a directory: block makes the source plain Directory. The kustomization is
    then read as a manifest, never built, and none of its resources sync.
    """
    resolved = root.resolve()
    out: dict[str, str] = {}
    for app, source in _app_source_paths(manifests):
        path = source.get("path")
        if not path or "directory" not in source:
            continue
        found = [n for n in KUSTOMIZATION_NAMES if (resolved / path / n).is_file()]
        if found:
            out[f"Application {app.name}"] = (
                f"{app.label}: source.directory forces the Directory type on {path}, "
                f"so its {found[0]} is never built"
            )
    return out


def load_restrictor_relaxed(build_options: str) -> bool:
    """True when kustomize build options lift the default LoadRestrictionsRootOnly."""
    args = build_options.replace("=", " ").split()
    return any(a == "--load-restrictor" and b == "LoadRestrictionsNone" for a, b in zip(args, args[1:]))


def files_outside_kustomization_root(root: Path, manifests: list[Manifest]) -> dict[str, str]:
    """File resources a synced Kustomization lists from outside its own directory (#76).

    kustomize's default LoadRestrictionsRootOnly refuses a file that is not in
    or below the kustomization's directory, and the whole build fails. A
    directory holding its own kustomization.yaml may sit anywhere.
    """
    resolved = root.resolve()
    out: dict[str, str] = {}
    for _, _, top in _kustomize_roots(resolved, manifests):
        for directory, resource, target in _kustomization_resources(top):
            if target.is_file() and not target.is_relative_to(directory.resolve()):
                kustomization = (directory / "kustomization.yaml").resolve().relative_to(resolved)
                out[f"{kustomization}: {resource}"] = (
                    f"{kustomization} lists the file {resource}, outside its root; "
                    f"kustomize refuses it under LoadRestrictionsRootOnly"
                )
    return out


def unsynced_reference_grants(manifests: list[Manifest], synced: set[str]) -> dict[str, str]:
    """ReferenceGrants defined in the repo but applied by no ArgoCD Application (synced_paths).

    missing_reference_grants reads every YAML file, so a grant dropped from
    its kustomization still satisfies it while ArgoCD never applies the
    grant, and the route reports RefNotPermitted on the cluster.
    """
    return {
        f"ReferenceGrant {m.namespace}/{m.name}": (
            f"{m.label}: no ArgoCD Application syncs {m.path}, so the grant never reaches the cluster"
        )
        for m in manifests
        if m.group == GATEWAY_API and m.kind == "ReferenceGrant" and m.path not in synced
    }


def _default_route_kinds(protocol: str) -> set[str]:
    return {
        "HTTP": {"HTTPRoute"},
        "HTTPS": {"HTTPRoute"},
        "TLS": {"TLSRoute"},
        "TCP": {"TCPRoute"},
        "UDP": {"UDPRoute"},
    }.get(protocol, set())


def _attaching_kind(route: Manifest) -> str | None:
    """The route kind a listener sees for this manifest, or None if it is no route."""
    if route.kind in ROUTE_KINDS:
        return route.kind
    return GENERATED_ROUTE_KINDS.get((route.group, route.kind))


def _listener_admits(listener: dict, gateway: Manifest, route: Manifest, namespaces: dict[str, dict]) -> bool:
    allowed = listener.get("allowedRoutes") or {}
    kinds = {k["kind"] for k in allowed.get("kinds") or []} or _default_route_kinds(listener["protocol"])
    if _attaching_kind(route) not in kinds:
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
    routes may attach. A route it refuses is never programmed into Envoy. An
    AIGatewayRoute is judged as the HTTPRoute its controller generates.
    """
    index = _index(manifests)
    namespaces = {m.name: m.doc for m in manifests if m.group == "" and m.kind == "Namespace"}
    out: dict[str, str] = {}
    for ref in collect_refs(manifests):
        if ref.field != "parentRef" or _attaching_kind(ref.source) is None or ref.kind != "Gateway":
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
