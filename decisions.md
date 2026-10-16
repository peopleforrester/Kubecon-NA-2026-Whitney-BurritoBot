# Decisions Log

Append-only audit trail of approvals, amendments, backward steps, and conditional-skip rationales. See [[state-persistence]] for schema.

## 2026-10-16T11:01:07Z · init · PROJECT_STATE.md migrated to the lifecycle schema

init-state migrated the pre-lifecycle PROJECT_STATE.md (issue #21).
The lifecycle header was prepended and the old body kept verbatim
below it. Phase 3.3 was deduced from git state: clean tree on
`4b435be`, with the last cycle already promoted to main on 2026-10-15.
Approved reads `pending` because no plan has been sealed with a
sha256 yet. The 2026-10-15 promotion entry stays where it was, at
the foot of PROJECT_STATE.md, so the body is unchanged.

## 2026-10-16T12:00:00Z · decision · BurritBot is independent of the upstream workshop BurritoBot (issue #25)

The workshop bot in `Unleash_an_Agent_Watch_It_Burn` (BurritoBot: a
secret recipe to protect, jailbreak and exfil exercises, a guard proxy
toggled live, kagent and Bedrock on EKS) is not an ancestor of this
platform. Nothing here is ported from it, and its premise, canon and
punchline are not to be imported.

Settled by the existing spec, not by a new call:

- CLAUDE.md names the lineage: forked conceptually from kubeauto-ai-day,
  with `docs/KUBEAUTO-REUSE-MAP.md` as the per-file map. The workshop
  repo appears nowhere in it.
- CLAUDE.md fixes the narrative to the Chipotle viral-chatbot incident
  and the canonical Act 1 prompts (salsa moves, hot dog party, karaoke
  songs), with injection, jailbreak and data extraction driven by the
  presenters only.
- CLAUDE.md lists the two-namespace guarded/unguarded split as a
  non-negotiable architecture decision; the workshop's single deploy
  with a runtime guard toggle contradicts it.
- The accepted CFP (`presentations/kubecon-na-2026/docs/CFP-SUBMISSION.md`)
  promises that A/B demo: same model, same system prompt, two outcomes.

The shared word "burrito" is coincidence of theme, not lineage. Work on
the workshop platform (terminal auth, browser IDE, notebook tab, Bedrock
tutor, fleet converge) does not transfer here. Reopen only if Michael
decides the talk should adopt the workshop's secret-recipe narrative,
which would amend CLAUDE.md and the CFP first.

## 2026-10-16T14:00:00Z · decision · The gateway listener admits only routes in burritbot-net (issue #26)

The cross-manifest checks added for #26 found that the Gateway
listener in `ai-gateway/envoy/gateway.yaml` admitted routes only from
namespaces labelled `burritbot.io/layer: application`, while the one
route it serves, the `burritbot-audience` HTTPRoute, lives in
`burritbot-net` (labelled `the-net`). The route was never admitted, so
the guarded path had no listener.

Two ways to admit it: relabel or reselect so `burritbot-net` matches,
or move the route into an application namespace. The route cannot
move: the AIGatewayRoute's `targetRefs` is a local reference, so the
HTTPRoute it guards must share its namespace. The listener is set to
`allowedRoutes.namespaces.from: Same`.

`Same` is also the tighter choice. The gateway is the single choke
point; under the old selector `burritbot-unguarded` and `audience`
could attach their own routes and claim hostnames on it. Application
namespaces now reach the gateway only as backends. The guarded
Service is opened to the route by a ReferenceGrant in
`burritbot-guarded` (`apps/burritbot/k8s/referencegrant-guarded.yaml`)
scoped to that one Service and to HTTPRoutes from `burritbot-net`.

Reopen if an application namespace needs to own its own route on this
gateway; widen the listener to a selector naming that namespace rather
than all of `burritbot.io/layer: application`.

## 2026-10-16T16:00:00Z · amendment · Talk title set to the accepted title (issue #33)

Per Michael, 2026-09-30, the talk title in `presentations/kubecon-na-2026/` is "BurritoBot
Said Let's Dance, the Platform Said No" (accepted 2026-08-04, matching
`conference-management/events/registry.yaml`). The earlier working
title is replaced everywhere in the repo, including inside bodies that
are otherwise kept verbatim: the pre-lifecycle body of
`PROJECT_STATE.md` (its heading) and the spec body of
`presentations/kubecon-na-2026/docs/BUILD-INSTRUCTIONS.md` (listed as
deviation 3 in its preamble). `tests/test_accepted_talk_title.py`
keeps the old title from coming back.

## 2026-10-16T18:00:00Z · amendment · conference-knowledge owns event state (issue #36)

Per Michael, 2026-10-03, `peopleforrester/conference-knowledge` is the
source of truth for conference information: events, CFP dates and
deadlines, submission status and outcomes, attendance, contacts, the
speaking record and travel. It replaces conference-management, which
the entry above cites for the acceptance. This repo reads that
information there and keeps no copy; changes go to that repo as
`agent-task` issues.

