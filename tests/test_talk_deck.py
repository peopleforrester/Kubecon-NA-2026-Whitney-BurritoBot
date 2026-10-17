# ABOUTME: Checks the talk deck (issue #120, spec 001 M5): runbook segment order, rules quoted verbatim, no cut or unbuilt points.
# ABOUTME: Holds the committed 16:9 PDF to the slide source by sha256; the live test renders the source and checks the layout.

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from html import unescape
from html.parser import HTMLParser

import pytest

from conftest import PROJECT_ROOT


TALK = PROJECT_ROOT / "presentations" / "kubecon-na-2026"
DECK = TALK / "deck"
SOURCE = DECK / "slides.html"
RECORD = DECK / "export.json"
RUNBOOK = TALK / "docs" / "RUNBOOK.md"
READINESS = TALK / "docs" / "ABSTRACT-READINESS.md"

TITLE = "BurritoBot Said Let's Dance, the Platform Said No"
SPEAKERS = ("Whitney Lee", "Michael Forrester")
# The deck opens, then follows the runbook's on-stage segments in order.
SEGMENTS = ("opening", "act-1", "cast-the-net", "act-2", "q-and-a")
RUNBOOK_HEADINGS = ("## Act 1", "## Cast the Net", "## Act 2")
CANONICAL_ACT1_PROMPTS = (
    "salsa dance moves",
    "hot dog party",
    "karaoke songs for a wedding",
)
# What each readiness row's point would put on a slide. A row whose status
# becomes CUT (talks-knowledge#29, with Whitney's agreement) must leave no
# trace of these in the deck.
POINT_TERMS = {
    "1": ("burrito-chain",),
    "2": ("MCP",),
    "3": ("IDP", "developer portal"),
    "4": ("hack",),
    "5": ("Kyverno", "Falco"),
    "6": ("mid-inference",),
    "7": ("gen_ai",),
    "8": ("carne asada bowl",),
    "9": ("recorded fallback",),
}
# Not in the repo, so not on a slide: no MCP server (readiness row 2), no
# portal (row 3), no SPIRE Application (row 3), no token limit (#58).
NOT_BUILT = ("MCP", "Backstage", "SPIFFE", "SPIRE", "token-based rate limit")
# Readiness row 4: the room sends off-topic asks; attacks are the presenters'.
AUDIENCE_ATTACK = re.compile(r"\b(hack|attack|jailbreak it|break it)\b", re.IGNORECASE)


