# Readiness Against the Accepted Abstract

Issue #75, from `peopleforrester/talks-knowledge#12` (priority 1, hard
date 2026-11-08). Assessed 2026-10-16 against staging at `f226129`.

**Checked against.** The accepted text is Sessionize session 1249553,
transcribed in talks-knowledge
`abstracts/recovered/sessionize-public-profile.md` section 5. The
checklist is the nine points in talks-knowledge
`talks/2026-10-16_hard-dated-commitments.md`. `CFP-SUBMISSION.md` in
this folder is an earlier draft, not what was accepted. This run had no
read access to talks-knowledge, so the points below are taken as issue
#75 names them, and their meaning is not checked against the accepted
wording. Where a point can be read more than one way, the row says so.

**Status key.**
- **READY-STATIC**: built and covered by the static suite. It has never
  run on a cluster.
- **PARTIAL**: part of the point is built, or the point conflicts with a
  rule in this repo.
- **MISSING**: not in the repo, or present but would not work on stage.

No point is verified live. Nothing has run on a cluster (`PROJECT_STATE.md`),
and every row below waits on the critical path `#17 → #18`. The cold read
in `PORTLAND-CARRY-FORWARD.md` turns into a paper read if #18 has not
happened by 2026-10-27.

## Verdict

**Not ready.** Two points are READY-STATIC, four are PARTIAL and three
are MISSING. GenAI observability is the most serious gap: the Grafana
dashboard is the talk's on-stage proof, and as built it would show
nothing. Three points (the MCP server, the full IDP and audience
hacking) are promises in the accepted text that this repo decided
against before the acceptance was read. They need a decision, not more
code.

## Checklist

