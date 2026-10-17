# burritbot Demo-Day Runbook

Operational runbook for running the burritbot demo live at KubeCon NA 2026.
Every section here is something Whitney or Michael should be able to run
without thinking — this is the "chess clock is ticking" document, not the
architecture doc.

---

## Night Before

Provision the evening before the talk, not the morning of. DevOpsDays
Portland did this for the Watch It Burn workshop: its fleet peaked at
479 routed hosts by 05:45 PT and was torn down within three hours of
close. See
`PORTLAND-CARRY-FORWARD.md` for what carried over from that delivery.

1. **Bring up the cluster** (Terraform rebuild is ~15 minutes). The
   `delivery` slug labels every node, disk and secret so this delivery's
   spend sums by label in the billing export. Detailed usage cost export
   must already be on for the billing account (`docs/BILLING-EXPORT.md`,
   one-time setup); usage before it is on is never exported.
   ```bash
   terraform -chdir=infrastructure/terraform apply -var delivery=kubecon-na-2026
   ```
   The model calls carry the same slug from this delivery's overlay
   (`presentations/kubecon-na-2026/deploy/`), which ArgoCD syncs. If the
   slug ever changes, change it in both places.

2. **Bootstrap ArgoCD once** (the only `kubectl apply` the rules allow):
   ```bash
   kubectl apply -f gitops/bootstrap/app-of-apps.yaml
   ```
   Wait for the root app to reach `Synced/Healthy`, then run the
   **Pre-flight** checklist below in full. Everything that fails tonight
   is a fix; everything that fails at T-60 is a rollback.

3. **Send one canonical prompt down each path** from a phone on cellular
   data: *teach me some salsa dance moves*. Expect choreography from the
   unguarded path and a redirect to the menu from the guarded path. Note
   the result in the **Measurements** record below. Then run the prompt
   replay once from the presenter laptop over the hotspot (**Rollback**
   step 5, `--rounds 1`), so the fallback is proven before it is needed.

4. **Leave it running.** Do not tear down overnight. Write down the time
   provisioning started; the Cost row in **Measurements** needs it.

---

## Pre-flight

Run this checklist T-60 minutes before the talk. Everything here is
**read-only** — nothing in this section modifies cluster state.

1. **Cluster reachable:**
   ```bash
   kubectl cluster-info
   kubectl get nodes
   ```
   Expect: all nodes `Ready`, no `NotReady` or `SchedulingDisabled`.

2. **All burritbot namespaces exist:**
   ```bash
   kubectl get ns argocd monitoring security burritbot-net \
     burritbot-unguarded burritbot-guarded audience
   ```
   Expect: 7 × `Active`.

3. **ArgoCD root app is `Synced` + `Healthy`:**
   ```bash
   kubectl -n argocd get applications root \
     -o jsonpath='{.status.sync.status}/{.status.health.status}'
   ```
   Expect: `Synced/Healthy`. Anything else → go to **Rollback**.

4. **Guarded path pods alive:**
   ```bash
   kubectl -n burritbot-net get pods -l app.kubernetes.io/part-of=burritbot
   kubectl -n burritbot-guarded get pods
   kubectl -n burritbot-unguarded get pods
   ```
   Expect: all `Running` + `1/1 Ready`.

5. **Kyverno + Falco operational:**
   ```bash
   kubectl -n security get pods -l app.kubernetes.io/component=admission-controller
   kubectl -n security get ds falco
   ```
   Expect: admission-controller `Running`; Falco DaemonSet
   `desired == ready`.

6. **Observability dashboards load:**
   Open Grafana. Verify the three burritbot dashboards render with live
   data: `The Eyes — Overview`, `BurritBot Prompt / Response Traces`,
   `Cast the Net — Before / After Comparison`.

7. **Traffic starts in the unguarded position:**
   ```bash
   ./scripts/cast-net.sh status
   ```
   Expect: `BURRITBOT_TARGET=burritbot-unguarded`. If not, run
   `./scripts/cast-net.sh recall`.

