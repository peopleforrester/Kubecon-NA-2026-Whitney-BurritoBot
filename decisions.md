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

## 2026-10-16T16:37:24Z · amendment · Missing live prerequisites fail the test; nothing in tests/ skips (issue #61)

Governance bans skip paths in tests. Most of the skips this issue
named were already removed by #62 (7f2d773): the live kubeconfig and
GCP client fixtures in `tests/conftest.py` call `pytest.fail` naming the
missing kubeconfig or Application Default Credentials, the Terraform
checks fail when `terraform` is not on PATH, the phase-08 ABOUTME check
asserts `scripts/` exists, and the Colang parse test imports
nemoguardrails directly. A missing kubernetes or google-cloud client
library fails the fixture with the import error; all of them are in the
dev group. This change keeps that conftest as it is and finishes the
rest:

- **The Prometheus rename check asserts** `additionalPrometheusRulesMap`
  is present instead of returning early when it is absent (an
  exit-as-skip). With the map removed from `gitops/apps/prometheus.yaml`
  the check now fails.
- **The Phase C5 plan is amended.** `docs/PHASE-C-GREENFIELD-PLAN.md`
  no longer lets the Colang test mark itself skipped when the package
  is missing.
- **No in-repo guard test.** A test that lists the banned markers has
  to spell them out, which trips the dispatcher's skip-markers gate on
  the diff. That gate already holds the rule.

The static Test command never requests the live fixtures, so it still
passes everywhere (409 passed). The E2E command exits non-zero with 0
skipped on a host without a cluster, ADC or terraform, each test naming
what is missing.

## 2026-10-16T16:41:38Z · amendment · Live fixtures are proven loud by a probe, and name the fix (issue #63)

#62 already made the `tests/conftest.py` live fixtures fail the test
when the cluster or ADC is missing. This change keeps that conftest
and adds what #63's approved design carried on top of it, re-landed on
current staging:

- **Probe test.** `tests/test_live_fixtures_fail_loudly.py` (static,
  7 cases) runs a one-test pytest subprocess per live fixture with
  `KUBECONFIG` and `GOOGLE_APPLICATION_CREDENTIALS` pointing at missing
  files. Each run must exit non-zero with a setup error. Against the
  pre-#62 conftest all seven fail, so the probe is not vacuous.
- **The message names the fix.** The kubeconfig failure now says to run
  `gcloud container clusters get-credentials` for the demo cluster, as
  the GCP fixtures already say `gcloud auth application-default login`.
  The probe asserts both.
- **No in-repo guard test** listing the banned markers, for the reason
  given under #61.

## 2026-10-16T17:04:13Z · decision · #72 is already satisfied by #68; no new install (issue #72)

#72 asks for a pinned chart Application for Envoy Gateway and the Envoy
AI Gateway CRDs and controller (AI Gateway v0.6.0 or later with its
matching Envoy Gateway; v1.2.0 needs Envoy Gateway 1.9.2 or later),
plus the `envoy-ai-gateway` GatewayClass. #68 (`39fd024`, merged to
staging in `db4e9ca`) already does all of it:

- `gitops/apps/envoy-gateway.yaml`: `gateway-helm` v1.9.2 (wave -1).
- `gitops/apps/ai-gateway-crds.yaml`: `ai-gateway-crds-helm` v1.2.0
  (wave -1).
- `gitops/apps/ai-gateway-controller.yaml`: `ai-gateway-helm` v1.2.0
  (wave 2).
- `ai-gateway/envoy/gatewayclass.yaml`: GatewayClass
  `envoy-ai-gateway`, rendered by `deploy/ai-gateway/kustomization.yaml`.

The app-of-apps (`gitops/bootstrap/app-of-apps.yaml`) picks all three
up from `gitops/apps` (recursive, `*.yaml`).
`tests/test_ai_gateway_controller_install.py` holds the pins, the
GatewayClass and the waves (22 static cases pass). Nothing changes in
the manifests. #68's own entry records that this deploy configuration
waits for Michael's review before any cluster syncs it. That applies to
#72 too.

## 2026-10-16T17:08:11Z · decision · The guardrails ExtProc reaches a burritbot-extproc gRPC sidecar, not the scanners' REST ports (issue #66)

The `burritbot-guardrails` EnvoyExtensionPolicy named `nemo-guardrails:8000`
and `llm-guard:8000` as ExtProc backends. Envoy's ext_proc filter speaks
gRPC `envoy.service.ext_proc.v3.ExternalProcessor`; both scanners serve
REST (the NeMo Guardrails microservice `/v1/guardrail/checks`,
llm-guard-api `/analyze/prompt` and `/analyze/output`). With failOpen
false, every request through the gateway would have been a 500.

- **An ext_proc adapter, not a different hook.** The issue offered moving
  enforcement elsewhere. Moving it into BurritBot's code would make the
  app guard itself, while the talk's claim is that the platform says no
  and the gateway is the single choke point (phase-05 spec). The net
  stays on the gateway.
- **One sidecar per scanner pod.** `ai-gateway/extproc/adapter.py` runs as
  `burritbot-extproc` (the name Kyverno's `require-burritbot-sidecar-naming`
  demands) beside each scanner and calls it on `127.0.0.1:8000`. `SCANNER`
  picks the REST contract. The Services gain an `extproc` port, 50051,
  which the policy names. Port 9000 was avoided: the #23 mutation tests
  use it as the drifted port they must catch. The two ExtProc entries,
  their order and their buffered bodies are unchanged.
- **What the adapter does.** It reads the user text from BurritBot's
  `{"prompt"}` or an OpenAI `{"messages"}` body, and the model text from
  `{"reply"}` or OpenAI `{"choices"}`. A blocked prompt or reply gets a
  403 JSON body naming the scanner and its findings. When LLM Guard
  sanitizes text (Anonymize, Sensitive), the body is rewritten and its
  content-length set. Responses with no model text (health checks,
  error details) pass unscanned because there is nothing to scan.
