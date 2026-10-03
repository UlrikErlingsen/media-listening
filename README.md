<p align="center">
  <img src="assets/listensignal-banner.png" alt="Listen Signal: Who is talking about the brand in Norwegian media, and in what tone?" width="100%">
</p>

<p align="center">
  <a href="https://github.com/UlrikErlingsen/media-listening/actions"><img alt="Tests" src="https://github.com/UlrikErlingsen/media-listening/actions/workflows/tests.yml/badge.svg"></a>
  <a href="https://github.com/UlrikErlingsen/signal-hub"><img alt="Signal · Market" src="https://img.shields.io/badge/Signal-Market-728157?labelColor=2e2b25"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2e2b25?logo=python&logoColor=f9f4ed">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-app-728157?logo=streamlit&logoColor=f9f4ed">
  <a href="LICENSE"><img alt="License: AGPL-3.0-or-later" src="https://img.shields.io/badge/License-AGPL--3.0--or--later-645c50"></a>
</p>

<p align="center"><strong>Open Norwegian media listening: mentions, share of voice and Norwegian-language sentiment, run locally.</strong></p>

**Listen Signal** is an open, local-first media and social listening tool for **Norwegian-language sources**. It is
a free alternative for small brands to paid monitoring services such as Retriever, Meltwater and Brandwatch. It
combines brand matching that understands Bokmål and Nynorsk, an RSS/Atom collector with strict politeness rules,
local Norwegian sentiment, explainable topics and a weekly brand pulse. The open-source listening tools checked on
1 October 2026 (Obsei, OpenMagpie, Harken) are English-first, and none of them handles Norwegian sources or
Norwegian sentiment. Listen Signal answers one question:

> How often is our brand (and each competitor) mentioned in Norwegian media and forums, in what tone, about which
> topics — and what changed this week?

Everything runs on your machine. There are no accounts, no telemetry and no external AI calls. The only network
traffic is to the RSS feeds you configure, plus a one-time optional model download.

<p align="center"><img src="assets/screenshot-overview-charts.png" alt="Overview page: weekly mention volume per brand, share of voice and sentiment mix for the fictional demo" width="100%"></p>

## Read this first

Listen Signal counts **what the configured feeds published while the collector ran**. It does not measure what
people think, how many people saw a story, or why a change happened.

- **Coverage is limited by design.** v1 reads RSS/Atom feeds only: headlines and the short snippet each feed
  publishes. It does not scrape articles, store full text, read paywalled content, or cover X/Twitter, Instagram,
  TikTok or Facebook.
- **Sentiment is an indicator, not a verdict.** It labels the tone of a headline and snippet, not the tone
  *towards your brand*. NorBERT3 measured a weighted F1 of 0.749 on Norwegian *review* sentences; the lexicon
  fallback measured 0.498. Accuracy on *news headlines* has not been measured, and NorBERT3 labels most news
  Neutral. See [the sentiment evaluation](docs/sentiment-evaluation.md).
- **Spikes are a screening rule, not proof.** With many brand-days on screen a few flags will be ordinary noise.
  The rule and threshold are shown next to every flag.
- **A new installation has no history.** Week-over-week changes and spike baselines need two full weeks of
  collection; until then the app says so instead of reporting gaps in collection as news.

**Working-name status:** no company-name, domain or trademark screen has been done for “ListenSignal” (written
“Listen Signal”) yet. Treat the name as provisional.

## Scope

**Version 1.0 supports:**

- brand and competitor definitions with aliases, exclusion phrases, Bokmål/Nynorsk inflection and hyphenated
  compounds (`brands.yaml`, or edited in the app for one session);
- public RSS/Atom feeds configured in `sources.yaml`, collected with robots.txt checks, a 30-minute poll floor and
  conditional requests;
- local sentence-level sentiment with NorBERT3 (optional extra) or a transparent Bokmål/Nynorsk lexicon, with the
  scorer recorded for every label;
- share of voice, sentiment mix, net tone, top sources, z-score spikes, a week-over-week “what changed” panel,
  rising terms and TF-IDF topic groups;
- a weekly brand pulse as a one-page HTML summary and an XLSX workbook.

