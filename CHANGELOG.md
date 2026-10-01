# Changelog

## 1.0.0 — unreleased (local build, 2026-10-01)

First version of **ListenSignal**, built from the v1 brief.

### Listening

- Brand and competitor definitions in `brands.yaml`: aliases, exclusion phrases, Bokmål/Nynorsk inflection,
  hyphenated compounds, optional case sensitivity.
- RSS/Atom collector (`python -m listensignal.collect`): robots.txt checked on every run, a 30-minute poll floor
  that configuration cannot lower, conditional requests, a descriptive User-Agent and a 5 MB feed cap. It stores
  headline, feed snippet (max 400 characters), link, source and time, never full text, and de-duplicates by
  normalized URL and headline hash.
- The collector reports a **possible gap** when every item in a feed is new since the last poll (feeds are a
  sliding window; VG's holds only 10 items). `run_collect.bat` runs one collection for Windows Task Scheduler and
  logs to `logs/collect.log`; NorBERT3 is loaded only when there is something new to score.
- `sources.yaml` seeded with six feeds verified on 2026-10-01 (VG, E24, Aftenposten, Nettavisen, Kampanje, Teknisk
  Ukeblad). NRK, Dagbladet, DN, Google News (`hl=no&gl=NO`) and r/norge are seeded disabled with the reason;
  Finansavisen and Kom24 were dropped (no working feed).

### Analysis

- Sentence-level sentiment with local NorBERT3 (`ltg/norbert3-base_sentence-sentiment`, pinned revision, optional
  `[sentiment]` extra, transformers < 5), or a Bokmål/Nynorsk lexicon fallback; every label records its scorer.
- Measured on the NoReC_sentence test split: NorBERT3 weighted F1 0.749, lexicon 0.498, always-Neutral 0.301.
  Accuracy on news headlines is not measured (`docs/sentiment-evaluation.md`).
- Share of voice, sentiment mix, net tone, top sources, z-score spikes with the rule shown, a week-over-week
  “what changed” panel and rising terms. Days before the first collection are excluded, so collection gaps are
  never reported as news.
- TF-IDF → LSA → k-means topic groups with top terms.

### Dashboard and export

- **Brand profile** page: weekly volume and tone, distinctive terms against competitors, sources, latest positive
  and negative items; KPI tiles show the change against the previous equally long period (suppressed when that
  period predates the data).
- **Edit brands for this session**: visitors can change aliases and exclusions or add a brand in the dashboard;
  every page re-matches the same items, nothing is written to disk, and the list downloads as `brands.yaml`.
- `LISTENSIGNAL_PUBLIC_DEMO=1` for hosting: fictional data only, no database, no outbound feed requests.
- Feed text and user-typed brand names are HTML-escaped wherever the dashboard renders custom HTML.

- Streamlit dashboard (Overview, What changed, Mentions, Topics, Weekly pulse, Sources & brands, Methods &
  limits) on the shared Signal-suite shell, with a matcher tester and a “collect now” button.
- Weekly brand pulse as a one-page HTML summary and an XLSX workbook, protected against formula injection.
- Deterministic fictional demo (three invented brands, 572 items over 12 weeks, one engineered recall spike with a
  knock-on competitor spike), with varied headlines, loaded by default and usable offline.

### Engineering

- Package under `src/listensignal/` with a public API and no Streamlit imports (enforced by a test). Storage
  sits behind `storage.py`.
- Dependency floors verified by running the suite on Python 3.10 with pandas 2.0.3, numpy 1.26, plotly 5.19,
  scikit-learn 1.3.2, feedparser 6.0.11 and Streamlit 1.51 (the lowest versions the pins allow).
- pytest suite, ruff, CI for Python 3.10–3.13, Windows/macOS launchers, and a non-root Docker image with a
  health check.
