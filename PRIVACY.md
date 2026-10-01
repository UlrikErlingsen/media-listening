# Privacy

Listen Signal has no accounts, telemetry, advertising, tracking pixels or external AI calls. Nothing is uploaded
anywhere.

## What is stored

The local SQLite database (`data/listensignal.db`) holds, for each feed item: the headline, the snippet as
published in the feed (max 400 characters), the link, the source name, the published and collected times, and
the sentiment label with the scorer that produced it. It stores no full article text, no reader data, no
cookies and no account data.

## Personal data

Listen Signal stores **no personal data beyond what appears in public headlines and feed snippets**. Those can
name people (for example a person quoted in a news story). Listen Signal does not profile individuals, does not
link mentions across sources to people, and is not designed to monitor private persons. Configure brands, not
people. Forum feeds (such as r/norge) are seeded disabled.

You control the data: delete `data/listensignal.db` to remove everything collected. If you deploy Listen Signal for
others, you are responsible for retention, access control and any legal basis required where you operate.

## Network use

The collector contacts only the feeds you enable in `sources.yaml` and their `robots.txt`. The optional NorBERT3
model is downloaded from Hugging Face only when you explicitly run the download command.