| # | Point | Status | Evidence |
|---|---|---|---|
| 1 | Burrito-chain bot | **READY-STATIC** | BurritBot (`apps/burritbot/app.py`) is a FastAPI bot on Gemini 3 Pro whose system prompt keeps it to burritos, the menu, hours and locations. The same image runs unguarded and guarded (`apps/burritbot/k8s/`). There is no menu data and no ordering: the bot's menu is whatever the model says. |
| 2 | Under-protected MCP server | **MISSING** | There is no MCP server in the repo. `PORTLAND-CARRY-FORWARD.md` ("Hallway asks") ruled MCP out of scope for a two-act, 30-minute session. The only MCP reference is the AI Gateway controller's session seed (`gitops/apps/ai-gateway-controller.yaml`). The accepted text promises one. |
| 3 | Full IDP | **PARTIAL** | The platform is GitOps end to end: Terraform GKE (`infrastructure/terraform/`), ArgoCD app-of-apps with sync waves (`gitops/apps/`), External Secrets, cert-manager, Workload Identity. There is no developer portal: Backstage was excluded on purpose (`docs/KUBEAUTO-REUSE-MAP.md`). SPIFFE/SPIRE, which Act 2 narrates as part of The Web, has no ArgoCD Application. Whether "full IDP" needs a portal is a question for the talk. |
| 4 | Starts wide open with live audience hacking | **PARTIAL** | Wide open: the unguarded Deployment calls Vertex directly with no gateway, scanner or rail (`apps/burritbot/k8s/deployment-unguarded.yaml`), and `scripts/cast-net.sh` starts the room there. Live audience: the phone page `/` and the projector QR `/qr` exist (`apps/audience-frontend/static/index.html`). Hacking: this repo's rule (AGENTS.md, RUNBOOK Act 1) keeps the audience to off-topic asks; prompt injection, jailbreak and data extraction are presenter-driven, and `tests/test_portland_carry_forward.py` fails if Act 1 invites the room to attack. If the accepted text promises the audience hacks, the rule and the text disagree. |
| 5 | Kubernetes layers | **READY-STATIC** | Kyverno: `require-burritbot-labels` and `require-burritbot-sidecar-naming` in Enforce, `restrict-burritbot-network` generating an egress NetworkPolicy (`security/kyverno/policies/`). Falco: three tagged rules (`security/falco/rules/burritbot-the-net.yaml`). Workload Identity on the guarded ServiceAccount. SPIRE is not installed (row 3). |
| 6 | Pre- and mid-inference guardrails | **PARTIAL** | Pre-inference: the `burritbot-guardrails` EnvoyExtensionPolicy (`ai-gateway/envoy/gateway.yaml`) sends every request body through NeMo Guardrails, then LLM Guard, via the `burritbot-extproc` adapter (`ai-gateway/extproc/adapter.py`), failing closed. The response body takes the same path, so replies are scanned before the audience sees them. Read as "in the inference path", that is in place. Read as "during generation", it is not: bodies are buffered whole and BurritBot does not stream. Separately, three of the four NeMo rails the config enables do not exist (`ai-gateway/nemo-guardrails/config.yaml` names `burrito only input`, `topic enforcement input` and `output sanitize`; the `.co` files define only longer names such as `burrito only input off topic`). Loaded with nemoguardrails 0.11.1, only `jailbreak detect input` resolves. |
| 7 | GenAI observability on stage | **MISSING** | BurritBot never sets a tracer or meter provider and runs under plain `uvicorn` (`apps/burritbot/Dockerfile`), so `FastAPIInstrumentor` records nothing. A probe with the Deployment's `OTEL_*` env showed a `ProxyTracerProvider` and `span.is_recording()` False. No code emits `gen_ai.*` spans: the collector (`observability/otel-collector/config.yaml`) renames `llm.*` attributes that nothing sets. None of the metrics the three dashboards query (`observability/grafana/dashboards/`), such as `burritbot_llm_guard_block_total` or `burritbot_burritbot_unguarded_leak_total`, is emitted anywhere in the repo. The Tempo panel's `burritbot.*chat` span name would not match FastAPI's `POST /chat` either. The C4 static tests pass because they check that the instrumentor is called and the env is set, not that anything is exported. |
| 8 | Ends selling burritos only | **PARTIAL** | The intent is built: `ai-gateway/nemo-guardrails/rails/burrito-only.co` lists the canonical Act 1 prompts as off-topic and redirects to the menu, and LLM Guard's `BanTopics` backs it (`ai-gateway/llm-guard/config.yaml`). But the burrito-only rail is one of the three the config cannot find (row 6), so as wired it would not run. The rail also lists "what are your hours" as off-topic while its own refusal says the bot helps with hours. |
| 9 | Recorded fallback for the live input | **MISSING** | No recording exists. Phase 8's backup videos need a live cluster and were never made (`presentations/kubecon-na-2026/docs/SCORECARD.md`: rehearsal RED). The RUNBOOK's worst-case step sends presenters to a static screenshots deck under docs/fallback-deck/, which does not exist. Nothing replays a recorded set of audience prompts if phones or venue Wi-Fi fail. |

## What closes the gap

In order, with the 2026-11-08 date in mind:

1. **Decide the three scope points** (rows 2, 3, 4): build an
   under-protected MCP server or cut it from the talk, say what "full
   IDP" means on stage, and say whether the room hacks or the presenters
   do. The repo's rules were written before the acceptance was read.
2. **Make The Eyes see** (row 7): configure the OTel SDK in BurritBot,
   emit `gen_ai.*` spans and the block, leak and latency metrics the
   dashboards query, and test the export rather than the import.
3. **Wire the rails** (rows 6, 8): make the flow names in
   `ai-gateway/nemo-guardrails/config.yaml` match the `.co` files, and
   move "what are your hours" to on-topic.
4. **Go live** (all rows): #17, then #18, then a full rehearsal that
   fills the RUNBOOK Measurements record.
5. **Record the fallback** (row 9) from that rehearsal: one video per
   segment, a screenshots deck, and a replayable prompt set for the live
   input.
