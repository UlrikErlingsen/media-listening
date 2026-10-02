"""Listen Signal Streamlit shell: page registry, sidebar, masthead and footer.

Everything that draws the app runs inside ``render()`` (or the functions it calls), so it runs on every rerun, both
in the standalone ``app.py`` and inside Signal Hub. Module-level code here only defines constants and functions.
``render()`` never calls ``st.set_page_config`` or ``st.navigation``: Signal Hub owns both, so pages are picked with
a namespaced sidebar radio. The standalone ``app.py`` keeps its ``st.navigation`` layout over the same page
functions (``PAGES``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import streamlit as st

from listensignal import __version__
from listensignal.ui import signal_theme as sig
from listensignal.ui.common import NS, k, show_error, sidebar_data_controls
from listensignal.ui.pages import brand, mentions, methods, overview, pulse, sources, topics, what_changed

SIDEBAR_TAGLINE = "Norwegian media listening without the monitoring subscription."
MASTHEAD_PROMISES = ["Norwegian sources", "Local sentiment", "Visible rules"]
MASTHEAD_KICKER = "LISTEN → COMPARE → FLAG"
FOOTER_LINE = "counts what feeds published, not what people think"


@dataclass(frozen=True)
class Page:
    slug: str  # also the standalone page file: pages/<slug>.py
    title: str
    icon: str
    show: Callable[[], None]


PAGES: tuple[Page, ...] = (
    Page("overview", "Overview", ":material/insights:", overview.show),
    Page("what_changed", "What changed", ":material/trending_up:", what_changed.show),
    Page("brand", "Brand profile", ":material/person_search:", brand.show),
    Page("mentions", "Mentions", ":material/article:", mentions.show),
    Page("topics", "Topics", ":material/category:", topics.show),
    Page("pulse", "Weekly pulse", ":material/download:", pulse.show),
    Page("sources", "Sources & brands", ":material/rss_feed:", sources.show),
    Page("methods", "Methods & limits", ":material/menu_book:", methods.show),
)
_BY_SLUG = {page.slug: page for page in PAGES}


def sidebar_header() -> None:
    sig.sidebar_brand(NS, SIDEBAR_TAGLINE)
    with st.sidebar:
        st.caption(f"Media & social listening · v{__version__}")


def run_page(show: Callable[[], None]) -> None:
    """Run one page; errors become the friendly message (tracebacks only with LISTENSIGNAL_DEBUG=1)."""
    try:
        show()
    except Exception as exc:
        show_error(exc)


def masthead() -> None:
    sig.masthead(NS, MASTHEAD_PROMISES, MASTHEAD_KICKER)


def footer() -> None:
    sig.footer(NS, __version__, FOOTER_LINE)


def render() -> None:
    """Draw the whole Listen Signal app on the current page. Never calls st.set_page_config or st.navigation."""
    sig.apply(NS)
    sidebar_header()
    with st.sidebar:
        slug = st.radio("Page", [page.slug for page in PAGES], format_func=lambda s: _BY_SLUG[s].title, key=k("page"))
    sidebar_data_controls()
    masthead()
    run_page(_BY_SLUG[slug].show)
    footer()
