"""Weekly brand pulse: an auditable XLSX workbook and a one-page HTML summary.

    python -m listensignal.pulse [--demo] [--end 2026-09-27] [--out exports]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import html
from io import BytesIO
from pathlib import Path
import re
import sys

import pandas as pd

from . import __version__
from .analysis import (
    SENTIMENT_ORDER,
    SpikeRule,
    WeekWindow,
    change_headlines,
    coverage_note,
    daily_counts,
    detect_spikes,
    sentiment_mix,
    share_of_voice,
    top_sources,
    weekly_change,
)
from .config import DEFAULT_BRANDS, DEFAULT_DB
from .topics import rising_terms
from .workspace import Workspace, database_workspace, demo_workspace

SENTIMENT_LIMITS = (
    "Sentiment is an indicator, not a verdict. It labels the tone of each headline and feed snippet — not the "
    "tone towards a particular brand — and has not been validated on Norwegian news headlines by Listen Signal. "
    "Each label records which scorer produced it (NorBERT3 or the lexicon fallback)."
)
COUNT_LIMITS = (
    "Counts cover only the configured RSS feeds, only what those feeds published while the collector ran, and "
    "headlines and snippets only (no full text, no paywalled content, no social platforms)."
)
_FORMULA_START = re.compile(r"^[=+\-@\t\r]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def safe_cell(value: object) -> object:
    """Neutralize spreadsheet formula injection (headlines often start with '-') and strip control characters."""
    if isinstance(value, str):
        value = _CONTROL.sub("", value)
        if _FORMULA_START.match(value):
            return "'" + value
    return value


def _safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    clean = frame.copy()
    clean.columns = [safe_cell(str(column)) for column in clean.columns]
    for column in clean.columns:
        if clean[column].dtype == object:
            clean[column] = clean[column].map(safe_cell)
        if isinstance(clean[column].dtype, pd.DatetimeTZDtype):
            clean[column] = clean[column].dt.tz_convert("Europe/Oslo").dt.tz_localize(None)
    return clean


@dataclass
class PulseReport:
    workspace_label: str
    is_demo: bool
    notice: str
    window: WeekWindow
    rule: SpikeRule
    change: pd.DataFrame
    headlines: list[str]
    sov: pd.DataFrame
    sentiment: pd.DataFrame
    spikes: pd.DataFrame
    sources: pd.DataFrame
    rising: pd.DataFrame
    daily: pd.DataFrame
    latest: pd.DataFrame
    scorers: list[str] = field(default_factory=list)
    generated: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))


def build_pulse(workspace: Workspace, end: date | None = None, rule: SpikeRule = SpikeRule()) -> PulseReport:
    mentions = workspace.mentions
    brands = workspace.brand_names
    if end is None:
        end = max(mentions["date"]) if not mentions.empty else date.today()
    window = WeekWindow.ending(end)
    this_week = mentions.loc[(mentions["date"] >= window.this_start) & (mentions["date"] <= window.this_end)]
    prev_week = mentions.loc[(mentions["date"] >= window.prev_start) & (mentions["date"] <= window.prev_end)]
    daily = daily_counts(mentions, brands, window.prev_start - timedelta(days=rule.window_days), end)
    spikes = detect_spikes(daily, rule, workspace.coverage_start)
    spikes = spikes.loc[spikes["date"] >= window.prev_start]
    change = weekly_change(mentions, brands, window, rule, workspace.coverage_start)
    note = coverage_note(window, workspace.coverage_start)
    aliases = tuple(alias for brand in workspace.brands for alias in brand.aliases)

    def texts(frame: pd.DataFrame) -> list[str]:
        unique = frame.drop_duplicates("article_id")
        return (unique["title"].fillna("") + ". " + unique["summary"].fillna("")).tolist()

    return PulseReport(
        workspace_label=workspace.label,
        is_demo=workspace.is_demo,
        notice=workspace.notice,
        window=window,
        rule=rule,
        change=change,
        headlines=([note] if note else []) + change_headlines(change, rule),
        sov=share_of_voice(this_week, brands),
        sentiment=sentiment_mix(this_week, brands),
        spikes=spikes,
        sources=top_sources(this_week, 10),
        rising=rising_terms(texts(this_week), texts(prev_week), remove_terms=aliases),
        daily=daily.loc[daily.index >= window.prev_start].reset_index(),
        latest=this_week[["published", "brand", "source", "title", "sentiment", "sentiment_scorer", "url"]].head(200),
        scorers=sorted(this_week["sentiment_scorer"].dropna().astype(str).unique()),
    )


def pulse_xlsx(report: PulseReport) -> bytes:
    about = pd.DataFrame(
        [
            ("Report", "Listen Signal weekly brand pulse"),
            ("Version", f"Listen Signal {__version__}"),
            ("Generated", report.generated),
            ("Data", report.workspace_label),
            ("Demo notice", report.notice or "—"),
            ("Period", report.window.label()),
            ("Sentiment scorer(s)", ", ".join(report.scorers) or "—"),
            ("Spike rule", report.rule.describe()),
            ("Sentiment limits", SENTIMENT_LIMITS),
            ("Coverage limits", COUNT_LIMITS),
        ],
        columns=["Item", "Value"],
    )
    sheets = {
        "About": about,
        "What changed": pd.DataFrame({"note": report.headlines or ["No change crossed the reporting rules."]}),
        "Week vs week": report.change,
        "Share of voice": report.sov,
        "Sentiment mix": report.sentiment,
        "Spikes": report.spikes,
        "Daily counts": report.daily,
        "Top sources": report.sources,
        "Rising terms": report.rising,
        "Mentions": report.latest,
    }
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            _safe_frame(frame).to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            for column_cells in sheet.columns:
                width = max(len(str(cell.value or "")) for cell in column_cells[:60])
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(10, width + 2), 90)
    return buffer.getvalue()


def _pct(value: object) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):.0%}"


# Signal "Organic" tokens, mirrored from listensignal/ui/signal_theme.py (CORE, FAMILIES, DIVERGING) for the
# standalone HTML export. This module must stay Streamlit-free, so it cannot import the theme itself.
SENTIMENT_HEX = {"Positive": "#4f80a2", "Neutral": "#a19786", "Mixed": "#a06f1f", "Negative": "#b2622d",
                 "Unscored": "#ebddc5"}


def _signed(value: object) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):+.2f}"


def _md_bold(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text))


def pulse_html(report: PulseReport) -> str:
    e = html.escape
    colors = SENTIMENT_HEX
    rows = []
    for row in report.change.itertuples(index=False):
        mix = report.sentiment.loc[report.sentiment["brand"] == row.brand]
        bar = "".join(
            f'<span style="width:{share * 100:.1f}%;background:{colors[label]}" title="{e(label)} {share:.0%}"></span>'
            for label, share in zip(mix["sentiment"], mix["share"])
            if share > 0
        )
        change = "—" if row.change_pct is None or pd.isna(row.change_pct) else f"{row.change_pct:+.0%}"
        rows.append(
            f"<tr><td><strong>{e(row.brand)}</strong></td><td class=n>{row.mentions_this_week}</td>"
            f"<td class=n>{row.mentions_prev_week}</td><td class=n>{change}</td><td class=n>{_pct(row.sov_this_week)}</td>"
            f"<td class=n>{_signed(row.net_tone_this_week)}</td><td><div class=bar>{bar}</div></td>"
            f"<td>{e(row.spike_days) or '—'}</td></tr>"
        )
    notes = "".join(f"<li>{_md_bold(note)}</li>" for note in report.headlines) or "<li>No change crossed the reporting rules.</li>"
    rising = ", ".join(e(term) for term in report.rising["term"].head(8)) or "—"
    sources = ", ".join(f"{e(str(r.source))} ({r.mentions})" for r in report.sources.head(6).itertuples()) or "—"
    latest = "".join(
        f'<li><a href="{e(str(r.url))}">{e(str(r.title))}</a> <span class=m>· {e(str(r.source))} · {e(str(r.brand))} · '
        f"{e(str(r.sentiment))}</span></li>"
        for r in report.latest.head(8).itertuples()
    ) or "<li>No mentions this week.</li>"
    legend = " ".join(f'<span class=k style="background:{colors[label]}"></span>{label}' for label in SENTIMENT_ORDER)
    demo = f'<p class=demo><strong>Fictional demo.</strong> {e(report.notice)}</p>' if report.is_demo else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Listen Signal weekly pulse {report.window.this_end:%Y-%m-%d}</title>
<style>
body{{font-family:Figtree,system-ui,Segoe UI,Arial,sans-serif;color:#201e1d;background:#f5ead8;margin:0;padding:24px}}
main{{max-width:960px;margin:auto;background:#f9f4ed;border-radius:28px;padding:28px 32px}}
h1{{margin:0;font-size:26px;font-weight:800;letter-spacing:-.03em}} h1 span{{color:#728157}} h2{{font-size:15px;margin:22px 0 8px;text-transform:uppercase;letter-spacing:.08em;color:#56633f}}
.sub{{color:#645c50;margin:4px 0 0}} table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:6px 8px;border-bottom:1px solid rgba(32,30,29,.16);text-align:left}} th{{font-size:11px;color:#645c50;text-transform:uppercase}}
.n{{text-align:right;font-variant-numeric:tabular-nums}} .bar{{display:flex;height:12px;border-radius:6px;overflow:hidden;min-width:140px;background:#ebddc5}}
.bar span{{display:block;height:100%}} .k{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px}}
ul{{margin:0;padding-left:18px;font-size:14px;line-height:1.55}} .m{{color:#645c50;font-size:12px}} a{{color:#56633f}}
.demo{{background:#fff2eb;color:#643312;padding:8px 12px;border-radius:16px;font-size:13px}}
.limits{{font-size:11.5px;color:#645c50;line-height:1.5;border-top:1px solid rgba(32,30,29,.16);margin-top:22px;padding-top:10px}}
@media print{{body{{padding:0;background:#fff}} main{{border:0}}}}
</style></head><body><main>
<h1>Listen <span>Signal</span> · weekly brand pulse</h1>
<p class=sub>{e(report.window.label())} · {e(report.workspace_label)} · generated {e(report.generated)}</p>
{demo}
<h2>What changed</h2><ul>{notes}</ul>
<h2>Brands this week</h2>
<table><tr><th>Brand</th><th class=n>Mentions</th><th class=n>Prev. week</th><th class=n>Change</th><th class=n>Share of voice</th>
<th class=n>Net tone</th><th>Sentiment mix</th><th>Spike days</th></tr>{''.join(rows)}</table>
<p class=m>{legend}. Net tone = (positive − negative) / scored mentions, from −1 to +1.</p>
<h2>Rising terms</h2><p>{rising}</p>
<h2>Top sources</h2><p>{sources}</p>
<h2>Latest mentions</h2><ul>{latest}</ul>
<p class=limits><strong>Spike rule:</strong> {e(report.rule.describe())}<br><strong>Sentiment:</strong> {e(SENTIMENT_LIMITS)}
 Scorer(s) this week: {e(', '.join(report.scorers) or '—')}.<br><strong>Coverage:</strong> {e(COUNT_LIMITS)}<br>
Listen Signal {__version__} · local-first · part of the Signal suite · AGPL-3.0-or-later</p>
</main></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m listensignal.pulse", description="Write the weekly brand pulse.")
    parser.add_argument("--demo", action="store_true", help="use the fictional demo instead of the local database")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--brands", default=str(DEFAULT_BRANDS))
    parser.add_argument("--end", help="last day of the reporting week (YYYY-MM-DD); default: latest mention")
    parser.add_argument("--out", default="exports", help="output folder")
    args = parser.parse_args(argv)
    workspace = demo_workspace() if args.demo else database_workspace(args.db, args.brands)
    end = date.fromisoformat(args.end) if args.end else None
    report = build_pulse(workspace, end)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"listensignal-pulse-{report.window.this_end:%Y-%m-%d}{'-demo' if workspace.is_demo else ''}"
    (out / f"{stem}.xlsx").write_bytes(pulse_xlsx(report))
    (out / f"{stem}.html").write_text(pulse_html(report), encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"Wrote {out / stem}.xlsx and .html ({report.window.label()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