- **Fail closed.** A request body with no readable user text is a 400.
  An unreachable scanner, an error status or a reply outside the
  contract is a 503. Unscanned text never goes through. `failOpen`
  stays unset (false).
- **Timeouts.** Envoy's ext_proc `message_timeout` defaults to 200ms,
  which no scanner meets: NeMo's rails can call Gemini. Each entry now sets
  `messageTimeout: 10s`. The adapter's `SCANNER_TIMEOUT_SECONDS` is 8, so a
  slow scanner gets the adapter's explicit 503 rather than Envoy's 500.
- **New dependencies (2026-10-16):** `envoy-data-plane==2.2.0`
  (2026-07-21), `betterproto2==0.9.1` and `grpclib==0.4.9`, in the image's
  `ai-gateway/extproc/requirements.txt` and in the dev group so the
  static tests run the real adapter. Why: Envoy publishes no Python
  stubs for ext_proc, and generating them needs the whole Envoy, xds,
  udpa and validate proto tree. envoy-data-plane ships that tree
  generated, with a grpclib `ExternalProcessorBase`. betterproto2 is
  pinned at 0.9.1 because envoy-data-plane 2.2.0 needs `<0.10`. OSV
  listed no advisory for any of these versions, or for h2 4.4.1 or
  protobuf 7.36.2, on 2026-10-16. httpx stays at the existing 0.28.1 pin.

Tests: `tests/test_guardrails_extproc.py` resolves each ExtProc backend
through its Service to the container behind it and requires the adapter
there. Mutation tests point an entry back at port 8000, drop the timeout,
set it under the adapter's and turn failOpen on. A real in-process gRPC
round trip shows the adapter refusing with a 503 when the scanner is down
and a 400 when the body is unreadable. The live tests port-forward to
each sidecar and expect the salsa prompt refused with a 403.

Not verified here: nothing has run on a cluster (#18). The image
`burritbot-extproc:0.1.0` is not built or pushed; this run had no Docker
access. The adapter targets the REST contracts as documented, and the
scanner Deployments themselves have unverified gaps, which are raised as
follow-ups.

## 2026-10-16T17:19:39Z · decision · #73 is already satisfied by #66; scanner protocol confirmed off-cluster (issue #73)

#73 asks to check whether the `burritbot-guardrails` ExtProc backends
speak Envoy ext_proc gRPC and, if they do not, to put an ext_proc
adapter in front of each scanner. #66 (`e59ad98`, merged to staging in
`be59dba`) already did that. Each ExtProc entry names port 50051 of a
`burritbot-extproc` sidecar (`ai-gateway/extproc/adapter.py`) in the
scanner's pod, never the scanner's port 8000, and `failOpen` stays
unset. `tests/test_guardrails_extproc.py` holds that wiring (456 static
cases pass). Nothing changes in the manifests.

