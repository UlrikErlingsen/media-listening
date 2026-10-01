"""Shared Streamlit helpers for ListenSignal pages. All analysis lives in the listensignal package."""

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
)
from listensignal.analysis import SENTIMENT_ORDER
from listensignal.config import DEFAULT_BRANDS, DEFAULT_DB

# Validated categorical order (passes adjacent CVD and normal-vision checks); colour follows the brand's
# position in brands.yaml, never its rank, so filtering never repaints a brand.
BRAND_PALETTE = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
OTHER_COLOR = "#898781"
# Diverging: blue (positive) <-> red (negative) with a gray midpoint; Mixed is a separate non-polar hue.
SENTIMENT_COLORS = {"Positive": "#2a78d6", "Neutral": "#c3c2b7", "Mixed": "#eda100", "Negative": "#e34948",
                    "Unscored": "#e1e0d9"}
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#17322e", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
PERIODS = {"Last 4 weeks": 28, "Last 12 weeks": 84, "All data": None}


@st.cache_data(show_spinner="Building the fictional demo …")
def _demo() -> Workspace:
    return demo_workspace()


@st.cache_data(show_spinner="Reading the local database …")
def _database(db_path: str, brands_path: str, _db_mtime: float, _brands_mtime: float) -> Workspace:
    return database_workspace(db_path, brands_path)


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def db_count() -> int:
    return database_has_items(DEFAULT_DB)


def workspace() -> Workspace:
    if st.session_state.get("data_mode", "demo") == "db":
        return _database(str(DEFAULT_DB), str(DEFAULT_BRANDS), _mtime(DEFAULT_DB), _mtime(DEFAULT_BRANDS))
    return _demo()


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


def header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(f'<div class="pulse-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pulse-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pulse-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def data_banner(v: View) -> None:
    if v.ws.is_demo:
        st.markdown(f'<div class="warning-box"><strong>Fictional demo.</strong> {v.ws.notice}</div>', unsafe_allow_html=True)
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
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=52 if legend else 12, b=8),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', color=INK_2, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0, title=None, traceorder="normal")
        if legend
        else None,
        showlegend=legend,
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=GRID),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickfont_color=MUTED, ticks="", title_font_color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=AXIS, tickfont_color=MUTED, title_font_color=MUTED)
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
    "towards the brand, and ListenSignal has not measured its accuracy on news headlines. "
)


def scorer_caption(mentions: pd.DataFrame) -> str:
    scorers = mentions["sentiment_scorer"].dropna().astype(str).value_counts()
    if scorers.empty:
        return SENTIMENT_NOTE + "No item in this view has been scored yet."
    used = " · ".join(f"{name}: {count:,}" for name, count in scorers.items())
    return SENTIMENT_NOTE + f"Scorer per mention — {used}."
