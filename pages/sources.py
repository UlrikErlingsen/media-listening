"""Sources & brands: configuration, matcher tester, collection status and a manual collect button."""

from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from listensignal import DataProblem, brands_to_yaml, collect_run, find_matches, load_sources, norbert_available, parse_brands_yaml
from listensignal.config import DEFAULT_BRANDS, DEFAULT_SOURCES
from pages._ui import PUBLIC_DEMO, base_workspace, clear_caches, custom_brands_key, header, show_error, workspace

header(
    "Configuration",
    "Sources & brands",
    "What ListenSignal listens to and how it recognises each brand. Try your own brand list below for this "
    "session, or edit <code>brands.yaml</code> and <code>sources.yaml</code> in the project folder.",
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

with st.expander("Edit brands for this session", expanded=bool(st.session_state.get(custom_brands_key()))):
    st.caption(
        "Change aliases or exclusions, or add your own brand, and apply: every page re-matches the same feed items. "
        "Nothing is written to disk. Download the result as brands.yaml to keep it."
    )
    key = custom_brands_key()
    text = st.text_area(
        "Brand list (YAML)",
        value=st.session_state.get(key) or brands_to_yaml(base_workspace().brands),
        height=260,
        key=f"{key}_editor",
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Apply for this session", type="primary", width="stretch"):
        try:
            brands = parse_brands_yaml(text)
            if len(brands) > 12:
                raise DataProblem("Use at most 12 brands so charts stay readable.")
            st.session_state[key] = brands_to_yaml(brands)
            st.rerun()
        except DataProblem as exc:
            show_error(exc)
    if c2.button("Reset to original brands", width="stretch", disabled=not st.session_state.get(key)):
        st.session_state.pop(key, None)
        st.session_state.pop(f"{key}_editor", None)
        st.rerun()
    c3.download_button("Download as brands.yaml", text.encode("utf-8"), "brands.yaml", "text/yaml", width="stretch")

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
if PUBLIC_DEMO:
    st.info("Collection is switched off in this public demo. Run ListenSignal on your own machine to collect feeds.")
elif st.button("Fetch enabled feeds", type="primary", disabled=config is None):
    log = StringIO()
    with st.spinner("Fetching feeds and scoring new items …"):
        try:
            collect_run(DEFAULT_SOURCES, out=log)
        except Exception as exc:  # noqa: BLE001
            show_error(exc)
    clear_caches()
    st.code(log.getvalue() or "No output.")
    st.caption("Switch the sidebar to “My collected data” to analyse what was collected.")
