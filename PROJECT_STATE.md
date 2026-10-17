Phase: 3.3 Promote
Approved: pending

# Project State: burritbot

Phase: 3.3 Promote
Approved: pending

## Lifecycle
- [x] 1.1 Research
- [x] 1.2 Plan
- [x] 1.3 Approve
- [x] 2.1 Test
- [x] 2.2 Implement
- [x] 2.3 Verify
- [x] 3.1 Stage
- [x] 3.2 Confirm CI
- [x] 3.3 Promote  ← you are here

## Contracts
_(none sealed under the lifecycle schema yet. Work before 2026-10-16
was approved ad hoc and is recorded in the pre-lifecycle body below.
Approved plans land here with ts + sha256.)_

## Current Plan
Nothing in flight. The last cycle (Dependabot bumps, promoted
2026-10-15) is complete. Spec 001 (#114) sets the dated milestones
to delivery; its working copy and milestone status are in
`specs/001-ready-by-11-08-delivered-11-12.md`. The live path is the critical path in the
"Open Work" section below: `#17 → #18 → #20` (#22, #23 and #24 are
fixed statically).

## Branch & Tests
- Branch: `staging` (default working branch)
- Working tree: clean
- Last CI: n/a (no CI workflows in this repo); local Test command
  (ruff check, then static suite) 814 passed, 54 deselected after the
  #119 GKE load-balancer rule reading what ArgoCD syncs
- Remote: `origin → https://github.com/peopleforrester/burritobot`

## Phase History
_(append-only. Each phase transition adds one line, oldest first.)_
- 2026-10-16T11:01:07Z · init-state migrated pre-lifecycle file → Phase 3.3
- 2026-10-16 · #27 Portland carry-forward: PORTLAND-CARRY-FORWARD.md + runbook Night Before / rule-on-screen / Measurements; 248 static green
- 2026-10-16 · #33 accepted talk title replaces the old working title repo-wide; 253 static green
- 2026-10-16 · #36 conference-knowledge owns event state: CFP header becomes a pointer, AGENTS.md gains "Where things live"; 255 static green
- 2026-10-16 · #37 Europe 2027 tutorial is workshop-lineage, not built here: decisions.md entry + README Ancestry disclaims the workshop bot; 256 static green
- 2026-10-16 · #40 identity check: README gains "The Talk" (title, speakers, argument, event, status, Europe 2027 slate, sources) and "Where things live"; AGENTS.md names talks-knowledge for the register and abstracts; 261 static green
- 2026-10-16 · #44 lint gate: ruff 0.17.1 pinned in the dev group with an explicit rule set; Test command runs `ruff check .` before the static suite; first-run findings fixed; 264 static green
- 2026-10-16 · #46 pre-lifecycle body refreshed: pause replaced by Open Work, stale counts and duplicate Branch & Test Status removed, resolved known gaps marked; 265 static green
- 2026-10-16 · #47 the 2026-10-15 promote entry moves from the foot of this file to decisions.md; AGENTS.md sends every decision entry, promote-time ones included, to decisions.md; 268 static green
- 2026-10-16 · #39 advisory guard: static test holds uv.lock at or above the patched anyio, urllib3, oauthlib, fsspec and multidict releases; 273 static green
- 2026-10-16 · #49 AIGatewayRoute takes the upstream v1beta1 shape (parentRefs to the Gateway, x-ai-eg-model match); NeMo/LLM Guard ExtProc moves to the burritbot-guardrails EnvoyExtensionPolicy on the Gateway; 287 static green
- 2026-10-16 · #52 listener fix (`from: Same`) already landed under #26; probes now prove application namespaces cannot attach routes to the gateway; 291 static green
- 2026-10-16 · #53 gateway.yaml verified against upstream AI Gateway CRDs v0.2.0-v1.2.0 and Envoy Gateway v1.7.0/v1.9.2: valid from AI Gateway v0.6.0 (first v1beta1 release); static field sets narrowed to that floor, docs floor 0.2+ → 0.6+, live tests check the installed CRDs; 301 static green
- 2026-10-16 · #55 fastapi / google-genai / OpenTelemetry pins held at 0.135.3 / 1.71.0 / 1.41.0 + 0.62b0 through the November 2026 delivery (decisions.md); static test keeps the pins equal across both requirements files, pyproject.toml, uv.lock, AGENTS.md and the phase-06 spec; 315 static green
- 2026-10-16 · #56 audience phone page: `/` (index.html + app.js + styles.css, Feedback button) and the `/qr` projector landing, served by the backend; `FEEDBACK_URL` and `AUDIENCE_PUBLIC_URL` fail the page with a 503 when unset; image context moves to apps/audience-frontend; 339 static green
- 2026-10-16 · #59 costable delivery: GKE cluster and Secret Manager secret carry `burritbot-io_delivery` (required `var.delivery`), GKE cost allocation on, out-of-band detailed billing export playbook and Cost row queries in docs/BILLING-EXPORT.md, cost envelope re-priced for Gemini 3 Pro; 348 static green
- 2026-10-16 · #62 ruff gate widened to BLE, S110, S112, PLW1510, PERF102 and TRY401; research.py catches only Playwright errors and logs them; live fixtures and terraform checks fail instead of skipping; 349 static green
- 2026-10-16 · #51 ReferenceGrant already in burritbot-guarded via deploy/burritbot; new static check proves every ReferenceGrant is rendered by an ArgoCD-synced Kustomization, with a mutation test that drops it from the kustomization; 353 static green
- 2026-10-16 · #57 exposure path decided: phones reach the audience frontend through a GKE Gateway (global external ALB); the 10/minute limit keys on the client entry that load balancer writes into X-Forwarded-For, trusted only from Google's LB ranges; venue Wi-Fi NAT still shares one budget (follow-up); 365 static green
- 2026-10-16 · #65 question 133: ship skill and state-persistence rule (llm-coding-workflow 0c68e17) already send promote-time decision entries to decisions.md; the 2026-10-15 stray predates this repo's decisions.md; closed as satisfied, no writer change; 365 static green
- 2026-10-16 · #67 guarded traffic takes its gateway routes: EnvoyProxy pins the proxy Service (`burritbot-ai-gateway.envoy-gateway-system`, ClusterIP); the frontend sends Host `burritbot.burritbot.local` so `burritbot-audience` matches; guarded BurritBot posts OpenAI chat completions to the gateway (AIGatewayRoute → vertex-ai-gemini) instead of calling Vertex; the guarded egress lock admits the proxy pods; 379 static green
- 2026-10-16 · #68 gateway controllers installed by ArgoCD: `envoy-gateway` (gateway-helm v1.9.2, Gateway API + EG CRDs, AI Gateway extension manager), `ai-gateway-crds` and `ai-gateway-controller` (v1.2.0, webhook on 10250 with a cert-manager cert, MCP seed kept out of Git), GatewayClass `envoy-ai-gateway`, namespaces `envoy-gateway-system` / `envoy-ai-gateway-system`; `ai-gateway` moves to wave 3; GKE-managed Gateway API is now an incompatible pair; 409 static green
- 2026-10-16 · #61 no skip paths: the last exit-as-skip (Prometheus rules-map early return) now asserts; the Phase C5 plan no longer lets the Colang test skip; live fixtures and Terraform checks already fail naming what is missing (#62); the E2E command exits non-zero with 0 skipped on a bare host; 409 static green
- 2026-10-16 · #63 live fixtures proven loud: a subprocess probe requests each kubeconfig and GCP client fixture with no kubeconfig and no ADC and sees a setup error, a non-zero exit and the command that fixes it (`gcloud container clusters get-credentials` or `gcloud auth application-default login`); 416 static green
- 2026-10-16 · #72 duplicate of #68: Envoy Gateway v1.9.2, AI Gateway CRDs and controller v1.2.0 and GatewayClass `envoy-ai-gateway` are already installed by ArgoCD; recorded in decisions.md, no manifest change; 416 static green
- 2026-10-16 · #66 the guardrails ExtProc reaches a gRPC ext_proc server: a `burritbot-extproc` sidecar (ai-gateway/extproc/adapter.py) in each scanner pod turns buffered bodies into NeMo `/v1/guardrail/checks` and LLM Guard `/analyze/*` calls, blocks with a 403, applies LLM Guard sanitization, and fails closed (503 scanner down, 400 unreadable body); the policy names port 50051 with a 10s messageTimeout; 456 static green
- 2026-10-16 · #73 duplicate of #66: the burritbot-extproc gRPC adapter already sits in front of both scanners; llm-guard-api 0.3.9 confirmed REST (FastAPI/uvicorn, no gRPC) from its image, NeMo Guardrails microservice 25.07 REST from NVIDIA's docs; scanner config defects found on the way are raised as follow-ups; recorded in decisions.md, no manifest change; 456 static green
- 2026-10-16 · #74 Gateway API floor v1.2 → v1.4+: BackendTLSPolicy `gateway.networking.k8s.io/v1` (vertex-ai-backend.yaml) first ships in v1.4.0, v1.2/v1.3 serve only v1alpha3 (experimental), confirmed from the release CRDs; phase-05 spec, spec scorecard and the AI gateway skill say v1.4+ (the skill's AI Gateway line 0.2+ → 0.6+ too); `tests/test_gateway_api_floor.py` derives the floor from the manifests, holds the docs to it and checks the installed CRDs live; 467 static green
- 2026-10-16 · #75 readiness against the accepted abstract (Sessionize 1249553, talks-knowledge#12): `presentations/kubecon-na-2026/docs/ABSTRACT-READINESS.md` rates the nine checklist points, 2 READY-STATIC, 4 PARTIAL, 3 MISSING (MCP server, GenAI observability, recorded fallback); not ready; CFP-SUBMISSION.md header says it is a draft; 471 static green
- 2026-10-16 · #70 live fixtures: the k8s, GCP and Terraform skips the issue names were already gone (#61, #62); the installed-CRD schema checks (`tests/helpers/crd_schema.py` `installed_schema`, used by the AI Gateway route and Gateway API floor tests), the CRD presence check and the deployed audience page check now take the shared `k8s_apiextensions_v1` (new, probed like the other #63 fixtures) / `k8s_core_v1` fixtures instead of loading kubeconfig themselves, so every live test on a bare host fails naming kubeconfig, ADC or terraform; 0 skipped; 472 static green
- 2026-10-16 · #60 cold read confirmed (question 130, decided by Michael): Whitney reads on 2026-10-26, paper-read check 2026-10-23; PORTLAND-CARRY-FORWARD.md, PLAN.md and the critical path updated, test pins the date, reader and check, ABSTRACT-READINESS.md takes the new paper-read date; 474 static green
- 2026-10-16 · #79 attribution correction: decisions.md gains a dated amendment naming hecaton's coordinator, under Michael's standing rules, as the decider of the #24, #26 and #44 draft approvals and the #26 and #45 draft reruns; no earlier entry edited; the stated static count catches up with #76's tests; 497 static green
- 2026-10-16 · #83 detailed billing export: a console-only step for a Billing Account Administrator or Costs Manager, with no API, gcloud or Terraform resource; no GCP credential or project exists to check or enable it from a run, so it waits on #17 (the identity, project and billing account) and then on Michael; placed on the critical path between #17 and the first Night Before apply (#18); the stated static count catches up with #78's tests; 519 static green
- 2026-10-16 · #84 live Terraform checks: the skip was already a fail (#62); validate now runs `init -backend=false` first, plan takes `-var delivery=$BURRITBOT_DELIVERY` (no default, fails naming it) after a GCS-backed init and asserts the delivery label and cost allocation in the plan JSON, each in its own TF_DATA_DIR; #59's Terraform validated and offline-planned with Terraform 1.16.6 (decisions.md); the real-project plan waits on #17's credentials; 519 static green
- 2026-10-16 · #85 skip paths outside conftest.py: the four the issue names were already gone (the terraform fail in #62/#84, the scripts/ assert and the plain nemoguardrails import in 7f2d773, the asserted Prometheus rules map in ead6cd3); a sweep of tests/ found one more silent pass, the ArgoCD path test returning early for 13 Helm-source Applications, now split into path-source cases that resolve the dir and chart-source cases that assert repoURL and an exact chart version; 520 static green
- 2026-10-16 · #82 unguarded Vertex AI calls carry `burritbot-io_owner` and `burritbot-io_delivery` (from `BURRITBOT_DELIVERY`; unset or invalid is a 502 naming it); the guarded path's equivalents found (AIServiceBackend `bodyMutation` after the gateway's translation, `ChatVertexAI` `labels` via NeMo model `parameters`), both needing the slug as a manifest literal; where the slug lives waits for Michael; 531 static green
- 2026-10-16 · #82 question 152 (decided by hecaton's research under Michael's standing rules): the delivery slug lives in kustomize overlays under `presentations/kubecon-na-2026/deploy/{burritbot,ai-gateway}`, which the ArgoCD `burritbot` and `ai-gateway` Applications now sync; they set `BURRITBOT_DELIVERY`, the AIServiceBackend labels `bodyMutation` and both NeMo `vertexai` models' labels; the platform base carries a placeholder too long to be a label value; the Vertex AI Cost row query filters by `burritbot-io_delivery`; 542 static green
- 2026-10-17 · #87 Grafana dashboards reach the cluster: `observability/grafana/dashboards/kustomization.yaml` lists the three dashboard ConfigMaps and `deploy/monitoring` references that directory (no TODO left for them); a static test holds each dashboard ConfigMap to a file an ArgoCD-synced kustomization renders; 545 static green
- 2026-10-17 · #90 nemo-guardrails Deployment checked against NVIDIA's 25.07 microservice docs and OpenAPI (NGC refuses anonymous pulls, so not the image): it listens on `GUARDRAILS_PORT` 7331 (was 8000, the open-source server's), serves config id `burritbot` from `CONFIG_STORE_PATH=/config-store` with `config.yml` and `rails/` under `/config-store/burritbot/` (was `NEMO_GUARDRAILS_CONFIG_PATH=/config`, which it does not read), `DEFAULT_CONFIG_ID=burritbot`, probes on `/v1/health` (was `/v1/rails/configs`); the Service's http port and the adapter's `SCANNER_URL` move to 7331; `tests/test_nemo_guardrails_microservice.py` holds the contract with mutation cases and a live checks call; 560 static green
- 2026-10-17 · #91 llm-guard Deployment checked against the `laiyer/llm-guard-api` image (registry config, app layers, v0.3.16 source): image 0.3.9 → 0.3.16, the last release (upstream archived 2026-07-08; no 0.3.17 exists, docs said 0.3.17+); the API reads `CONFIG_FILE` (was `LLM_GUARD_CONFIG`, read by nothing); config.yaml rewritten to the API schema (`type` + `params`, constructor arguments only; the flat keys, `enabled`, `cache` and `telemetry` were dropped unread), `lazy_load: false`, no auth, OTLP/HTTP tracing and metrics to :4318; uid 1001 kept (image files world-readable), `HF_HOME` on the emptyDir under the image's HOME `/home/user` (was `/home/llm-guard`), cache 4Gi → 6Gi for ~4.3 GiB of models, startupProbe, readiness on `/readyz`; `tests/test_llm_guard_api_image.py` holds it with mutation cases, a docs version pin and live analyze calls; Anonymize/Sensitive still need spaCy `zh_core_web_sm`, which the image lacks (follow-up); 595 static green
- 2026-10-17 · #92 guarded path timeouts: Host and proxy Service already fixed by #67 (decisions.md); the frontend's 10s guarded timeout and Envoy's 15s default on `burritbot-audience` both cut the guarded chain; AIGatewayRoute rule `timeouts.request: 30s` (was the 60s AI Gateway default), BurritBot `GATEWAY_TIMEOUT_SECONDS` 30 → 75, `burritbot-audience` `timeouts.request: 80s`, frontend `GUARDED_TIMEOUT_SECONDS` 125 (unguarded keeps 10); `tests/test_guarded_timeout_budget.py` derives each bound from the manifests; 604 static green
- 2026-10-17 · #88 question 157 (decided by the coordinator under Michael's standing rules): the audience `/chat` limit is 10/minute per browser token (`X-Audience-Token`, random, kept in localStorage) under a 300/minute per-address ceiling; a tokenless phone is held to 10/minute on its address; both numbers are set by `presentations/kubecon-na-2026/deploy/audience`, which the ArgoCD `audience` Application now syncs, and the app refuses to start without them; Phase 7 spec, RUNBOOK step 8 and the Room network row updated; 624 static green
- 2026-10-17 · #94 the guardrails ExtProc already reached the `burritbot-extproc` gRPC adapter (#66) and llm-guard-api is 0.3.16, the last release (#91); which hops each scanner scans: both scanners, both hops (the Gateway target, #49), prompt and reply. Checked against Envoy AI Gateway v0.6.0 and v1.2.0 source: on the model hop the gateway's own ext_proc runs ahead of the net, so the net saw Vertex's reply before translation and passed it unscanned, and a prompt rewrite there would be dropped. The adapter now scans Vertex `candidates`, refuses an encoded reply (502) and a model-hop prompt rewrite (403); guarded BurritBot asks the gateway for `Accept-Encoding: identity` and relays a refusal naming its scanner with the net's status and body; 641 static green
- 2026-10-17 · #96 private nodes let the GKE control plane reach pods on TCP 443 and 10250 only; Kyverno's admission and cleanup controllers move their webhook servers from the chart's 9443 to 10250 (the cert-manager and AI Gateway controller port), their startup, liveness and readiness probes follow the named `https` port, and the chart's 9443-only webhook NetworkPolicies stay off; the live admission-controller check now looks in `security`, where Kyverno is installed; 644 static green
- 2026-10-17 · #97 the Gateway API CRDs get one owner: gateway-helm `crds.enabled: false`; a new `envoy-gateway-crds` Application (gateway-crds-helm v1.9.2, wave -2, before Envoy Gateway reads which CRDs exist at startup) installs the Envoy Gateway CRDs and, while `gateway_api_config` stays off, the standard-channel Gateway API v1.6.1 CRDs; turning GKE's Gateway API on is one change that sets `crds.gatewayAPI.enabled: false` and a `min_master_version` of at least 1.34.1-gke.1822000 (GKE bundle v1.4.0, the first with BackendTLSPolicy v1; 1.35.2-gke.1842000 brings v1.5.0); GKE serves every Gateway API object the manifests use from that floor, but no GKE bundle is the v1.6.1 the Envoy Gateway v1.9 matrix lists (decisions.md); `tests/test_gateway_api_crd_owner.py` holds one owner, the floor and the flip; 674 static green
- 2026-10-17 · #100 restates #90, already fixed by 1ee3d4e (port 7331, `CONFIG_STORE_PATH=/config-store/burritbot/`, `/v1/health`); the Deployment is unchanged and the stale "port 8000" comment in `ai-gateway/envoy/gateway.yaml` is corrected. NVIDIA's 25.7.0 custom-providers tutorial says "Only OpenAI compatible LLM providers are supported", so `config.yaml`'s `engine: vertexai` models likely won't load in the microservice; the route to an OpenAI-compatible Gemini is left as a follow-up (decisions.md); 674 static green
- 2026-10-17 · #102 (partial) burrito-only.co moves "what are your hours" from off-topic to on-topic, matching its own refusal; the unresolved rail names wait on question 170; 681 static green
- 2026-10-17 · #102 question 170 (decided by hecaton's research under Michael's standing rules): the four NeMo rails test the lower-cased `$user_message`/`$bot_message` against phrase lists from the old examples and `stop`, under the names `config.yaml` already enables (Colang 1.0 input rails run before any user intent exists, so intent-matching rails wait forever); `tests/test_nemo_rail_flows.py` builds the mounted ConfigMaps with real `LLMRails` (every enabled flow resolves; the old suffixed name is rejected) and runs `check_async`: 35 asks and replies blocked by their rail, 14 menu asks and replies pass (decisions.md); 733 static green
- 2026-10-17 · #104 readiness points checked against the accepted wording (talks-knowledge#29): same nine points, same order; ABSTRACT-READINESS.md drops the unchecked caveat, rows 4 and 6 quote the accepted text, rows 5 and 9 name the "Ready means" parts left for #18 (Kubernetes layers before the LLM layer; live input over the venue network); scope calls are with Michael and Whitney; ratings unchanged; 736 static green
- 2026-10-17 · #106 synced-manifest check widened to Directory sources: `synced_paths` (tests/helpers/manifest_graph.py) takes every Application source by ArgoCD's type (explicit block, else kustomization → Kustomize, Chart.yaml → Helm, else Directory) and walks Directory sources as the reposerver does (recurse, manifest extensions, include/exclude as gobwas globs with no separators, skip-file-rendering marker); the ReferenceGrant, dashboard ConfigMap and GatewayClass sync tests use it; new `tests/test_synced_paths.py` holds every cluster manifest in the repo to some Application, the hand-applied root `gitops/bootstrap/app-of-apps.yaml` the one exception, with mutation cases dropping cert-manager-issuers and the root; no manifest was unsynced; 773 static green
- 2026-10-17 · #109 GKE load-balancer timeout: `tests/test_guarded_timeout_budget.py` now holds any GKE Gateway (`gke-l7-*` GatewayClass) route to `audience/audience-frontend` to a GCPBackendPolicy on that Service with `spec.default.timeoutSec` above the frontend's `GUARDED_TIMEOUT_SECONDS` (125s; the load balancer's default is 30s), and any `timeouts.request` on that route above it too; mutation cases cover no policy, the 30s default, a timeout equal to the frontend's and a short route timeout. No Gateway or GCPBackendPolicy manifest is added: the #57 Gateway, its hostname, certificate and `gateway_api_config` wait for Michael, and without GKE's Gateway controller the GCPBackendPolicy CRD does not exist, so the audience sync would fail (decisions.md); 780 static green
- 2026-10-17 · #110 guardrails refusal on the phone page: the audience backend's `upstream_failure` relays a 403 whose JSON names a scanner in `blocked_by` and says why in `detail` (the net's block on either hop, and guarded BurritBot's relay of one since #94) as that JSON plus `target`, where it used to quote it inside an HTTPException detail; every other upstream error keeps its status. `app.js` reads a 403's body and, when `refusalOf` finds the net's refusal, `showRefusal` shows its detail as a `BurritBot · guarded` reply styled `reply refused`, not "Something went wrong (HTTP 403)"; a net 502/503 still reads as unreachable. New `tests/test_phase_07_guardrails_refusal.py`; 794 static green
- 2026-10-17 · #113 ABSTRACT-READINESS.md follows the #102 rail rewrite: row 6 (still PARTIAL, mid-inference is the talks-knowledge#29 call) says every enabled NeMo rail resolves in real `LLMRails` (`tests/test_nemo_rail_flows.py`), as phrase checks that call no model, with the 25.07 container (#18) and its `engine: vertexai` models (#100) unverified; row 8 PARTIAL → READY-STATIC (the burrito-only rail resolves, refuses the seven Act 1 asks, passes "what are your hours"); verdict 3 READY-STATIC, 3 PARTIAL, 3 MISSING, still not ready; step 3 done statically, live part left to #100 and #18; `tests/test_abstract_readiness.py` holds rows 6 and 8 to #102 and the rail test (decisions.md); 795 static green
- 2026-10-17 · #114 spec 001 working copy: `specs/001-ready-by-11-08-delivered-11-12.md` names its source (personal-knowledge `specs/talks/burritobot/001-ready-by-11-08-delivered-11-12.md`) and sha256, carries the delivered text between markers, and tracks M1 to M9 (M3 and M5 OPEN, the rest WAITING on #17 → #83 → #18 or a date); `tests/test_spec_001_working_copy.py` holds the text to the sha256 bar Corrections and the status rows to the spec's milestones, dates and KRs; Open Work points to it; 802 static green
- 2026-10-17 · #95 question 163 (decided by hecaton's research under Michael's standing rules), first child #116: the guarded BurritBot KSA (`burritbot-guarded/burritbot`) drops its `iam.gke.io/gcp-service-account` annotation, since guarded BurritBot reaches Vertex only through the AI gateway's GSA (#67); `tests/test_critical_fix_a2_service_accounts.py::test_burritbot_guarded_sa_has_no_wif_annotation` replaces the old has-annotation test; removing `workload_wif_binding` from iam.tf and the readiness record are the next two children (decisions.md); 802 static green
- 2026-10-17 · #119 (partial) the #109 GKE load-balancer rule now reads what ArgoCD syncs: `synced_manifests` (tests/helpers/manifest_graph.py) parses every file an Application syncs, delivery overlays under `presentations/` included, with the Application's destination namespace on objects that set none, so a #57 Gateway or GCPBackendPolicy in `presentations/<event>/deploy/audience` is checked (it was invisible to `load_manifests`); `frontend_exposure_violations` fails on any way to `audience/audience-frontend` that rule cannot see (a non-ClusterIP Service, an overlay patch to one, a JSON 6902 patch on it, an Ingress, a route through a non-GKE Gateway); `synced_patches` reads the overlays' patches. The repo still sets no backend timeout: the GCPBackendPolicy goes in with the #57 Gateway, which waits for Michael (decisions.md); 814 static green

---

_Everything below this line is the pre-lifecycle body. The migration
(#21) preserved it verbatim; #46 refreshed its stale sections (the
2026-08-26 pause, the current status, the duplicate branch and test
block, the known gaps since fixed). The earlier text is in git
history._
- 2026-10-16 · #78 images install from uv.lock: `image-burritbot`, `image-audience-frontend` and `image-extproc` dependency groups resolve with dev; each image's requirements.txt is `uv export` of its group with hashes (scripts/export-image-requirements.sh) and the Dockerfiles run `pip install --no-deps --require-hashes`; shared resolution moves dev to the images' pydantic 2.12.5, protobuf 6.33.6 and kubernetes 36.0.3; 519 static green

# Project State — burritbot (BurritoBot Said Let's Dance, the Platform Said No)

## Open Work

### Spec 001: ready by 11-08, delivered 11-12
The approved spec (#114, personal-knowledge
`specs/talks/burritobot/001-ready-by-11-08-delivered-11-12.md`) sets
milestones M1 to M9 from the live bring-up (2026-10-23) to delivery
(2026-11-12) and the campaign after it. The working copy, with each
milestone's status and what it waits on, is
`specs/001-ready-by-11-08-delivered-11-12.md`. Corrections go in its
Corrections section; changes to the spec go back to personal-knowledge
as an issue. The critical path below is M1.

### The 2026-08-26 pause has ended
Michael paused this project on 2026-08-26 until after DevOpsDays
Portland (2026-09-08 to 09-10), whose deliverable was the Watch It Burn
workshop in `~/repos/talks/Unleash_an_Agent_Watch_It_Burn`. That end
condition has passed. Issue work here resumed on 2026-10-16 with
Michael approving each merge (see Phase History in the header), and the
Portland results are carried forward in
`presentations/kubecon-na-2026/docs/PORTLAND-CARRY-FORWARD.md` (#27).
This platform's own delivery is 2026-11-09 to 11-12 (see
`presentations/` for the event).

### Ground truth
- **Nothing has ever run on a cluster.** No GCP resources exist; the
  Terraform state bucket created in June was deleted in the same
  session, verified empty.
- The GCP credential had expired by 2026-10-15 (`invalid_grant`), so
  the live tests fail until #17 restores an identity (see the
  2026-10-15 entry at the foot of this file).

