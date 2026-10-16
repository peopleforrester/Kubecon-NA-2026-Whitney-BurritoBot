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
