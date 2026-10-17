# Live-Demo Fallback

What the presenters fall back to when the live input fails (#103, found
in #75, `docs/ABSTRACT-READINESS.md` row 9). `docs/RUNBOOK.md`
**Rollback** steps 5 and 6 send presenters here.

There are two ways the live input fails, and two fallbacks:

| Failure | Fallback | State |
|---|---|---|
| Phones or venue Wi-Fi fail; the cluster is healthy | Replay the recorded audience prompts from the presenter laptop | Built (this folder) |
| The cluster is down | Recorded video of each segment, and a screenshots deck | Waits on the first full rehearsal after #18 |

## Prompt replay (built)

- `prompts.yaml` is the replayable prompt set. `audience` holds the three
  canonical Act 1 asks the room sends from their phones; `menu` holds
  on-topic asks for the end of Act 2. Prompt injection, jailbreak and data
  extraction are presenter-driven and are not in the set.
- `scripts/replay-prompts.py` sends a set to the audience frontend's
  `/chat`. It reads the per-browser limit from `/config`, keeps one token
  under it, prints each reply with the bot that answered, and stops at
  the first failed prompt with the reason.

RUNBOOK **Rollback** step 5 has the commands. The Night Before section
runs the replay once over the hotspot so it is proven before it is
needed.

`tests/test_fallback_replay.py` holds the set to the canonical asks,
runs both sets through the NeMo rails the cluster mounts (the audience
asks are redirected by `burrito only input`; the menu asks pass), and
runs the replay against the real frontend. Its live test replays the
`audience` set through a port-forward to the deployed frontend; that
test has not run, because no cluster exists yet.

## Recordings (wait on #18)

Phase 8's backup videos and the screenshots deck need a working demo to
record, and nothing has run on a cluster yet. Record them at the first
full rehearsal after #18, the same rehearsal that fills the RUNBOOK
**Measurements** record:

- One video per segment: Act 1 (phones and the unguarded replies), Cast
  the Net (the command and the dashboard turning), Act 2 (the same asks
  redirected, the menu asks answered, and the rule-on-screen walk).
- A screenshots deck that tells the same story without video: the phone
  page in each mode, the `Cast the Net — Before / After Comparison`
  dashboard before and after, and each rule file Act 2 puts on screen.

Where the recordings live (this folder, Git LFS, or storage this README
links to) is decided when they exist. Until then RUNBOOK step 6 says
plainly that there is no recording.
