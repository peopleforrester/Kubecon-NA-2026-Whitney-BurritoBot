# Portland Carry-Forward

What the DevOpsDays Portland delivery (2026-09-08) proved and what it left
unmeasured, mapped onto this talk. Requested from
`peopleforrester/2026-portland-devopsdays`; the source is that repo's
`notes/DEBRIEF.md`, summarised in issue #27 here.

Portland ran the Watch It Burn workshop, which is a different format on a
different platform. Its BurritoBot is independent of this one (see
`decisions.md`, 2026-10-16, issue #25). This file carries over the
**delivery** lessons only. It does not import workshop content, and it
does not re-argue what Portland settled.

| | Portland | This talk |
|---|---|---|
| Format | Hands-on workshop, attendees work through numbered challenges | 30-minute session, two speakers, audience on phones |
| Platform | EKS, Bedrock, kagent | GKE, Vertex AI, NeMo Guardrails, LLM Guard, Envoy AI Gateway |
| Live history | Ran live; 479 routed hosts at peak | Has never run on a cluster as of 2026-10-16 |

---

## Proven at Portland

These are kept as settled. Where a result belongs to the workshop format
it is named as workshop-only rather than forced into a 30-minute session.

| Result | What it means here | Where it lands |
|---|---|---|
| **Hands-on format.** Attendees apply the policy, then retry the attack. | Workshop-only. A 30-minute session cannot hand a room a policy to apply. The nearest equivalent is already in the design: the audience drives Act 1 and Act 2 from their phones, and the repo is the Monday-morning takeaway (CFP takeaway 4). | No change. |
| **Denial of wallet instead of the fork bomb.** The cost meter makes it visible. | This talk never had a fork bomb, and its attack set is fixed by the narrative (CLAUDE.md). What does carry over is the visible cost meter. The CFP promises Envoy AI Gateway "token-based rate limiting", but `ai-gateway/envoy/gateway.yaml` has no token limit. LLM Guard's `TokenLimit` caps a single prompt at 1024 tokens, which is not a spend limit. BurritBot already returns `input_tokens` and `output_tokens`, yet no Grafana panel shows them. | Follow-up: build the token limit and a token panel, or drop the claim from the talk. |
| **Step zero, then step N equals challenge N.** | Workshop numbering, and this talk has no challenges. The lesson underneath it is that the document's structure should match what is happening in the room. The runbook headings match the on-stage segments one to one (Night Before, Pre-flight, Act 1, Cast the Net, Act 2), so a cold reader can always find their place. | `RUNBOOK.md` structure. |
| **Real policy YAML, not a `guards-on` toggle.** | Carries over directly. The two-namespace A/B split and `cast-net.sh` stay, because that architecture is non-negotiable. But the switch is not the argument. Act 2 now puts on screen the rule that fired: the Colang rail, the LLM Guard scanner, the Kyverno policy or the Falco rule. | `RUNBOOK.md` Act 2 step 3. `tests/test_portland_carry_forward.py` checks that every file it names exists. |
| **Provision the night before.** | Carries over, at a smaller scale: one cluster, not a workshop fleet. Bring-up, ArgoCD sync and the full pre-flight run the evening before, which leaves T-60 for read-only checks. Teardown finishes within three hours of the session closing. | `RUNBOOK.md` Night Before and Teardown. |
| **A Feedback button inside the lab.** | Carries over as a requirement for the audience phone page: a feedback link on the page people already have open. That page does not exist yet (see Mobile below). Until it does, the conference session survey is the only feedback channel, which was Portland's zero-feedback baseline. | Requirement on the phone-page follow-up. |

Portland's result (NPS 62, mean 9.0, zero detractors, 8 of 8 respondents
rating pacing and difficulty "just right", attendance growing from 21 to
30–35) belongs to a workshop. It is not a target for a 30-minute session.

---

## Still unmeasured

