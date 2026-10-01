"""Brand profile: one brand's volume, tone over time, distinctive terms, sources and recent mentions."""

from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from listensignal import period_comparison, rising_terms, top_sources, weekly_tone
from listensignal.analysis import SENTIMENT_ORDER, TIMEZONE
from listensignal.ui import signal_theme as sig
from pages._ui import (
    MUTED,
    NS,
    SENTIMENT_COLORS,
    SURFACE,
    data_banner,
    empty_state,
    scorer_caption,
    style,
    view,
)

sig.header(
    "Brand profile",
    "One brand, up close",
    "Volume and tone week by week, the words that set this brand's coverage apart from its competitors', where it "
    "is covered, and the latest positive and negative items to read.",
)
v = view()
data_banner(v)
if empty_state(v):
    st.stop()

own = [b.name for b in v.ws.brands if b.role == "own"]
brand = st.selectbox("Brand", v.brands, index=v.brands.index(own[0]) if own else 0)
mine = v.mentions.loc[v.mentions["brand"] == brand]
others = v.mentions.loc[v.mentions["brand"] != brand]

compare = period_comparison(v.ws.mentions, v.brands, v.start, v.end, v.ws.coverage_start).set_index("brand").loc[brand]
days = (v.end - v.start).days + 1


def _delta(now, before, fmt):
    if before is None or pd.isna(before) or now is None or pd.isna(now):
        return None
    return fmt(now - before)


c1, c2, c3, c4 = st.columns(4)
c1.metric("Mentions", f"{int(compare['mentions']):,}",
          _delta(compare["mentions"], compare["mentions_before"], lambda d: f"{d:+,.0f}"),
          help=f"Compared with the {days} days before the selected period.")
c2.metric("Share of voice", f"{compare['sov']:.0%}",
          _delta(compare["sov"], compare["sov_before"], lambda d: f"{d * 100:+.0f} pts"))
tone_now = compare["net_tone"]
c3.metric("Net tone", "—" if tone_now is None or pd.isna(tone_now) else f"{tone_now:+.2f}",
          _delta(tone_now, compare["net_tone_before"], lambda d: f"{d:+.2f}"),
          help="(positive − negative) / scored mentions. Headline tone, not tone towards the brand.")
negative = float((mine["sentiment"] == "Negative").mean()) if len(mine) else None
c4.metric("Negative share", "—" if negative is None else f"{negative:.0%}")
if compare["mentions_before"] is None or pd.isna(compare["mentions_before"]):
    since = f" ({v.ws.coverage_start:%d.%m.%Y})" if v.ws.coverage_start else ""
    st.caption(f"No change shown: the {days} days before this period fall before the data starts{since}.")

weeks = weekly_tone(v.ws.mentions, [brand], v.start, v.end)
labels = [f"{w:%d.%m}" for w in weeks["week"]]
left, right = st.columns(2)
with left:
    st.markdown("#### Mentions per week")
    fig = go.Figure(go.Bar(x=labels, y=weeks["mentions"], marker=dict(color=v.colors[brand], cornerradius=4),
                           hovertemplate="Week of %{x}: %{y} mentions<extra></extra>"))
    fig.update_xaxes(title="Week starting (Monday)", type="category")
    fig.update_yaxes(rangemode="tozero")
    sig.chart(NS, style(fig, 320, legend=False), key="listen:brand_weekly_mentions")
with right:
    st.markdown("#### Tone per week")
    tone = go.Figure()
    totals = weeks["mentions"].replace(0, pd.NA)
    for label in SENTIMENT_ORDER:
        share = (weeks[label] / totals).astype(float)
        tone.add_bar(x=labels, y=share, name=label, customdata=weeks[label],
                     marker=dict(color=SENTIMENT_COLORS[label], line=dict(color=SURFACE, width=2)),
                     hovertemplate="Week of %{x} · " + label + ": %{y:.0%} (%{customdata})<extra></extra>")
    tone.update_layout(barmode="stack")
    tone.update_yaxes(tickformat=".0%", range=[0, 1])
    tone.update_xaxes(title="Week starting (Monday)", type="category")
    sig.chart(NS, style(tone, 320), key="listen:brand_weekly_tone")
st.caption(scorer_caption(mine))

left, right = st.columns(2)
with left:
    st.markdown(f"#### What sets {brand} apart")
    texts = lambda frame: (frame.drop_duplicates("article_id")["title"].fillna("") + ". "  # noqa: E731
                           + frame.drop_duplicates("article_id")["summary"].fillna("")).tolist()
    aliases = tuple(alias for b in v.ws.brands for alias in b.aliases)
    distinct = rising_terms(texts(mine), texts(others), remove_terms=aliases, top_n=12)
    if distinct.empty:
        st.caption("Too few mentions to compare vocabulary.")
    else:
        st.dataframe(
            distinct.rename(columns={"this_week": f"items about {brand}", "prev_week": "items about others"}),
            hide_index=True, width="stretch",
            column_config={"log_ratio": st.column_config.NumberColumn("log ratio", format="%.2f")},
        )
        st.caption("Terms (brand names removed) found in a larger share of this brand's items than competitors'.")
with right:
    st.markdown("#### Where it is covered")
    sources = top_sources(mine, 8)
    bar = go.Figure(go.Bar(y=sources["source"][::-1], x=sources["mentions"][::-1], orientation="h",
                           marker=dict(color=v.colors[brand], cornerradius=4), text=sources["mentions"][::-1],
                           textposition="outside", textfont=dict(color=MUTED),
                           hovertemplate="%{y}: %{x} mentions<extra></extra>"))
    bar.update_yaxes(gridcolor="rgba(0,0,0,0)")
    sig.chart(NS, style(bar, 90 + 34 * len(sources), legend=False), key="listen:brand_sources")


def _latest(label: str) -> None:
    rows = mine.loc[mine["sentiment"] == label].head(6)
    if rows.empty:
        st.caption(f"No {label.lower()} items in this period.")
        return
    items = []
    for row in rows.itertuples():
        when = pd.Timestamp(row.published).tz_convert(TIMEZONE)
        url = str(row.url) if str(row.url).startswith(("https://", "http://")) else "#"
        items.append(  # feed text is untrusted: escape everything
            f'<li><a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(str(row.title))}</a>'
            f' <span style="color:var(--sg-muted);font-size:.86rem">· {escape(str(row.source))} · '
            f"{when:%d.%m %H:%M}</span></li>"
        )
    st.markdown(f'<ul style="padding-left:1.1rem;margin:.2rem 0 0;line-height:1.6">{"".join(items)}</ul>',
                unsafe_allow_html=True)


left, right = st.columns(2)
with left:
    st.markdown("#### Latest negative items")
    _latest("Negative")
with right:
    st.markdown("#### Latest positive items")
    _latest("Positive")
