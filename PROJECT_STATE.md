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
2026-10-15) is complete. The live path is the critical path in the
"Open Work" section below: `#17 → #18 → #20` (#22, #23 and #24 are
fixed statically).

## Branch & Tests
- Branch: `staging` (default working branch)
- Working tree: clean
- Last CI: n/a (no CI workflows in this repo); local Test command
  (ruff check, then static suite) 291 passed, 16 deselected after the
  #52 listener probes
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

---

_Everything below this line is the pre-lifecycle body. The migration
(#21) preserved it verbatim; #46 refreshed its stale sections (the
2026-08-26 pause, the current status, the duplicate branch and test
block, the known gaps since fixed). The earlier text is in git
history._

# Project State — burritbot (BurritoBot Said Let's Dance, the Platform Said No)

## Open Work

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
`#17 → #18 → #20`

1. **#17** swap the dead `kk-community-projects` GCP identity and the
   `michael@kodekloud.com` ACME email. Michael lost access to that
   account. Blocks everything below.
2. **#18** live cluster bring-up. The three verified defects that would
   have broken it are fixed statically: #22 (Dataplane V2 and legacy
   Calico both enabled, D4), #23 (gateway port, now covered by the #26
   cross-manifest checks) and #24 (Vertex AI backend). Their live
   confirmation rides on #18. #22's lesson stands: a green
   `terraform plan` did NOT catch it — plan is client-side, the GKE API
   rejects the combination only at apply. Do not read a green plan as
   apply-ready.
3. **#20** the Grafana screenshot for the README needs a live rehearsal.

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
| C2  | ServiceAccount manifests added; WIF annotation on guarded SA   | `test_critical_fix_a2_service_accounts.py`            | Yes             | No            |
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
- Portland carry-forward (6), #27: the carry-forward map covers every
  proven and unmeasured result, the cold read sits a week clear of the
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
- Lint gate (3), #44: ruff is pinned exactly in the dev group with an
  explicit rule set, and the Test command runs `ruff check .` before
  the static suite
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
- **Total: 291 static tests green. Live tests skip cleanly when
  kubeconfig is absent — no mocks, no fallbacks.** Drift in this
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
  B5). Still open: the Grafana dashboard ConfigMaps exist under
  `observability/grafana/dashboards/` (C1) but no sync target lists
  them, and the ServiceMonitor / PodMonitor extras are still TODO in
  `deploy/monitoring/kustomization.yaml`.

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
