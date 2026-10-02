"""Shared Streamlit helpers for Listen Signal pages. All analysis lives in the UI-free listensignal package.

Every session-state key and every explicit widget key goes through ``k()``, so Listen Signal can share one
Streamlit session with the other apps in Signal Hub.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import os
from pathlib import Path
import traceback

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from listensignal import (
    DataProblem,
    Workspace,
    database_has_items,
    database_workspace,
    demo_workspace,
    friendly_message,
    parse_brands_yaml,
)
from listensignal.analysis import SENTIMENT_ORDER
from listensignal.config import DEFAULT_BRANDS, DEFAULT_DB
from listensignal.ui import signal_theme as sig

NS = "listen"  # signal_theme key and Signal Hub slug: Listen Signal, Market family


def k(name: str) -> str:
    """Namespace a session-state or widget key with the app slug, so apps can share one Hub session."""
    return f"{NS}:{name}"


# Categorical brand colours from the Signal colorway (own family first). Colour follows the brand's position in
# brands.yaml, never its rank, so filtering never repaints a brand; brands beyond the palette share the neutral.
BRAND_PALETTE = tuple(sig.colorway(NS)[:-1])
OTHER_COLOR = sig.CORE["muted"]
# Diverging: Decide blue (positive) <-> Brand clay (negative) with a neutral midpoint; Mixed is a separate
# non-polar hue (Research family).
SENTIMENT_COLORS = {"Positive": sig.DIVERGING[1], "Neutral": sig.CORE["soft"], "Mixed": sig.FAMILIES["research"]["600"],
                    "Negative": sig.DIVERGING[5], "Unscored": sig.CORE["surface"]}
INK, MUTED, BAND, SURFACE = sig.CORE["text"], sig.CORE["muted"], sig.CORE["soft"], sig.CORE["paper"]
PERIODS = {"Last 4 weeks": 28, "Last 12 weeks": 84, "All data": None}
HUB_NOTE = "Live feed collection is off in Signal Hub; run Listen Signal locally to collect real feeds."
PUBLIC_DEMO_NOTE = "Public demo: fictional data only. Run Listen Signal locally to collect real feeds."


def hub_mode() -> bool:
    """Running inside Signal Hub: fictional demo only, no files, no database, no outbound requests."""
    return os.environ.get("SIGNAL_HUB") == "1"


def public_demo() -> bool:
    """Hosted demo (LISTENSIGNAL_PUBLIC_DEMO=1): only the fictional data, no database and no feed requests."""
    return os.getenv("LISTENSIGNAL_PUBLIC_DEMO") == "1"


def demo_only() -> bool:
    """True when the local database, the project files and live collection must stay untouched."""
    return hub_mode() or public_demo()


def demo_only_note() -> str:
    return HUB_NOTE if hub_mode() else PUBLIC_DEMO_NOTE


@st.cache_data(show_spinner="Building the fictional demo …")
def _demo() -> Workspace:
    return demo_workspace()  # generated in memory from code; reads and writes nothing


@st.cache_data(show_spinner="Reading the local database …")
def _database(db_path: str, brands_path: str, db_mtime: float, brands_mtime: float) -> Workspace:
    return database_workspace(db_path, brands_path)


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def db_count() -> int:
    return 0 if demo_only() else database_has_items(DEFAULT_DB)


@st.cache_data(show_spinner="Matching your brands …", max_entries=8)
def _custom(mode: str, base_mtime: float, _base: Workspace, brands_yaml: str) -> Workspace:
    return _base.with_brands(parse_brands_yaml(brands_yaml))


def data_mode() -> str:
    if demo_only():
        return "demo"
    return st.session_state.get(k("data_mode"), "demo")


def base_workspace() -> Workspace:
    if data_mode() == "db":
        return _database(str(DEFAULT_DB), str(DEFAULT_BRANDS), _mtime(DEFAULT_DB), _mtime(DEFAULT_BRANDS))
    return _demo()


def custom_brands_key() -> str:
    return k(f"custom_brands_{data_mode()}")


def workspace() -> Workspace:
    """The selected data, re-matched with this session's custom brand list if the visitor set one."""
    base = base_workspace()
    custom = st.session_state.get(custom_brands_key())
    if not custom:
        return base
    mode = data_mode()
    return _custom(mode, _mtime(DEFAULT_DB) if mode == "db" else 0.0, base, custom)


def clear_caches() -> None:
    _database.clear()


@dataclass(frozen=True)
class View:
    ws: Workspace
    mentions: pd.DataFrame  # filtered to the selected period
    start: date
    end: date
    brands: list[str]
    colors: dict[str, str]


def brand_colors(names: list[str]) -> dict[str, str]:
    return {name: BRAND_PALETTE[i] if i < len(BRAND_PALETTE) else OTHER_COLOR for i, name in enumerate(names)}


def view() -> View:
    ws = workspace()
    mentions = ws.mentions
    if mentions.empty:
        end = date.today()
    else:
        end = max(mentions["date"])
    days = PERIODS.get(st.session_state.get(k("period"), "Last 12 weeks"))
    if days is None:
        start = min(mentions["date"]) if not mentions.empty else end - timedelta(days=27)
    else:
        start = end - timedelta(days=days - 1)
    scoped = mentions.loc[(mentions["date"] >= start) & (mentions["date"] <= end)] if not mentions.empty else mentions
    return View(ws, scoped, start, end, ws.brand_names, brand_colors(ws.brand_names))


