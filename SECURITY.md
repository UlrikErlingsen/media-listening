# Security policy

## Supported version

The latest released version receives security fixes.

## Reporting

Report suspected vulnerabilities privately to the repository owner before public disclosure.

## Design notes

- **Network:** the app and collector contact only the feed URLs in `sources.yaml` (and their `/robots.txt`).
  The NorBERT3 model is downloaded only when you run `python -m listensignal.sentiment --download`; otherwise it
  is loaded with `local_files_only=True`.
- **Remote code:** NorBERT3 requires `trust_remote_code=True`, which runs Python code shipped with the model.
  ListenSignal pins the model to one reviewed revision (`a6f56334e237664a30573cf2c4b9f94a28934425`), so a later
  change to the model repository cannot run on your machine without a code change here.
- **Feed content is untrusted input.** Feeds are size-capped (5 MB) and time-limited. Markup is stripped from
  snippets. HTML exports escape all feed text, and XLSX exports neutralize spreadsheet formulas (cells starting
  with `=`, `+`, `-`, `@`).
- **No authentication.** The dashboard has no login. It binds to `127.0.0.1` in the launchers. A shared or public
  deployment needs access control, TLS, logging and retention policies appropriate to the setting.
