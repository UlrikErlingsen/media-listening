"""Listen Signal Streamlit application (entry point). Pages live in pages/; analysis lives in src/listensignal/."""

from __future__ import annotations

import os

# Keep Arrow serialization stable on macOS. This must be set before Streamlit imports Arrow.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from listensignal import __version__
from listensignal.ui import signal_theme as sig
from pages._ui import NS, PERIODS, PUBLIC_DEMO, db_count, show_error, workspace

SIDEBAR_TAGLINE = "Norwegian media listening without the monitoring subscription."
MASTHEAD_PROMISES = ["Norwegian sources", "Local sentiment", "Visible rules"]
MASTHEAD_KICKER = "LISTEN → COMPARE → FLAG"
FOOTER_LINE = "counts what feeds published, not what people think"

st.set_page_config(**sig.page_config(NS, "Norwegian media listening"))
sig.apply(NS)

PAGES = [
    st.Page("pages/overview.py", title="Overview", icon=":material/insights:", default=True),
    st.Page("pages/what_changed.py", title="What changed", icon=":material/trending_up:"),
    st.Page("pages/brand.py", title="Brand profile", icon=":material/person_search:"),
    st.Page("pages/mentions.py", title="Mentions", icon=":material/article:"),
    st.Page("pages/topics.py", title="Topics", icon=":material/category:"),
    st.Page("pages/pulse.py", title="Weekly pulse", icon=":material/download:"),
    st.Page("pages/sources.py", title="Sources & brands", icon=":material/rss_feed:"),
    st.Page("pages/methods.py", title="Methods & limits", icon=":material/menu_book:"),
]

sig.sidebar_brand(NS, SIDEBAR_TAGLINE)
with st.sidebar:
    st.caption(f"Media & social listening · v{__version__}")

page = st.navigation(PAGES)

with st.sidebar:
    if PUBLIC_DEMO:
        st.caption("Public demo: fictional data only. Run Listen Signal locally to collect real feeds.")
    else:
        stored = db_count()
        modes = {"demo": "Fictional demo", "db": f"My collected data ({stored:,} items)"}
        st.radio("Data", list(modes), format_func=modes.get, key="data_mode")
    st.selectbox("Period", list(PERIODS), index=1, key="period")
    ws = workspace()
    st.caption(f"{len(ws.brands)} brands · {len(ws.articles):,} feed items · {len(ws.mentions):,} brand mentions")
    st.caption("Local mode · no telemetry · no accounts · no external AI calls · network only for your RSS feeds")

sig.masthead(NS, MASTHEAD_PROMISES, MASTHEAD_KICKER)
try:
    page.run()
except Exception as exc:  # friendly message; tracebacks only with LISTENSIGNAL_DEBUG=1
    show_error(exc)
sig.footer(NS, __version__, FOOTER_LINE)
