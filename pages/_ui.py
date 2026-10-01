"""Shared Streamlit helpers for Listen Signal pages. All analysis lives in the listensignal package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import os
from pathlib import Path
import traceback

import pandas as pd
import plotly.graph_objects as go
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

NS = "listen"  # signal_theme key: Listen Signal, Market family
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
# Hosted demo: only the fictional data, no database and no outbound feed requests.
PUBLIC_DEMO = os.getenv("LISTENSIGNAL_PUBLIC_DEMO") == "1"


@st.cache_data(show_spinner="Building the fictional demo …")
def _demo() -> Workspace:
    return demo_workspace()


@st.cache_data(show_spinner="Reading the local database …")
def _database(db_path: str, brands_path: str, db_mtime: float, brands_mtime: float) -> Workspace:
    return database_workspace(db_path, brands_path)


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def db_count() -> int:
    return database_has_items(DEFAULT_DB)


@st.cache_data(show_spinner="Matching your brands …", max_entries=8)
def _custom(mode: str, base_mtime: float, _base: Workspace, brands_yaml: str) -> Workspace:
    return _base.with_brands(parse_brands_yaml(brands_yaml))


def base_workspace() -> Workspace:
    if st.session_state.get("data_mode", "demo") == "db":
        return _database(str(DEFAULT_DB), str(DEFAULT_BRANDS), _mtime(DEFAULT_DB), _mtime(DEFAULT_BRANDS))
    return _demo()


def custom_brands_key() -> str:
    return f"custom_brands_{st.session_state.get('data_mode', 'demo')}"


def workspace() -> Workspace:
    """The selected data, re-matched with this session's custom brand list if the visitor set one."""
    if PUBLIC_DEMO:
        st.session_state["data_mode"] = "demo"
    base = base_workspace()
    custom = st.session_state.get(custom_brands_key())
    if not custom:
        return base
    mode = st.session_state.get("data_mode", "demo")
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
    days = PERIODS.get(st.session_state.get("period", "Last 12 weeks"))
    if days is None:
        start = min(mentions["date"]) if not mentions.empty else end - timedelta(days=27)
    else:
        start = end - timedelta(days=days - 1)
    scoped = mentions.loc[(mentions["date"] >= start) & (mentions["date"] <= end)] if not mentions.empty else mentions
    return View(ws, scoped, start, end, ws.brand_names, brand_colors(ws.brand_names))


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
    """Chart layout on top of Listen Signal's Plotly template (Figtree, Market-family colorway)."""
    fig.update_layout(
        template=sig.template(NS),
        height=height,
        margin=dict(l=8, r=8, t=52 if legend else 12, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0, title=None, traceorder="normal")
        if legend
        else None,
        showlegend=legend,
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, ticks="", tickfont_color=MUTED, title_font_color=MUTED)
    fig.update_yaxes(zeroline=False, ticks="", tickfont_color=MUTED, title_font_color=MUTED)
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