The event-state header of
`presentations/kubecon-na-2026/docs/CFP-SUBMISSION.md` (location,
dates, CFP deadline, submission platform) is replaced with a pointer,
and `AGENTS.md` gains a "Where things live" section.
`tests/test_conference_source_of_truth.py` keeps both in place.

Kept, because they are planning inputs or dated history rather than a
working copy of the event record: the event start date in
`tests/test_portland_carry_forward.py` (the cold-read gate needs a
date to compare against, and the comment names its owner), the dates
in `PORTLAND-CARRY-FORWARD.md` and in the pre-lifecycle body of
`PROJECT_STATE.md`, the acceptance date in the entry above and in the
`BUILD-INSTRUCTIONS.md` preamble, and the CFP's "Has This Been
Presented Before?" answer, which is submitted text. The event name
and city still identify the delivery in `README.md` and `PLAN.md`.

## 2026-10-16T20:00:00Z · decision · The Europe 2027 tutorial is not built on this platform (issue #37)

Whitney's Europe 2027 tutorial abstract (shared 2026-10-04) is a
hands-on, attack-then-block workshop: kagent, one cluster per
attendee, a browser terminal, and a goth burrito chain with a secret to
protect. Every one of those is the `Unleash_an_Agent_Watch_It_Burn`
workshop's architecture or canon. This platform's shape (the
guarded/unguarded A/B in two namespaces, Vertex through Envoy AI
Gateway, no terminal, no per-attendee provisioning) matches it on the
burrito theme only.

Settled by the #25 entry above, not by a new call: the workshop's
premise and canon are not imported here, and workshop platform work
does not transfer. A tutorial built on that platform is workshop work,
so this repo does not carry it and stays the platform behind the NA
2026 delivery. #25 stands as "independent on purpose", and the README's
Ancestry section now says so (`tests/test_workshop_lineage.py`).

Consequences for this repo:

- KubeArmor, Istio, kagent, classifier models and tool allow-lists,
  which the abstract names and this repo lacks, are not backlog here.
  Their absence is the intended scope, not a gap to close.
- The submission itself (event, track, Sessionize invite) is event
  state and lives in conference-knowledge, per the #36 entry; nothing
  about it is copied here.

Reopen if Michael and Whitney decide the 2027 tutorial runs on this
platform. That reopens #25 too, and amends CLAUDE.md (narrative,
non-negotiable architecture) before any port starts.

## 2026-10-16T22:00:00Z · amendment · The repo states who it is and points at talks-knowledge (issue #40)

Per the fleet standard for talk repos (requested from talks-knowledge
on Michael's ask, 2026-10-14), `peopleforrester/talks-knowledge` is
the source of truth for the talks: the register (`talks/register.md`),
the research index, and the abstracts and talk scripts. The README
gains "The Talk" (title, speakers, argument, event, status, sources)
and "Where things live"; AGENTS.md's "Where things live" names
talks-knowledge by its full name and points at the register.
`tests/test_talk_identity.py` keeps all of it in place.

Two calls made to fit the standard to the entries above:

- The standard asks for the event date; the #36 entry keeps event
  state out of this repo. The README gives the month (November 2026)
  next to the event name and city, enough to identify the delivery,
  and leaves exact dates and the slot to conference-knowledge.
- The issue asks the status to say BurritoBot is on the Europe 2027
  slate, submitted by Whitney. The README says so and, per the #37
  entry, that the submission is built on the workshop rather than on
  this platform. The submission's state stays in conference-knowledge
  and its abstract in talks-knowledge; nothing of either is copied.

`decisions.md` already existed when this landed (created by the
2026-10-16 lifecycle migration), so the audit's "no decisions.md"
needed no new file.

## 2026-10-16T23:00:00Z · decision · question 119: ruff joins the dev group and the light Test command (issue #44)

Question 119 asked whether the repo may add a Python linter as a new
dev dependency and run it in the Test command. Answer (coordinator,
for Michael): approved, ruff pinned in the dev group plus a
`ruff check` step in the Test command. A new dev package does not need
Michael's approval; his rule (2026-10-16) is approval only at
publication, and hecaton#125 removes the old rule.

What it changes:

- `pyproject.toml` pins `ruff==0.17.1` in `[dependency-groups].dev`
  and `uv.lock` carries it.
- `[tool.ruff.lint]` selects an explicit rule set (`E4`, `E7`, `E9`,
  `F`, `I`, `UP`) rather than ruff's defaults, which widened in 0.17
  to blind-except, bandit and pylint checks. An upgrade cannot change
  the gate on its own; widening it is a deliberate edit. isort treats
  `conftest` and `helpers` as first-party (they sit on pytest's
  pythonpath) and keeps two blank lines after imports, the repo's
  existing style.
- The first run's findings (unsorted and unused imports, deprecated
  `typing` imports, `timezone.utc`, one TypeVar generic) are fixed
  with no behaviour change.
- The Test command in AGENTS.md (CLAUDE.md links to it) is
  `uv run --managed-python --frozen ruff check . && uv run --managed-python --frozen pytest -m static`.
  `tests/test_lint_gate.py` keeps the pin, the explicit rule set and
  the command in place.

## 2026-10-16T23:30:00Z · amendment · The pre-lifecycle body of PROJECT_STATE.md is refreshed (issue #46)