8. **Audience URL reachable from phones:**
   Hit the audience frontend URL from the venue Wi-Fi before the lights
   come down. The venue NAT often breaks things that passed in rehearsal.
   The page needs two settings on the Deployment, `FEEDBACK_URL` (the
   page's Feedback button) and `AUDIENCE_PUBLIC_URL` (what the QR code
   encodes). Either one missing returns a `503` that names it. Expect
   `200` from `/` with the Feedback button in the header, and open `/qr`
   on the projector laptop: the URL printed under the code is the one
   phones will open.
   The frontend's `/chat` limit is `10/minute` per browser: the page
   keeps a random token in `localStorage`, so phones sharing the venue
   NAT each get their own budget. One address is capped at `300/minute`
   however many tokens it sends (about 30 phones at the full rate). A
   phone that sends no token is held to `10/minute` on its address.
   Behind the GKE Gateway the address is the client entry the load
   balancer writes into `X-Forwarded-For`. Both numbers live in
   `presentations/kubecon-na-2026/deploy/audience/delivery-audience.yaml`
   (`AUDIENCE_TOKEN_LIMIT`, `AUDIENCE_ADDRESS_LIMIT`). To retune at the
   venue, change them there and let ArgoCD sync; the pod restarts with
   the new numbers and fresh budgets. Skip `kubectl set env`: the
   Application self-heals the Deployment back to Git. Watch for `429`s in the first minute of Act 1 and record
   them under **Room network**. A phone that hits the ceiling is told to
   wait or switch to cellular.

---

## Act 1 — The Unguarded Demo

Chipotle incident narration. Audience sees a wide-open BurritBot.

1. Confirm traffic is pointed at the unguarded target:
   ```bash
   ./scripts/cast-net.sh status
   ```

2. Narrate the Chipotle chatbot incident. Invite the audience to send
   BurritBot the lighthearted off-topic asks from their phones: *teach me
   some salsa dance moves*, *how do I throw a hot dog party*, *recommend
   karaoke songs for a wedding*. The unguarded bot writes the
   choreography. Prompt injection, jailbreak and data extraction are
   driven by the presenters, never crowdsourced from the room.

3. While the audience plays: pull up the `Cast the Net — Before / After`
   dashboard on the shared screen. The left panel will start lighting up
   red as unguarded BurritBot leaks.

4. **Hard rule: never let Act 1 run longer than five minutes.** The demo
   joke is funnier than a broken chatbot at minute six. Move on.

---

## Cast the Net

The central reveal. One command, under 500ms on a warm cluster.

1. From the demo laptop shell:
   ```bash
   ./scripts/cast-net.sh cast
   ```
   This patches the `BURRITBOT_TARGET` env var on the audience-frontend
   Deployment to `burritbot-guarded`. ArgoCD will not race the patch
   because `cast-net.sh` uses `kubectl patch --type=json` (never `apply`).

2. Immediately re-run status to confirm:
   ```bash
   ./scripts/cast-net.sh status
   ```
   Expect: `BURRITBOT_TARGET=burritbot-guarded`.

3. Flip the shared screen back to the Grafana `Cast the Net` dashboard.
   The block-rate panel should start climbing within seconds as the
   audience's leftover attacks now hit The Net.

---

## Act 2 — The Guarded Demo

Same audience, same prompts — The Net catches the problems.

1. Invite the audience to try the exact same prompts from Act 1. Point
   out the block events appearing on the dashboard in real time.

2. Walk through the layers as each one catches something:
   - **The Eyes**: OTel Collector decorates every call with `gen_ai.*`
     attributes — you can see them in the trace table.
   - **The Net**: NeMo Colang rails refuse off-topic and jailbreak
     attempts. The content scanners block prompt-injection and sanitize
     model replies. Kyverno enforces burritbot.io labels on every guarded
     pod. Falco alerts on any shell that escapes.
   - **The Web**: ArgoCD sync status, Gateway API routes, SPIFFE
     identities — the platform scaffolding holding the live demo up.

3. **Put the rule that fired on screen.** The dashboard proves something
   was caught; the policy file is the argument of the talk. Show the
   rule itself, not just the `cast-net.sh` switch:
   - Audience off-topic asks →
     `ai-gateway/nemo-guardrails/rails/burrito-only.co` (the `ask off
     topic` examples are the canonical Act 1 prompts).
   - Presenter-driven injection and jailbreak →
     `ai-gateway/nemo-guardrails/rails/jailbreak-detect.co`, then the
     `PromptInjection` scanner in `ai-gateway/llm-guard/config.yaml`.
   - Pod admission → `security/kyverno/policies/require-burritbot-labels.yaml`.
   - Runtime shell escape → `security/falco/rules/burritbot-the-net.yaml`.

4. Close the act with the scorecard: pull up
   `presentations/kubecon-na-2026/docs/SCORECARD.md` in the browser, talk
   through what's real vs. aspirational. Do not green-wash.

---

## Measurements

Portland's pacing result was attendee perception, not measurement, and
nobody wrote down whether the network held or what the delivery cost.
Fill this record at every full rehearsal and on the day. A stopwatch per
segment costs nothing and answers what to cut if the slot shrinks. Blank
cells are unmeasured; do not backfill from memory.