**It does not:** cover X/Twitter, Instagram, TikTok or Facebook (API terms and cost), scrape full text, read
paywalled content, call external LLM APIs, or estimate reach, audience size or impressions. For survey-based brand
measures use **[Track Signal](https://github.com/UlrikErlingsen/brand-tracking)**; for in-depth analysis of
open-ended text use **[Text Signal](https://github.com/UlrikErlingsen/open-text-analysis)**.

## Try the demo in three minutes

1. Start the app (`run_app.bat` on Windows). The fictional demo is already loaded and works offline.
2. **Overview:** weekly mention volume for three invented drinks brands — *Fjellbrus* (own brand), *Kystkraft* and
   *Nordlys Energi* — with share of voice, sentiment mix and top sources.
3. **What changed:** the final demo week holds an engineered spike, a fictional Fjellbrus product recall. Its
   knock-on stories also lift a competitor, Nordlys Energi, two days later. Read the plain-language notes, the
   z-score chart with its threshold line, and the rising terms (*tilbakekaller …*).
4. **Brand profile:** one brand's weekly volume and tone, the words that set its coverage apart, its sources and
   its latest positive and negative items.
5. **Mentions:** filter by brand, tone or source, and see which alias text triggered each match.
6. **Topics:** headline groups with their top terms.
7. **Sources & brands:** paste a headline into the matcher tester. The demo's Nordlys Energi aliases include
   “Nordlys”, and the exclusions stop aurora headlines (“nordlyset”) from counting. Under **Edit brands for this
   session**, change aliases or add your own brand: every page re-matches the same items, and nothing is written to
   disk.
8. **Weekly pulse:** download the one-page HTML summary and the XLSX workbook.

**The demo is fictional.** Every brand, outlet, headline and link in it is generated by code
(`src/listensignal/demo.py`, links on the reserved `.invalid` domain). It describes no real company or
publication. The app says so on every page that shows demo data.

<p align="center"><img src="assets/screenshot-spikes.png" alt="What changed page: daily mentions with spike markers next to the z-score chart with the threshold line" width="100%"></p>

<p align="center"><img src="assets/screenshot-brand.png" alt="Brand profile page: weekly mentions and weekly tone mix for one fictional brand" width="100%"></p>

## Data contract

Listen Signal works on two small configuration files and one local database.

### `brands.yaml`

```yaml
brands:
  - name: Tine
    role: own                     # own | competitor
    aliases: [Tine, TINE, TINE SA]
    exclude: [Tine Sundt]         # "Tine Sundt" is a person, not the dairy
    case_sensitive: true          # "tine" is also a verb (to thaw)
  - name: Q-Meieriene
    role: competitor
    aliases: [Q-Meieriene, Q-meieriet]
```

Matching works on word boundaries and is case-insensitive unless `case_sensitive: true`. It allows one Bokmål or
Nynorsk suffix: genitive *-s*; definite and plural *-en, -et, -a, -ene, -ane, -er, -ar* and their genitives. It
also matches hyphenated compounds (“Tine-sjefen”). Closed compounds (“Tinemelk”) are not matched unless you list
them as aliases. A hit that overlaps an exclusion phrase is discarded. Exclusions are inflected too, so “Tine
Sundts” is excluded as well. Set `inflect: false` for exact matching.

### `sources.yaml`

Every seeded feed URL was fetched on **1 October 2026** with Listen Signal's User-Agent and checked against the
site's robots.txt.

| Seeded on | Feeds |
|---|---|
| **Enabled** (robots.txt allows) | VG, E24, Aftenposten, Nettavisen, Kampanje, Teknisk Ukeblad |
| **Disabled**, with the reason in the file | NRK (robots.txt reserves text and data mining without written permission) · Dagbladet (content signal `ai-input=no`) · DN (robots.txt: media monitoring requires an agreement) · Google News RSS with `hl=no&gl=NO` and r/norge (both disallowed by robots.txt) |
| **Dropped** | Finansavisen and Kom24: no working public feed found |

The collector enforces its politeness rules in code:

- it sends a descriptive User-Agent;
- it re-checks robots.txt on every run and skips a disallowed or unreachable feed;
- it polls each feed at most once every 30 minutes (configuration can raise this, never lower it);
- it uses conditional requests (ETag / Last-Modified);
- it never opens article pages.

Publishers' terms change, so read each note before enabling a feed.

```bash
python -m listensignal.collect               # all enabled feeds
python -m listensignal.collect --only "NRK toppsaker"   # one feed, even if disabled (only with permission)
python -m listensignal.collect --sentiment lexicon      # force the fallback scorer
python -m listensignal.collect --rescore     # re-label items scored by a different scorer
```

### Schedule collection

Feeds are a sliding window of each outlet's latest items (VG's carries only 10), so Listen Signal sees only what
is in the feed when it polls. Poll every 30–60 minutes for continuous coverage. When every item in a feed is new
since the last poll, the collector reports a **possible gap**: older items probably rolled out of the feed
unseen. Each run of `run_collect.bat` collects once and appends to `logs\collect.log`. To run it every 30 minutes
with Windows Task Scheduler:

```bash
schtasks /Create /TN "ListenSignal collect" /SC MINUTE /MO 30 /TR "C:\path\to\media-listening\run_collect.bat"
```

Remove the task again with `schtasks /Delete /TN "ListenSignal collect" /F`. The app's **Sources & brands** page
also has a **Collect now** button.

### The local database

The database lives in `data/listensignal.db` (gitignored). It stores the headline, the feed snippet (capped at 400
characters), the link, the source, the published time and the sentiment label with its scorer. Items are
de-duplicated by normalized URL (tracking parameters removed) and by a hash of the normalized headline, so a wire
story published by several outlets counts once.

## Methods

- **Sentiment.** With the optional extra, `ltg/norbert3-base_sentence-sentiment` (University of Oslo, Language
  Technology Group; CC-BY-4.0) runs locally on CPU. It is pinned to revision `a6f5633` because it needs
  `trust_remote_code=True`, and it is loaded from the local cache only. Without the extra, a transparent
  Bokmål/Nynorsk word list with simple negation is used. Both scorers label each sentence and then combine them:
  Mixed if any sentence is Mixed or both Positive and Negative occur; otherwise Positive, then Negative, then
  Neutral. Every stored label records which scorer produced it. Net tone = (positive − negative) / scored mentions.
- **Share of voice** = a brand's mentions / all brand mentions in the period. An item naming two brands counts
  once for each.
- **Spikes.** A day is flagged when its count is at least 5 and its z-score is at least 3.0. The z-score is
  z = (count − mean) / SD over the previous 28 days, excluding that day, with at least 14 days of history and the
  SD floored at 1. Days before the first collection are never scored. Threshold and minimum count are adjustable
  on screen.
- **What changed** compares the last 7 days with the 7 before. Notes appear for spikes, for volume changes of at
  least 50 % and 5 mentions, and for rises of at least 15 points in the negative share.
- **Topics.** TF-IDF over headline + snippet (1–2-word terms; Norwegian stop-words and brand names removed) feeds
  LSA (20 dimensions) and then k-means with a fixed seed. Each group is described by its highest mean-TF-IDF terms.
  Rising terms compare the share of items containing a term this week and last week.
- Daily buckets use Norwegian time (Europe/Oslo). See **Methods & limits** in the app and
  [the sentiment evaluation](docs/sentiment-evaluation.md).

## Exports

The **Weekly pulse** page, or `python -m listensignal.pulse [--demo]`, writes two files:

- a **one-page HTML summary**: what changed, a per-brand table (mentions, change, share of voice, net tone,
  sentiment mix, spike days), rising terms, top sources, latest mentions, and the spike rule, sentiment limits and
  coverage limits;
- an **XLSX workbook** with every table behind it: About, What changed, Week vs week, Share of voice, Sentiment
  mix, Spikes, Daily counts, Top sources, Rising terms, Mentions.

Both state the period, the data source, the sentiment scorer and the spike rule. Every cell is sanitized against
spreadsheet formula injection, which matters because Norwegian headlines often start with “- ”. The HTML escapes
all feed text.

## Run locally

You need Python 3.10 or newer.

**Windows:** double-click `run_app.bat`. **macOS:** double-click `run_app.command`.

The first launch creates a private `.venv` and installs the open-source dependencies. The dashboard opens at
`http://127.0.0.1:8595` with the fictional demo loaded; no network is needed. Set `LISTENSIGNAL_PORT` to change the
port. Set `LISTENSIGNAL_PUBLIC_DEMO=1` for a hosted demo: the app then shows only the fictional data, and
collection is switched off, so it never fetches feeds or writes a database. Set `LISTENSIGNAL_DEBUG=1` to show
technical details for unexpected errors. Or from a terminal:

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[ui]"      # the package, its CLI commands and the dashboard (Streamlit, Plotly)
python -m streamlit run app.py
```

`pip install -e .` without `[ui]` installs only the UI-free core and the `listensignal-collect` /
`listensignal-pulse` commands, for example on a machine that only runs scheduled collection.
`requirements.txt` (used by the launchers and Docker) installs everything.

### Optional: local NorBERT3 sentiment

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install "transformers>=4.36,<5"
python -m listensignal.sentiment --download
```

The download is about 0.5 GB and happens once. The model's remote code is incompatible with transformers 5, hence
the pin. After this, `collect` uses NorBERT3 automatically; without it, the lexicon fallback is used and labelled
as such.

### Docker

```bash
docker build -t listensignal .
docker run --rm -p 8595:8595 -v ./data:/app/data listensignal
```

Then open http://127.0.0.1:8595. The container runs as a non-root user.

### In Signal Hub

[Signal Hub](https://github.com/UlrikErlingsen/signal-hub) runs Listen Signal next to the other Signal apps by
calling `listensignal.ui.render()` with `SIGNAL_HUB=1`. In that mode Listen Signal shows the bundled fictional demo
only: there is no switch to a local database, live feed collection is off (the app says so), it makes no network
requests, writes no files, and scores sentiment with the lexicon fallback. Brand lists edited in the app stay in the
browser session. Run Listen Signal locally to collect real feeds.

## Privacy

Listen Signal stores no personal data beyond what appears in public headlines and feed snippets: names of people
in the news can appear there. It has no accounts, telemetry, tracking or external AI calls. See
[PRIVACY.md](PRIVACY.md).

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
python scripts/evaluate_sentiment.py      # optional: downloads the NoReC test split to data/eval/
```

The tests cover:

- alias and exclusion matching, including Bokmål and Nynorsk inflections;
- URL and headline de-duplication, and that only snippets are stored;
- robots.txt handling, the 30-minute poll floor and conditional requests;
- spike detection, coverage awareness and week-over-week notes;
- the lexicon fallback and scorer labelling (NorBERT3 too, when installed);
- demo determinism, topics, the pulse export and formula-injection protection;
- every Streamlit page and the shared Signal shell;
- an architecture test that fails if anything under `src/` outside `src/listensignal/ui/` imports Streamlit;
- the Signal Hub contract: `render()` draws every page from the packaged files alone with namespaced widget keys,
  and in hub mode (`SIGNAL_HUB=1`) writes no file and makes no network call.

### Architecture

All logic, data models and storage live in `src/listensignal/` and never import Streamlit, so **Signal Hub** can
reuse them. The only exception is `src/listensignal/ui/`: the shared Signal theme synced from Signal Hub
(`from listensignal.ui import signal_theme as sig`), the page functions (`ui/pages/`), and `render()` with
`APP_INFO`, the Signal Hub entry point. The public API is in `src/listensignal/__init__.py`, and SQLite sits behind
`storage.py`. The standalone `app.py` keeps one URL per page with `st.navigation`; `pages/*.py` are thin wrappers
around the same page functions.

## Where this fits in Signal

Listen Signal listens to what Norwegian media publish about brands. Track Signal measures how people perceive the
brand in surveys, and Text Signal analyses open-ended text in depth, beyond Listen Signal's headline-level topics.

<!-- signal-suite:start (generated from signal-hub/apps.yaml by scripts/sync_readme_suite.py) -->
| Family | App | Asks |
|---|---|---|
| Brand | [Track Signal](https://github.com/UlrikErlingsen/brand-tracking) | Is the brand moving, or is the tracker just noisy? |
| Brand | [Position Signal](https://github.com/UlrikErlingsen/brand-positioning) | Where do brands sit relative to competitors? |
| Market | [Prospect Signal](https://github.com/UlrikErlingsen/b2b-prospecting) | Which Norwegian companies fit your ideal customer, and which first? |
| Market | **Listen Signal** (this app) | Who is talking about the brand in Norwegian media, and in what tone? |
| Market | [Influence Signal](https://github.com/UlrikErlingsen/influencer-campaigns) | Which creators delivered, and was every post labelled properly? |
| Market | [Season Signal](https://github.com/UlrikErlingsen/marketing-calendar) | What does the Norwegian marketing year look like, worked backwards? |
| Market | [Adopt Signal](https://github.com/UlrikErlingsen/adoption-forecasting) | When will a new product be adopted? |
| Market | [Rival Signal](https://github.com/UlrikErlingsen/competitor-analysis) | Which rivals matter, and how could they respond? |
| Market | [Reach Signal](https://github.com/UlrikErlingsen/location-catchment-analysis) | Where could a new location reach, and how would it share demand with existing sites? |
| Customer | [Worth Signal](https://github.com/UlrikErlingsen/customer-value-analytics) | What are customers and relationships worth? |
| Customer | [Segment Signal](https://github.com/UlrikErlingsen/customer-segmentation) | Do customers form stable, useful groups? |
| Customer | [Trace Signal](https://github.com/UlrikErlingsen/journey-path-analysis) | How do logged customer journeys actually unfold? |
| Customer | [Blueprint Signal](https://github.com/UlrikErlingsen/service-blueprinting) | How is the customer experience actually delivered, and where do the handoffs fail? |
| Customer | [Recommend Signal](https://github.com/UlrikErlingsen/recommender-evaluation) | Which recommendation policy should be tested live? |
| Research | [Choice Signal](https://github.com/UlrikErlingsen/conjoint-analysis) | How do product attributes drive choice? |
| Research | [Driver Signal](https://github.com/UlrikErlingsen/survey-driver-analysis) | Which measured experiences move with satisfaction? |
| Research | [Measure Signal](https://github.com/UlrikErlingsen/measurement-validation) | Does a multi-item score have a defensible structure? |
| Research | [Text Signal](https://github.com/UlrikErlingsen/open-text-analysis) | What recurring patterns appear in open-ended responses? |
| Research | [Tag Signal](https://github.com/UlrikErlingsen/pricing-analysis) | What price range is supported, and how does profit move? |
| Research | [Learn Signal](https://github.com/UlrikErlingsen/research-prioritization) | Which uncertainty is worth paying to research before you decide? |
| Decide | [Experiment Signal](https://github.com/UlrikErlingsen/experiment-analysis) | Did the treatment cause a practically meaningful change? |
| Decide | [Gate Signal](https://github.com/UlrikErlingsen/launch-decision-gate) | Does a concept deserve the next investment? |
| Decide | [Shift Signal](https://github.com/UlrikErlingsen/cannibalization-analysis) | Does a launch grow the portfolio, or move existing demand around? |
| Decide | [Alloc Signal](https://github.com/UlrikErlingsen/marketing-mix-allocation) | Where should the next marketing budget go? |

All 24 apps run side by side in [Signal Hub](https://github.com/UlrikErlingsen/signal-hub), each opening with fictional demo data. Every repo carries the [`signal-suite`](https://github.com/topics/signal-suite) topic, and the suite is listed at [ulrikerlingsen.com](https://ulrikerlingsen.com). Freddo CRM is a separate product.
<!-- signal-suite:end -->

## References

- Language Technology Group, University of Oslo. `ltg/norbert3-base_sentence-sentiment` model card (CC-BY-4.0).
  https://huggingface.co/ltg/norbert3-base_sentence-sentiment
- Samuel, D., Kutuzov, A., Touileb, S., Velldal, E., Øvrelid, L., Rønningstad, E., Sigdel, E., & Palatkina, A.
  (2023). NorBench – A Benchmark for Norwegian Language Models. *Proceedings of the 24th Nordic Conference on
  Computational Linguistics (NoDaLiDa)*, 618–633. https://aclanthology.org/2023.nodalida-1.61/
- Øvrelid, L., Mæhlum, P., Barnes, J., & Velldal, E. (2020). A Fine-grained Sentiment Dataset for Norwegian.
  *Proceedings of the 12th Language Resources and Evaluation Conference (LREC)*, 5025–5033.
  https://aclanthology.org/2020.lrec-1.618/ The NoReC_sentence data used in
  [the sentiment evaluation](docs/sentiment-evaluation.md) are derived from this dataset (CC BY-NC 4.0).

## Originality and license

Listen Signal is independently designed and written. The Norwegian lexicon, stop-word list, demo templates and code
are original to this project. NorBERT3 is used as a downloaded model under its CC-BY-4.0 licence and is not
redistributed. NoReC evaluation data are downloaded on demand and not redistributed (CC BY-NC 4.0). All bundled
demo data are fictional and generated by code.

The software and documentation are free under **AGPL-3.0-or-later**. See [LICENSE](LICENSE). The license covers
this project's expression, not ownership of published methods.

This application was developed with AI coding assistance and checked through source review, automated tests, live
feed runs and visual inspection. Verify material decisions independently; no warranty is provided.

See [CHANGELOG.md](CHANGELOG.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and
[PRIVACY.md](PRIVACY.md).

---

<p>
  <img src="assets/listensignal-mark-64.png" width="20" height="20" alt="" align="absmiddle">
  <strong>Listen Signal</strong> is part of <a href="https://github.com/UlrikErlingsen/signal-hub"><strong>Signal</strong></a>, open marketing-evidence tools by <a href="https://ulrikerlingsen.com">Ulrik Erlingsen</a>.
</p>
