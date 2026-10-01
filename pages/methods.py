"""Methods & limits."""

from __future__ import annotations

import streamlit as st

from listensignal import SpikeRule
from listensignal.sentiment import MODEL_ID, MODEL_REVISION
from pages._ui import header

header(
    "Methods and boundaries",
    "What ListenSignal calculates — and what it cannot tell you",
    "Every number on the other pages comes from one of the simple, inspectable rules below.",
)

st.markdown("### Sources and collection")
st.write(
    "ListenSignal reads RSS/Atom feeds listed in `sources.yaml` and stores the headline, the snippet as published "
    "in the feed (capped at 400 characters), the link, the source name and the published time. It never opens "
    "article pages, never stores full text and never bypasses paywalls. Each feed is polled at most once per 30 "
    "minutes with a descriptive User-Agent; robots.txt is checked on every run and a disallowed feed is skipped. "
    "Items are de-duplicated by a normalized URL (no tracking parameters) and by a hash of the normalized headline, "
    "so the same wire story published by several outlets counts once — under the outlet collected first."
)
st.markdown("### Brand matching")
st.write(
    "Aliases match on word boundaries, case-insensitively unless a brand is marked case-sensitive. One Bokmål or "
    "Nynorsk suffix is allowed (genitive -s; definite and plural -en, -et, -a, -ene, -ane, -er, -ar and their "
    "genitives) as well as hyphenated compounds such as “Tine-sjefen”. Closed compounds (“Tinemelk”) are not "
    "matched unless listed as aliases. A hit that overlaps an exclusion phrase (“Tine Sundt”) is discarded. An item "
    "naming two brands counts once for each brand."
)
st.markdown("### Sentiment")
st.write(
    f"With the optional `[sentiment]` extra, ListenSignal runs `{MODEL_ID}` (University of Oslo, Language "
    f"Technology Group; CC-BY-4.0) locally on CPU, pinned to revision `{MODEL_REVISION[:7]}` because the model "
    "requires `trust_remote_code=True`. Its model card reports a weighted F1 of 0.764 on the sentence-level NoReC "
    "test data; ListenSignal's own run on that split (1 Oct 2026) measured 0.749. Without the extra, a transparent "
    "word-list scorer (`lexicon-v1`, Bokmål and Nynorsk, simple negation) is used; it measured a weighted F1 of "
    "0.496 on the same split (always guessing Neutral scores 0.301) and finds only about one in ten negative "
    "sentences. Those are review sentences: ListenSignal has **not** measured accuracy on news headlines, where "
    "NorBERT3 labels most items Neutral. Details: `docs/sentiment-evaluation.md`."
)
st.write(
    "Both scorers label each sentence and combine them: Mixed if any sentence is Mixed or both Positive and Negative "
    "appear; otherwise Positive, then Negative, then Neutral. The label describes the headline and snippet, not the "
    "tone towards a particular brand. Every stored label records which scorer produced it. Net tone = (positive − "
    "negative) / scored mentions."
)
st.markdown("### Topics")
st.write(
    "TF-IDF over headline + snippet (1–2-word terms, Norwegian stop-words and brand names removed, terms in at least "
    "two items and at most 60 % of items), reduced to 20 dimensions with LSA, then k-means with a fixed seed. Groups "
    "are described by the terms with the highest mean TF-IDF inside the group. Rising terms compare the share of "
    "items containing a term this week and last week (smoothed log ratio)."
)
st.markdown("### Spikes")
st.write(SpikeRule().describe() + " Daily buckets use Norwegian time (Europe/Oslo). A z-score is a screening "
         "device: with dozens of brand-days on screen, a few flags will be ordinary noise. Read the items behind "
         "every flag before acting on it.")
st.markdown("### Out of scope in v1")
st.write(
    "- X/Twitter, Instagram, TikTok and Facebook (API terms and cost).\n"
    "- Full-text scraping and paywalled content.\n"
    "- LLM calls to external APIs. Nothing leaves the machine except the feed requests you configure.\n"
    "- Reach, audience size or impressions: a mention in a small trade feed counts the same as one in a national paper."
)
st.markdown(
    '<div class="boundary"><strong>Interpretation boundary:</strong> ListenSignal counts what the configured feeds '
    "published while the collector ran. It does not measure what people think, the reach of a story, or why a "
    "change occurred.</div>",
    unsafe_allow_html=True,
)