| Segment | Budget | Rehearsal | Day-of | Notes |
|---|---|---|---|---|
| Pre-flight | T-60, read-only | — | — | Duration of the checklist, not part of the slot |
| Act 1 | ≤ 5 min (hard rule) | — | — | |
| Cast the Net | — | — | — | Command to first block on the dashboard |
| Act 2 | — | — | — | Include the rule-on-screen walk |
| Q&A | ~5 min (`PLAN.md`) | — | — | |

| Record | What to capture | Rehearsal | Day-of |
|---|---|---|---|
| Real devices | Audience page on at least one iOS Safari and one Android Chrome phone, on venue Wi-Fi and on cellular: loads, no overlapping elements, prompt submits | — | — |
| Room network | Venue Wi-Fi held for the whole slot (yes / no / when it dropped); count of `429` responses, per-browser (`phone`) and per-address ceiling (`network`) | — | — |
| Cost | Spend from provisioning start (Night Before) to teardown complete, GKE and Vertex AI separately, from the billing export queries in `docs/BILLING-EXPORT.md` (read at least three days after teardown) | — | — |

---

## Teardown

Post-talk cleanup. Finish within three hours of the session closing,
as Portland did, and write the time teardown completed into the Cost
row of **Measurements**.

1. Recall traffic and stop any in-flight probes:
   ```bash
   ./scripts/cast-net.sh recall
   ```

2. Drain the cluster gracefully. Scale ArgoCD down first so it does not
   try to re-sync deleted resources mid-teardown:
   ```bash
   kubectl -n argocd scale deploy argocd-application-controller --replicas=0
   kubectl -n argocd scale deploy argocd-applicationset-controller --replicas=0
   ```

3. Run the teardown script (destroys Terraform-managed infra):
   ```bash
   ./scripts/teardown.sh
   ```

4. Verify no lingering GCP resources. The script prints a final
   `gcloud container clusters list` and `gcloud compute networks list`
   for a visual sanity check. Spot-check in the GCP console.

5. Revoke demo-day credentials: rotate the Vertex Secret Manager entry
   and the audience-frontend public URL.

---

## Rollback

Use this if the pre-flight checklist fails or if the cluster looks wrong
mid-demo. **Rollback is preferred over debugging live.**

1. **ArgoCD OutOfSync or Degraded:**
   ```bash
   kubectl -n argocd get applications
   kubectl -n argocd describe application root
   argocd app sync root --force
   ```
   If still broken: re-apply the bootstrap manifest by hand:
   ```bash
   kubectl apply -f gitops/bootstrap/app-of-apps.yaml
   ```

2. **BurritBot pods crash-looping:**
   ```bash
   kubectl -n burritbot-guarded rollout undo deploy/burritbot
   kubectl -n burritbot-unguarded rollout undo deploy/burritbot
   ```

3. **Cast the Net misfires (toggle stuck):**
   ```bash
   ./scripts/cast-net.sh recall
   # If that still fails, patch by hand:
   kubectl -n audience set env deploy/audience-frontend BURRITBOT_TARGET=burritbot-unguarded
   ```

4. **Full reset:** rerun the Phase 2 bootstrap from a clean state — see
   `spec/phases/phase-02-gitops.md`. Only do this if the talk is not live.

5. **Phones or venue Wi-Fi fail, cluster healthy:** the presenter laptop
   stands in for the room. Join the cellular hotspot and replay the
   recorded audience prompts:
   ```bash
   kubectl -n audience port-forward svc/audience-frontend 8080:80
   uv run --managed-python --frozen python scripts/replay-prompts.py \
     --url http://127.0.0.1:8080 \
     --prompts presentations/kubecon-na-2026/fallback/prompts.yaml \
     --set audience --rounds 10
   ```
   It sends the three canonical Act 1 asks as one browser, paced under
   the frontend's per-browser limit (about one prompt every 6.6s at
   `10/minute`), and prints each reply with the bot that answered. Leave
   it running through **Cast the Net**: the same asks start coming back
   as menu redirects and the dashboard sees the blocks. Close Act 2 with
   `--set menu` to show the guarded bot still sells burritos. Ctrl-C
   stops it. It stops by itself at the first failed prompt and prints
   why; treat that as the next step, not something to debug live.

6. **Worst case, the cluster is down:** play the recorded segments and
   the screenshots deck from `presentations/kubecon-na-2026/fallback/`.
   They are recorded at the first full rehearsal after #18 (see that
   folder's `README.md`); until that rehearsal there is no recording,
   and the worst case is the story without the demo. The audience came
   for the story, not the cluster.
