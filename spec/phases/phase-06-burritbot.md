# Phase 6: BurritBot Application

**Goal:** FastAPI chatbot wrapping Vertex AI `gemini-3-pro` via the
`google-genai` SDK (`vertexai=True`), deployed twice — once in
`burritbot-unguarded` (bypasses the gateway) and once in
`burritbot-guarded` (routes through `burritbot-net`). Same container
image for both.

**Inputs:** Phase 5 complete. `burritbot-net` is serving the AI
gateway. `burritbot-unguarded` and `burritbot-guarded` namespaces
exist.

**Outputs:**

- `apps/burritbot/app.py` — FastAPI app; pins `MODEL_NAME` to
  `gemini-3-pro`; no references to 1.5, 2.0, or 2.5 Flash/Pro
- `apps/burritbot/requirements.txt` — `uv export` of the
  `image-burritbot` group in uv.lock, every package pinned with hashes
- `apps/burritbot/Dockerfile` — two ABOUTME lines at top
- `apps/burritbot/k8s/deployment-unguarded.yaml` — namespace
  `burritbot-unguarded`
- `apps/burritbot/k8s/deployment-guarded.yaml` — namespace
  `burritbot-guarded`, with full `burritbot.io/*` label set
- `apps/burritbot/k8s/service-unguarded.yaml`
- `apps/burritbot/k8s/service-guarded.yaml`
- `gitops/apps/burritbot-unguarded.yaml`, `gitops/apps/burritbot-guarded.yaml`

**Test Criteria (tests/test_phase_06_burritbot.py):**

Static:

- `test_burritbot_tree_exists`
- `test_burritbot_app_pins_gemini_3_pro` — string match for the
  correct model; explicit rejection of 1.5, 2.0, and 2.5 variants
- `test_burritbot_app_uses_google_genai_sdk` — imports
  `from google import genai`, configures `vertexai=True`, and
  forbids the removed `from vertexai.generative_models` import
- `test_burritbot_manifests_present` — four required manifests
- `test_burritbot_unguarded_deployment_valid` — kind Deployment in
  `burritbot-unguarded`
- `test_burritbot_guarded_deployment_has_burritbot_labels` — full
  three-label set on metadata
- `test_burritbot_dockerfile_has_aboutme`

Live:

- `test_unguarded_burritbot_running`
- `test_guarded_burritbot_running`

**Key Technology Decisions:**

- Python 3.13 (matches `pyproject.toml` `requires-python`)
- FastAPI 0.135.x, uvicorn for the server
- `google-genai` 1.71.0 with `genai.Client(vertexai=True, project=...,
  location=...)` inside a lazy cached accessor, not at import time.
  `google-cloud-aiplatform.vertexai.generative_models` is removed
  after 2026-06-24 and must not be reintroduced.
- `gemini-3-pro` — 1.5 is unsupported; 2.0 Flash is retired; 2.5
  Flash/Pro retire 2026-10-16 (four weeks before the talk); 3 Flash
  is preview-tier; 3 Pro is the only GA model guaranteed live on
  demo day
- **Same image** for unguarded and guarded; the difference is
  namespace + labels + the gateway route, not the image

**Known Risk:** The Vertex SDK's `usage_metadata` field name differs
between SDK versions. Pin the SDK and test with a live Vertex call
during Phase 6 rehearsal — the OTel gen_ai.* emission depends on
this exact field shape. The fastapi, google-genai and OpenTelemetry
pins hold through the November 2026 delivery; the google-genai 2.x bump waits
until after the talk unless an advisory lands against a pin (see
`decisions.md`, issue #55).

**Completion Promise:** `<promise>PHASE6_DONE</promise>`

**Skill:** `.claude/skills/burritbot-vertex-ai.md`

**Commits:** 3 expected (app + Dockerfile; manifests; ArgoCD apps)
