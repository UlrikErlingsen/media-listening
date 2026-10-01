"""Topics: TF-IDF + LSA + k-means clusters with their top terms."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from listensignal import cluster_topics
from listensignal.analysis import SENTIMENT_ORDER
from listensignal.topics import default_k
from listensignal.ui import signal_theme as sig
from pages._ui import SENTIMENT_COLORS, SURFACE, data_banner, empty_state, style, view

sig.header(
    "Topics",
    "What the coverage is about",
    "Headlines and snippets grouped by shared vocabulary. Each group is described by its most characteristic terms, "
    "so you can see why items ended up together. Groups are a reading aid, not a fixed taxonomy.",
)
v = view()
data_banner(v)
if empty_state(v):
    st.stop()

c1, c2 = st.columns([2, 1])
chosen = c1.multiselect("Brands", v.brands, default=v.brands)
scope = v.mentions.loc[v.mentions["brand"].isin(chosen)].drop_duplicates("article_id")
auto = default_k(len(scope))
k = c2.slider("Number of groups", 2, 15, min(auto, 15), help=f"Default for {len(scope)} items: {auto} (≈ √(n/2)).")
if len(scope) < 8:
    st.info("Topic grouping needs at least 8 mentions in the selected brands and period.")
    st.stop()

aliases = tuple(alias for b in v.ws.brands for alias in b.aliases)
texts = (scope["title"].fillna("") + ". " + scope["summary"].fillna("")).tolist()
result = cluster_topics(texts, k=k, remove_terms=aliases)
scope = scope.assign(topic=result.assignments)
st.caption(f"Method: {result.method}. Brand names are removed before grouping. Deterministic (fixed seed).")

mix = scope.groupby(["topic", "sentiment"]).size().unstack("sentiment", fill_value=0)
clusters = result.clusters.copy()
fig = go.Figure()
order = clusters["cluster"].tolist()[::-1]
names = [f"#{c} · {', '.join(t.split(', ')[:3])}" for c, t in zip(clusters["cluster"], clusters["top_terms"])][::-1]
for label in SENTIMENT_ORDER:
    if label not in mix:
        continue
    fig.add_bar(y=names, x=mix[label].reindex(order).fillna(0), name=label, orientation="h",
                marker=dict(color=SENTIMENT_COLORS[label], line=dict(color=SURFACE, width=2)),
                hovertemplate="%{y}<br>" + label + ": %{x}<extra></extra>")
fig.update_layout(barmode="stack")
fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
fig.update_xaxes(title="Items")
st.plotly_chart(style(fig, 110 + 34 * len(clusters)), width="stretch")

brand_mix = scope.groupby(["topic", "brand"]).size().unstack("brand", fill_value=0)
clusters["brands"] = [
    ", ".join(f"{b} {n}" for b, n in brand_mix.loc[c].sort_values(ascending=False).items() if n) for c in clusters["cluster"]
]
st.dataframe(clusters, hide_index=True, width="stretch",
             column_config={"top_terms": st.column_config.TextColumn("top terms", width="large"),
                            "example": st.column_config.TextColumn("most typical item", width="large")})

topic = st.selectbox("Read the items in a group", clusters["cluster"].tolist(),
                     format_func=lambda c: f"#{c} · {clusters.set_index('cluster').at[c, 'top_terms']}")
items = scope.loc[scope["topic"] == topic, ["published", "source", "title", "sentiment", "url"]]
items = items.assign(published=pd.to_datetime(items["published"]).dt.tz_convert("Europe/Oslo").dt.tz_localize(None))
st.dataframe(items, hide_index=True, width="stretch",
             column_config={"url": st.column_config.LinkColumn("link", display_text="open"),
                            "published": st.column_config.DatetimeColumn(format="DD.MM.YYYY HH:mm")})
