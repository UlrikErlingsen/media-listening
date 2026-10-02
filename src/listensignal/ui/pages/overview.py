"""Overview: volume over time, share of voice, sentiment mix, top sources."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from listensignal import daily_counts, detect_spikes, period_comparison, sentiment_mix, share_of_voice, top_sources
from listensignal.ui import signal_theme as sig
from listensignal.ui.common import (
    INK,
    MUTED,
    NS,
    SURFACE,
    data_banner,
    empty_state,
    k,
    scorer_caption,
    sentiment_bar,
    style,
    view,
)


def show() -> None:
    v = view()

    sig.hero(
        NS,
        eyebrow="NORWEGIAN MEDIA LISTENING",
        title="Who is talking about the brand —",
        em="and in what tone?",
        body="Mentions of your brand and competitors in Norwegian news feeds, with share of voice, local Norwegian "
        "sentiment (NorBERT3 or a transparent lexicon) and spikes flagged by a rule you can read.",
        pills=["Bokmål & Nynorsk matching", "exclusion terms", "share of voice", "sentence-level sentiment",
               "z-score spikes", "weekly pulse export"],
    )
    data_banner(v)
    if empty_state(v):
        return

    own = [b.name for b in v.ws.brands if b.role == "own"]
    focus = own[0] if own else v.brands[0]
    sov = share_of_voice(v.mentions, v.brands)
    daily = daily_counts(v.ws.mentions, v.brands, v.start - timedelta(days=28), v.end)
    spikes = detect_spikes(daily, coverage_start=v.ws.coverage_start)
    recent_spikes = spikes.loc[spikes["date"] > v.end - timedelta(days=7)]
    compare = period_comparison(v.ws.mentions, v.brands, v.start, v.end, v.ws.coverage_start).set_index("brand")
    row = compare.loc[focus]
    covered = row["mentions_before"] is not None and not pd.isna(row["mentions_before"])
    days = (v.end - v.start).days + 1
    total_before = compare["mentions_before"].sum() if covered else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Brand mentions", f"{len(v.mentions):,}",
              f"{len(v.mentions) - total_before:+,.0f}" if covered else None,
              help=f"An item naming two brands counts once for each. Delta: vs the {days} days before.")
    c2.metric(f"{focus} share of voice", f"{row['sov']:.0%}",
              f"{(row['sov'] - row['sov_before']) * 100:+.0f} pts" if covered else None)
    tone_now, tone_before = row["net_tone"], row["net_tone_before"]
    c3.metric(
        f"{focus} net tone",
        "—" if tone_now is None or pd.isna(tone_now) else f"{tone_now:+.2f}",
        f"{tone_now - tone_before:+.2f}" if covered and tone_now is not None and tone_before is not None
        and not pd.isna(tone_now) and not pd.isna(tone_before) else None,
        help="(positive − negative) / scored mentions, from −1 to +1. Headline tone, not tone towards the brand.",
    )
    if not covered:
        since = f" ({v.ws.coverage_start:%d.%m.%Y})" if v.ws.coverage_start else ""
        st.caption(f"No change shown: the {days} days before this period fall before the data starts{since}.")
    c4.metric("Spike days, last 7 days", f"{len(recent_spikes)}", help="See What changed for the rule and threshold.")

    st.markdown("### Mention volume")
    grain = st.radio("Granularity", ["Weekly", "Daily"], horizontal=True, label_visibility="collapsed",
                     key=k("overview_grain"))
    counts = daily.loc[(daily.index >= v.start)]
    if grain == "Weekly":
        index = pd.to_datetime(pd.Index(counts.index))
        counts = counts.set_axis(index).resample("W-SUN").sum()
        counts.index = counts.index.date
    fig = go.Figure()
    for brand in v.brands:
        fig.add_scatter(
            x=list(counts.index), y=counts[brand], name=brand, mode="lines+markers",
            line=dict(color=v.colors[brand], width=2), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
            hovertemplate=f"{brand}: %{{y}}<extra></extra>",
        )
    if grain == "Daily":
        marked = spikes.loc[spikes["date"] >= v.start]
        if not marked.empty:
            fig.add_scatter(
                x=list(marked["date"]), y=marked["count"], mode="markers", name="Spike day",
                marker=dict(symbol="diamond-open", size=15, color=INK, line=dict(width=2)),
                customdata=marked[["brand", "z"]], hovertemplate="Spike · %{customdata[0]}: %{y} (z = %{customdata[1]:.1f})<extra></extra>",
            )
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title="Mentions per " + ("week (ending Sunday)" if grain == "Weekly" else "day"), rangemode="tozero")
    sig.chart(NS, style(fig, 380), key=k("overview_volume"))

    left, right = st.columns(2)
    with left:
        st.markdown("### Share of voice")
        ordered = sov.iloc[::-1]
        bar = go.Figure(
            go.Bar(
                y=ordered["brand"], x=ordered["share"], orientation="h",
                marker=dict(color=[v.colors[b] for b in ordered["brand"]], cornerradius=4),
                text=[f"{s:.0%} · {n}" for s, n in zip(ordered["share"], ordered["mentions"])], textposition="outside",
                textfont=dict(color=MUTED), customdata=ordered["mentions"],
                hovertemplate="%{y}: %{x:.1%} (%{customdata} mentions)<extra></extra>",
            )
        )
        bar.update_xaxes(tickformat=".0%", range=[0, max(0.1, float(sov["share"].max()) * 1.3)], gridcolor="rgba(0,0,0,0)")
        bar.update_yaxes(gridcolor="rgba(0,0,0,0)")
        sig.chart(NS, style(bar, 90 + 46 * len(v.brands), legend=False), key=k("overview_share_of_voice"))
        st.caption("Share of all brand mentions in the period. Coverage is limited to your configured feeds.")
    with right:
        st.markdown("### Sentiment mix")
        mix = sentiment_mix(v.mentions, v.brands)
        sig.chart(NS, sentiment_bar(mix, v.brands), key=k("overview_sentiment"))
        st.caption(scorer_caption(v.mentions))

    st.markdown("### Top sources")
    sources = top_sources(v.mentions, 10)
    by_source = v.mentions.groupby(["source", "brand"]).size().unstack("brand", fill_value=0).reindex(
        index=sources["source"], columns=v.brands, fill_value=0
    )
    src = go.Figure()
    for brand in v.brands:
        src.add_bar(
            y=by_source.index, x=by_source[brand], name=brand, orientation="h",
            marker=dict(color=v.colors[brand], line=dict(color=SURFACE, width=2)),
            hovertemplate="%{y} · " + brand + ": %{x}<extra></extra>",
        )
    src.update_layout(barmode="stack")
    src.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    src.update_xaxes(title="Brand mentions", title_font_color=MUTED)
    sig.chart(NS, style(src, 110 + 34 * len(sources)), key=k("overview_sources"))

    with st.expander("Table view"):
        st.dataframe(sov, hide_index=True, column_config={"share": st.column_config.NumberColumn("share of voice", format="percent")})
        st.dataframe(mix.pivot(index="brand", columns="sentiment", values="mentions").reindex(v.brands))
        st.dataframe(counts.rename_axis("period"))
        st.dataframe(sources, hide_index=True)
