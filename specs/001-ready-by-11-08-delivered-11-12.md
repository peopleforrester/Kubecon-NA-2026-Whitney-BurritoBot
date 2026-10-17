# Working copy: Spec 001, BurritoBot ready by 11-08, delivered 11-12

- **Source:** personal-knowledge `specs/talks/burritobot/001-ready-by-11-08-delivered-11-12.md`
- **sha256:** `fdc5f0742d9e2f6235178bcada13da9ee875dae64072cfe8f6633ecc04ee2d16`
  (the delivered file, whose Corrections section reads "None yet.")
- **Issue:** #114. Approved by Michael 2026-10-17.

The spec sits between the BEGIN and END markers below, as delivered.
Only its Corrections section changes here. Changes to the spec go back
to personal-knowledge as an issue. Issues for this work derive from
this spec. `tests/test_spec_001_working_copy.py` hashes the text
between the markers, with Corrections put back as delivered, against
the sha256 above.

## Milestone status

This table is this repo's tracking and not part of the spec. Each
milestone closes with the KR or metric the spec says it moves. Read
2026-10-17 from staging at `1945a6f`.

| Milestone | Due | Status | Closes with | Waits on | Where it stands |
|---|---|---|---|---|---|
| M1 | 2026-10-23 | WAITING | `kubecon-na-burritobot` | #17, then #83, then #18 | Nothing has run on a cluster. The GCP credential returns `invalid_grant`. #17 swaps the identity; gcp-management owns the credential. #83 is Michael's console step for the billing export, before the first apply. #18 is the bring-up from the runbook. |
| M2 | 2026-10-26 | WAITING | `kubecon-na-burritobot` | M1 | Whitney reads `RUNBOOK.md` cold on 2026-10-26, 10:00 to 16:00 Central (#60). If #18 has not landed by 2026-10-23 it becomes a paper read, which is not a run against the live platform. |
| M3 | 2026-10-31 | OPEN | TALK.DELIVER | talks-knowledge#29 for rows 2, 3, 4 and 6; #18 for anything live | Metric: 0 of 9 READY live. `presentations/kubecon-na-2026/docs/ABSTRACT-READINESS.md` (after #113) rates 3 READY-STATIC, 3 PARTIAL, 3 MISSING. The scope calls (MCP server, full IDP, who hacks, mid-inference) are with Michael and Whitney. GenAI observability (#101) needs nothing external. #58 and #112 are not settled. |
| M4 | 2026-11-01 | WAITING | TALK.DELIVER | M1 | The recorded fallback (#103) and the Grafana screenshot (#20) both need a live rehearsal. Readiness row 9 is MISSING, and until #101 lands the dashboard would show nothing. |
| M5 | 2026-11-04 | OPEN | TALK.DELIVER | nothing for the deck; the presenters for the Sessionize upload | No deck exists under `presentations/` and no issue tracks one yet. |
| M6 | 2026-11-08 | WAITING | `kubecon-na-burritobot` | M1, M5 | No run-through with Whitney is scheduled. Two timed runs, demo included, need the live platform and the deck. |
| M7 | 2026-11-12 | WAITING | `kubecon-na-burritobot` | 2026-11-12 | Thursday 13:50 to 14:20 MST, Grand Ballroom BDF (Sessionize 1249553). |
| M8 | by 2026-12-12 | WAITING | `mrf-talk-campaigns`, `mrf-talk-clips` | M7 | mrf-engagement-orchestrator does the posting. This repo supplies the public-repo checks and the source for the clip. |
| M9 | after M7 | WAITING | TALK.REUSE | M7 | Logged in talks-knowledge's register, then the move into `talks/burritobot/` per repo-management#22. |

<!-- BEGIN SPEC 001 -->
<!-- ABOUTME: Spec 001 for the BurritoBot talk: the platform live and the abstract's promises met by 11-08, delivered with Whitney Lee on 11-12. -->
<!-- ABOUTME: Derived from okrs.yaml repo objective talk-folders.1 (talks grouping approved 2026-10-17). -->

---
spec: talks/burritobot/001
status: approved
approved: 2026-10-17 by Michael ("yes approve talks, write the specs")
chain:
  vision_subtracks: [V3b, V3a, V6c]
  objective: 2026q4.H
  sub_objectives: [TALK.DELIVER, TALK.CAMPAIGN, TALK.REUSE]
  repo_objective: talk-folders.1
  krs: [kubecon-na-burritobot, mrf-talk-campaigns, mrf-talk-clips]
  metrics: ["abstract points READY (target 9 of 9 or cut from the talk with Whitney's agreement)"]
repo_plan: none; PROJECT_STATE.md, spec/ and ABSTRACT-READINESS.md carry the work
priority: 1 (hard dates 2026-10-23, 10-26, 11-04, 11-08, 11-12)
---

# BurritoBot: ready by 11-08, delivered 11-12

## Why

"BurritoBot Said Let's Dance, the Platform Said No" is the accepted KubeCon NA
breakout with Whitney Lee (Sessionize 1249553), Thursday 2026-11-12, 13:50 to
14:20 MST, Grand Ballroom BDF. It is the largest stage of the quarter and the
only co-presented talk, so a live demo that fails costs both presenters.

## Where it stands (2026-10-17, read from origin/staging)

- 674 static tests green. **Nothing has run on a cluster yet**: the GCP
  credential returns `invalid_grant`.
- Critical path: #17 (GCP identity) to #83 (billing export) to #18 (live
  bring-up) to #20 (Grafana screenshot).
- ABSTRACT-READINESS: 2 ready, 4 partial, 3 missing (MCP server, GenAI
  observability #101, recorded fallback #103).
- No slide deck exists under `presentations/`.
- KubeCon registry items still pending: speaker promo video (due 10-13), the
  speaker-change and AV cutoffs (10-16). Those are conference-knowledge's to
  close; this repo supplies the content.

## Milestones

| # | Done when | Moves | Date |
|---|---|---|---|
| M1 | The live platform comes up on GCP from the runbook (#17, #83, #18). gcp-management owns the credential; file there if it blocks | `kubecon-na-burritobot` | **2026-10-23** |
| M2 | Whitney's cold read of RUNBOOK.md runs against the live platform, and her findings are filed | `kubecon-na-burritobot` | **2026-10-26** |
| M3 | Every abstract point is READY or has been cut with Whitney's agreement and recorded. #58 (token rate limiting promised) and #112 (NeMo with Vertex models) settled | TALK.DELIVER | 2026-10-31 |
| M4 | Recorded fallback (#103) and Grafana screenshot (#20) captured, so the talk survives a dead network | TALK.DELIVER | 2026-11-01 |
| M5 | Deck built and the 16:9 PDF uploaded to Sessionize | TALK.DELIVER | **2026-11-04** |
| M6 | Two full timed run-throughs with Whitney, demo included | `kubecon-na-burritobot` | **2026-11-08** |
| M7 | Delivered | `kubecon-na-burritobot` | **2026-11-12** |
| M8 | Campaign: at least two articles, a clip posted to YouTube and as native LinkedIn video, the repo made public after the public-repo checks. mrf-engagement-orchestrator executes the posting | `mrf-talk-campaigns`, `mrf-talk-clips` | by 2026-12-12 |
| M9 | Delivery logged in talks-knowledge's register; the repo moves into `talks/burritobot/` under the layout (local folder only once delivered, per repo-management#22) | TALK.REUSE | after M7 |

## Boundaries

Event logistics (travel, registration, the KubeCon cutoffs) belong to
conference-knowledge and kubecon-events. GCP account and billing belong to
gcp-management. Costs go to Financal_Management_Tool.

## Corrections

None yet.
<!-- END SPEC 001 -->
