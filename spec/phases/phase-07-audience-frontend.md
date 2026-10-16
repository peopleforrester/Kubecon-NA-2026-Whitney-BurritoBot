# Phase 7: Audience Frontend + Cast-Net Toggle

**Goal:** FastAPI frontend for the audience in the room, fronted by a
QR code, rate-limited to 10 requests per minute per browser (a token
the page sets) under a per-address ceiling, with
`scripts/cast-net.sh` wiring the live demo toggle between unguarded
and guarded BurritBot paths.

**Inputs:** Phase 6 complete. Both BurritBot deployments running.
`audience` namespace exists.

**Outputs:**

- `apps/audience-frontend/backend/main.py` — FastAPI app, imports
  FastAPI, limits `/chat` per browser token (`X-Audience-Token`) under a
  per-address ceiling, read from `AUDIENCE_TOKEN_LIMIT` and
  `AUDIENCE_ADDRESS_LIMIT` (slowapi), references both
  `burritbot-unguarded` and `burritbot-guarded` upstream targets
- `apps/audience-frontend/backend/requirements.txt` — `uv export` of
  the `image-audience-frontend` group in uv.lock, pinned with hashes
- `apps/audience-frontend/backend/Dockerfile`
- `apps/audience-frontend/static/` — single-page frontend (HTML + JS)
  with a chat box and a QR code generator
- `apps/audience-frontend/k8s/deployment.yaml` — namespace `audience`
- `apps/audience-frontend/k8s/service.yaml`
- `scripts/cast-net.sh` — executable, two ABOUTME lines, references
  both `burritbot-unguarded` and `burritbot-guarded`
- `gitops/apps/30-audience.yaml` — sync-wave `2`, syncing the active
  delivery's overlay `presentations/<event>/deploy/audience`, which sets
  both limits (10/minute and 300/minute)

**Test Criteria (tests/test_phase_07_frontend.py):**

Static:

- `test_audience_frontend_tree_exists`
- `test_backend_uses_fastapi`
- `test_backend_enforces_rate_limit` — `main.py` reads both limit
  settings and the token header and limits a route
  (`tests/test_phase_07_browser_token.py` drives the limits: per-token
  budgets, the per-address ceiling, a missing token falling back to the
  per-address limit, the overlay's numbers)
- `test_backend_declares_burritbot_targets` — both unguarded and
  guarded string references
- `test_cast_net_script_exists_and_is_executable` — file exists, has
  `stat.S_IXUSR` bit, ABOUTME lines
- `test_cast_net_script_toggles_between_targets`
- `test_frontend_deployment_targets_audience_namespace`

Live:

- `test_audience_frontend_pod_running`

**Key Technology Decisions:**

- FastAPI backend (matches the rest of the Python stack)
- slowapi for rate limiting. The limit is 10 per minute per browser:
  the page keeps a random token in `localStorage` and sends it as
  `X-Audience-Token`. A request without one is held to the same number
  on its source address. A per-address ceiling (300/minute, about 30
  phones on one venue Wi-Fi at the full rate) caps one address however
  many tokens it sends, so clearing the token cannot get around it.
  Both numbers are settings in the delivery's kustomize overlay, tuned
  at the venue without a code change; the app refuses to start without
  them (question 157, `decisions.md`). A per-IP limit alone gave every
  phone behind one venue NAT a single shared budget.
- `cast-net.sh` uses `kubectl patch --type=json` on an HTTPRoute in
  `burritbot-net`, not `kubectl apply` — the runbook rehearsal target
  is under 500ms
- QR code is generated at page load via JS from the venue URL, or
  pre-baked into `static/` — either way, no secrets in the frontend

**Known Risk:** slowapi's default key function uses `request.client.host`,
which becomes `127.0.0.1` when the frontend sits behind an Envoy
sidecar. Configure it to read `X-Forwarded-For` or the demo will
rate-limit the whole audience as one client.

**Completion Promise:** `<promise>PHASE7_DONE</promise>`

**Skill:** `.claude/skills/cast-net-toggle.md`

**Commits:** 3 expected (backend + Dockerfile; frontend static +
manifests; cast-net.sh)