The #21 migration kept the pre-lifecycle body verbatim. That body is
no longer kept verbatim: #46 edits its stale sections in place, and
the earlier text stays in git history.

- `## PAUSED — 2026-08-26` becomes `## Open Work`. The pause's end
  condition (after DevOpsDays Portland, 2026-09-10) has passed. The
  critical path drops #22, #23 and #24, which are fixed statically,
  to `#17 → #18 → #20`, and #21 leaves the any-time list.
- `## Branch & Test Status` (80 passing) is removed; the lifecycle
  header's `## Branch & Tests` is the one status section and gains the
  remote line. The `Total: N static tests` line and the Phase 8
  mentions stay, for `test_critical_fix_a6` and
  `test_phase_08_hardening`.
- "this session" labels on the 2026-04-25 senior review are dated.
  Known gaps C11 and C12 are marked fixed (D1, D2), C13 mitigated
  (D3), and the deploy-manifest gap narrowed to what is still open.
- `tests/test_critical_fix_a6_project_state_truthful.py` gains a
  check that the file has one branch and test status section whose
  count agrees with the Total line.

## 2026-10-16T23:45:00Z · amendment · Promote-time entries append to decisions.md (issue #47)

The #21 migration left the 2026-10-15 promote entry at the foot of
`PROJECT_STATE.md` so the body stayed unchanged; the init entry above
says so. #46 has since stopped keeping that body verbatim, so the
reason is gone. The entry is carried over below with its original
heading and text, and removed from `PROJECT_STATE.md`.

From now on every decision entry, the promote-time ones included
(main fast-forwarded with known failures, a skipped gate, an accepted
red test), is appended here and never to `PROJECT_STATE.md`. AGENTS.md
§ "Session Discipline" states the rule.
`tests/test_decision_entries_location.py` fails if a
`## <timestamp> · ...` entry heading reappears in `PROJECT_STATE.md`.

The writer of the 2026-10-15 entry is the promote step outside this
repo (commit `cd5dd0f`, "Trivial: decision log entry"). Its target
file is fixed there, not here; this repo's rule and test catch a
stray entry at the next Test command run.

## 2026-10-15T12:00:00Z · 3.3 · Main fast-forwarded with known test failures

On Michael's instruction, main was fast-forwarded to staging to ship the Dependabot fix with these failures, all present on main before the fix, accepted: test_terraform_plan and test_gke_cluster_is_standard_with_wif_and_nap need live GCP; the credential has expired (invalid_grant).

## 2026-10-16T13:13:37Z · decision · The AIGatewayRoute takes the upstream CRD shape; ExtProc moves to an EnvoyExtensionPolicy on the Gateway (issue #49)

`burritbot-gemini-route` set `spec.targetRefs` (an HTTPRoute),
`spec.schema` and `spec.filters[].extProc`. The upstream
AIGatewayRoute (`aigateway.envoyproxy.io`, v1alpha1 and v1beta1)
defines none of them, so ArgoCD's ServerSideApply rejects or strips
them. The route is now v1beta1 (matching the AIServiceBackend from
#24) with `parentRefs: burritbot-ai-gateway`, and matches on
`x-ai-eg-model`, the header the gateway sets from the request body,
instead of `x-ai-model`, which nothing sets.

The NeMo Guardrails and LLM Guard ExtProc entries move to the
`burritbot-guardrails` EnvoyExtensionPolicy, unchanged in order,
port and buffered bodies. It targets the Gateway, not one route.
The old filters guarded the route they were attached to, the audience
HTTPRoute. The phase-05 spec has every guarded call traverse both
scanners, and the gateway is the single choke point. A Gateway target
covers the audience route and the HTTPRoute generated from the
AIGatewayRoute alike.

The #26 entry above holds the route in `burritbot-net` because the old
`targetRefs` was local. That reason is gone, but the listener stays
`from: Same`: the generated HTTPRoute takes the AIGatewayRoute's
namespace, so both routes on the gateway still live in `burritbot-net`.
The cross-manifest listener check now judges an AIGatewayRoute as
the HTTPRoute it generates.

`tests/test_ai_gateway_route_schema.py` holds both objects to the
fields their CRDs define, and its mutation tests catch each pre-#49
shape.

## 2026-10-16T13:41:30Z · decision · gateway.yaml needs Envoy AI Gateway v0.6.0 or later; the 0.2+ floor is raised to 0.6+ (issue #53)

No chart in this repo pins Envoy AI Gateway or Envoy Gateway, so the
pinned version is the documented floor, 0.2+. gateway.yaml was checked
against the upstream CRDs of every floor-relevant release
(`ai-gateway-crds-helm` at v0.2.0, v0.5.0, v0.6.0, v0.7.0, v1.0.0,
v1.1.0, v1.2.0; Envoy Gateway `gateway-crds-helm` at v1.7.0 and v1.9.2).

- The recollection in #53 was right about v1alpha1: in v0.2.0
  `spec.targetRefs` (required) names Gateways and `spec.schema` is
  required. v0.3.0 deprecates targetRefs for parentRefs. No release
  ever defined `spec.filters`, so the pre-#49 ExtProc was always
  pruned.
- The post-#49 AIGatewayRoute (v1beta1, parentRefs to the Gateway,
  `x-ai-eg-model` header match) is valid in v0.6.0 through v1.2.0 and
  unservable in v0.2.0 through v0.5.0, which serve only v1alpha1.
  The AIServiceBackend and BackendSecurityPolicy in
  vertex-ai-backend.yaml are v1beta1 too, so v0.6.0 is the floor for
  the whole guarded path.