def _load_exporter():
    spec = importlib.util.spec_from_file_location("deck_export_pdf", DECK / "export_pdf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Deck(HTMLParser):
    """Collects slides (segment, visible text) and excerpts (source, text) from slides.html."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.slides: list[tuple[str, list[str]]] = []
        self.excerpts: list[tuple[str, list[str]]] = []
        self.paths: list[str] = []
        self._hidden = 0
        self._capture: list[str] | None = None
        self._path: list[str] | None = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "section" and "slide" in classes:
            self.slides.append((attrs.get("data-segment", ""), []))
        if tag in ("style", "title") or "notes" in classes or self._hidden:
            self._hidden += 1
        if attrs.get("data-source"):
            self._capture = []
            self.excerpts.append((attrs["data-source"], self._capture))
            self._depth = 1
        elif self._capture is not None and tag not in ("br",):
            self._depth += 1
        if tag == "code" and "path" in classes:
            self._path = []

    def handle_endtag(self, tag):
        if self._hidden:
            self._hidden -= 1
        if self._capture is not None:
            self._depth -= 1
            if self._depth == 0:
                self._capture = None
        if tag == "code" and self._path is not None:
            self.paths.append("".join(self._path))
            self._path = None

    def handle_data(self, data):
        if self._capture is not None:
            self._capture.append(data)
        if self._path is not None:
            self._path.append(data)
        if not self._hidden and self.slides:
            self.slides[-1][1].append(data)


def _deck() -> _Deck:
    parser = _Deck()
    parser.feed(SOURCE.read_text(encoding="utf-8"))
    return parser


def _slide_text(segment: str | None = None) -> str:
    text = " ".join(" ".join(parts) for seg, parts in _deck().slides if segment in (None, seg))
    return re.sub(r"\s+", " ", unescape(text))


def _readiness_statuses(text: str) -> dict[str, str]:
    rows = re.findall(r"^\| (\d) \| [^|]+ \| \*\*([A-Z-]+)\*\* \|", text, re.MULTILINE)
    return dict(rows)


def cut_points_on_slides(deck_text: str, readiness_text: str) -> list[str]:
    """Readiness rows marked CUT whose terms still appear in the deck text."""
    found = []
    for row, status in _readiness_statuses(readiness_text).items():
        if status != "CUT":
            continue
        for term in POINT_TERMS[row]:
            if re.search(re.escape(term), deck_text, re.IGNORECASE):
                found.append(f"row {row}: {term}")
    return found


def _is_subsequence(excerpt: list[str], lines: list[str]) -> bool:
    it = iter(lines)
    return all(any(want == have for have in it) for want in excerpt)


@pytest.mark.static
def test_title_slide_names_the_talk_and_both_speakers() -> None:
    """The first slide carries the accepted title and both presenters."""
    segment, parts = _deck().slides[0]
    text = re.sub(r"\s+", " ", unescape(" ".join(parts)))
    assert segment == "opening", "the deck does not open on the title slide"
    assert TITLE in text, "title slide lacks the accepted title"
    for name in SPEAKERS:
        assert name in text, f"title slide does not name {name}"


@pytest.mark.static
def test_slides_follow_the_runbook_segments_in_order() -> None:
    """Segments run opening, Act 1, Cast the Net, Act 2, Q&A, each contiguous, as RUNBOOK.md orders them."""
    runbook = RUNBOOK.read_text(encoding="utf-8")
    positions = [runbook.index(h) for h in RUNBOOK_HEADINGS]
    assert positions == sorted(positions), "RUNBOOK.md no longer orders Act 1, Cast the Net, Act 2"
    order = [seg for seg, _ in _deck().slides]
    collapsed = [seg for i, seg in enumerate(order) if i == 0 or order[i - 1] != seg]
    assert tuple(collapsed) == SEGMENTS, f"deck segments run {collapsed}, expected {list(SEGMENTS)}"


@pytest.mark.static
def test_act_1_invites_the_canonical_off_topic_asks_and_keeps_attacks_with_the_presenters() -> None:
    """Act 1 names the canonical asks, says the presenters drive the attacks, and never invites the room to hack."""
    act1 = _slide_text("act-1")
    for ask in CANONICAL_ACT1_PROMPTS:
        assert ask in act1.lower(), f"Act 1 slides do not offer {ask!r}"
    assert "our job, not yours" in act1, "Act 1 slides do not keep injection and jailbreak with the presenters"
    hits = AUDIENCE_ATTACK.findall(_slide_text())
    assert not hits, f"the deck invites the audience to attack: {hits}"


@pytest.mark.static
def test_cut_abstract_points_do_not_appear() -> None:
    """No readiness row marked CUT leaves its point on a slide; every row's status parses."""
    readiness = READINESS.read_text(encoding="utf-8")
    statuses = _readiness_statuses(readiness)
    assert sorted(statuses) == sorted(POINT_TERMS), f"readiness rows parsed as {statuses}"
    assert not cut_points_on_slides(_slide_text(), readiness)


@pytest.mark.static
def test_cut_rule_catches_a_cut_point_left_on_a_slide() -> None:
    """Mutation: marking row 2 CUT fails a deck that mentions MCP, and passes one that does not."""
    readiness = READINESS.read_text(encoding="utf-8")
    cut = re.sub(r"^(\| 2 \| [^|]+ \| )\*\*[A-Z-]+\*\*", r"\1**CUT**", readiness, flags=re.MULTILINE)
    assert cut != readiness, "could not mark row 2 CUT"
    assert cut_points_on_slides("Next: an under-protected MCP server", cut) == ["row 2: MCP"]
    assert cut_points_on_slides(_slide_text(), cut) == []


@pytest.mark.static
def test_deck_promises_nothing_the_repo_has_not_built() -> None:
    """No slide names a component the repo does not have."""
    text = _slide_text()
    named = [term for term in NOT_BUILT if re.search(rf"\b{re.escape(term)}", text, re.IGNORECASE)]
    assert not named, f"the deck names components the repo lacks: {named}"


@pytest.mark.static
def test_every_rule_on_screen_is_quoted_from_its_file() -> None:
    """Each excerpt's lines appear, in order, in the file it cites, so a slide cannot drift from the rule."""
    excerpts = _deck().excerpts
    assert len(excerpts) >= 6, "fewer rule excerpts than the runbook's rule-on-screen walk names"
    for source, parts in excerpts:
        path = PROJECT_ROOT / source
        assert path.is_file(), f"excerpt cites {source}, which does not exist"
        file_lines = [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()]
        text = unescape("".join(parts)).strip("\n")
        want = [line.rstrip() for line in text.splitlines()]
        assert any(want), f"the {source} excerpt is empty"
        if len(want) == 1:
            assert want[0].strip() in path.read_text(encoding="utf-8"), f"{source} no longer says {want[0]!r}"
        else:
            assert _is_subsequence(want, file_lines), f"the {source} excerpt no longer matches the file"


@pytest.mark.static
def test_runbook_rule_files_are_on_screen() -> None:
    """Every rule file RUNBOOK.md Act 2 step 3 puts on screen has an excerpt in the deck."""
    runbook = RUNBOOK.read_text(encoding="utf-8")
    step = runbook[runbook.index("**Put the rule that fired on screen.**") : runbook.index("4. Close the act")]
    named = set(re.findall(r"`([\w./-]+\.(?:co|yaml))`", step))
    cited = {source for source, _ in _deck().excerpts}
    assert named, "RUNBOOK.md Act 2 step 3 names no rule files"
    assert named <= cited, f"rules the runbook puts on screen with no slide: {sorted(named - cited)}"


@pytest.mark.static
def test_paths_on_slides_exist() -> None:
    """Every repo path printed on a slide exists."""
    paths = _deck().paths
    assert paths, "no repo paths on the slides"
    missing = [p for p in paths if not (PROJECT_ROOT / p).exists()]
    assert not missing, f"slides name paths that do not exist: {missing}"


@pytest.mark.static
def test_committed_pdf_is_the_export_of_the_current_source() -> None:
    """export.json matches slides.html and its assets, and the PDF it names: one 16:9 page per slide."""
    exporter = _load_exporter()
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert record["source_sha256"] == exporter.source_digest(), (
        "slides.html or an asset changed since the PDF was exported; run "
        "`uv run --managed-python --frozen python presentations/kubecon-na-2026/deck/export_pdf.py`"
    )
    pdf = (DECK / record["pdf"]).read_bytes()
    assert hashlib.sha256(pdf).hexdigest() == record["pdf_sha256"], "the PDF is not the one export.json records"
    width, height = record["page_size_pt"]
    assert width * 9 == height * 16, f"page size {width}x{height}pt is not 16:9"
    boxes = exporter.page_boxes(pdf)
    assert len(boxes) == len(_deck().slides) == record["pages"], (
        f"{len(boxes)} PDF pages, {len(_deck().slides)} slides, export.json says {record['pages']}"
    )
    assert set(boxes) == {(width, height)}, f"PDF pages are not all {width}x{height}pt: {set(boxes)}"


@pytest.mark.live
def test_every_slide_fits_its_page_in_chromium() -> None:
    """Rendered in Playwright's Chromium, nothing spills off a slide and no request path wraps."""
    exporter = _load_exporter()
    assert exporter.layout_problems() == []


@pytest.mark.live
def test_layout_check_catches_a_slide_that_spills(tmp_path) -> None:
    """Mutation: a request path too long for the slide is reported, so the layout check is not vacuous."""
    exporter = _load_exporter()
    html = SOURCE.read_text(encoding="utf-8")
    broken = html.replace('<div class="hop">frontend</div>', '<div class="hop">' + "frontend " * 12 + "</div>")
    assert broken != html, "could not lengthen a request path hop"
    copy = tmp_path / "slides.html"
    copy.write_text(broken, encoding="utf-8")
    problems = exporter.layout_problems(copy)
    assert any("overflows" in p or "wraps" in p for p in problems), problems
