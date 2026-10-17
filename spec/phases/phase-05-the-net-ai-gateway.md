# Phase 5: The Net — AI Gateway (NeMo + LLM Guard + Envoy)

**Goal:** Content-aware enforcement running in the `burritbot-net`
namespace. Every call on the guarded path traverses NeMo Guardrails
Colang rails, LLM Guard input and output scanners, and an Envoy AI
Gateway route before reaching Vertex AI.

**Inputs:** Phase 4 complete. `burritbot-net` namespace exists and
Kyverno is enforcing the burritbot.io label set and the burritbot-*
sidecar naming convention.

**Outputs:**

- `ai-gateway/nemo-guardrails/config.yaml` — wires models (Vertex AI,
  `gemini-3-pro` via `google-genai`) and references the Colang rails
- `ai-gateway/nemo-guardrails/burrito-only.co`
- `ai-gateway/nemo-guardrails/jailbreak-detect.co`
- `ai-gateway/nemo-guardrails/topic-enforcement.co`
- `ai-gateway/nemo-guardrails/output-sanitize.co`
- `ai-gateway/llm-guard/config.yaml` — declares both `input_scanners`
  and `output_scanners` (non-empty)
- `ai-gateway/envoy/` — at least one of `Gateway`, `HTTPRoute`, or
  `AIGatewayRoute`
- `ai-gateway/extproc/` — the `burritbot-extproc` gRPC ext_proc adapter.
  NeMo Guardrails and LLM Guard serve REST, so the ExtProc entries name
  this sidecar in each scanner pod, not the scanner (#66). The policy
  targets the Gateway, so both scanners scan the audience hop and the
  model hop, prompt and reply; on the model hop the adapter reads
  Vertex's own reply and refuses a prompt rewrite the gateway would
  drop (#94)
- `gitops/apps/nemo-guardrails.yaml`, `gitops/apps/llm-guard.yaml`,
  `gitops/apps/envoy-ai-gateway.yaml`

**Test Criteria (tests/test_phase_05_the_net_gateway.py):**

Static:

- `test_ai_gateway_tree_exists`
- `test_nemo_colang_rails_present` — all four `.co` files
- `test_nemo_config_yaml_valid` — parses and declares `models` or
  `rails`
- `test_llm_guard_declares_input_and_output_scanners` — both lists
  non-empty
- `test_envoy_ai_gateway_manifest_exists`
- `test_guarded_path_namespace_is_burritbot_net` — no legacy
  `guardrails` namespace references anywhere under `ai-gateway/`

Live:

- `test_nemo_guardrails_pod_running`
- `test_envoy_ai_gateway_pod_running`

**Key Technology Decisions:**

- NeMo Guardrails 0.11+ with Colang 2.0
- LLM Guard 0.3.16 (the last release; upstream archived 2026-07-08) — always run both input and output scanners
- Envoy AI Gateway 0.6+ (the first release serving the v1beta1
  AIGatewayRoute; 0.2-0.5 serve only v1alpha1)
- Gateway API v1.4+ (the first release serving BackendTLSPolicy
  `gateway.networking.k8s.io/v1`, which `vertex-ai-backend.yaml`
  applies; v1.2 and v1.3 serve only v1alpha3, experimental channel)
- All three live in the **`burritbot-net`** namespace. The name
  `guardrails` is from an earlier draft; a Phase 5 test greps for it
  and fails.

**Known Risk:** LLM Guard's `Regex` output scanner needs double-escaped
backslashes when shipped via YAML (`"kubectl\\s+\\w+"`), not single.
Easy to miss in code review.

**Completion Promise:** `<promise>PHASE5_DONE</promise>`

**Skill:** `.claude/skills/the-net-ai-gateway.md`

**Commits:** 4 expected (NeMo rails + config; LLM Guard config; Envoy
gateway + route; ArgoCD apps)
