"""ListenSignal: local-first media and social listening for Norwegian-language sources.

Public API (the Streamlit app and any future Signal Hub use only these names):

    load_brands, load_sources, Brand, Source          configuration
    find_matches, match_brands, mentions_brand        Norwegian alias / exclusion matching
    get_scorer, LexiconScorer                         sentiment (NorBERT3 or lexicon fallback)
    collect_run                                       fetch configured feeds into SQLite
    demo_workspace, database_workspace, Workspace     data the dashboard works on
    mention_table, daily_counts, share_of_voice,      analysis
    sentiment_mix, net_tone, top_sources,
    SpikeRule, spike_scores, detect_spikes,
    WeekWindow, weekly_change, change_headlines
    cluster_topics, rising_terms                      topic grouping
    build_pulse, pulse_xlsx, pulse_html               weekly brand pulse export

The package never imports Streamlit.
"""

__version__ = "1.0.0"

USER_AGENT = (
    f"ListenSignal/{__version__} (+https://github.com/UlrikErlingsen/media-listening; "
    "local RSS reader for brand monitoring)"
)

# Public names resolve lazily (PEP 562), so `python -m listensignal.collect` does not import every module twice.
_EXPORTS = {
    "analysis": (
        "SpikeRule", "WeekWindow", "change_headlines", "coverage_note", "daily_counts", "detect_spikes", "mention_table",
        "net_tone",
        "sentiment_mix", "share_of_voice", "spike_scores", "top_sources", "weekly_change",
    ),
    "config": ("Brand", "Source", "load_brands", "load_sources", "parse_brands", "parse_sources"),
    "errors": ("DataProblem", "friendly_message"),
    "matching": ("find_matches", "match_brands", "mentions_brand"),
    "pulse": ("PulseReport", "build_pulse", "pulse_html", "pulse_xlsx"),
    "sentiment": ("LexiconScorer", "get_scorer", "norbert_available"),
    "topics": ("cluster_topics", "rising_terms"),
    "workspace": ("Workspace", "database_has_items", "database_workspace", "demo_workspace"),
}
_LOCATION = {name: module for module, names in _EXPORTS.items() for name in names}
_LOCATION["collect_run"] = "collect"


def __getattr__(name: str):
    module_name = _LOCATION.get(name)
    if module_name is None:
        raise AttributeError(f"module 'listensignal' has no attribute {name!r}")
    from importlib import import_module

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, "run" if name == "collect_run" else name)
    globals()[name] = value
    return value


__all__ = [
    "Brand", "DataProblem", "LexiconScorer", "PulseReport", "Source", "SpikeRule", "USER_AGENT", "WeekWindow",
    "Workspace", "__version__", "build_pulse", "change_headlines", "cluster_topics", "coverage_note", "collect_run", "daily_counts",
    "database_has_items", "database_workspace", "demo_workspace", "detect_spikes", "find_matches", "friendly_message",
    "get_scorer", "load_brands", "load_sources", "match_brands", "mention_table", "mentions_brand", "net_tone",
    "norbert_available", "parse_brands", "parse_sources", "pulse_html", "pulse_xlsx", "rising_terms",
    "sentiment_mix", "share_of_voice", "spike_scores", "top_sources", "weekly_change",
]