- The `burritbot-guardrails` EnvoyExtensionPolicy is valid in Envoy
  Gateway v1.7.0 (what AI Gateway v0.6.0 builds against) and v1.9.2
  (AI Gateway v1.2.0). The AI Gateway controller creates no
  EnvoyExtensionPolicy of its own; it inserts its ext_proc through the
  extension server ahead of user ext_proc filters, so a Gateway-level
  policy also covers the generated HTTPRoute.

The phase-05 spec and both scorecards now say 0.6+. The static field
sets in `tests/test_ai_gateway_route_schema.py` are narrowed to what
every release from the floor up serves, and live tests check
gateway.yaml against the CRDs actually installed on the cluster.
`.claude/skills/the-net-ai-gateway.md` still says 0.2+: this run could
not write under `.claude/`.

## 2026-10-16T13:50:09Z · decision · The fastapi, google-genai and OpenTelemetry pins hold through the November 2026 delivery (issue #55)

Issue #55 (split from #28) asked whether to bump the exact pins
`fastapi==0.135.3`, `google-genai==1.71.0`,
`opentelemetry-api`/`-sdk`/`-exporter-otlp==1.41.0` and
`opentelemetry-instrumentation-fastapi==0.62b0` to the current
releases (fastapi 0.143.2, google-genai 2.31.0, OpenTelemetry 1.45.1 /
0.66b1). Decision: hold them. The spec settles it:

- The phase-06 spec and AGENTS.md Critical Versions pin these releases.
  The phase-06 Known Risk says to pin the SDK and prove it with a live
  Vertex call during rehearsal, because the `usage_metadata` shape that
  the gen_ai.* telemetry reads differs between SDK versions. No rule
  asks the pins to track the latest release, so a bump needs a reason.
- No reason exists today. OSV (queried 2026-10-16) lists no advisory
  for any of the exact pins: fastapi 0.135.3, google-genai 1.71.0,
  OpenTelemetry 1.41.0 / 0.62b0, uvicorn 0.44.0, pydantic 2.12.5,
  httpx 0.28.1, slowapi 0.1.9, or the locked starlette 1.8.0. PyPI has
  not yanked google-genai 1.71.0.
- A bump is not finished until a live `/chat` call against Vertex
  `gemini-3-pro` confirms the 2.x `response.text` and `usage_metadata`
  path. Nothing has run on a cluster yet and the GCP credential has
  expired, so a bump now would put an unproven major SDK change on the
  live critical path (`#17 → #18 → #20`) about three weeks before demo
  day.

What is accepted: google-genai 1.x has had no release since 1.75.0
(2026-05-04). 2.0.0 shipped on 2026-05-07, so a future 1.x security
fix will not come. The issue's isolated probe already shows that
2.31.0 imports `apps/burritbot/app.py` and builds the app, so the
bump is cheap once there is a reason.

When to revisit: after the delivery (2026-11-12). Bump earlier if an
advisory lands against any of these pins, or if the Phase 6 rehearsal
call fails on 1.71.0. A bump carries the spec and AGENTS.md amendment,
the pins in `pyproject.toml`, `apps/burritbot/requirements.txt` and
`apps/audience-frontend/backend/requirements.txt`, a refreshed
`uv.lock`, and the live `/chat` check.
`tests/test_burritbot_runtime_pins.py` fails if any one of those
moves without the rest.

## 2026-10-16T14:39:50Z · decision · The audience phone page: one Send button, request/response, page links from the Deployment env (issue #56)

#56 builds the page that BUILD-INSTRUCTIONS.md and the phase-07 spec
list but that was never written: `apps/audience-frontend/static/`
holds `index.html` (served at `/`), `app.js`, `styles.css` and
`qr.html` (the projector QR landing at `/qr`, with the bare code at
`/qr.svg`). Where the two specs disagree, the platform spec wins:

