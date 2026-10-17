# Talk Deck

The deck for "BurritoBot Said Let's Dance, the Platform Said No"
(Sessionize 1249553, Thursday 2026-11-12). It is spec 001 M5 (#120).
The presenters upload the PDF to Sessionize; nothing here uploads it.

| File | What it is |
|---|---|
| `slides.html` | The source. One 1920x1080 `<section class="slide">` per slide, with speaker notes in `<aside class="notes">` (not printed). |
| `export_pdf.py` | Renders `slides.html` in Playwright's Chromium to the PDF, after checking that nothing spills off a slide. |
| `burritobot-said-lets-dance.pdf` | The 16:9 export for Sessionize: 22 pages at 1440x810pt. |
| `export.json` | The sha256 of the source (with `assets/hero.png`) and of the PDF, so the static suite can tell when the PDF is stale. |

## Rebuild the PDF

After any edit to `slides.html` or `assets/hero.png`:

```bash
uv run --managed-python --frozen python presentations/kubecon-na-2026/deck/export_pdf.py
```

`tests/test_talk_deck.py` fails until the PDF is exported again.

## How it follows the runbook

The slides run in the order of the `RUNBOOK.md` segments: an opening
(the Chipotle story, the argument, the ogre-faced spider, the two
request paths), **Act 1** (the canonical off-topic asks from phones,
with injection and jailbreak left to the presenters), **Cast the Net**
(`./scripts/cast-net.sh cast`), **Act 2** (the Kubernetes layers before
the LLM layer, then each rule the runbook puts on screen, The Eyes and
the scorecard), and **Q&A**. The live parts (the `/qr` page, Grafana,
`SCORECARD.md` in the browser) are switched to from the deck, so the
PDF carries no status that goes stale.

Every rule on a slide is quoted from its file, and the static suite
checks that each excerpt still matches.

## What is left out

- **Cut abstract points.** None of the nine points in
  `../docs/ABSTRACT-READINESS.md` is marked CUT yet. The scope calls
  (MCP server, full IDP, who hacks, what counts as mid-inference) are
  with Michael and Whitney (talks-knowledge#29). When a row is marked
  CUT, the test fails while the deck still names that point.
- **What the repo has not built.** No slide names an MCP server, a
  developer portal, SPIFFE/SPIRE or token-based rate limiting, because
  the repo has none of them. If talks-knowledge#29 keeps one in the
  talk, it gets a slide once it is built, and `NOT_BUILT` in the test
  changes with it.
- **The repo URL.** Spec 001 M8 makes the repo public after the talk,
  so no slide links to it yet. The presenters decide whether the closing
  slide gets one.
