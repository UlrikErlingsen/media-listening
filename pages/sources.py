"""Sources & brands: configuration, matcher tester, collection status and a manual collect button."""

from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from listensignal import collect_run, find_matches, load_sources, norbert_available
from listensignal.config import DEFAULT_BRANDS, DEFAULT_SOURCES
from pages._ui import clear_caches, header, show_error, workspace

header(
    "Configuration",
    "Sources & brands",
    "What ListenSignal listens to and how it recognises each brand. Edit <code>brands.yaml</code> and "
    "<code>sources.yaml</code> in the project folder; this page reads them on every visit.",
)
ws = workspace()

st.markdown("### Brands" + (" (fictional demo set)" if ws.is_demo else f" ({DEFAULT_BRANDS.name})"))
st.dataframe(
    pd.DataFrame(
        [
            {"brand": b.name, "role": b.role, "aliases": ", ".join(b.aliases), "exclusions": ", ".join(b.exclude) or "—",
             "inflections": "yes" if b.inflect else "no", "case-sensitive": "yes" if b.case_sensitive else "no"}
            for b in ws.brands
        ]
    ),
    hide_index=True,
    width="stretch",
)
if len(ws.brands) > 8:
    st.warning("More than eight brands: brands after the eighth share one gray chart colour. Consider fewer brands.")

st.markdown("#### Test the matcher")
sample = st.text_area(
    "Paste a Norwegian headline",
    value="Kystkraft-sjefen jubler, men nordlyset stjal showet for Nordlys Energis lansering i Tromsø",
    height=80,
)
rows = []
for brand in ws.brands:
    for match in find_matches(sample, brand):
        rows.append({"brand": brand.name, "matched text": match.text, "alias": match.alias,
                     "result": f"excluded by “{match.excluded_by}”" if match.excluded_by else "counts as a mention"})
if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
else:
    st.caption("No alias of the current brands appears in this text.")
st.caption("Matching: word boundaries, case-insensitive unless the brand is case-sensitive, Bokmål/Nynorsk suffixes "
           "(-s, -en, -et, -a, -ene, -ane, -er, -ar …) and hyphenated compounds. Closed compounds are not matched.")

st.markdown(f"### Feeds ({DEFAULT_SOURCES.name})")
try:
    config = load_sources(DEFAULT_SOURCES)
    st.dataframe(
        pd.DataFrame([{"source": s.name, "enabled": s.enabled, "kind": s.kind, "verified": s.verified, "url": s.url,
                       "note": s.note} for s in config.sources]),
        hide_index=True,
        width="stretch",
        column_config={"url": st.column_config.LinkColumn(), "note": st.column_config.TextColumn(width="large")},
    )
    st.caption(f"Each feed is polled at most once per {config.min_interval_minutes} minutes, and robots.txt is "
               "re-checked on every run with ListenSignal's User-Agent.")
except Exception as exc:  # noqa: BLE001 - shown to the user
    show_error(exc)
    config = None

if not ws.is_demo and not ws.fetch_log.empty:
    st.markdown("#### Last collection per feed")
    st.dataframe(ws.fetch_log, hide_index=True, width="stretch")

st.markdown("### Collect now")
available, why = norbert_available()
st.caption(("Sentiment: NorBERT3 will be used if its model is in the local cache. " if available else "Sentiment: ")
           + ("" if available else why + " The lexicon fallback will be used."))
if st.button("Fetch enabled feeds", type="primary", disabled=config is None):
    log = StringIO()
    with st.spinner("Fetching feeds and scoring new items …"):
        try:
            collect_run(DEFAULT_SOURCES, out=log)
        except Exception as exc:  # noqa: BLE001
            show_error(exc)
    clear_caches()
    st.code(log.getvalue() or "No output.")
    st.caption("Switch the sidebar to “My collected data” to analyse what was collected.")