- **One Send button, not "Send to Unguarded" and "Send to Guarded".**
  BUILD-INSTRUCTIONS.md Phase 7 asks for two buttons. The phase-07 spec
  and the runbook make the target a server-side switch that
  `cast-net.sh` flips during the talk, and Cast the Net only works as a
  reveal if the room cannot choose the guarded path for itself. Each
  reply is labelled with the bot that answered (`unguarded` or
  `guarded`, from the `/chat` response's `target`).
- **Request/response, no WebSocket.** BUILD-INSTRUCTIONS.md lists
  WebSocket streaming. `/chat` returns one JSON reply, and BurritBot
  returns no stream to relay. Streaming would mean changing BurritBot,
  the gateway path and the proxy, three weeks before the delivery, to
  show a reply that arrives in about a second anyway.
- **The QR code is rendered on the server** from `AUDIENCE_PUBLIC_URL`
  with `qrcode` (the spec allows generated or pre-baked). It is not
  generated from the browser's own address: a rehearsal through
  `kubectl port-forward` would otherwise project a `localhost` code.
  No JavaScript QR library is needed, and nothing loads from a CDN on
  venue Wi-Fi.
- **Page links fail loudly.** `FEEDBACK_URL` and `AUDIENCE_PUBLIC_URL`
  are read per request. If either is unset or is not an absolute
  http(s) URL, `/` or `/qr` returns `503` naming the variable.
  `/healthz` and `/chat` keep working, so a missing link cannot take
  down the probes. The runbook's Pre-flight step 8 checks both.

Neither value is set in `apps/audience-frontend/k8s/deployment.yaml`.
The feedback destination (session survey, a form of our own, or
something else) and the public hostname (no Ingress exists yet) are
facts and deploy configuration for Michael.

The image build context moves from `backend/` to
`apps/audience-frontend`, so the image carries `static/` beside
`backend/`, the same layout as the repo. No script or doc in the repo
built the image, so nothing else changes.

Dependencies:

- Runtime: `qrcode==8.2` joins `apps/audience-frontend/backend/requirements.txt`.
  8.2 is the current PyPI release (checked 2026-10-16) and the version
  `uv.lock` already resolves for the dev group. It is pure Python; the
  SVG is written by hand from `get_matrix()`, so Pillow is not needed.
- Dev: `slowapi==0.1.9` and `httpx==0.28.1` join the dev group, pinned to
  the image's versions (slowapi 0.1.10 is current, but the image pin was
  held under #55). They let `tests/test_phase_07_audience_page.py` load
  the real `main.py` and drive it in-process through FastAPI's
  `TestClient`. No upstream is faked: the static tests never reach
  `/chat` past validation.

Not done here: the Real devices row in the runbook's Measurements
record needs a real iOS Safari phone and a real Android Chrome phone
against a live cluster. Headless Chromium rendered the page with
iPhone SE, iPhone 13 and Pixel 7 emulation (320, 390 and 412 px wide):
no horizontal overflow, and the Feedback button showed in the header.
That is not the device check.

## 2026-10-16T15:08:29Z · decision · A delivery is costed by the burritbot-io_delivery label; the billing export dataset stays out of Terraform (issue #59)

Issue #59 asked for GKE resource labels and a billing export so a
delivery can be costed by label. Terraform is deploy configuration, so
this lands for Michael's review before it is applied.

- **The delivery labels itself.** `var.delivery` is required with no
  default and validates as a GCP label value. `local.cost_labels`
  (`labels.tf`) carries `burritbot-io_owner` and
  `burritbot-io_delivery`; the GKE cluster (`resource_labels`, which
  GKE copies to node VMs and disks) and the Secret Manager secret merge
  them. An apply without a slug fails rather than labelling spend under
  the wrong delivery. The runbook's Night Before apply passes
  `-var delivery=<slug>` with the talk's own slug.
- **GKE cost allocation is on** (`cost_management_config`). It adds
  `k8s-namespace` and `k8s-label/*` to the detailed export, which
  splits guarded from unguarded spend. It only reaches the detailed
  usage cost export, and rows take up to three days to land.
- **The export dataset is out of band.** `scripts/teardown.sh` runs
  `terraform destroy` within hours of a delivery, before billing rows
  land, and a billing account has one detailed export. So the dataset is
  created once with `bq mk` and the export enabled in the console (the
  only way Cloud Billing export can be enabled), the same pattern as the
  state bucket. `docs/BILLING-EXPORT.md` holds the steps and the Cost
  row queries.
- **Vertex AI spend is read by project, service and time window.**
  Model calls carry no labels yet, so another Vertex AI user of the
  project inside the window would be counted too.
- **Cost envelope re-priced** in `PLAN.md` §9 and the
  BUILD-INSTRUCTIONS table for Gemini 3 Pro at list prices checked
  2026-10-16 ($2 / $12 per 1M input / output tokens, ≤200K prompts),
  the $0.10/hr regional cluster fee, and the night-before provisioning
  window. They are still estimates until a rehearsal is measured.

Not verified here: no `terraform` binary on the build host, so
`terraform validate` / `plan` did not run against these changes.

## 2026-10-16T15:20:34Z · decision · The ruff gate widens to blind-except and silent-swallow checks (issue #62)

Issue #62 asked whether to widen the #44 rule set. Decided yes: the
rules catch exactly the silent fallbacks the "no fallbacks" rule
forbids, and all 21 findings had a fix that did not need a `noqa`
except one.

What it changes:

- `[tool.ruff.lint].select` adds `BLE`, `S110`, `S112`, `PLW1510`,
  `PERF102` and `TRY401` as explicit codes, not whole families, so a
  ruff upgrade still cannot widen the gate on its own. The other S, PLW,
  PERF and TRY rules are not selected; adding them is a separate,
  deliberate edit. `tests/test_lint_gate.py` fails if BLE, S110, S112
  or PLW1510 drop out.
- `chatbot-research/research.py` catches only Playwright's `Error`
  (its `TimeoutError` subclasses it) and logs each caught error instead
  of passing or continuing silently: selector probes at debug, the
  send-button fallback at info, a failed error screenshot at warning.
  Anything else now stops the run. Playwright is imported at module top,
  so the old "playwright is not installed" exit path is gone; it is in
  the dev group.
- `tests/conftest.py` no longer turns any exception into a skip. The
  kubeconfig fixtures catch only `kubernetes.config.ConfigException`
  and the GCP client fixtures only `DefaultCredentialsError`, and both
  call `pytest.fail` with the missing prerequisite named. The unused
  `kubeconfig_loaded` fixture is removed. Live tests on a host without
  a cluster or ADC now fail instead of skipping, as the Tests rule asks.
- The two terraform live tests fail when terraform is not on PATH, and
  `test_all_shell_scripts_start_with_aboutme` asserts `scripts/` exists
  instead of skipping, and the Colang parse test imports nemoguardrails
  (a dev dependency) directly instead of `pytest.importorskip`. These
  were the remaining skip paths in tests/.
- `subprocess.run` calls whose return code the test asserts carry
  `check=False` explicitly.
- `test_colang_v1_rail_parses` keeps `except Exception` with
  `# noqa: BLE001`: nemoguardrails' `ColangParser` raises bare
  `Exception`, so there is nothing narrower to catch, and the handler
  fails the test with the rail's name rather than swallowing.
- The audience backend's `logger.exception` drops the redundant
  exception argument (TRY401); the traceback already carries it.

## 2026-10-16T15:40:00Z · decision · The repo banner is a Pillow composite, not a Gemini-generated repo-showcase render (issue #32)

- `assets/hero.png` (1376x768, the Unleash banner's size) is the first
  image in `README.md`, directly under the H1, so the MRF-website
  banner sync picks it up.
- It is drawn with Pillow: the BurritoBot burrito
  (`Unleash_an_Agent_Watch_It_Burn` `assets/burrito.png`) caught in a
  glowing cyan orb-web net on the dark ember-and-violet palette of
  `watch-it-burn-hero.png`. The two headshot circles and their
  positions are lifted 1:1 from that already-public banner.
- The repo-showcase path (Gemini background, Drive portraits) had no
  key or Drive access from the run. The earlier run's question offered
  this composite as the default; it is taken. A repo-showcase render
  can replace the file at the same path later without a README change.
- The GitHub social preview card is a repo setting and stays manual.

## 2026-10-16T15:44:16Z · decision · Phones reach the audience frontend through a GKE Gateway; the 10/minute limit keys on the load balancer's client entry (issue #57)

The audience limit was keyed on `get_remote_address`, the connecting
address. Whatever sat in front of the pod, the room shared one budget.

- **Exposure path: a GKE Gateway** with GatewayClass
  `gke-l7-global-external-managed` (the global external Application Load
  Balancer), routed by an HTTPRoute to the `audience-frontend` Service.
  This is the Gateway API swap that `docs/KUBEAUTO-REUSE-MAP.md` and
  `docs/PHASE-B-EKS-ADAPT-PLAN.md` already set for the kubeauto ALB
  ingress, and "Gateway API" is in the Web layer in `CLAUDE.md`. The
  regional class was not chosen: its proxies send from the proxy-only
  subnet, a range that differs per VPC, so the frontend could not name
  its trusted proxy without deploy configuration.
- **The limit stays per source address, 10/minute** (spec Phase 7, which
  also names the `X-Forwarded-For` fix as the known risk). A room-sized
  global limit was not chosen. It would drop the per-phone fairness the
  spec asks for, and one keen phone could take the whole room's budget.
- **`client_address()` replaces `get_remote_address`.** A peer in
  Google's documented load-balancer source ranges (`35.191.0.0/16`,
  `130.211.0.0/22`, `2600:2d00:1:1::/64`) is keyed on the
  second-from-last `X-Forwarded-For` entry. The load balancer appends
  `<client-ip>,<load-balancer-ip>`, so anything further left came from
  the phone and is ignored. A load-balancer request without a valid
  client entry gets a `400` and is never keyed on the proxy. Any other
  peer (a port-forward, an in-cluster caller) is keyed on itself and its
  header is ignored. Source:
  https://docs.cloud.google.com/load-balancing/docs/https (firewall
  rules; X-Forwarded-For), read 2026-10-16.
