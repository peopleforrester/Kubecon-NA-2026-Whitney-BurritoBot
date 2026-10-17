# Readiness Against the Accepted Abstract

Issue #75, from `peopleforrester/talks-knowledge#12` (priority 1, hard
date 2026-11-08). Assessed 2026-10-16 against staging at `f226129`.
The points were checked against the accepted wording on 2026-10-17
(issue #104, from `peopleforrester/talks-knowledge#29`); the ratings
did not change. Rows 6 and 8 and step 3 of "What closes the gap" were
brought up to date on 2026-10-17 after #102 rewrote the NeMo rails
(issue #113). Row 8 moved from PARTIAL to READY-STATIC.

**Checked against.** The accepted text is Sessionize session 1249553,
transcribed in talks-knowledge
`abstracts/recovered/sessionize-public-profile.md` section 5. The
checklist is the nine points in talks-knowledge
`talks/2026-10-16_hard-dated-commitments.md`. talks-knowledge#29
compared the two: each of the nine points below is the same point as
the accepted text, in the same order. Rows 4 and 6 quote the accepted
wording. `CFP-SUBMISSION.md` in this folder is an earlier draft, not
what was accepted. Where a point can be read more than one way, the row
says so.

**Status key.**
- **READY-STATIC**: built and covered by the static suite. It has never
  run on a cluster.
- **PARTIAL**: part of the point is built, or the point conflicts with a
  rule in this repo.
- **MISSING**: not in the repo, or present but would not work on stage.

No point is verified live. Nothing has run on a cluster (`PROJECT_STATE.md`),
and every row below waits on the critical path `#17 → #18`. The cold read
in `PORTLAND-CARRY-FORWARD.md` (Whitney, 2026-10-26) turns into a paper
read if #18 has not landed by 2026-10-23.

## Verdict

**Not ready.** Three points are READY-STATIC, three are PARTIAL and
three are MISSING. GenAI observability is the most serious gap: the Grafana
dashboard is the talk's on-stage proof, and as built it would show
nothing. Three points (the MCP server, the full IDP and audience
hacking) are promises in the accepted text that this repo decided
against before the acceptance was read. They need a decision, not more
code. talks-knowledge#29 sent those calls, with what counts as
mid-inference (row 6), to Michael and Whitney.

## Checklist

| # | Point | Status | Evidence |
|---|---|---|---|
| 1 | Burrito-chain bot | **READY-STATIC** | BurritBot (`apps/burritbot/app.py`) is a FastAPI bot on Gemini 3 Pro whose system prompt keeps it to burritos, the menu, hours and locations. The same image runs unguarded and guarded (`apps/burritbot/k8s/`). There is no menu data and no ordering: the bot's menu is whatever the model says. |
| 2 | Under-protected MCP server | **MISSING** | There is no MCP server in the repo. `PORTLAND-CARRY-FORWARD.md` ("Hallway asks") ruled MCP out of scope for a two-act, 30-minute session. The only MCP reference is the AI Gateway controller's session seed (`gitops/apps/ai-gateway-controller.yaml`). The accepted text promises one. |
| 3 | Full IDP | **PARTIAL** | The platform is GitOps end to end: Terraform GKE (`infrastructure/terraform/`), ArgoCD app-of-apps with sync waves (`gitops/apps/`), External Secrets, cert-manager, Workload Identity. There is no developer portal: Backstage was excluded on purpose (`docs/KUBEAUTO-REUSE-MAP.md`). SPIFFE/SPIRE, which Act 2 narrates as part of The Web, has no ArgoCD Application. Whether "full IDP" needs a portal is a question for the talk. |
| 4 | Starts wide open with live audience hacking | **PARTIAL** | Wide open: the unguarded Deployment calls Vertex directly with no gateway, scanner or rail (`apps/burritbot/k8s/deployment-unguarded.yaml`), and `scripts/cast-net.sh` starts the room there. Live audience: the phone page `/` and the projector QR `/qr` exist (`apps/audience-frontend/static/index.html`). Hacking: this repo's rule (AGENTS.md, RUNBOOK Act 1) keeps the audience to off-topic asks; prompt injection, jailbreak and data extraction are presenter-driven, and `tests/test_portland_carry_forward.py` fails if Act 1 invites the room to attack. The accepted wording is "It starts wide open, and we let the audience hack it live", in a text that also says "A user does not need to be malicious to embarrass an enterprise, just a little bit weird" and closes "Bring your weirdest off-topic question". The off-topic asks fit the rule; whether "hack it live" means the room attacks is the who-hacks call with Michael and Whitney (talks-knowledge#29). |
| 5 | Kubernetes layers | **READY-STATIC** | Kyverno: `require-burritbot-labels` and `require-burritbot-sidecar-naming` in Enforce, `restrict-burritbot-network` generating an egress NetworkPolicy (`security/kyverno/policies/`). Falco: three tagged rules (`security/falco/rules/burritbot-the-net.yaml`). Workload Identity on the guarded ServiceAccount. SPIRE is not installed (row 3). Not assessed: the checklist's "Ready means" asks that the Kubernetes layers are shown before the LLM layer. Check the stage order once the live bring-up (#18) is up. |
| 6 | Pre- and mid-inference guardrails | **PARTIAL** | The accepted wording is "LLM-specific guardrails, like pre- and mid-inference prompt analysis". What counts as mid-inference is a call with Michael and Whitney (talks-knowledge#29). Pre-inference: the `burritbot-guardrails` EnvoyExtensionPolicy (`ai-gateway/envoy/gateway.yaml`) sends every request body through NeMo Guardrails, then LLM Guard, via the `burritbot-extproc` adapter (`ai-gateway/extproc/adapter.py`), failing closed. The response body takes the same path, so replies are scanned before the audience sees them. Read as "in the inference path", that is in place. Read as "during generation", it is not: bodies are buffered whole and BurritBot does not stream. The NeMo rails resolve: #102 rewrote the four rails `ai-gateway/nemo-guardrails/config.yaml` enables as phrase checks under those names (question 170 in `decisions.md`). `tests/test_nemo_rail_flows.py` loads the config the Deployment mounts in real `LLMRails` (nemoguardrails 0.24.1) and checks that each rail blocks its asks and lets menu asks through. The rails match listed phrases and call no model, so a paraphrase outside the lists gets past NeMo and falls to LLM Guard. None of this has run in the 25.07 microservice container (#18), whose bundled nemoguardrails version is unknown. That container may not load the config's `engine: vertexai` models at all (#100). |
| 7 | GenAI observability on stage | **MISSING** | BurritBot never sets a tracer or meter provider and runs under plain `uvicorn` (`apps/burritbot/Dockerfile`), so `FastAPIInstrumentor` records nothing. A probe with the Deployment's `OTEL_*` env showed a `ProxyTracerProvider` and `span.is_recording()` False. No code emits `gen_ai.*` spans: the collector (`observability/otel-collector/config.yaml`) renames `llm.*` attributes that nothing sets. None of the metrics the three dashboards query (`observability/grafana/dashboards/`), such as `burritbot_llm_guard_block_total` or `burritbot_burritbot_unguarded_leak_total`, is emitted anywhere in the repo. The Tempo panel's `burritbot.*chat` span name would not match FastAPI's `POST /chat` either. The C4 static tests pass because they check that the instrumentor is called and the env is set, not that anything is exported. |
| 8 | Ends selling burritos only | **READY-STATIC** | `ai-gateway/nemo-guardrails/rails/burrito-only.co` defines `burrito only input`, the name the config enables, and answers the canonical Act 1 asks (salsa dance moves, a hot dog party, karaoke songs for a wedding and the rest) with a redirect to the menu. LLM Guard's `BanTopics` catches paraphrases the phrase lists miss (`ai-gateway/llm-guard/config.yaml`). #102 rewrote the rail (question 170) and made "what are your hours" an on-topic ask, matching the refusal that offers the menu, hours and locations. `tests/test_nemo_rail_flows.py` runs it in real `LLMRails`: the seven Act 1 asks are refused, and twelve menu asks pass, among them "what are your hours" and "do you have mild salsa". Not run on a cluster: the 25.07 container (#18) and its model engine (#100) are unverified, as row 6 says. |
| 9 | Recorded fallback for the live input | **MISSING** | No recording exists. Phase 8's backup videos need a live cluster and were never made (`presentations/kubecon-na-2026/docs/SCORECARD.md`: rehearsal RED). The RUNBOOK's worst-case step sends presenters to a static screenshots deck under docs/fallback-deck/, which does not exist. Nothing replays a recorded set of audience prompts if phones or venue Wi-Fi fail. Not assessed: the checklist's "Ready means" also asks that the live audience input works over the venue network, beside the recorded fallback. Check that once the live bring-up (#18) is up. |

## What closes the gap

In order, with the 2026-11-08 date in mind:

1. **Decide the three scope points** (rows 2, 3, 4): build an
   under-protected MCP server or cut it from the talk, say what "full
   IDP" means on stage, and say whether the room hacks or the presenters
   do, and what counts as mid-inference (row 6). The repo's rules were
   written before the acceptance was read. These calls are with Michael
   and Whitney (talks-knowledge#29).
2. **Make The Eyes see** (row 7): configure the OTel SDK in BurritBot,
   emit `gen_ai.*` spans and the block, leak and latency metrics the
   dashboards query, and test the export rather than the import.
3. **Wire the rails** (rows 6, 8): done statically by #102. The `.co`
   files define the four rails `ai-gateway/nemo-guardrails/config.yaml`
   enables, as phrase checks, and "what are your hours" is on-topic.
   What is left is live: settle the NeMo container's model engine
   (#100), then load the rails in the 25.07 container (#18).
4. **Go live** (all rows): #17, then #18, then a full rehearsal that
   fills the RUNBOOK Measurements record.
5. **Record the fallback** (row 9) from that rehearsal: one video per
   segment, a screenshots deck, and a replayable prompt set for the live
   input.
