"""Capture README screenshots of the running app (fictional demo) into assets/.

    python -m streamlit run app.py --server.port=8595 &
    python -m pip install playwright      # dev-only; uses the installed Chrome, no browser download
    python scripts/capture_screenshots.py [--url http://localhost:8595]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
# name -> (path, text to scroll into view first or None)
PAGES = {
    "overview": ("", None),
    "overview-charts": ("", "Mention volume"),
    "what-changed": ("what_changed", None),
    "spikes": ("what_changed", "Spike detection"),
    "brand": ("brand", "Mentions per week"),
    "topics": ("topics", None),
    "pulse": ("pulse", "Preview"),
    "sources": ("sources", "Test the matcher"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8595")
    parser.add_argument("--channel", default="chrome", help="installed browser channel: chrome or msedge")
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        for name, (path, anchor) in PAGES.items():
            page.goto(f"{args.url}/{path}", wait_until="networkidle")
            page.wait_for_selector(".ps-footer", timeout=60_000)
            page.wait_for_timeout(2500)  # let Plotly finish drawing
            if anchor:
                page.get_by_text(anchor, exact=True).first.evaluate("el => el.scrollIntoView({block: 'start'})")
                page.wait_for_timeout(1200)
            page.add_style_tag(content="[data-testid='stToolbar'],[data-testid='stDecoration']{display:none!important}")
            target = ROOT / "assets" / f"screenshot-{name}.png"
            page.screenshot(path=str(target), full_page=False)
            print("wrote", target.relative_to(ROOT))
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