- **uvicorn's `--proxy-headers` is not used.** It walks
  `X-Forwarded-For` from the right and stops at the first untrusted
  address, which is the load balancer's own forwarding-rule IP. That IP
  is not known until the Gateway exists, so it would key the room on
  the load balancer again.

Not done here:

- The venue NAT is still a shared address. Phones on one venue Wi-Fi
  leave through the same public IP and share its 10 prompts a minute.
  Only phones on cellular get a budget each. Whether to raise the
  per-address limit, key on something per browser, or accept it is a
  talk decision. It is raised as a follow-up.
- No Gateway or HTTPRoute manifest is added. The hostname, the
  certificate and enabling the Gateway API on the cluster are facts
  and deploy configuration for Michael, raised as a follow-up. Until
  then, `client_address()` keys port-forwarded rehearsals on the peer.

## 2026-10-16T16:05:49Z · decision · question 133: the promote step already appends decision entries to decisions.md (issue #65)

Question 133 asked how to close #65. The promote step that wrote
`cd5dd0f` lives outside this repo, and `decisions.md` did not exist
here when that commit landed.

Answer: check the ship skill and state-persistence.md. If their
decision-entry append already goes to a root `decisions.md` when one
exists, close #65 as already satisfied. If not, change the target to
`decisions.md` (append-only, repo root) and close #65.