There is no cluster (#18), so the protocol check ran against what each
image publishes:

- **LLM Guard (`laiyer/llm-guard-api:0.3.9`)**: REST, confirmed from the
  image. The amd64 image config is `CMD ["llm_guard_api",
  "/home/user/app/config/scanners.yml"]` with `EXPOSE 8000/tcp`. The app
  layer is FastAPI 0.109.2 on uvicorn 0.27.0, with no gRPC dependency.
  It serves `GET /`, `/healthz`, `/readyz`, `/metrics` and `POST
  /analyze/prompt` and `/analyze/output`. Its `schemas.py` matches the
  adapter's contract field for field: `{prompt}` returns
  `{sanitized_prompt, is_valid, scanners}`, and `{prompt, output}`
  returns `{sanitized_output, is_valid, scanners}`.
- **NeMo Guardrails (`nvcr.io/nvidia/nemo-microservices/guardrails:25.07`)**:
  REST, from NVIDIA's 25.07 documentation. NGC refuses anonymous pulls,
  so the image itself was not read. The microservice serves
  `/v1/guardrail/chat/completions`, `/v1/guardrail/checks` and
  `/v1/health`, which matches the adapter's `/v1/guardrail/checks` call.

So the issue's premise holds, and #66's adapter is the fix it asks for.
The same reading found that neither scanner container, as deployed,
would answer the adapter. These are scanner configuration defects, not
ext_proc protocol defects, so they are raised as follow-ups instead of
being fixed here:

- llm-guard-api takes its config path only from that positional
  argument. It ignores `LLM_GUARD_CONFIG`, so the mounted
  `/config/config.yaml` is never read. The image's built-in
  `scanners.yml` turns on `auth: http_bearer` with an empty
  `${AUTH_TOKEN:}`, so every `/analyze/*` call without a bearer token
  is refused, which the adapter turns into a 503. The ConfigMap also
  uses flat scanner keys, while the API expects `type` plus `params`.
- The NeMo microservice listens on `GUARDRAILS_PORT`, which defaults to
  7331, not 8000. It reads configurations from `CONFIG_STORE_PATH`
  (default `/app/services/guardrails/config-store`, one directory per
  config id), not from `NEMO_GUARDRAILS_CONFIG_PATH`. `/v1/rails/configs`
  belongs to the open-source `nemoguardrails` server, not the
  microservice, so the probes would never pass.

As with #66, live confirmation rides on #18.

## 2026-10-16T17:26:45Z · decision · The ai-gateway manifests need Gateway API v1.4 or later; the v1.2 floor is raised to v1.4+ (issue #74)

The phase-05 spec, the spec scorecard and the AI gateway skill pinned
Gateway API v1.2. The served versions were read from the upstream
`standard-install.yaml` and `experimental-install.yaml` CRDs of v1.0.0,
v1.1.0, v1.2.0, v1.2.1, v1.3.0, v1.4.0, v1.4.1, v1.5.1 and v1.6.1:

- BackendTLSPolicy, which `ai-gateway/envoy/vertex-ai-backend.yaml`
  applies at `gateway.networking.k8s.io/v1`, is served only as
  v1alpha3 in v1.2 and v1.3, and only in the experimental channel.
  v1 first ships in v1.4.0 (standard and experimental). So #74 is
  right: on a v1.2 install the Vertex AI TLS policy does not apply.
- The policy validates against the v1.4.0, v1.4.1 and v1.6.1 v1
  schemas. The other Gateway API objects (GatewayClass, Gateway,
  HTTPRoute v1; ReferenceGrant v1beta1) validate from v1.2.0 on.
  Gateway `spec.infrastructure` is unknown to the v1.0 and v1.1
  standard CRDs.
- Envoy Gateway v1.7.0 and AI Gateway v0.6.0 (the #53 floor) build
  against gateway-api v1.4.1 (`go.mod`). Envoy Gateway v1.9.2 and
  AI Gateway v1.2.0 (the #68 install) build against v1.6.1. So the
  v1.4 floor agrees with the AI Gateway 0.6 floor.

The three docs now say v1.4+. `tests/test_gateway_api_floor.py` records
the first release that serves each Gateway API apiVersion and kind in
the manifests, derives the floor from them, and holds the docs to it.
It fails if a Gateway API object turns up whose apiVersion and kind are
not recorded. A live test checks each object against the CRDs installed
on the cluster. The skill's Envoy AI Gateway line, left at 0.2+ by #53,
now says 0.6+ and is part of the #53 doc-floor test.

## 2026-10-16T17:37:09Z · amendment · The platform is checked against the accepted abstract, not the CFP draft (issue #75)

talks-knowledge#12 asked for readiness against the accepted text,
Sessionize session 1249553 (talks-knowledge
`abstracts/recovered/sessionize-public-profile.md`, section 5), using the
nine-point checklist in talks-knowledge
`talks/2026-10-16_hard-dated-commitments.md`. Two things follow:

- `presentations/kubecon-na-2026/docs/CFP-SUBMISSION.md` is an earlier
  draft. Its header now says so and points at the accepted session. The
  #25 entry above calls it "the accepted CFP"; that entry stands as
  written, and this one corrects it.
- The record is `presentations/kubecon-na-2026/docs/ABSTRACT-READINESS.md`.
  The run had no read access to talks-knowledge, so the points are taken
  as issue #75 names them. Where a point reads two ways ("mid-inference"
  as in the inference path or during generation), the row rates both.
  Verdict: not ready. 2 READY-STATIC, 4 PARTIAL, 3 MISSING.

Three points in the accepted text conflict with scope this repo set
before the acceptance was read: the MCP server (ruled out in
`PORTLAND-CARRY-FORWARD.md`), the full IDP (Backstage excluded in
`docs/KUBEAUTO-REUSE-MAP.md`) and live audience hacking (AGENTS.md keeps
attacks presenter-driven). They are open questions for Michael and
Whitney; nothing here changes those rules. `tests/test_abstract_readiness.py`
holds the record to nine rated rows and to paths that exist.

## 2026-10-16T17:52:00Z · decision · question 130: the cold read is Monday 2026-10-26 and Whitney reads (issue #60)

Question 130 asked Michael and Whitney to confirm the proposed cold read
of `RUNBOOK.md` (Night Before through Teardown, against a live cluster,
Measurements record open, one issue for every stop or guess) on
2026-10-30, with Whitney as the reader, and a paper-read fallback if #18
had not landed by 2026-10-27.

Answer: Monday 2026-10-26, Whitney reads. Michael and Whitney are both
back in Austin on 2026-10-25, and the 26th leaves 14 days for fixes
before 2026-11-09. It is on Michael's calendar, 10:00 to 16:00 Central.
The paper-read fallback check moves to 2026-10-23: if #18 (live
bring-up) has not landed by then, the read becomes a paper read.

Decided by Michael. Verdict: overridden (the proposed date was
replaced).

What it changes:

- `PORTLAND-CARRY-FORWARD.md` § Cold read states the confirmed date,
  time, place and reader instead of a proposal, and the gate's
  fallback date moves to 2026-10-23.
- `PLAN.md` §3 carries the confirmed cold read and the 2026-10-23
  paper-read check under the Phase 8 rehearsals.
- `PROJECT_STATE.md` dates the `#17 → #18 → #20` critical path against
  the 2026-10-23 check and the 2026-10-26 read.
- `tests/test_portland_carry_forward.py` pins `COLD_READ_DATE`
  (2026-10-26), `COLD_READ_READER` (Whitney) and `PAPER_READ_CHECK`
  (2026-10-23). The lead-time test checks the pinned date, not the
  earliest date in the section, and a new test holds the section to
  exactly those dates plus the event start, names the reader and
  rejects "proposed".
- `ABSTRACT-READINESS.md` (added under #75 while this was in flight)
  restates the fallback with the 2026-10-23 date, and a static test
  holds every presentation doc that mentions the paper read to that
  date.
## 2026-10-16T19:36:51Z · decision · The deploy/<x> wrappers reference per-directory kustomizations; the load restrictor stays at its default (issue #76)

#54 found that the five `deploy/<x>` wrapper Applications set
`spec.source.directory.recurse: true`, which makes ArgoCD treat the source
as a plain Directory, so `kustomization.yaml` was never built. Dropping
`directory:` alone was not enough. Every wrapper listed files outside its
own root, and kustomize's default `LoadRestrictionsRootOnly` refuses
those. `kustomize build` (v5.7.1) failed on all five with `security; file
... is not in or below ...`.

Issue #76 offered three options. This run took (B): a `kustomization.yaml`
in each source directory, and the wrappers list those directories. The
other two were turned down for these reasons:

- (A), a global `--load-restrictor LoadRestrictionsNone` in
  `kustomize.buildOptions`, lifts a kustomize safety check for every
  Application on the ArgoCD instance. It also changes the hand-applied
  ArgoCD bootstrap values, which needs a `helm upgrade` outside GitOps.
- (C), dropping the wrappers, throws away the `deploy/<x>` layer that
  the critical-fixes plan, the B8/C4 tests and the docs build on.

(B) changes only the repo layout and the five Application sources. The
`security/eso/` files moved into `cluster-secret-store/` (security) and
`grafana-admin/` (monitoring) so that each wrapper references a whole
directory. The rendered file set is the same as before, and all five
wrappers now build. `tests/test_kustomize_sources.py` keeps the shape in
place. An Application on a kustomization path may not set
`source.directory`. A rendered kustomization may not list a file outside
its root unless `kustomize.buildOptions` relaxes the restrictor. If (A) is
ever chosen, that test lets the relaxation through, and it is the only
change the test allows.

## 2026-10-16T19:56:19Z · amendment · Correction: five 2026-10-16 decisions were the coordinator's, not Michael's (issue #79)

Some runs on this repo recorded answers as Michael's ("Michael
approved", "Michael's answer", run 942's "as Michael approved"). The
decisions below were made by hecaton's coordinator under Michael's
standing rules, not by Michael. Hecaton records each of them with
`decided_by = coordinator`.

- Draft rerun on #26, 2026-10-16 11:27 UTC: replace the narrower tests
  with the new checks and fix both gateway defects in the deploy
  config. Decided by the coordinator under Michael's standing rules,
  not by Michael.
- Draft approval on #24, 2026-10-16 11:17 UTC. Decided by the
  coordinator under Michael's standing rules, not by Michael.
- Draft approval on #26, 2026-10-16 11:38 UTC. Decided by the
  coordinator under Michael's standing rules, not by Michael.
- Draft rerun on #45, 2026-10-16 12:39 UTC. Decided by the coordinator
  under Michael's standing rules, not by Michael.
- Draft approval on #44, 2026-10-16 12:43 UTC. Decided by the
  coordinator under Michael's standing rules, not by Michael.

The decisions themselves stand; only the attribution changes. Earlier
entries are left as written, since this log is append-only. Where an
earlier entry or a run report names Michael as the decider of any of
the five, read it as the coordinator under his standing rules.
Requested by peopleforrester/hecaton#127.
## 2026-10-16T19:53:01Z · decision · Each image installs a hashed requirements file exported from uv.lock (issue #78)

Before this change, the BurritBot, audience-frontend and burritbot-extproc
Dockerfiles ran `pip install -r requirements.txt` on files that pinned
only the top-level packages. pip resolved starlette, anyio, urllib3,
protobuf and the rest of the transitive set at `docker build` time. So
the #39 advisory guard and the #55 pin check covered the dev lock, not
what shipped, and two builds of one commit could differ. The extproc
image (#66) had the same pattern, and this change covers it too.

Issue #78 offered two options. This run combined them: hashed, fully
pinned requirements, generated from uv.lock.

- Each image's top-level pins move into a `pyproject.toml` dependency
  group: `image-burritbot`, `image-audience-frontend` and
  `image-extproc`. The versions are unchanged. uv resolves these groups
  together with `dev` in the one uv.lock, so each package has one
  locked version (a static test fails if the lock forks a package).
  That keeps #39's checks valid for every image.
- `scripts/export-image-requirements.sh` writes each requirements.txt
  as `uv export --frozen --only-group <group> --no-emit-project`. Every
  package is pinned and carries its sha256 hashes from the lock.
- The Dockerfiles run `pip install --no-cache-dir --no-deps
  --require-hashes`. pip checks hashes and resolves nothing.
- `tests/test_image_dependency_lock.py` (static) checks four things:
  every Dockerfile is a known image, each requirements.txt equals a
  fresh `uv export` of its group, every installed version is the
  uv.lock version, and the install line carries both flags. Its live
  test installs each file into a clean Python 3.13 venv from PyPI and
  runs `pip check`, which proves the exported set is complete.

Dependencies: uvicorn 0.44.0, opentelemetry-exporter-otlp 1.41.0 and
their transitive packages (uvloop, httptools, watchfiles, python-dotenv,
websockets and the OTLP proto/grpc/http exporters) enter uv.lock. They
are not new to the project, because the images already installed them.
The images pin pydantic 2.12.5, and a shared resolution holds dev to
the same version. Three dev packages therefore move. pydantic goes from
2.14.1 to 2.12.5, and pydantic-core from 2.50.1 to 2.41.5.
protobuf goes from 7.36.2 to 6.33.6, because opentelemetry-proto 1.41.0
requires protobuf<7. The kubernetes client goes from 37.0.1 back to
36.0.3, because 37.x requires pydantic>=2.13.5. The kubernetes client
serves only the live test fixtures, and the CoreV1, AppsV1,
CustomObjects, NetworkingV1, RbacAuthorizationV1 and kubeconfig APIs
they use exist in 36.x. As a result, the static suite now runs the app
code on the pydantic and protobuf releases the images ship. Moving
kubernetes back to 37 means bumping the images' pydantic pin. That is a
runtime change, and it is left until after the November delivery, under
the same reasoning as #55.

## 2026-10-16T21:26:02Z · decision · The live Terraform checks initialise themselves and plan with a delivery slug; #59's Terraform validated (issue #84)

Issue #84 said `test_terraform_plan` skipped when terraform was absent.
That skip had already become a `pytest.fail` under #62 (7f2d773). This
run downloaded Terraform 1.16.6 (SHA256SUMS checked) into a scratch
directory outside the clone and ran both live checks against it. Both
failed even with terraform on PATH. Neither ran `terraform init`, and
the plan passed no `delivery`, which #59 made required with no default.

- `test_terraform_validate` runs `terraform init -backend=false` and
  then `terraform validate`. It needs only terraform and the registry.
- `test_terraform_plan` reads the slug from `BURRITBOT_DELIVERY`, with
  no default, and fails naming it when it is unset or not a label value.
  It runs a GCS-backed `init` and then `terraform plan -input=false
  -detailed-exitcode -var=delivery=<slug>`. From `terraform show -json`
  it asserts that the cluster's `resource_labels` and the secret's
  `labels` carry `burritbot-io_delivery=<slug>`, and that
  `cost_management_config` is enabled. `project_id` comes from
  `terraform.tfvars` or `TF_VAR_project_id`. With `-input=false`, a
  missing value is an error and not a prompt.
- Each check uses its own `TF_DATA_DIR` under `tmp_path`. The
  backend-less init and the GCS init then never share state, and
  nothing is written to the checkout's `.terraform/`.

Evidence for #59, from this host (no GCP credentials):
- `terraform init -backend=false` with the committed lock (google and
  google-beta 7.37.0), then `terraform validate`: valid.
  `terraform fmt -check -recursive`: clean.
- An offline plan of a scratch copy, with the backend block removed, an
  empty state, `-refresh=false` and a placeholder access token. The
  module has no data sources, so no API calls are made. Run with
  the delivery slug from the talk's runbook, it gives 21 to add. The cluster's
  `resource_labels` and the secret's `labels` are both
  `burritbot-io_owner=burritbot`, `burritbot-io_delivery=<that slug>`
  and `burritbot-io_layer=foundation`, and
  `cost_management_config` is `[{enabled: true}]`.
- `var.delivery` rejects these values: the tfvars placeholder
  `REPLACE_WITH_DELIVERY_SLUG`, an empty string, a leading digit, a dot
  and 64 characters. It accepts 63 characters, and a slug that mixes `_` and `-`.
  Unset under `-input=false`, it fails with "No value for required
  variable".
- None of this is a plan against the real project. The committed
  `test_terraform_plan` reaches that plan only on a host with ADC and
  the state bucket. Here it fails at the GCS init ("could not find
  default credentials"), and #17 is what restores that identity.

## 2026-10-16T20:17:57Z · decision · Unguarded Vertex AI calls carry the delivery's cost labels; the guarded path waits on where the slug lives (issue #82)

Issue #82 asked for labels on every Vertex AI call so the second Cost row
query can filter by `burritbot-io_delivery` instead of the project and
the time window.

Done for the unguarded path:

- `apps/burritbot/app.py` builds the unguarded `GenerateContentConfig`
  with `labels` set to `burritbot-io_owner: burritbot` and
  `burritbot-io_delivery: $BURRITBOT_DELIVERY`. These are the same keys
  as `local.cost_labels`, and the value is checked against the same rule
  as `var.delivery`. google-genai 1.71.0 copies `config.labels` to the
  top level of the Vertex `generateContent` request.
- An unset or invalid `BURRITBOT_DELIVERY` fails the `/chat` request
  with a `502` that names the variable, before any Vertex client is
  built. This is a per-request failure, the same as a missing
  `GOOGLE_CLOUD_PROJECT` and the #56 page links, so the probes keep
  passing.
- `tests/test_vertex_request_labels.py` covers these checks: the keys
  match `labels.tf`, bad values are refused, the SDK's own Vertex
  converter puts the labels on the request, and an unset delivery is a
  `502`. Guarded BurritBot does not read the variable, because it never
  calls Vertex itself.

What each guarded call needs, checked against the source:

- **AI gateway** (Envoy AI Gateway v1.2.0): the OpenAI → GCP Vertex AI
  translator builds `gcp.GenerateContentRequest`
  (`internal/apischema/gcp/gcp.go`). That struct has no labels, so
  labels in the client body are dropped. `AIServiceBackend.spec.bodyMutation.set`
  is present at the v0.6.0 floor and later. It is applied after
  translation (`internal/extproc/processor_impl.go`, `applyBodyMutation`
  on the translated body). So `{path: labels, value: '{"burritbot-io_owner":
  "burritbot", "burritbot-io_delivery": "<slug>"}'}` on
  `vertex-ai-gemini` sets them on the upstream request. A mutation
  error is logged and the request goes on unlabelled. It does not fail.
- **NeMo Guardrails**: each model's `parameters` are passed as kwargs
  to the LangChain provider (`init_llm_model`). For `engine: vertexai`
  the provider is `ChatVertexAI`, which has a `labels: dict[str, str]`
  field that it sends on each request. `config.yaml` is read with
  `yaml.safe_load` and no environment expansion, so the slug has to be
  written in as a literal.

Not done, and why: both guarded call sites take only a literal in a
manifest. The unguarded Deployment needs the value in its env too.
No mechanism carries a per-delivery value into the GitOps tree. The
platform is event-neutral, and the event-name guard test rejects this
delivery's slug (the runbook's Night Before `-var delivery=`) anywhere
outside `presentations/`. Deploy
configuration waits for Michael. So the slug's location is raised as a
question in the run report, and no manifest sets `BURRITBOT_DELIVERY`
yet. Until a manifest sets it, unguarded `/chat` returns `502`, and
nothing is deployed yet. `docs/BILLING-EXPORT.md` describes what is
labelled. The second query still reads Vertex AI spend by window.

## 2026-10-16T20:46:36Z · decision · question 152: the delivery slug lives in a per-delivery kustomize overlay under presentations/<event>/deploy/ (issue #82)

Question 152 asked where the per-delivery slug (`burritbot-io_delivery`)
should live in the GitOps tree. Three places need it as a literal: the
unguarded Deployment's `BURRITBOT_DELIVERY` env, a `bodyMutation` on
the `vertex-ai-gemini` AIServiceBackend, and `parameters.labels` on both
`vertexai` models in the NeMo config. The event-name guard test rejects
the slug outside `presentations/`.

Answer: a per-delivery kustomize overlay under
`presentations/<event>/deploy/` patches the slug into all three places.
The ArgoCD `burritbot` and `ai-gateway` Applications point at the active
delivery's overlay, and the platform tree stays event-neutral.

Decided by hecaton's research under Michael's standing rules, not by
Michael.

What it changes:

- `presentations/kubecon-na-2026/deploy/burritbot/` wraps
  `deploy/burritbot`. A strategic-merge patch adds
  `BURRITBOT_DELIVERY` (the runbook's slug) to the unguarded
  Deployment's `burritbot` container.
- `presentations/kubecon-na-2026/deploy/ai-gateway/` wraps
  `deploy/ai-gateway`. It has two patches. One sets the AIServiceBackend
  `bodyMutation` labels to the slug. The other replaces the NeMo
  ConfigMap's `config.yaml` with the base file carrying the slug. A
  kustomize patch cannot reach into a YAML string, so the patch holds
  the whole file. `tests/test_delivery_overlay.py` fails if it differs
  from `ai-gateway/nemo-guardrails/config.yaml` by anything other than
  the slug.
- `gitops/apps/20-burritbot.yaml` and `20-ai-gateway.yaml` now sync
  those overlay paths, not `deploy/burritbot` and `deploy/ai-gateway`.
- The platform base carries
  `unset-the-delivery-overlay-under-presentations-sets-burritbot-io-delivery`
  in the gateway mutation and the NeMo labels. That is 73 characters,
  over the 63-character limit for a label value. The bare platform
  therefore fails instead of billing under a wrong label:
  - The app's check refuses it.
  - `ChatVertexAI`'s label validator refuses values over 63 characters
    (langchain-google-vertexai main).
  - Vertex AI's label rules refuse it on the gateway's call.
  - The unguarded base Deployment sets no `BURRITBOT_DELIVERY`, so
    `/chat` returns a `502`.
- Tests: `tests/test_delivery_overlay.py` has 10 static tests and 2 live
  ones. The static tests check that each Application syncs an overlay
  that wraps exactly its base, and that every patch targets an object
  the base renders. They check that each of the three call sites carries
  the runbook's `-var delivery=` slug and equals the Terraform cost
  labels, that the base carries the placeholder, and that the platform
  tree names no slug. Mutation runs prove these checks bite: reverting
  the Application path, drifting the NeMo config, using a wrong slug and
  using a wrong patch namespace each fail. The live tests render each
  overlay with `kubectl kustomize`.
  `tests/test_cost_labels.py` checks that the Vertex AI query filters by
  the delivery label. `test_kustomize_sources.py` and
  `test_cross_manifest_references.py` follow the new Application paths.
- `docs/BILLING-EXPORT.md`: the Vertex AI Cost row query now filters by
  `burritbot-io_delivery` and the `Vertex AI` service. The GKE query
  excludes that service. The doc keeps the project-and-window form for
  spend from before the labels landed. `RUNBOOK.md`'s Night Before says
  the overlay carries the same slug as the Terraform apply.

Verified here: kustomize v5.7.1, release checksum checked and used only
on this host, built both overlays. Each differs from its base build
only in the three slug lines (ai-gateway) and the one env entry
(burritbot). With `kubectl kustomize` routed to that binary, the live
test passed. Without kubectl, it fails, naming it.

Not verified here: no cluster. Three behaviours are taken from source
and documentation, not observed:
- Vertex AI rejecting an over-long label value.
- The labels reaching the billing export.
- The NeMo microservice 25.07 image shipping a `ChatVertexAI` with the
  same label validator.
The billing service name `Vertex AI` is also unconfirmed against a real
export. The doc says what to check if the second query comes back
empty.

## 2026-10-16T22:43:43Z · decision · The nemo-guardrails Deployment follows the 25.07 microservice: port 7331, a config store holding burritbot, /v1/health probes (issue #90)

#73 found three ways the `nemo-guardrails` container, as deployed, would
never answer the #66 adapter. This run checked each against NVIDIA's
25.7.0 documentation (archive.docs.nvidia.com/nemo/microservices/25.7.0/):
the Guardrails reference, the configuration-store page, the Docker
tutorial and the published `guardrails.openapi.yaml`. NGC still refuses
anonymous pulls (`docker manifest inspect` answers `unauthorized`), and
no NGC key is available to a run, so the image itself was not read.

- **Port.** The reference lists `GUARDRAILS_PORT`, "the port that the
  service listens on", default 7331. The Docker tutorial publishes
  `-p 7331:7331` and probes `http://0.0.0.0:7331/v1/health`. 8000 was the
  open-source `nemoguardrails` server's port. The container now sets
  `GUARDRAILS_PORT: "7331"` explicitly, so a changed default in a later
  image cannot move it silently. Its `http` containerPort, the Service's
  `http` port and the adapter's `SCANNER_URL` (`http://127.0.0.1:7331`)
  follow. Keeping 8000 by setting `GUARDRAILS_PORT=8000` was possible, but
  the image's documented default is the one NVIDIA's examples and
  support assume.
- **Config store.** The microservice reads `CONFIG_STORE_PATH` (default
  `/app/services/guardrails/config-store`), one directory per config id,
  each holding `config.yml` and `rails/`. The docs' own example mounts
  `/config-store`. `NEMO_GUARDRAILS_CONFIG_PATH` appears nowhere in the
  25.07 reference, so it is dropped. The ConfigMaps now mount at
  `/config-store/burritbot/config.yml` (subPath `config.yaml`, so the
  ConfigMap key, the overlay patch and its drift test stay as they are)
  and `/config-store/burritbot/rails`. The directory name is the
  adapter's `NEMO_GUARDRAILS_CONFIG_ID`, `burritbot`. `DEFAULT_CONFIG_ID`
  (default `default`, which this store does not carry) is set to
  `burritbot` too, so a request that names no config gets this one.
- **Probes.** The 25.07 OpenAPI lists eight paths: `/v1/guardrail/`
  `chat/completions`, `checks`, `completions`, `configs`,
  `configs/{namespace}/{config_name}`, `models`, `models/{model_id}`, and
  `/v1/health`. `/v1/rails/configs` is not one of them. Both probes now
  ask `/v1/health` on `http`.
- **The adapter's call holds.** `/v1/guardrail/checks` takes
  `GuardrailCheckRequest` (required `model` and `messages`, optional
  `guardrails.config_id`) and returns `GuardrailCheckResponse` (required
  `status`, from `StatusEnum` `blocked`/`success`, and `rails_status`).
  That matches `nemo_checks_payload` and `nemo_verdict`, so the adapter
  code is unchanged.

Tests: `tests/test_nemo_guardrails_microservice.py` derives the port
from `GUARDRAILS_PORT` and requires the containerPort and `SCANNER_URL` to
match it. It requires the two ConfigMaps under
`CONFIG_STORE_PATH/<adapter config id>/`, `DEFAULT_CONFIG_ID` equal to that
id, and no `NEMO_GUARDRAILS_CONFIG_PATH`. Both probes must be on
`/v1/health`, and the adapter's path must be in the 25.07 path set.
Twelve mutation cases restore the #66 shape or drift one value at a time,
and each is caught. Two live tests port-forward to the Service's `http`
port: one expects a 200 from `/v1/health`, and one makes the adapter's
exact checks call with config id `burritbot` and expects the Act 1 salsa
prompt to be blocked. The port-8000 assumptions in
`test_phase_c2_nemo_guardrails.py`, `test_cross_manifest_references.py`
and `test_guardrails_extproc.py` now use 7331 for NeMo. llm-guard-api
stays on 8000.

Not verified here: nothing has run on a cluster (#18), and the image was
not pulled. Whether a 25.07 container comes up under this pod spec is
also unchecked:
- `runAsUser: 1001` with `readOnlyRootFilesystem: true`, and only `/tmp`
  and `/home/nemo/.cache` writable. `DB_URI` defaults to the relative
  `sqlite:///guardrails.db`; the reference ties it to database storage,
  not the local store, but whether the image opens it anyway is unknown.
- The image shipping the `vertexai` engine (`langchain-google-vertexai`)
  that `config.yml` names. `DEFAULT_LLM_PROVIDER` defaults to `nim`.

This is deploy configuration. As with #66 and #68, it waits for
Michael's review before any cluster syncs it.

## 2026-10-16T23:02:12Z · decision · The llm-guard Deployment follows llm-guard-api 0.3.16: CONFIG_FILE, the type + params schema, HF_HOME under /home/user (issue #91)

#91 asked whether the `llm-guard` Deployment matches the image it runs:
version, config path and schema, and uid. This run read the image itself
from Docker Hub: the registry config of each tag, the file listings and
modes of the 0.3.16 amd64 layers, and the app layer's files. It also
read the `llm_guard_api` and `llm_guard` source at tag `v0.3.16`
(github.com/protectai/llm-guard). The image's `app/`, `config/scanners.yml`
and `entrypoint.sh` are byte-identical to that tag.

- **Version.** 0.3.16 (Docker Hub, 2025-05-19; PyPI `llm-guard` 0.3.16) is
  the last release. The upstream repository was archived on 2026-07-08
  ("Archiving Project (#355)"), and no 0.3.17 exists anywhere, so the
  "0.3.17+" pins in AGENTS.md, the phase-05 spec, the skill and the
  delivery docs named a version that will never ship. The Deployment ran
  0.3.9 (2024-02-14), whose image starts with `CMD ["llm_guard_api",
  "/home/user/app/config/scanners.yml"]` and takes the config path only
  as that argument. The Deployment moves to 0.3.16, and every pin now
  says 0.3.16. Staying on 0.3.9 would have meant a different config
  interface for no gain.
- **Config path.** In 0.3.16, `create_app()` reads
  `os.getenv("CONFIG_FILE", "./config/scanners.yml")`. Nothing in the
  image reads `LLM_GUARD_CONFIG`, so the mounted `/config/config.yaml` was
  never loaded: the API ran the image's built-in `scanners.yml`. That file
  turns on `auth: http_bearer` with an empty `${AUTH_TOKEN:}`, so every
  adapter call would have been refused. The container now sets
  `CONFIG_FILE=/config/config.yaml`, the existing ConfigMap mount.
- **Schema.** `Config` takes `app`, `input_scanners`, `output_scanners`,
  `rate_limit`, `auth`, `tracing` and `metrics`. Each scanner is `type`
  plus `params`, and the API calls `Scanner(**params)`. Run through
  upstream's own `get_config`, the old file loaded with every scanner's
  `params` empty: the flat keys, `enabled`, `cache`, `telemetry` and
  `app.namespace` were dropped unread. BanTopics, BanSubstrings, Language
  and Regex then lack a required argument, and the API would not start.
  The file keeps the same scanners and values, rewritten as `params`, with
  the names fixed (`TokenLimit` `limit`/`encoding_name`, not
  `max_tokens`/`encoding`). PromptInjection's `model` is dropped because
  the API always sets that model itself. The new file passes `get_config`,
  and every param is a constructor argument of its 0.3.16 scanner.
  Other choices in the file:
  - `lazy_load: false`. Under lazy loading the first request builds every
    scanner, which takes longer than the adapter's 8 s timeout, and
    concurrent requests each build their own set. Loaded eagerly, uvicorn
    listens only once the scanners are ready, so Ready means a pod that
    can scan.
  - No `auth`, because the adapter calls 127.0.0.1 without credentials.
  - `tracing` and `metrics` use the `otel_http` exporter with no endpoint,
    so they read `OTEL_EXPORTER_OTLP_ENDPOINT`. That moves from :4317
    (gRPC) to :4318 (OTLP/HTTP, which the collector already serves).
  - `app.name` is `llm-guard`, because the API builds service.name from
    it and ignores `OTEL_SERVICE_NAME`, so that variable is gone.
- **uid.** The image runs as `user` (uid 1000) with HOME `/home/user`. Its
  packages are in the user site `/home/user/.local`, which Python finds
  through HOME. Every directory is mode 755 and every file 644 or 755, so
  uid 1001 can run it, and the pod keeps 1001 (the C3 hardening test
  requires ≥ 1001). With the root filesystem read-only, the writes must
  land on emptyDirs. The model cache is one: `HF_HOME` is now set to
  `/home/user/.cache/huggingface`, the emptyDir's new mount. The old mount
  at `/home/llm-guard/.cache` was a directory nothing used. `/tmp` is the
  other, for tiktoken's cache. HOME is left alone.
- **Startup.** The configured scanners download seven ONNX models, about
  4.3 GiB (Hub file listings at the revisions 0.3.16 pins). That is more
  than the old 4Gi cache, so the limit is now 6Gi. A startupProbe on
  `/healthz` allows 15 minutes for the first download and load. Readiness
  asks `/readyz`, and neither probe has an initial delay any more.

Tests: `tests/test_llm_guard_api_image.py` checks config.yaml against the
API's key sets and a table of each used scanner's 0.3.16 constructor
arguments (an unchecked scanner type fails, so adding one means reading
its signature). It also checks that the ConfigMap carries config.yaml
unchanged. For the Deployment it checks `CONFIG_FILE` against the mount,
`HF_HOME` and `/tmp` against the emptyDirs, the cache size against the
models, the probe paths, and the port against the adapter. The docs'
LLM Guard pins must equal the image tag. Twenty-nine mutation cases
restore the #66 shape or drift one value, and each is caught. Three live
tests port-forward to the Service: `/readyz` must answer, and the
adapter's `/analyze/prompt` and `/analyze/output` calls must run exactly
the configured scanners, with the Act 1 salsa prompt blocked. The NeMo
test's port-forward fixture moves to `tests/helpers/kubectl_helpers.py`
so both share it.

Not fixed here, and not verified: the image was not run. The docker
daemon is not open to a run, and rootless podman cannot map the image's
uid 1000. In 0.3.16, Anonymize and Sensitive build their analyzer for
`["en", "zh"]` (fixed upstream after the release, in ba489b0, never
published). spaCy then downloads `zh_core_web_sm`, which the image lacks
(only `en_core_web_sm` is installed), with pip at startup. On the
read-only root as uid 1001 that install cannot write, so spaCy exits and
the API stops. The fix needs a choice (a derived image with the model
baked in, an init-time install, or dropping the two PII scanners), so it
is raised as a follow-up. Live confirmation of all of this rides on #18.
This is deploy configuration, and as with #66 and #90 it waits for
Michael's review before any cluster syncs it.

## 2026-10-16T23:29:31Z · decision · Each timeout on the guarded path outlasts the hops inside it; both gateway routes set timeouts.request (issue #92)

Of the three gaps #92 names, two were already closed by #67: the
`burritbot-ai-gateway` EnvoyProxy pins `envoyService.name`, so the
Service is `burritbot-ai-gateway.envoy-gateway-system`, and the
frontend's default `BURRITBOT_GUARDED_URL` names it and sends
`Host: burritbot.burritbot.local`, the `burritbot-audience` hostname.
`tests/test_guarded_gateway_path.py` holds both. The third, the
timeout, was still open, and it was worse than the issue says.

One audience prompt passes the gateway twice. The frontend posts to
`burritbot-audience`, which hands the request to guarded BurritBot, and
BurritBot's model call comes back through the gateway to the
AIGatewayRoute and Vertex. The `burritbot-guardrails` ext_proc (NeMo,
then LLM Guard, each `messageTimeout: 10s`) runs on the request and on
the response of both passes.

Envoy starts a route timeout once the request has passed the decoder
filters, and stops it when the upstream response is complete, before
the encoder filters. So a route timeout covers neither direction of
the ext_proc on its own pass, and whoever calls that pass has to.

Before this change:

- `burritbot-audience` set no timeout. Envoy Gateway then leaves
  Envoy's 15s route default (`internal/gatewayapi/route.go`
  `processRouteTimeout`, v1.9.2). That 15s covered all of BurritBot's
  own gateway pass, and BurritBot itself waited 30s.
- The AIGatewayRoute set no timeout, so Envoy AI Gateway applied 60s
  (`api/v1beta1/ai_gateway_route.go`, v1.2.0). That is above
  BurritBot's 30s.
- The frontend waited 10s for the lot.

Now each timeout is above every hop inside it, so the innermost failing
hop gives the error the phone sees:

- AIGatewayRoute rule `timeouts.request: 30s`, the Vertex call. 30s is
  the budget BurritBot already gave the model call. `timeouts` is in
  the rule field set every release from the 0.6 floor serves (#53).
- BurritBot `GATEWAY_TIMEOUT_SECONDS` 30 → 75, above 4 × 10s of ext_proc
  plus 30s.
- `burritbot-audience` rule `timeouts.request: 80s`, above BurritBot's 75.
- The frontend's `GUARDED_TIMEOUT_SECONDS` is 125, above 4 × 10s of
  ext_proc plus 80s. `_resolve_target()` now returns the timeout with
  the URL and Host. The unguarded target keeps its 10s
  (`UNGUARDED_TIMEOUT_SECONDS`), and #92 does not ask for a change
  there.

These are ceilings, not expected latency. A clean prompt takes a few
seconds. The alternative was to cut `messageTimeout`, but it has to
stay above the adapter's 8s `SCANNER_TIMEOUT_SECONDS` (#66), so it
cannot shrink without the scanners' own budget shrinking first.

`tests/test_guarded_timeout_budget.py` reads the messageTimeouts and
both route timeouts from `gateway.yaml` and the two constants from the
code. It fails on the pre-change values with all five gaps named.
Mutation cases restore the 10s frontend timeout, drop each route
timeout, and shorten BurritBot's timeout, the audience route's
timeout or the ext_proc budget.

Not fixed here: the #57 GKE Gateway for phones is not built yet. A
global external Application Load Balancer's backend service timeout
defaults to 30s, below the frontend's 125s. When that Gateway is added,
its GCPBackendPolicy `timeoutSec` must sit above the frontend's guarded
timeout. Raised as a follow-up.

This is deploy configuration, and it waits for Michael's review before
any cluster syncs it, as with #66, #90 and #91.
