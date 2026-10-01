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
- `sources.yaml` seeded with six feeds verified on 2026-10-01 (VG, E24, Aftenposten, Nettavisen, Kampanje, Teknisk
  Ukeblad). NRK, Dagbladet, DN, Google News (`hl=no&gl=NO`) and r/norge are seeded disabled with the reason;
  Finansavisen and Kom24 were dropped (no working feed).

### Analysis

- Sentence-level sentiment with local NorBERT3 (`ltg/norbert3-base_sentence-sentiment`, pinned revision, optional
  `[sentiment]` extra, transformers < 5), or a Bokmål/Nynorsk lexicon fallback; every label records its scorer.
- Measured on the NoReC_sentence test split: NorBERT3 weighted F1 0.749, lexicon 0.496, always-Neutral 0.301.
  Accuracy on news headlines is not measured (`docs/sentiment-evaluation.md`).
- Share of voice, sentiment mix, net tone, top sources, z-score spikes with the rule shown, a week-over-week
  “what changed” panel and rising terms. Days before the first collection are excluded, so collection gaps are
  never reported as news.
- TF-IDF → LSA → k-means topic groups with top terms.

### Dashboard and export

- Streamlit dashboard (Overview, What changed, Mentions, Topics, Weekly pulse, Sources & brands, Methods &
  limits) on the shared Signal-suite shell, with a matcher tester and a “collect now” button.
- Weekly brand pulse as a one-page HTML summary and an XLSX workbook, protected against formula injection.
- Deterministic fictional demo (three invented brands, 581 items over 12 weeks, one engineered spike), loaded by
  default and usable offline.

### Engineering

- Package under `src/listensignal/` with a public API and no Streamlit imports (enforced by a test). Storage
  sits behind `storage.py`.
- pytest suite, ruff, CI for Python 3.10–3.13, Windows/macOS launchers, and a non-root Docker image with a
  health check.