### The critical path
`#17 → #83 → #18 → #20`

1. **#17** swap the dead `kk-community-projects` GCP identity and the
   `michael@kodekloud.com` ACME email. Michael lost access to that
   account. Blocks everything below.
2. **#83** turn on the detailed usage cost export for the billing
   account behind the new project (`docs/BILLING-EXPORT.md` steps 1-3:
   reuse an existing export, or create the `US` dataset and enable it).
   Console only, by a Billing Account Administrator or Costs Manager,
   so it is Michael's. It must be on before #18's first apply: usage
   before the export is on is never exported, apart from the one-time
   multi-region backfill.
3. **#18** live cluster bring-up. The three verified defects that would
   have broken it are fixed statically: #22 (Dataplane V2 and legacy
   Calico both enabled, D4), #23 (gateway port, now covered by the #26
   cross-manifest checks) and #24 (Vertex AI backend). Their live
   confirmation rides on #18. #22's lesson stands: a green
   `terraform plan` did NOT catch it — plan is client-side, the GKE API
   rejects the combination only at apply. Do not read a green plan as
   apply-ready.
4. **#20** the Grafana screenshot for the README needs a live rehearsal.

Dated against this path (#60, question 130): #18 must land by
2026-10-23, or the cold read becomes a paper read. Whitney reads
`RUNBOOK.md` cold on Monday 2026-10-26, 10:00 to 16:00 Central, 14 days
before the event opens on 2026-11-09.

### Doable any time, needs nothing external
- **#15** cut a dated release (`v0.1.0-static`)

### Related work that is NOT this repo
`Unleash_an_Agent_Watch_It_Burn` also contains a working BurritoBot —
a genuinely independent implementation (Bedrock/EKS/kagent vs this
repo's Vertex/GKE/NeMo), zero shared file ancestry, and unlike this one
it has actually run. Cousins, not forks. Context handoff for Portland
was filed there as issue #73. Do not conflate the two.

## Verification Method
Tracker contents are reconciled against actual repo state (file reads,
`pytest --collect-only`, `git log`) at every transition — not from
prior session summaries. The "static tests passing" count below is
asserted by `tests/test_critical_fix_a6_project_state_truthful.py`,
which fails the suite if this number drifts from reality.

The senior-review pass on 2026-04-25 surfaced five demo-breaking
defects that all five Phase 1–8 scorecards had silently rated GREEN.
The lesson written into the state-persistence rule
(`~/.claude/rules/state-persistence.md`) — distinguish "written" from
"confirmed against reality" — is now enforced for the critical-fix
work tracked below.

## Current Status
**Phases 1–8 offline build complete; six critical defects (C1, C2,
C3, C4, C5, C9) found and repaired under TDD; Phases B, G, C and the
offline part of D complete; #22, #23 and #24 fixed statically.** Work
lands on `staging` and is promoted to `main` once its tests pass. Live
cluster validation (terraform apply, helm installs, live Kyverno +
Falco + Envoy + NeMo Guardrails smoke tests) remains deferred until #17
restores GCP auth (see "Open Work" above).

**Recent rewrites (post-Phase-8):**
- Commit F (`0bd0f34`) — hard rename Deinopis → burritbot across 78 files.
- Commit G (`43b4db3`) — narrative shift to a lighthearted Act 1.
- Critical-fix series (2026-04-25 senior review) — see "Critical Fixes" below.
- 2026-10-16 issue work (#21 to #46) — see Phase History in the header.

## Platform Context
- Platform name: **burritbot** (ogre-faced spider — The Eyes + The Net)
- Chatbot name: **BurritBot** (Chipotle viral chatbot incident as narrative hook)
- Format: Two-act live demo (unguarded then guarded BurritBot on GKE)
- Talk-specific delivery artifacts (CFP, runbook, scorecard, build plan)
  live under `presentations/<event>/`. See `README.md` for the current
  active deliveries.

## Critical Fixes (2026-04-25 senior review)
Plan: `docs/CRITICAL-FIXES-PLAN.md`. Each phase landed a failing test
first, then the minimum fix, then re-ran the full static suite before
commit.

| ID  | Fix                                                            | Test                                                  | Verified-Static | Verified-Live |
| --- | -------------------------------------------------------------- | ----------------------------------------------------- | --------------- | ------------- |
| C1  | ArgoCD Application paths now resolve (`deploy/<x>/` stubs)     | `test_critical_fix_a1_argocd_paths.py`                | Yes             | No            |
| C2  | ServiceAccount manifests added; guarded SA has no WIF annotation (#95, question 163) | `test_critical_fix_a2_service_accounts.py`            | Yes             | No            |
| C9  | audience-frontend Dockerfile + requirements.txt added          | `test_critical_fix_a3_audience_dockerfile.py`         | Yes             | No            |
| C3  | NeMo `colang_version` aligned with rail syntax (1.0)           | `test_critical_fix_a4_colang_alignment.py`            | Yes             | No            |
| C4  | OTel auto-instrumentation wired; unguarded Deployment exports OTEL_* | `test_critical_fix_a5_otel_app_wired.py`, `..._unguarded_env.py` | Yes             | No            |
| C5  | PROJECT_STATE.md test-count drift now asserted by a test       | `test_critical_fix_a6_project_state_truthful.py`      | Yes             | n/a           |

## What's Done

### Phase 0 — Bootstrap
- [x] Git repo initialized (`main` + `staging` branches pushed to origin)
- [x] GitHub repo: `peopleforrester/burritobot`
- [x] `kubeauto-ai-day/` subdir kept local-only (gitignored)
- [x] `CLAUDE.md`, `README.md`, `.gitignore`
- [x] `presentations/kubecon-na-2026/docs/BUILD-INSTRUCTIONS.md` (verbatim spec + preamble)
- [x] `presentations/kubecon-na-2026/docs/PLAN.md`, `docs/KUBEAUTO-REUSE-MAP.md`, `docs/CRITICAL-FIXES-PLAN.md`
- [x] `PROJECT_STATE.md` (this file)

### Offline Build (Tasks #7 – #18)
| # | Task | Status | Commit |
|---|------|--------|--------|
| 7 | Rebaseline docs to burritbot spec | completed | 5daad64 |
| 8 | Python env + test scaffolding | completed | 1608114 |
| 9 | Project skills and slash commands | completed | c978e63 |
| 10 | Phase specs + scorecard skeleton | completed | 500bef7 |
| 11 | Phase 1: Terraform (GKE Standard + NAP) | completed | c89a4b5 |
| 12 | Phase 2: ArgoCD GitOps bootstrap | completed | 25d7f5d |
| 13 | Phase 3: The Eyes (observability) | completed | af6629a |
| 14 | Phase 4: The Net — Security (Kyverno + Falco) | completed | 1d77e42 |
| 15 | Phase 5: The Net — AI Gateway | completed | e4602e2 |
| 16 | Phase 6: BurritBot application (gemini-3-pro) | completed | cdb1dda |
| 17 | Phase 7: Audience frontend + rate limiter | completed | 542c194 |
| 18 | Phase 8: Hardening, runbook, docs | completed | (Phase 8 commit) |
| 19 | Critical fixes C1–C5, C9 (senior-review pass) | completed | see Critical Fixes |

### Static Test Totals
- Phase 1: 8 passed
- Phase 2: 4 passed
- Phase 3: 6 passed
- Phase 4: 7 passed
- Phase 5: 6 passed
- Phase 6: 7 passed
- Phase 7: 7 passed
- Phase 8: 5 passed
- Critical-fix series: 21 passed
- Phase B (EKS-adapt) — B1 cert-manager (7) + B2 external-secrets (7) + B3 prometheus (6) + B4 otel-collector (6) + B5 falco (8) + B6 loki/tempo/promtail (9) + B7 kyverno (4) + B8 deploy wiring (4) — **complete**
- Phase G (Genericize) — G1 move talk artifacts + G2 scrub platform refs + G3 rewrite README/instructions/state + G4 GitHub description + G5 leak test (1) — **complete**
- Phase C (Greenfield) — C1 grafana dashboard ConfigMaps (13) + C2 nemo-guardrails (10) + C3 llm-guard (10) + C4 ai-gateway wiring (7) + C5 colang parse (4) — **complete**
- Phase D (GCP live prereqs) — D1 tf gcs backend (4) + D2 tf private cluster (5) + D3 teardown guard (3) — **offline portion complete**
- D4 tf dataplane: Dataplane V2 enabled (1), closes #22; its Calico
  exclusions moved to the incompatible-settings registry below
- ESO controller GSA + WIF binding wired into iam.tf (5)
- Vertex AI AIServiceBackend + WIF-bound gateway GSA; every route backendRef resolves (9), closes #24
- Cross-manifest references (20), #26: every backendRef / parentRef /
  targetRef resolves to a defined object, on a port the Service exposes
  and a container serves, with ReferenceGrants and listener
  allowedRoutes honoured; mutation tests inject #23/#24-shaped defects.
  Replaces the #23 gateway-port test. The two defects the checks found
  are fixed: a ReferenceGrant in burritbot-guarded admits the
  HTTPRoute's backend, and the Gateway listener admits routes from its
  own namespace (`from: Same`, see decisions.md)
- Incompatible settings registry (9), #26: Dataplane V2 vs Calico
  policy / addon, Autopilot vs Falco, each with its reason and mutations
- Portland carry-forward (8), #27 and #60: the carry-forward map covers every
  proven and unmeasured result, the cold read (2026-10-26, Whitney,
  paper-read check 2026-10-23, #60) sits a week clear of the
  event, and the runbook provisions the night before, puts existing rule
  files on screen in Act 2, keeps Act 1 to the canonical prompts, and
  has a Measurements record
- Accepted talk title (5), #33: no file carries the old working title,
  and every file that names the talk carries the accepted one
- Conference source of truth (2), #36: the CFP doc keeps no event-state
  copy and points at conference-knowledge, and AGENTS.md says where
  conference information lives
- Workshop lineage (1), #37: the README's Ancestry section names the
  workshop BurritoBot as a separate project, not an ancestor
- Talk identity (5), #40: the README states the talk, its status (with
  the Europe 2027 slate) and its sources, README and AGENTS.md name
  talks-knowledge and conference-knowledge, CLAUDE.md links AGENTS.md,
  and PROJECT_STATE.md and decisions.md exist
- Lint gate (4), #44 and #62: ruff is pinned exactly in the dev group
  with an explicit rule set that includes the blind-except and
  silent-swallow checks (BLE, S110, S112, PLW1510), and the Test command
  runs `ruff check .` before the static suite
- State file (1), #46: PROJECT_STATE.md has one branch and test status
  section, and its count agrees with the Total line below
- Decision entries (3), #47: PROJECT_STATE.md holds no decision-entry
  headings, the 2026-10-15 promote entry sits in decisions.md, and
  AGENTS.md sends promote-time entries there
- Dependency advisories (5), #39: uv.lock holds anyio, urllib3,
  oauthlib, fsspec and multidict at or above each advisory's first
  patched release
- AIGatewayRoute + guardrails ExtProc schema (12), #49: the route and
  the EnvoyExtensionPolicy use only fields their upstream CRDs define;
  mutation tests reintroduce targetRefs, schema, filters, a singular
  backendRef and the old BUFFERED spelling
- Gateway listener admits no application routes (4), #52: a probe
  HTTPRoute from each `burritbot.io/layer: application` namespace is
  refused; mutation tests widen the listener to `from: All`, the old
  application selector and a part-of selector
- AI Gateway floor (10), #53: the route and ExtProc field sets are the
  ones every release from AI Gateway v0.6.0 / Envoy Gateway v1.7.0 up
  serves; mutation tests add hostnames, rule name, streamIdleTimeout,
  excludeFromModelsEndpoint, shadowMode, statusOnError and a
  ListenerSet target; the phase-05 spec and both scorecards state 0.6+
- BurritBot runtime pins (14), #55: fastapi, google-genai,
  opentelemetry-api/sdk and -instrumentation-fastapi are pinned to the
  same release in apps/burritbot/requirements.txt, pyproject.toml and
  uv.lock; the OTLP exporter tracks opentelemetry-api; the audience
  backend ships the same fastapi; AGENTS.md and the phase-06 spec name
  the pinned versions
- Audience phone page (24), #56: static/ files carry ABOUTME lines and
  ship in the image; `/` serves the page with an escaped Feedback link
  and the three canonical asks; `/qr` and `/qr.svg` encode
  AUDIENCE_PUBLIC_URL; an unset or non-http(s) page URL is a 503 that
  names it while `/healthz` and `/chat` keep working
- Cost labels (9), #59: `var.delivery` has no default and validates as a
  label value; `local.cost_labels` labels the cluster and the secret;
  GKE cost allocation is on; the billing export dataset stays out of the
  module teardown destroys; the runbook applies with a delivery slug and
  reads the Cost row from docs/BILLING-EXPORT.md; both cost envelopes
  price Gemini 3 Pro
- Audience rate-limit key (12), #57: the limiter keys on
  `client_address()`; a Google load-balancer peer is keyed on the
  client entry it appended to X-Forwarded-For, a direct peer on itself;
  a load-balancer request without a client entry is a 400; two phones
  behind the load balancer each get their own 10/minute budget
- Audience browser-token limit (20), #88 question 157: each browser
  token gets its own budget behind one venue NAT; one address is capped
  by the ceiling however many tokens it sends; a tokenless phone falls
  back to the per-address limit; a malformed token is a 400; the app
  refuses to start without parseable `AUDIENCE_TOKEN_LIMIT` and
  `AUDIENCE_ADDRESS_LIMIT`; the page keeps and sends the token; the
  delivery overlay sets 10/minute and 300/minute and the `audience`
  Application syncs it; the base sets neither
- Audience guardrails refusal (14), #110: a 403 naming its scanner and
  its reason reaches the phone as the net's JSON plus the target, for a
  prompt or reply block and the model-hop rewrite refusal; a net 502 or
  503, a 403 without `blocked_by` or `detail`, and non-JSON keep their
  status as errors; `/chat` answers upstream errors through
  `upstream_failure`; the page shows the refusal's detail as a guarded
  reply styled `.reply.refused`, never as an error
- Guarded gateway path (22), #67, #94: the frontend's guarded URL and the
  guarded `AI_GATEWAY_URL` are the Service the EnvoyProxy names; the
  frontend's guarded Host is a `burritbot-audience` hostname; the
  gateway body's model matches the AIGatewayRoute; a guarded `/chat`
  fails on the gateway hop, never on Vertex; the egress lock admits the
  proxy pods; the model call asks for an uncompressed reply and only a
  refusal naming its scanner is relayed
- Gateway controller install (30), #68: Envoy Gateway and the AI Gateway
  CRDs and controller are pinned Helm Applications; the extension
  manager names the controller Service; Backend API on; every Gateway
  names a synced GatewayClass that Envoy Gateway owns; the webhook port
  is one the GKE control plane reaches and its cert comes from
  cert-manager; the MCP seed is neither committed nor reminted; waves
  put the controllers before `ai-gateway`; GKE-managed Gateway API CRDs
  and the gateway-helm copy are an incompatible pair
- Live fixtures fail loudly (8), #63, #70: each cluster and GCP client
  fixture errors in a probe run with no kubeconfig and no ADC, the
  probe exits non-zero, and the message names the command that fixes it
- Guardrails ext_proc adapter (49), #66, #94: each ExtProc backend resolves
  to a `burritbot-extproc` container configured for the scanner it
  names, never the scanner's REST port; messageTimeout sits above the
  adapter's scanner timeout and failOpen stays off; the adapter reads
  BurritBot and OpenAI bodies, reads both scanners' REST replies and
  refuses unreadable ones; a real in-process gRPC round trip refuses a
  prompt with a 503 when the scanner is down and a 400 when the body is
  unreadable; on the model hop it scans Vertex's own reply (a 503 with
  the scanner down), refuses a compressed reply with a 502 and a prompt
  rewrite the gateway would drop with a 403
- NeMo Guardrails microservice 25.07 (15), #90: the container's
  `GUARDRAILS_PORT`, http containerPort, Service http port and the
  adapter's `SCANNER_URL` agree; the config and rails ConfigMaps sit at
  `CONFIG_STORE_PATH/<adapter config id>/` with `DEFAULT_CONFIG_ID` the
  same id; probes and the adapter's checks call use 25.07 API paths;
  mutation tests restore the #66 shape and drift each value
- llm-guard-api 0.3.16 (35), #91: config.yaml keeps to the API's Config
  schema and each scanner's llm_guard 0.3.16 constructor arguments, with
  lazy loading off and no auth; the ConfigMap carries it unchanged; the
  Deployment runs 0.3.16 with `CONFIG_FILE` on the mounted key, `HF_HOME`
  and `/tmp` on emptyDirs under the image's HOME, a cache big enough for
  the configured models, and startup/readiness/liveness on the API's
  health paths; the docs pin the deployed version; mutation tests
  restore the #66 shape and drift each value
- Guarded timeout budget (9), #92: the frontend's guarded timeout sits
  above the guardrails ext_proc both ways plus the `burritbot-audience`
  route timeout, which sits above BurritBot's gateway timeout, which sits
  above the ext_proc both ways plus the AIGatewayRoute's Vertex timeout;
  neither route is left on its default; mutation tests restore the old
  10s, drop each route timeout and shorten or swell each hop
- Gateway API CRD owner (27), #97: exactly one of gateway-helm,
  gateway-crds-helm and GKE's `gateway_api_config` installs the Gateway
  API CRDs; the CRD chart is Envoy Gateway's release, syncs before it and
  uses the standard channel; with GKE on, `min_master_version` must reach
  the GKE version whose bundle serves the manifests' floor; mutation tests
  make the flip cleanly and get it wrong eight ways
- NeMo rail flows (59), #102: every flow `config.yaml` enables is defined
  and real `LLMRails` loads the mounted ConfigMaps; a mutation restores the
  old suffixed name and is rejected; `check_async` blocks each rail's asks
  and leak replies under its own name and passes menu asks and replies;
  both ConfigMaps mirror their sources
- Spec 001 working copy (7), #114: the working copy names its source and
  sha256, its spec text hashes to the delivered file with Corrections put
  back as delivered (mutations: a correction passes, a moved date and a
  dropped milestone fail), the milestone status rows follow the spec's
  milestones, dates and KRs, and Open Work points to it
- Synced manifests (37), #106: every cluster manifest is applied by an
  ArgoCD Application through a Kustomize or Directory source, the
  hand-applied root excepted; Directory walks honour recurse, include,
  exclude, the extension filter and the skip marker; type detection and
  gobwas glob cases pin ArgoCD's behaviour; mutation tests drop
  cert-manager-issuers and the root
- **Total: 814 static tests green. Live tests fail loudly when
  kubeconfig, GCP auth or terraform is absent — no skips, no mocks, no
  fallbacks.** Drift in this
  number is asserted against `pytest --collect-only -m static` by the
  Phase A6 test.

## Phase 1 Preconditions (authoritative)
1. **GCP project ID:** `burritbot-kubecon-2026` (placeholder — confirm real
   ID before `terraform apply`).
2. **Region:** `us-west1`.
3. **GKE mode:** **Standard with node auto-provisioning.** Not Autopilot —
   Falco DaemonSet needs privileged container support.
4. **Gemini model:** `gemini-3-pro` (GA) accessed via `google-genai` with
   `vertexai=True`. 1.5 is unsupported; 2.0 Flash is retired; 2.5 Flash/Pro
   retire 2026-10-16 — four weeks before the talk; 3 Flash is preview-tier.
   3 Pro is the only Vertex AI model guaranteed to be live on demo day.
5. **Audience frontend backend:** FastAPI (matches the rest of the stack).
6. **Licensing:** Apache 2.0 (matching kubeauto-ai-day lineage).

## Local Tooling
- Installed: `yamllint`, `jq`, `kyverno`, `shellcheck`, `uv`, `python3.13`,
  `terraform`, `kubectl`, `helm`, `gcloud`
- Still missing: `kubeconform`, `docker`
- gcloud accounts authenticated: `michael@kodekloud.com` (Michael has
  lost access to it; #17 replaces it), `michaelrishiforrester@gmail.com`
  (personal, do not use)
- ADC for the Terraform google provider: expired by 2026-10-15
  (`invalid_grant`). Once #17 settles the identity, run
  `gcloud auth application-default login` before the first
  `terraform init`.

Offline TDD strategy: Python code via pytest; Kyverno via `kyverno test`;
YAML via yamllint; JSON dashboards via `jq empty`; shell via shellcheck.
Terraform `init`/`validate`/`plan` are now runnable locally; `apply`
remains a deliberate operator step.

## Known Gaps (deferred — not blocking the critical-fix series)

These were surfaced in the senior review but are out of scope for the
critical-fix pass. Each is tracked here so a future session can pick
them up without re-discovering them.

### From the senior review
- **C3 live verification.** Colang `1.0` matches the rail syntax, but
  this needs to be confirmed against a running NeMo Guardrails 0.11
  container before demo day.
- **C7 — CORS `allow_origins=["*"]`.** Lock to known audience hostnames.
- **C8 — per-pod rate limiter.** slowapi in-memory storage scales
  per replica; either keep replicas: 1 (the audience Deployment's
  current setting) or wire to Redis.
- **C10 — `cast-net.sh` hardcoded `containers/0`.** Switch to
  `kubectl set env deployment/...` or look up by container name.
- **C11 — Terraform GCS backend.** Fixed statically by D1: a
  `backend "gcs"` block in `infrastructure/terraform/main.tf`.
- **C12 — Public GKE nodes.** Fixed statically by D2: a
  `private_cluster_config` block in `infrastructure/terraform/gke.tf`.
- **C13 — `deletion_protection = false`.** Mitigated by D3:
  `teardown.sh --yes` also requires `CAST_NET_ALLOW_DESTROY=true`, so a
  stray CI run with `--yes` alone still prompts. `deletion_protection`
  itself is still `false`.
- All Medium/Low items (#14–#27 in the senior review).

### Newly surfaced (deeper structural)
- **Deployment manifests, mostly closed.** The `deploy/`
  Kustomizations created in Phase A1 were deliberately shallow. Since
  then NeMo Guardrails (C2), LLM Guard (C3) and the Vertex AI backend
  (#24) are wired into `deploy/ai-gateway/`, and the OTel Collector and
  Falco ship as their own Helm Applications under `gitops/apps/` (B4,
  B5). The Grafana dashboard ConfigMaps (C1) sync through
  `deploy/monitoring` since #87. Still open: the ServiceMonitor /
  PodMonitor extras are still TODO in
  `deploy/monitoring/kustomization.yaml`.
- **The `deploy/<x>/` wrapper Applications never run kustomize (#54,
  confirmed against ArgoCD `release-3.3` source).**
  `gitops/apps/10-monitoring.yaml`, `10-security.yaml`,
  `20-ai-gateway.yaml`, `20-burritbot.yaml` and `30-audience.yaml` point
  at `deploy/<x>/` (only a `kustomization.yaml`) and set
  `spec.source.directory.recurse: true`. `GetAppSourceType`
  (`reposerver/repository/repository.go`) uses `source.ExplicitType()`
  before any auto-detection, and a non-nil `directory` makes the type
  `Directory`. `docs/user-guide/tool_detection.md` says the same:
  an explicitly configured tool wins. In directory mode ArgoCD reads
  every yaml file with `apiVersion:` and `kind:` as a manifest. That
  means each app's only object is a `kustomize.config.k8s.io/v1beta1`
  `Kustomization`, which the cluster has no API for. None of the
  referenced manifests sync. Removing `directory:` is not enough
  on its own. Every `resources:` entry is a *file* outside the
  kustomization root (`../../apps/...`, `../../ai-gateway/...`,
  `../../security/...`). kustomize's default `LoadRestrictionsRootOnly`
  rejects those files with `security; file ... is not in or below ...`,
  and `gitops/argocd/values.yaml` sets only `--enable-helm` in
  `kustomize.buildOptions`. The fix needs a choice between two options:
  a global `--load-restrictor LoadRestrictionsNone`, or per-directory
  kustomizations referenced as directories. That choice is open. Not
  affected: `cert-manager-issuers.yaml` (`security/cert-manager/` is
  plain yaml) and the root `app-of-apps.yaml` (`gitops/apps/`).

## Next Session — Phase 1 Live Validation
Once #17 restores a GCP identity and the real project ID is confirmed:

```bash
claude -p "Read CLAUDE.md, PROJECT_STATE.md, \
presentations/kubecon-na-2026/docs/BUILD-INSTRUCTIONS.md, \
presentations/kubecon-na-2026/docs/PLAN.md, \
and docs/CRITICAL-FIXES-PLAN.md. Validate Phase 1: GKE \
Foundation. Run terraform validate, terraform plan, then terraform apply. \
Run tests/test_phase_01_foundation.py with the live marker." --max-iterations 20
```

Then walk Phases 2 → 8 forward in the same autonomous staging→main
workflow, promoting YELLOW scorecard rows to GREEN as each live check
passes. **Do not green-wash the scorecard.**

## Demo-Day Artifacts (Phase 8)
- `presentations/kubecon-na-2026/docs/RUNBOOK.md` — Pre-flight / Act 1 / Cast the Net / Act 2 / Teardown / Rollback
- `presentations/kubecon-na-2026/docs/SCORECARD.md` — honest per-component status, YELLOW where live
  validation has not happened yet
- `docs/CRITICAL-FIXES-PLAN.md` — the senior-review repair plan
- `scripts/teardown.sh` — `terraform destroy` with a two-step confirmation
- `scripts/cast-net.sh` — the single-command live traffic toggle

## Key References
- `CLAUDE.md` — project Claude Code instructions
- `presentations/<event>/docs/BUILD-INSTRUCTIONS.md` — talk-specific burritbot spec
- `docs/CRITICAL-FIXES-PLAN.md` — senior-review repair plan (2026-04-25)
- `presentations/<event>/docs/RUNBOOK.md` — demo-day operational runbook
- `presentations/<event>/docs/SCORECARD.md` — per-component scorecard
- `spec/BUILD-SPEC.md` — build-time pointer and completion protocol
- `spec/phases/phase-0[1-8]-*.md` — per-phase specs with completion promises
- Local reuse source: `~/repos/_archive/events/kubeauto-ai-day/` (local-only)
- Remote reuse source: https://github.com/peopleforrester/kubeauto-ai-day
