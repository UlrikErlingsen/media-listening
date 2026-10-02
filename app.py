"""Listen Signal standalone entry point.

Keeps the multipage ``st.navigation`` layout (one URL per page) over the page functions in
``listensignal.ui.pages``. Signal Hub calls ``listensignal.ui.render()`` instead, which draws the same pages behind a
namespaced sidebar radio.
"""

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

from listensignal.ui import signal_theme as sig
from listensignal.ui.app import PAGES, footer, masthead, sidebar_header
from listensignal.ui.common import NS, show_error, sidebar_data_controls

st.set_page_config(**sig.page_config(NS, "Norwegian media listening"))
sig.apply(NS)

sidebar_header()
page = st.navigation(
    [
        st.Page(f"pages/{p.slug}.py", title=p.title, icon=p.icon, default=index == 0)
        for index, p in enumerate(PAGES)
    ]
)
sidebar_data_controls()
masthead()
try:
    page.run()
except Exception as exc:  # friendly message; tracebacks only with LISTENSIGNAL_DEBUG=1
    show_error(exc)
footer()