Fix these here rather than carry them a third time. All four have a row in
the `RUNBOOK.md` **Measurements** record. Blank cells mean unmeasured.

1. **Per-segment timing.** The runbook now has a stopwatch row per
   segment, filled at each rehearsal and on the day. Only two budgets are
   known today: Act 1 at most 5 minutes (the runbook's hard rule) and Q&A
   about 5 minutes (`PLAN.md`). The first timed rehearsal sets the rest.
2. **Mobile.** The gap is worse here than at Portland: there is no phone
   page at all. `apps/audience-frontend/backend/main.py` is a JSON API
   (`/healthz`, `/config`, `/chat`). The `index.html`, `app.js`,
   `styles.css` and QR landing page in `BUILD-INSTRUCTIONS.md` were never
   built, and the Phase 7 static tests pass against the backend alone. The
   Real devices row requires one iOS Safari and one Android Chrome phone,
   each on venue Wi-Fi and on cellular.
3. **Room network.** The Room network row records whether venue Wi-Fi
   held. Reading the code turned up a second risk. The frontend's
   `10/minute` limit is keyed on the connecting address, uvicorn runs
   without `--proxy-headers`, and no Ingress manifest exists yet. So
   whatever sits in front of the pod (the venue NAT, a load balancer or
   both), a room of phones shares one budget of about 10 prompts a minute
   in total.
4. **Cost.** This talk has never been costed either, and labels cannot
   cost it today. The GKE cluster in `infrastructure/terraform/gke.tf`
   carries no `resource_labels` (only the Secret Manager secret is
   labelled), and no billing export is configured. This is the GCP
   counterpart of `Unleash_an_Agent_Watch_It_Burn#392`. The cost envelope
   in `PLAN.md` still prices Gemini 2.5 Flash, which retires on
   2026-10-16. The Cost row records spend from Night Before provisioning
   to teardown, with GKE and Vertex AI separated.

---

## Hallway asks

A KubeCon audience skews more cloud-native than DevOpsDays. Two asks came
up in the Portland hallway.

- **Enterprise model gateway and MCP intersection.** The model-gateway
  half is already the talk: Envoy AI Gateway in `burritbot-net` is the
  single choke point for guarded traffic. MCP is not in the stack, and
  there is no room for it in a two-act, 30-minute session. Treat it as
  a repo expansion after the talk and as a Q&A answer, not as scope.
- **Deeper economic cost distribution, leaning into one cloud.** Push
  back again, as at Portland. The platform runs on GKE for demo
  reliability, but the talk argues the opposite of cloud lock-in: the
  CNCF projects attendees already run close the gap with "about 20% more
  configuration on infrastructure you already own" (CFP). The talk's cost
  content is limited to the Cost measurement above, stated as this
  delivery's number and not as a lesson in one provider's pricing.

---

## Cold read

Portland closed about 60 issues in its final week, most of them on the
day. It caught four unwinnable challenges only because a co-presenter
happened to read the lab cold inside the last 72 hours. This time the
read is scheduled.

- **When:** proposed for 2026-10-30, ten days before the event opens on
  2026-11-09. That leaves a fix window long enough to act on what the
  read finds. A read at T-72h does not replace it.
- **Who:** a co-presenter who has not run this runbook before. Whitney
  fits, and it mirrors how Portland's catch was made. The date and the
  reader are proposals for Michael and Whitney to confirm.
- **What:** run `RUNBOOK.md` from Night Before through Teardown, cold,
  against a live cluster, with the Measurements record open. File an
  issue for every place the reader stops or guesses. That rehearsal
  fills the first Rehearsal column.
- **Gate:** nothing has ever run on a cluster. #22, #23 and #24 have
  landed, which leaves #17 (the GCP identity swap, which blocks
  everything) and then #18 (live bring-up). If #18 has not happened by
  2026-10-27, the cold read becomes a paper read. The first live run
  then becomes the risk to plan around.