Decided by hecaton under Michael's standing rules, not by Michael.

Checked in `peopleforrester/llm-coding-workflow` at `0c68e17`
(2026-10-13 17:42 -0400, before `cd5dd0f`), in the read-only runner
checkout:

- `claude-config/skills/ship/SKILL.md`, step 4 "Update state", appends
  the phase transition to `PROJECT_STATE.md` and, "for a conditional
  skip or a bypass", adds an entry to `decisions.md` per
  state-persistence. A fast-forward of main with known failures is a
  bypass, so its entry goes to `decisions.md`.
- `claude-config/rules/state-persistence.md` defines `decisions.md` as
  the append-only audit log and `PROJECT_STATE.md` as the overwritable
  dashboard. It has no fallback to `PROJECT_STATE.md`.
- `scripts/ship.sh` writes neither file.
- `claude-config/skills/init-state/SKILL.md` step 3b creates
  `decisions.md` when a repo lacks one.

What it changes: nothing in the writer, which already targets
`decisions.md`. The 2026-10-15 entry fell back to `PROJECT_STATE.md`
only because this repo had no `decisions.md` until init-state created
it in `aeb91f8` on 2026-10-16. #65 closes as already satisfied. The
#47 rule in AGENTS.md and `tests/test_decision_entries_location.py`
still catch a stray entry.

## 2026-10-16T16:14:31Z · decision · Guarded traffic enters the gateway by its pinned proxy Service and is split by Host; guarded BurritBot calls Vertex only through the AIGatewayRoute (issue #67)

Three gaps kept guarded traffic off the routes it was meant to take.

- **Proxy Service name.** Envoy Gateway runs the proxy in its controller
  namespace (`envoy-gateway-system`, the namespace the Terraform WIF
  binding already names) as `envoy-<ns>-<gateway>-<hash>`. The
  `burritbot-ai-gateway` EnvoyProxy now sets `envoyService.name:
  burritbot-ai-gateway` and `type: ClusterIP`, both defined in the
  EnvoyProxy CRD of Envoy Gateway v1.7.0 and v1.9.2. ClusterIP also
  stops the default `LoadBalancer` from putting the guarded gateway on
  an external IP. Callers use
  `burritbot-ai-gateway.envoy-gateway-system.svc.cluster.local:8080`.
  Gateway namespace mode was not chosen: it is a controller-wide
  setting in a chart this repo does not pin.
- **Routes split by Host.** The audience frontend sends
  `Host: burritbot.burritbot.local` (`BURRITBOT_GUARDED_HOST`) on the
  guarded target, so `burritbot-audience` wins. Every other Host falls
  to the hostname-less HTTPRoute generated from `burritbot-gemini-route`.
  A path split was not chosen: both routes would share the `*` virtual
  host. Hostnames on the AIGatewayRoute need AI Gateway v0.7.0, above
  the 0.6 floor.
- **Guarded model call.** With `BURRITBOT_GUARDED=true`, `app.py` posts
  an OpenAI chat completion (`/v1/chat/completions`, `model:
  gemini-3-pro`, system and user messages, `max_completion_tokens`,
  all read by the v0.6.0 OpenAI→GCPVertexAI translator) to
  `AI_GATEWAY_URL`, and reads `choices[0].message.content` and `usage`.
  A guarded pod without `AI_GATEWAY_URL` fails at startup. The guarded
  Deployment drops `GOOGLE_CLOUD_*`. Unguarded BurritBot still calls
  Vertex through google-genai, and both run the same image.
- **Egress lock.** `restrict-burritbot-network` let guarded BurritBot
  reach only pods in `burritbot-net`, where no proxy runs. It now admits
  the pods labelled `gateway.envoyproxy.io/owning-gateway-name:
  burritbot-ai-gateway` / `owning-gateway-namespace: burritbot-net` in
  `envoy-gateway-system` on 8080, plus DNS. The unused 443 port is gone.
- **Dependency.** `httpx==0.28.1` joins `apps/burritbot/requirements.txt`
  (2026-10-16) for the gateway call. It is already pinned at 0.28.1 in
  the audience image and the dev group, and google-genai 1.71.0 already
  installs it, so no new package enters the lock.

`tests/test_guarded_gateway_path.py` holds the three hops to the
manifests: the frontend URL and the guarded `AI_GATEWAY_URL` against
the EnvoyProxy, WIF namespace and listener port; the audience Host
against the route hostnames; and the model in the gateway body against
the route's `x-ai-eg-model` match. A guarded `/chat` with no Vertex
project fails on the gateway hop, not on Vertex.

## 2026-10-16T16:26:14Z · decision · Envoy Gateway v1.9.2 and Agent Router (Envoy AI Gateway) v1.2.0 are installed by ArgoCD; GatewayClass envoy-ai-gateway (issue #68)

