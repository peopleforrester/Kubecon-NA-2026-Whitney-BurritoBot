# ABOUTME: Renders slides.html to the 16:9 Sessionize PDF with Playwright's Chromium, one 1920x1080 page per slide.
# ABOUTME: Writes export.json with the source and PDF sha256 so the static suite can tell a stale PDF from a fresh one.

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


DECK_DIR = Path(__file__).resolve().parent
REPO_ROOT = DECK_DIR.parents[2]
SOURCE = DECK_DIR / "slides.html"
PDF_NAME = "burritobot-said-lets-dance.pdf"
RECORD_NAME = "export.json"
WIDTH_PX = 1920
HEIGHT_PX = 1080
# Chromium writes page sizes in PDF points: 1px = 0.75pt.
WIDTH_PT = WIDTH_PX * 3 // 4
HEIGHT_PT = HEIGHT_PX * 3 // 4

ASSET_URL = re.compile(r"""url\(["']?([^"')]+)["']?\)|<img[^>]+src=["']([^"']+)["']""")


def asset_paths(html: str) -> list[Path]:
    """Every local file the slide source pulls in, resolved from the deck folder."""
    paths: set[Path] = set()
    for match in ASSET_URL.finditer(html):
        ref = match.group(1) or match.group(2)
        if ref.startswith(("http:", "https:", "data:")):
            raise SystemExit(f"slides.html loads a remote asset ({ref}); the deck must render offline")
        paths.add((DECK_DIR / ref).resolve())
    return sorted(paths)


def source_digest(html_path: Path = SOURCE) -> str:
    """sha256 over slides.html and every asset it references, in a stable order."""
    html = html_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(html.encode("utf-8"))
    for path in asset_paths(html):
        if not path.is_file():
            raise SystemExit(f"slides.html references {path}, which does not exist")
        digest.update(path.relative_to(REPO_ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def page_boxes(pdf: bytes) -> list[tuple[float, float]]:
    """The MediaBox width and height of every page Chromium wrote."""
    boxes = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
    return [(float(w), float(h)) for w, h in boxes]


LAYOUT_PROBLEMS_JS = """
() => {
  const problems = [];
  document.querySelectorAll('section.slide').forEach((slide, i) => {
    const box = slide.getBoundingClientRect();
    slide.querySelectorAll('*').forEach((el) => {
      if (el.closest('.notes')) return;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return;
      if (r.right > box.right + 1 || r.bottom > box.bottom + 1 || el.scrollWidth > el.clientWidth + 1) {
        problems.push(`slide ${i + 1}: <${el.tagName.toLowerCase()} class="${el.className}"> overflows`);
      }
    });
    slide.querySelectorAll('.path-row').forEach((row) => {
      const tops = new Set([...row.querySelectorAll('.hop')].map((h) => Math.round(h.getBoundingClientRect().top)));
      if (tops.size > 1) problems.push(`slide ${i + 1}: a request path wraps onto ${tops.size} lines`);
    });
  });
  return problems;
}
"""


def open_slides(pw, source: Path):
    """A Chromium page with the slide source loaded at slide size and its fonts ready."""
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": WIDTH_PX, "height": HEIGHT_PX})
    page.goto(source.as_uri(), wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    return browser, page


def layout_problems(source: Path = SOURCE) -> list[str]:
    """Every element that spills out of its slide, and every request path that wraps."""
    with sync_playwright() as pw:
        browser, page = open_slides(pw, source)
        problems = page.evaluate(LAYOUT_PROBLEMS_JS)
        browser.close()
    return problems


def export(out_dir: Path) -> dict:
    html = SOURCE.read_text(encoding="utf-8")
    slide_count = len(re.findall(r'<section class="slide\b', html))
    pdf_path = out_dir / PDF_NAME
    problems = layout_problems()
    if problems:
        raise SystemExit("slides.html does not fit 1920x1080:\n  " + "\n  ".join(problems))
    with sync_playwright() as pw:
        browser, page = open_slides(pw, SOURCE)
        page.pdf(
            path=str(pdf_path),
            width=f"{WIDTH_PX}px",
            height=f"{HEIGHT_PX}px",
            print_background=True,
            prefer_css_page_size=True,
        )
        browser.close()
    pdf = pdf_path.read_bytes()
    boxes = page_boxes(pdf)
    if len(boxes) != slide_count:
        raise SystemExit(f"{PDF_NAME} has {len(boxes)} pages for {slide_count} slides: a slide overflowed")
    wrong = [i + 1 for i, box in enumerate(boxes) if box != (WIDTH_PT, HEIGHT_PT)]
    if wrong:
        raise SystemExit(f"pages {wrong} are not {WIDTH_PT}x{HEIGHT_PT}pt")
    record = {
        "source": "slides.html",
        "source_sha256": source_digest(),
        "pdf": PDF_NAME,
        "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        "pages": len(boxes),
        "page_size_pt": [WIDTH_PT, HEIGHT_PT],
    }
    (out_dir / RECORD_NAME).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DECK_DIR, help="folder for the PDF and export.json")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    record = export(args.out)
    print(f"{args.out / PDF_NAME}: {record['pages']} pages, sha256 {record['pdf_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
