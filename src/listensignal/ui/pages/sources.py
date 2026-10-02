"""Sources & brands: configuration, matcher tester, collection status and a manual collect button."""

from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from listensignal import DataProblem, brands_to_yaml, find_matches, load_sources, norbert_available, parse_brands_yaml
from listensignal.config import DEFAULT_BRANDS, DEFAULT_SOURCES, SEED_SOURCES
from listensignal.sentiment import LEXICON_NAME
from listensignal.ui import signal_theme as sig
from listensignal.ui.common import (
    BRAND_PALETTE,
    base_workspace,
    clear_caches,
    custom_brands_key,
    demo_only,
    hub_mode,
    k,
    public_demo,
    show_error,
    workspace,
)


def show() -> None:
    sig.header(
        "Configuration",
        "Sources & brands",
        "What Listen Signal listens to and how it recognises each brand. Try your own brand list below for this "
        "session, or edit brands.yaml and sources.yaml in the project folder.",
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
    if len(ws.brands) > len(BRAND_PALETTE):
        st.warning(f"More than {len(BRAND_PALETTE)} brands: brands after the {len(BRAND_PALETTE)}th share one neutral chart "
                   "colour. Consider fewer brands.")

    with st.expander("Edit brands for this session", expanded=bool(st.session_state.get(custom_brands_key()))):
        st.caption(
            "Change aliases or exclusions, or add your own brand, and apply: every page re-matches the same feed items. "
            "Nothing is written to disk. Download the result as brands.yaml to keep it."
        )
        key = custom_brands_key()
        editor_key = f"{key}_editor"  # key is already namespaced by k()
        text = st.text_area(
            "Brand list (YAML)",
            value=st.session_state.get(key) or brands_to_yaml(base_workspace().brands),
            height=260,
            key=editor_key,
        )
        c1, c2, c3 = st.columns(3)
        if c1.button("Apply for this session", type="primary", width="stretch", key=k("brands_apply")):
            try:
                brands = parse_brands_yaml(text)
                if len(brands) > 12:
                    raise DataProblem("Use at most 12 brands so charts stay readable.")
                st.session_state[key] = brands_to_yaml(brands)
                st.rerun()
            except DataProblem as exc:
                show_error(exc)
        if c2.button("Reset to original brands", width="stretch", disabled=not st.session_state.get(key),
                     key=k("brands_reset")):
            st.session_state.pop(key, None)
            st.session_state.pop(editor_key, None)
            st.rerun()
        c3.download_button("Download as brands.yaml", text.encode("utf-8"), "brands.yaml", "text/yaml", width="stretch",
                           key=k("brands_download"))

    st.markdown("#### Test the matcher")
    sample = st.text_area(
        "Paste a Norwegian headline",
        value="Kystkraft-sjefen jubler, men nordlyset stjal showet for Nordlys Energis lansering i Tromsø",
        height=80,
        key=k("matcher_sample"),
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

    # Signal Hub never reads the server's project folder: it shows the feed list that ships with the package.
    sources_path = SEED_SOURCES if hub_mode() else DEFAULT_SOURCES
    st.markdown("### Feeds (seeded sources.yaml)" if hub_mode() else f"### Feeds ({DEFAULT_SOURCES.name})")
    try:
        config = load_sources(sources_path)
        st.dataframe(
            pd.DataFrame([{"source": s.name, "enabled": s.enabled, "kind": s.kind, "verified": s.verified, "url": s.url,
                           "note": s.note} for s in config.sources]),
            hide_index=True,
            width="stretch",
            column_config={"url": st.column_config.LinkColumn(), "note": st.column_config.TextColumn(width="large")},
        )
        st.caption(f"Each feed is polled at most once per {config.min_interval_minutes} minutes, and robots.txt is "
                   "re-checked on every run with Listen Signal's User-Agent.")
    except Exception as exc:  # noqa: BLE001 - shown to the user
        show_error(exc)
        config = None

    if not ws.is_demo and not ws.fetch_log.empty:
        st.markdown("#### Last collection per feed")
        st.dataframe(ws.fetch_log, hide_index=True, width="stretch")

    st.markdown("### Collect now")
    if hub_mode():
        sig.note("boundary", "**Live feed collection is off in Signal Hub.** Signal Hub shows the fictional demo only "
                 "and makes no network requests; run Listen Signal locally to collect real feeds into your own database.")
        st.caption(f"Sentiment in Signal Hub: the transparent lexicon scorer ({LEXICON_NAME}). The local NorBERT3 model "
                   "is an optional extra for your own installation.")
        return
    available, why = norbert_available()
    st.caption(("Sentiment: NorBERT3 will be used if its model is in the local cache. " if available else "Sentiment: ")
               + ("" if available else why + " The lexicon fallback will be used."))
    if public_demo() or demo_only():
        st.info("Collection is switched off in this public demo. Run Listen Signal on your own machine to collect feeds.")
    elif st.button("Fetch enabled feeds", type="primary", disabled=config is None, key=k("collect_now")):
        from listensignal.collect import run as collect_run  # imported on demand: only a local install collects

        log = StringIO()
        with st.spinner("Fetching feeds and scoring new items …"):
            try:
                collect_run(DEFAULT_SOURCES, out=log)
            except Exception as exc:  # noqa: BLE001
                show_error(exc)
        clear_caches()
        st.code(log.getvalue() or "No output.")
        st.caption("Switch the sidebar to “My collected data” to analyse what was collected.")