def sidebar_data_controls() -> None:
    """Data source and period pickers plus the workspace summary, drawn in the sidebar on every rerun."""
    with st.sidebar:
        if demo_only():
            st.caption(("Signal Hub: fictional demo only. " if hub_mode() else "") + demo_only_note())
        else:
            stored = db_count()
            modes = {"demo": "Fictional demo", "db": f"My collected data ({stored:,} items)"}
            st.radio("Data", list(modes), format_func=modes.get, key=k("data_mode"))
        st.selectbox("Period", list(PERIODS), index=1, key=k("period"))
        ws = workspace()
        st.caption(f"{len(ws.brands)} brands · {len(ws.articles):,} feed items · {len(ws.mentions):,} brand mentions")
        if hub_mode():
            st.caption("Signal Hub · in memory only · no telemetry · no accounts · no external AI calls · no network")
        else:
            st.caption("Local mode · no telemetry · no accounts · no external AI calls · network only for your RSS feeds")


def data_banner(v: View) -> None:
    if v.ws.is_demo:
        sig.note("warn", f"**Fictional demo.** {v.ws.notice}")
    if st.session_state.get(custom_brands_key()):
        st.caption("Custom brand list active for this session (Sources & brands → Edit brands).")
    st.caption(f"{v.ws.label} · {v.start:%d.%m.%Y} – {v.end:%d.%m.%Y} · {len(v.mentions):,} brand mentions")


def empty_state(v: View) -> bool:
    if not v.mentions.empty:
        return False
    if v.ws.is_demo:
        st.info("No demo mentions in this period.")
    elif v.ws.articles.empty:
        st.info(
            "The local database is empty. Run `python -m listensignal.collect` (or use **Sources & brands → Collect "
            "now**), or switch back to the fictional demo in the sidebar."
        )
    else:
        st.info(
            f"{len(v.ws.articles):,} feed items are stored, but none mention a brand in brands.yaml in this period. "
            "Check aliases on **Sources & brands**, or widen the period."
        )
    return True


def style(fig: go.Figure, height: int = 360, *, legend: bool = True) -> go.Figure:
    """Chart layout on top of Listen Signal's Plotly template (Figtree, Market-family colorway).

    Streamlit's front end fills in its own font and background colours for any layout key a figure leaves unset,
    even with theme=None, so the template's font and transparent backgrounds are copied onto the figure itself.
    Axis automargin keeps tick labels inside the small margins.
    """
    base = pio.templates[sig.template(NS)].layout
    fig.update_layout(
        template=sig.template(NS),
        font=base.font,
        paper_bgcolor=base.paper_bgcolor,
        plot_bgcolor=base.plot_bgcolor,
        hoverlabel=base.hoverlabel,
        height=height,
        margin=dict(l=8, r=8, t=52 if legend else 12, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0, title=None, traceorder="normal")
        if legend
        else None,
        showlegend=legend,
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, ticks="", automargin=True, tickfont_color=MUTED, title_font_color=MUTED)
    fig.update_yaxes(zeroline=False, ticks="", automargin=True, tickfont_color=MUTED, title_font_color=MUTED)
    return fig


def sentiment_bar(mix: pd.DataFrame, brands: list[str], height: int | None = None) -> go.Figure:
    """100 % stacked horizontal bars: share of each sentiment label per brand."""
    fig = go.Figure()
    labels = [label for label in SENTIMENT_ORDER + ["Unscored"] if label in set(mix["sentiment"])]
    for label in labels:
        part = mix.loc[mix["sentiment"] == label].set_index("brand").reindex(brands)
        fig.add_bar(
            y=brands, x=part["share"], name=label, orientation="h",
            marker=dict(color=SENTIMENT_COLORS[label], line=dict(color=SURFACE, width=2)),
            customdata=part["mentions"],
            hovertemplate="%{y}<br>" + label + ": %{x:.0%} (%{customdata} mentions)<extra></extra>",
        )
    fig.update_layout(barmode="stack")
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    return style(fig, height or 120 + 46 * len(brands))


def show_error(exc: Exception) -> None:
    st.error(friendly_message(exc))
    if not isinstance(exc, (DataProblem, ValueError)) and os.getenv("LISTENSIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def item_texts(frame: pd.DataFrame) -> list[str]:
    """Headline + snippet once per feed item (an item naming two brands appears twice in the mention table)."""
    unique = frame.drop_duplicates("article_id")
    return (unique["title"].fillna("") + ". " + unique["summary"].fillna("")).tolist()


SENTIMENT_NOTE = (
    "Sentiment is an indicator, not a verdict: it labels the tone of the headline and snippet, not the tone "
    "towards the brand, and Listen Signal has not measured its accuracy on news headlines. "
)


def scorer_caption(mentions: pd.DataFrame) -> str:
    scorers = mentions["sentiment_scorer"].dropna().astype(str).value_counts()
    if scorers.empty:
        return SENTIMENT_NOTE + "No item in this view has been scored yet."
    used = " · ".join(f"{name}: {count:,}" for name, count in scorers.items())
    return SENTIMENT_NOTE + f"Scorer per mention — {used}."
