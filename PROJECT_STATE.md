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
2026-10-15) is complete. When work resumes, the path is the critical
path in the "PAUSED" section below: `#17 → #22 / #23 / #24 → #18 → #20`.

## Branch & Tests
- Branch: `staging` (default working branch)
- Working tree: clean
- Last CI: n/a (no CI workflows in this repo); local static suite
  253 passed, 16 deselected after the #33 accepted-talk-title checks

## Phase History
_(append-only. Each phase transition adds one line, oldest first.)_
- 2026-10-16T11:01:07Z · init-state migrated pre-lifecycle file → Phase 3.3
- 2026-10-16 · #27 Portland carry-forward: PORTLAND-CARRY-FORWARD.md + runbook Night Before / rule-on-screen / Measurements; 248 static green
- 2026-10-16 · #33 accepted talk title replaces the old working title repo-wide; 253 static green

---

_Everything below this line is the pre-lifecycle body, preserved
verbatim by the migration._

# Project State — burritbot (BurritoBot Said Let's Dance, the Platform Said No)

## PAUSED — 2026-08-26

**This project is paused by Michael's decision until after DevOpsDays
Portland (2026-09-08 to 09-10).** The nearer deadline owns attention:
Portland's deliverable is the Watch It Burn workshop in
`~/repos/talks/Unleash_an_Agent_Watch_It_Burn`, a different and far
more mature repo. This platform's own delivery is not until
2026-11-09 to 11-12 (see `presentations/` for the event), so the
runway is real.

Do not resume work here without Michael saying so.

### State at the pause
- Branch `staging`, working tree clean, `staging` and `main` both in
  sync with origin. Nothing unpushed, nothing stashed.
- 253 static tests green (203 at pause; +3 for #22; +4 for #23; +9 for #24; net +23 for #26; +6 for #27; +5 for #33). Zero open Dependabot alerts, zero open PRs.
- **Nothing has ever run on a cluster.** No GCP resources exist; the
  Terraform state bucket created in June was deleted in the same
  session, verified empty.
- 11 open issues, every one labeled `deferred`.

### The critical path when work resumes
`#17 → #22 / #23 / #24 → #18 → #20`

1. **#17** swap the dead `kk-community-projects` GCP identity and the
   `michael@kodekloud.com` ACME email. Michael lost access to that
   account. Blocks everything below.
2. **#22, #23, #24** three verified defects that would break a live
   bring-up. #22 in particular means `terraform apply` fails outright
   (Dataplane V2 and legacy Calico both enabled), which a green
   `terraform plan` did NOT catch — plan is client-side, the GKE API
   rejects the combination only at apply. Do not read a green plan as
   apply-ready.
3. **#18** live cluster bring-up.
4. **#20** the Grafana screenshot for the README needs a live rehearsal.

### Doable any time, needs nothing external
- **#15** cut a dated release (`v0.1.0-static`)
- **#21** migrate this file to the lifecycle schema (the SessionStart
  hook nags every session until it is done)

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
C3, C4, C5, C9) found and repaired under TDD.** Commits land on
`staging` and ride the autonomous staging→main flow once each phase's
test passes. Live cluster validation (terraform apply, helm installs,
live Kyverno + Falco + Envoy + NeMo Guardrails smoke tests) remains
deferred to a session with GCP auth and cluster access.

**Recent rewrites (post-Phase-8):**
- Commit F (`0bd0f34`) — hard rename Deinopis → burritbot across 78 files.
- Commit G (`43b4db3`) — narrative shift to a lighthearted Act 1.
- Critical-fix series (this session) — see "Critical Fixes" below.

## Platform Context
- Platform name: **burritbot** (ogre-faced spider — The Eyes + The Net)
- Chatbot name: **BurritBot** (Chipotle viral chatbot incident as narrative hook)
- Format: Two-act live demo (unguarded then guarded BurritBot on GKE)
- Talk-specific delivery artifacts (CFP, runbook, scorecard, build plan)
  live under `presentations/<event>/`. See `README.md` for the current
  active deliveries.

## Critical Fixes (this session)
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
| 19 | Critical fixes C1–C5, C9 (senior-review pass) | completed | this session |

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
- **Total: 253 static tests green. Live tests skip cleanly when
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
- gcloud accounts authenticated: `michael@kodekloud.com` (active, intended
  GCP identity), `michaelrishiforrester@gmail.com` (personal, do not use)
- ADC for the Terraform google provider: not yet set up — run
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
  per replica; either keep replicas: 1 or wire to Redis.
- **C10 — `cast-net.sh` hardcoded `containers/0`.** Switch to
  `kubectl set env deployment/...` or look up by container name.
- **C11 — Terraform GCS backend.** No `backend "gcs"` block; first
  `terraform apply` writes local state.
- **C12 — Public GKE nodes.** No `private_cluster_config` despite the
  NAT gateway suggesting private intent.
- **C13 — `deletion_protection = false`.** Combined with
  `teardown.sh --yes`, the cluster could be destroyed by a stray CI run.
- All Medium/Low items (#14–#27 in the senior review).

### Newly surfaced (deeper structural)
- **No Deployment manifests for the AI Gateway / NeMo / LLM Guard /
  OTel Collector / Falco DaemonSet / Grafana dashboards.** The
  `deploy/` Kustomizations created in Phase A1 are deliberately
  shallow — they reference what *is* deployable today (Kyverno
  ClusterPolicies, Envoy Gateway CR, BurritBot + audience workloads)
  and carry TODO comments for the rest. Future work needs to author
  the missing manifests (ConfigMap-wrap configs, Deployment specs,
  ServiceMonitor / PodMonitor, etc.).

## Next Session — Phase 1 Live Validation
Once a GCP project is confirmed and Terraform is installed:

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

## Branch & Test Status
- **Branch**: `staging` (default working branch)
- **Remote**: `origin → https://github.com/peopleforrester/burritobot`
- **Static tests**: 80 passing, 0 failing, live tests skip when kubeconfig absent

## Key References
- `CLAUDE.md` — project Claude Code instructions
- `presentations/<event>/docs/BUILD-INSTRUCTIONS.md` — talk-specific burritbot spec
- `docs/CRITICAL-FIXES-PLAN.md` — senior-review repair plan (this session)
- `presentations/<event>/docs/RUNBOOK.md` — demo-day operational runbook
- `presentations/<event>/docs/SCORECARD.md` — per-component scorecard
- `spec/BUILD-SPEC.md` — build-time pointer and completion protocol
- `spec/phases/phase-0[1-8]-*.md` — per-phase specs with completion promises
- Local reuse source: `~/repos/_archive/events/kubeauto-ai-day/` (local-only)
- Remote reuse source: https://github.com/peopleforrester/kubeauto-ai-day

## 2026-10-15T12:00:00Z · 3.3 · Main fast-forwarded with known test failures

On Michael's instruction, main was fast-forwarded to staging to ship the Dependabot fix with these failures, all present on main before the fix, accepted: test_terraform_plan and test_gke_cluster_is_standard_with_wif_and_nap need live GCP; the credential has expired (invalid_grant).
