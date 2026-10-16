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
