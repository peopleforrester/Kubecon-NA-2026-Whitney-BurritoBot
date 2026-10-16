# ABOUTME: Walks a manifest against a CRD's openAPIV3Schema and reads the served schema of an installed CRD,
# ABOUTME: so live tests can prove the cluster's CRDs neither refuse nor strip what the repo applies.

from __future__ import annotations

import json


def openapi_violations(obj: object, schema: dict, path: str = "") -> list[str]:
    """Unknown fields, missing required fields and out-of-enum values under a CRD's openAPIV3Schema.

    CEL rules (x-kubernetes-validations) are not evaluated; the static checks
    hold the ones the manifests depend on.
    """
    out: list[str] = []
    if isinstance(obj, dict):
        props = schema.get("properties")
        if props is not None and not schema.get("x-kubernetes-preserve-unknown-fields"):
            out += [f"{path}.{k}" for k in sorted(obj.keys() - props.keys())]
        out += [f"{path}.{k} (required)" for k in schema.get("required", []) if k not in obj]
        for k, v in obj.items():
            if props and k in props:
                out += openapi_violations(v, props[k], f"{path}.{k}")
    elif isinstance(obj, list):
        if "items" in schema:
            for i, v in enumerate(obj):
                out += openapi_violations(v, schema["items"], f"{path}[{i}]")
    elif "enum" in schema and obj not in schema["enum"]:
        out.append(f"{path} {obj!r} not in {schema['enum']}")
    return out


def installed_schema(apiext, crd_name: str, version: str) -> dict:
    """The served openAPIV3Schema of an installed CRD, read through the live cluster client.

    `apiext` is the k8s_apiextensions_v1 fixture, which fails the test naming
    the missing kubeconfig before this runs.
    """
    resp = apiext.read_custom_resource_definition(crd_name, _preload_content=False)
    crd = json.loads(resp.data)
    served = {v["name"]: v for v in crd["spec"]["versions"] if v.get("served")}
    assert version in served, f"installed CRD {crd_name} serves {sorted(served)}, not {version}"
    return served[version]["schema"]["openAPIV3Schema"]
