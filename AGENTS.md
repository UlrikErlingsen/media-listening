# AGENTS.md — Listen Signal (repo: media-listening)

You are building **Listen Signal**, a new product in Ulrik Erlingsen's **Signal** suite
(open-source, local-first marketing tools; see sibling repos such as `brand-tracking`
= Track Signal and `open-text-analysis` for house style). This repo starts empty except for this
file, a README stub, LICENSE and .gitignore. Build v1 from this brief.

Display name: **Listen Signal** (with a space) in every user-facing place. Technical identifiers stay
unchanged: package `listensignal`, `LISTENSIGNAL_*` variables, the `ListenSignal/<version>` User-Agent,
file slugs such as `listensignal-banner.png`.

## What it is

An open, local-first **media and social listening tool for Norwegian-language sources**.
Free alternative for small brands to paid monitoring such as Retriever, Meltwater and
Brandwatch. Existing open-source listening tools (Obsei, OpenMagpie, Harken — checked
2026-10-01) are English-first; none handles Norwegian sources or Norwegian sentiment.

## The question it answers

> How often is our brand (and each competitor) mentioned in Norwegian media and forums,
> in what tone, about which topics — and what changed this week?

## v1 scope

1. **Brands** — define tracked brands and competitors with aliases and exclusion terms
   (e.g. "Tine" but not "Tine Sundt"). Matching handles Bokmål/Nynorsk inflection
   (case-insensitive, word boundaries, simple suffix stemming).
2. **Sources** — RSS/Atom feeds only in v1, configured in `sources.yaml`. Seed with public
   feeds from Norwegian outlets (e.g. NRK, VG, E24, Dagbladet, Aftenposten, DN, Finansavisen,
   Kampanje, Kom24) and Google News RSS with `hl=no&gl=NO`. **Verify each feed URL works before
   seeding; drop any that don't.** Optional: Reddit r/norge via its public RSS feed.
   Respect each site's terms and robots.txt; poll at most every 30 min; send a clear User-Agent.
3. **Collector** — `python -m listensignal.collect` fetches feeds, de-duplicates by URL and
   title hash, stores **headline, short summary/snippet as given in the feed, URL, source,
   published time** in SQLite. Do not scrape or store full article text (copyright).
4. **Sentiment** — Norwegian sentence-level sentiment with the local model
   `ltg/norbert3-base_sentence-sentiment` (Hugging Face, University of Oslo LTG; needs
   `trust_remote_code=True` — read its model card first). Runs locally on CPU. Provide a
   fallback lexicon scorer if the model is not installed, and label which one produced each score.
   Show sentiment as an indicator with its limits, not a verdict.
5. **Topics** — simple, explainable topic grouping (TF-IDF + keyword clusters or BERTopic if
   it stays light). Show top terms per cluster.
6. **Dashboard** (Streamlit) — mention volume over time per brand, share of voice, sentiment
   mix, top sources, latest mentions table with links, "what changed vs last week" panel that
   flags spikes (simple z-score on daily counts, with the threshold shown).
7. **Weekly brand pulse export** — XLSX + one-page HTML summary.

Out of scope for v1: X/Twitter, Instagram, TikTok, Facebook (API terms / cost), full-text
scraping, paywalled content, LLM calls to external APIs.

## Demo data

Deterministic fictional demo (`src/listensignal/demo.py`): fictional brands "Fjellbrus",
"Kystkraft", "Nordlys Energi" with ~600 generated Norwegian headlines/snippets over 12 weeks,
including one engineered spike, so every chart has something to show without network access.
State on screen and in README that demo mentions are fictional.

## Stack and house style (match other Signal repos)

- Python 3.10+, Streamlit `app.py`, package `src/listensignal/`, tests in `tests/`.
- **No Streamlit import anywhere under `src/listensignal/` except `src/listensignal/ui/`** (enforced by
  `tests/test_architecture.py`). Analysis, storage and exports stay UI-free; Streamlit pages live in
  `src/listensignal/ui/pages/` (one `show()` per page; `listensignal.ui.render()` is the Signal Hub entry point,
  with every session/widget key namespaced `listen:` and a `SIGNAL_HUB=1` mode that uses the fictional demo only,
  writes nothing and makes no network calls). `app.py` and `pages/` are thin standalone wrappers.
- Look and feel comes from the synced Signal theme: `from listensignal.ui import signal_theme as sig`, key
  `listen` (Market family). Never edit the synced files (`src/listensignal/ui/signal_theme.py`,
  `src/listensignal/ui/assets/marks/*`, `.streamlit/config.toml`, `assets/listensignal-*.png|svg`); change
  them in Signal Hub `signal-theme/` and re-sync.
- SQLite in `./data/listensignal.db` (gitignored). feedparser, pandas, plotly, openpyxl, pyyaml,
  scikit-learn; `transformers` + `torch` as an **optional extra** `[sentiment]`.
- No telemetry, no accounts, no external AI APIs. Network use only for the RSS feeds the user configures.
- `pyproject.toml` (setuptools, AGPL-3.0-or-later, author "Ulrik Erlingsen"), `requirements.txt`,
  `Dockerfile`, `run_app.bat` — mirror `brand-tracking`.
- ruff (line length 120) + pytest. Tests: alias/exclusion matching incl. Norwegian inflections,
  de-duplication, spike detection, lexicon fallback, demo determinism.
- README follows the Signal README template (Signal Hub `signal-theme/README.template.md`); add
  CHANGELOG, SECURITY, PRIVACY (no personal data stored
  beyond what's in public headlines), CONTRIBUTING.

## Definition of done for v1

- `run_app.bat` opens the dashboard with the demo loaded (works offline).
- `collect` works against at least 5 verified live Norwegian feeds.
- Sentiment runs with NorBERT3 when the extra is installed, lexicon otherwise.
- `pytest` and `ruff check` pass; screenshots in `assets/`.

## Working rules

- Ulrik commits and pushes from **GitHub Desktop** himself; you do not push.
- Small logical commits; short summary at the end of each session.
- Never claim sentiment accuracy you have not measured; if you evaluate, say on what data.