`ai-gateway/envoy/gateway.yaml` named GatewayClass `envoy-ai-gateway`
and used CRDs that nothing in `gitops/apps` installed. Three Helm
Applications and a GatewayClass now do, following the upstream install
(Agent Router v1.2.0 `site/docs/getting-started/prerequisites.md` and
`installation.md`). Envoy AI Gateway was renamed Agent Router in v1.2.0
(released 2026-10-07); the charts, images and API groups kept their
names.

- **Versions.** `gateway-helm` v1.9.2, `ai-gateway-crds-helm` v1.2.0
  and `ai-gateway-helm` v1.2.0, all from `docker.io/envoyproxy` (OCI).
  These are the current releases (checked 2026-10-16), and v1.2.0 builds
  against Envoy Gateway v1.9.2. The #53 entry already checked
  gateway.yaml against both, and the #67 entry checked the EnvoyProxy
  against v1.9.2. The 0.6+ floor stays as the floor.
- **`envoy-gateway`** (wave -1, `envoy-gateway-system`) takes the
  upstream `manifests/envoy-gateway-values.yaml` at v1.2.0 inline:
  the extension manager hooks, `enableBackend` (the Vertex `Backend`)
  and `enableEnvoyPatchPolicy`, pointed at
  `ai-gateway-controller.envoy-ai-gateway-system:1063`. Its crds
  subchart installs the Gateway API CRDs and the Envoy Gateway CRDs.
  ServerSideApply, because the EnvoyProxy and Gateway API CRDs are
  larger than the client-side last-applied annotation allows. The
  topology-injector webhook is off: it listens on 9443 (see below) and
  zone-aware routing is not used.
- **`ai-gateway-crds`** (wave -1, `envoy-ai-gateway-system`), with
  ServerSideApply.
- **`ai-gateway-controller`** (wave 2, `envoy-ai-gateway-system`),
  after cert-manager (wave 1). Two chart defaults do not survive
  ArgoCD's `helm template` render, where `lookup` finds nothing:
  - The webhook keypair would be reminted by `genCA` on every render.
    `controller.mutatingWebhook.certManager.enable` has cert-manager
    issue it and inject the CA bundle.
  - The MCP session seed would be redrawn by `randAlphaNum` on every
    render. The v1.2.0 notes say to set `seed` or `existingSecret` for
    GitOps. A `seed` value in Git is a committed secret. An
    `existingSecret` would mean a new Secret Manager entry and
    ExternalSecret for a feature BurritBot does not use (no MCPRoute).
    Instead the Application ignores `/data/seed` on the
    `ai-gateway-controller-mcp-session-encryption` Secret with
    `RespectIgnoreDifferences=true`, so the seed minted at first sync
    stays and never reaches Git. If an MCPRoute is ever added, move to
    `existingSecret` from Secret Manager.
- **Webhook port 10250.** The cluster has private nodes and a
  `master_ipv4_cidr_block` (VPC peering). GKE's auto-created `-master`
  firewall rule lets the control plane reach nodes on TCP 443 and 10250
  only. The controller's pod-mutating webhook (failurePolicy Fail, on the
  Envoy proxy pods) defaults to 9443, which would time out and block the
  burritbot-ai-gateway proxy pod. It moves to 10250, the port
  cert-manager's webhook already uses. Kyverno's webhook on 9443 has the
  same exposure; that is raised separately.
- **`ai-gateway`** moves from wave 1 to wave 3, after the CRDs and the
  controller. BurritBot (wave 1) and the audience frontend (wave 2) call
  the gateway only at request time, so they do not need to wait.
- **GatewayClass `envoy-ai-gateway`** lives in
  `ai-gateway/envoy/gatewayclass.yaml` and is synced by the `ai-gateway`
  kustomization, with `controllerName:
  gateway.envoyproxy.io/gatewayclass-controller`, the same name as the
  Envoy Gateway config. The AI Gateway controller extends Envoy Gateway
  and owns no GatewayClass of its own.
- **Namespaces.** `envoy-gateway-system` and `envoy-ai-gateway-system`
  join `gitops/namespaces/namespaces.yaml`, so every app keeps
  `CreateNamespace=false`.
- **GKE-managed Gateway API.** gateway-helm brings its own Gateway API
  CRDs. Turning on `gateway_api_config` in Terraform (which the #57 GKE
  Gateway for the audience frontend would need) would give the cluster
  two owners of those CRDs. `tests/test_incompatible_settings.py` now
  reports that pair and names the way out: install only the Envoy
  Gateway CRDs from `gateway-crds-helm`, once GKE's Gateway API serves
  BackendTLSPolicy v1.

`tests/test_ai_gateway_controller_install.py` holds the pins, the
extension-manager target, the GatewayClass, the webhook port and cert,
the MCP seed handling and the waves. Its live tests check the CRDs, the
GatewayClass's Accepted condition, the Gateway's Programmed condition
and the controller Deployment. The phase-05 live check now looks for
the proxy pod in `envoy-gateway-system` by its owning-gateway labels,
not in `burritbot-net`.

This is deploy configuration. It lands for Michael's review before any
cluster syncs it; nothing has been applied.
