"""What changed vs last week: week-over-week table, plain-language notes, z-score spikes with the threshold shown."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from listensignal import SpikeRule, WeekWindow, change_headlines, daily_counts, rising_terms, spike_scores, weekly_change
from listensignal.analysis import coverage_note
from listensignal.analysis import SPIKE_MIN_COUNT, SPIKE_THRESHOLD
from listensignal.ui import signal_theme as sig
from pages._ui import BAND, INK, MUTED, NS, SURFACE, data_banner, empty_state, style, view

sig.header(
    "What changed",
    "This week vs last week",
    "The last seven days against the seven before, per brand — with spikes flagged by a simple z-score rule on "
    "daily mention counts. The rule and its threshold are shown so you can judge each flag yourself.",
)
v = view()
data_banner(v)
if empty_state(v):
    st.stop()

all_dates = sorted(set(v.ws.mentions["date"]))
c1, c2, c3 = st.columns([1.2, 1, 1])
end = c1.date_input("Week ending", value=v.end, min_value=all_dates[0], max_value=all_dates[-1])
threshold = c2.slider("z-score threshold", 2.0, 5.0, SPIKE_THRESHOLD, 0.5)
min_count = c3.slider("Minimum mentions on the day", 1, 15, SPIKE_MIN_COUNT)
rule = SpikeRule(threshold=threshold, min_count=min_count)
window = WeekWindow.ending(end)

change = weekly_change(v.ws.mentions, v.brands, window, rule, v.ws.coverage_start)
st.markdown(f"#### {window.label()}")
note = coverage_note(window, v.ws.coverage_start)
if note:
    sig.note("warn", note)
notes = change_headlines(change, rule)
if notes:
    for note in notes:
        sig.note("info", note)  # sig.note escapes the text (brand names are user input) and renders **bold**
else:
    sig.note("boundary", "No brand crossed the reporting rules this week.")
st.caption(
    "Notes appear for spikes, volume changes of at least 50 % and 5 mentions, and rises of at least 15 percentage "
    "points in the negative share (with at least 5 mentions)."
)

st.dataframe(
    change,
    hide_index=True,
    width="stretch",
    column_config={
        "mentions_this_week": st.column_config.NumberColumn("this week"),
        "mentions_prev_week": st.column_config.NumberColumn("prev. week"),
        "change_pct": st.column_config.NumberColumn("change", format="percent"),
        "sov_this_week": st.column_config.NumberColumn("SoV now", format="percent"),
        "sov_prev_week": st.column_config.NumberColumn("SoV before", format="percent"),
        "negative_share_this_week": st.column_config.NumberColumn("neg. now", format="percent"),
        "negative_share_prev_week": st.column_config.NumberColumn("neg. before", format="percent"),
        "net_tone_this_week": st.column_config.NumberColumn("net tone now", format="%+.2f"),
        "net_tone_prev_week": st.column_config.NumberColumn("net tone before", format="%+.2f"),
        "max_z": st.column_config.NumberColumn("max z", format="%.1f"),
    },
)

st.markdown("### Spike detection")
sig.note("boundary", f"**Rule.** {rule.describe()}")
start = window.prev_start - timedelta(days=42)
daily = daily_counts(v.ws.mentions, v.brands, start - timedelta(days=rule.window_days), end)
scores = spike_scores(daily, rule, v.ws.coverage_start)
scores = scores.loc[scores["date"] >= start]
brand = st.selectbox("Brand", v.brands, index=0)
part = scores.loc[scores["brand"] == brand]
flags = part.loc[part["spike"]]

left, right = st.columns(2)
with left:
    fig = go.Figure()
    fig.add_bar(x=list(part["date"]), y=part["count"], name="Mentions", marker=dict(color=v.colors[brand], cornerradius=4),
                hovertemplate="%{x|%a %d.%m}: %{y} mentions<extra></extra>")
    fig.add_scatter(x=list(part["date"]), y=part["baseline_mean"], name=f"{rule.window_days}-day baseline mean",
                    mode="lines", line=dict(color=MUTED, width=2, dash="dot"),
                    hovertemplate="baseline %{y:.1f}<extra></extra>")
    if not flags.empty:
        fig.add_scatter(x=list(flags["date"]), y=flags["count"], mode="markers", name="Spike",
                        marker=dict(symbol="diamond-open", size=15, color=INK, line=dict(width=2)),
                        hovertemplate="spike: %{y}<extra></extra>")
    fig.add_vrect(x0=pd.Timestamp(window.this_start) - pd.Timedelta(hours=12), x1=pd.Timestamp(window.this_end) + pd.Timedelta(hours=12),
                  fillcolor=BAND, opacity=0.18, line_width=0)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title="Mentions per day", rangemode="tozero")
    st.plotly_chart(style(fig, 340), width="stretch")
with right:
    zfig = go.Figure()
    zfig.add_scatter(x=list(part["date"]), y=part["z"], name="z-score", mode="lines+markers",
                     line=dict(color=v.colors[brand], width=2), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                     hovertemplate="%{x|%a %d.%m}: z = %{y:.2f}<extra></extra>")
    zfig.add_hline(y=threshold, line=dict(color=sig.roles(NS)["threshold"], width=2, dash="dash"),
                   annotation_text=f"threshold z = {threshold:g}", annotation_font_color=MUTED,
                   annotation_position="top left")
    zfig.add_vrect(x0=pd.Timestamp(window.this_start) - pd.Timedelta(hours=12), x1=pd.Timestamp(window.this_end) + pd.Timedelta(hours=12),
                   fillcolor=BAND, opacity=0.18, line_width=0)
    zfig.update_layout(hovermode="x unified")
    zfig.update_yaxes(title="z-score vs previous days")
    st.plotly_chart(style(zfig, 340), width="stretch")
st.caption("Shaded band = the reporting week. A z-score is blank until enough history exists.")
with st.expander("Table view of the scores"):
    st.dataframe(part.sort_values("date", ascending=False), hide_index=True, width="stretch")

st.markdown("### Rising terms")
this = v.ws.mentions.loc[(v.ws.mentions["date"] >= window.this_start) & (v.ws.mentions["date"] <= window.this_end)]
prev = v.ws.mentions.loc[(v.ws.mentions["date"] >= window.prev_start) & (v.ws.mentions["date"] <= window.prev_end)]


def _texts(frame):
    unique = frame.drop_duplicates("article_id")
    return (unique["title"].fillna("") + ". " + unique["summary"].fillna("")).tolist()


aliases = tuple(alias for b in v.ws.brands for alias in b.aliases)
rising = rising_terms(_texts(this), _texts(prev), remove_terms=aliases, top_n=15)
if rising.empty:
    st.caption("No term appears in at least two items this week and more often than last week.")
else:
    st.dataframe(
        rising, hide_index=True,
        column_config={"this_week": "items this week", "prev_week": "items last week",
                       "log_ratio": st.column_config.NumberColumn("log ratio", format="%.2f")},
    )
    st.caption("Terms (brand names removed) found in more headlines/snippets this week than last; smoothed log ratio "
               "of the share of items containing the term.")
