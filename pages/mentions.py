"""Latest mentions: filterable table with links and the alias that matched."""

from __future__ import annotations

import streamlit as st

from listensignal import find_matches
from listensignal.analysis import SENTIMENT_ORDER, TIMEZONE
from listensignal.ui import signal_theme as sig
from pages._ui import data_banner, empty_state, scorer_caption, view

sig.header(
    "Mentions",
    "Latest mentions",
    "Every feed item that names a tracked brand, newest first. Open the link to read the story on the publisher's "
    "site — Listen Signal stores only the headline and the snippet the feed itself published.",
)
v = view()
data_banner(v)
if empty_state(v):
    st.stop()

c1, c2, c3 = st.columns(3)
brands = c1.multiselect("Brands", v.brands, default=v.brands)
labels = [label for label in SENTIMENT_ORDER + ["Unscored"] if label in set(v.mentions["sentiment"])]
sentiments = c2.multiselect("Sentiment", labels, default=labels)
sources = sorted(v.mentions["source"].dropna().unique())
chosen_sources = c3.multiselect("Sources", sources, default=sources)
query = st.text_input("Search headlines and snippets", placeholder="e.g. tilbakekall, pris, sponsor")

rows = v.mentions.loc[
    v.mentions["brand"].isin(brands) & v.mentions["sentiment"].isin(sentiments) & v.mentions["source"].isin(chosen_sources)
]
if query:
    text = rows["title"].fillna("") + " " + rows["summary"].fillna("")
    rows = rows.loc[text.str.contains(query, case=False, regex=False)]
rows = rows.head(1000).copy()
by_name = {brand.name: brand for brand in v.ws.brands}
rows["matched"] = [
    ", ".join(sorted({m.text for m in find_matches(f"{t} \n {s}", by_name[b]) if m.excluded_by is None}))
    for t, s, b in zip(rows["title"].fillna(""), rows["summary"].fillna(""), rows["brand"])
]
rows["published"] = rows["published"].dt.tz_convert(TIMEZONE).dt.tz_localize(None)
st.caption(f"{len(rows):,} mentions shown (at most 1,000).")
st.dataframe(
    rows[["published", "brand", "source", "title", "summary", "sentiment", "sentiment_scorer", "matched", "url"]],
    hide_index=True,
    width="stretch",
    height=560,
    column_config={
        "published": st.column_config.DatetimeColumn("published (Oslo)", format="DD.MM.YYYY HH:mm"),
        "title": st.column_config.TextColumn("headline", width="large"),
        "summary": st.column_config.TextColumn("feed snippet", width="medium"),
        "sentiment_scorer": "scorer",
        "matched": st.column_config.TextColumn("matched text", help="Alias text that triggered the match"),
        "url": st.column_config.LinkColumn("link", display_text="open"),
    },
)
st.caption(scorer_caption(rows))
