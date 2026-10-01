# Contributing

Contributions should keep ListenSignal's boundaries:

- **Feeds only.** Use public RSS/Atom feeds that the publisher's robots.txt allows. No full-text scraping, no
  paywall workarounds, no unofficial platform APIs. Respect the 30-minute poll floor.
- **Local only.** No telemetry, no accounts, no calls to external AI or analytics services.
- **Honest numbers.** Never claim sentiment accuracy you have not measured. If you evaluate, say on what data, and
  do not tune on the test split.
- **Explainable rules.** Spike, matching and topic rules must stay readable and be shown in the app.
- **UI-free package.** Logic goes in `src/listensignal/` and must not import Streamlit; Streamlit code goes in
  `app.py` and `pages/`. Storage changes go through `storage.py`.

When adding a feed to `sources.yaml`, include the date you verified it, and a note if the publisher restricts
text and data mining or media monitoring.

Before submitting a change:

```bash
python -m pytest
python -m ruff check .
```

Use fictional or openly licensed test data. Do not commit collected feed data, NoReC data or model files.
