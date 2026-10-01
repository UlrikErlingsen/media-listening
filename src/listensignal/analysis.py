"""Mention counts, share of voice, sentiment mix, spike detection and week-over-week change.

All daily buckets use Norwegian local time (Europe/Oslo).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import Brand
from .matching import match_articles

TIMEZONE = "Europe/Oslo"
SENTIMENT_ORDER = ["Positive", "Neutral", "Mixed", "Negative"]

# Spike rule defaults (shown on screen next to every flag).
SPIKE_THRESHOLD = 3.0
SPIKE_WINDOW_DAYS = 28
SPIKE_MIN_HISTORY_DAYS = 14
SPIKE_MIN_COUNT = 5
SPIKE_MIN_SD = 1.0

MENTION_COLUMNS = [
    "article_id", "brand", "role", "date", "published", "source", "title", "summary", "url",
    "sentiment", "sentiment_confidence", "sentiment_scorer",
]


def mention_table(articles: pd.DataFrame, brands: tuple[Brand, ...] | list[Brand]) -> pd.DataFrame:
    """One row per (feed item, brand mentioned in it). An item naming two brands counts once for each."""
    if articles.empty:
        return pd.DataFrame(columns=MENTION_COLUMNS)
    pairs = match_articles(articles, brands)
    if pairs.empty:
        return pd.DataFrame(columns=MENTION_COLUMNS)
    roles = {brand.name: brand.role for brand in brands}
    merged = pairs.merge(articles, on="article_id", how="left", validate="many_to_one")
    published = pd.to_datetime(merged["published"], utc=True, errors="coerce")
    merged["published"] = published
    merged["date"] = published.dt.tz_convert(TIMEZONE).dt.date
    merged["role"] = merged["brand"].map(roles)
    for column in MENTION_COLUMNS:
        if column not in merged:
            merged[column] = None
    merged["sentiment"] = merged["sentiment"].fillna("Unscored")
    return merged[MENTION_COLUMNS].sort_values("published", ascending=False).reset_index(drop=True)


def date_range(mentions: pd.DataFrame, end: date | None = None, days: int | None = None) -> tuple[date, date]:
    if mentions.empty:
        today = end or date.today()
        return today - timedelta(days=(days or 28) - 1), today
    last = end or max(mentions["date"])
    first = last - timedelta(days=days - 1) if days else min(mentions["date"])
    return first, last


def daily_counts(
    mentions: pd.DataFrame, brands: list[str], start: date | None = None, end: date | None = None
) -> pd.DataFrame:
    """Date × brand mention counts with every day present (zero-filled)."""
    if start is None or end is None:
        start, end = date_range(mentions)
    days = pd.date_range(start, end, freq="D").date
    if mentions.empty:
        return pd.DataFrame(0, index=pd.Index(days, name="date"), columns=brands)
    table = mentions.groupby(["date", "brand"]).size().unstack("brand", fill_value=0)
    table = table.reindex(index=days, columns=brands, fill_value=0)
    table.index.name = "date"
    return table.astype(int)


def share_of_voice(mentions: pd.DataFrame, brands: list[str]) -> pd.DataFrame:
    counts = mentions.groupby("brand").size().reindex(brands, fill_value=0)
    total = int(counts.sum())
    share = counts / total if total else counts * 0.0
    return pd.DataFrame({"brand": brands, "mentions": counts.to_numpy(int), "share": share.to_numpy(float)})


def sentiment_mix(mentions: pd.DataFrame, brands: list[str]) -> pd.DataFrame:
    """Per brand: count and share of each sentiment label, plus which scorer(s) produced them."""
    labels = SENTIMENT_ORDER + (["Unscored"] if (mentions.get("sentiment") == "Unscored").any() else [])
    rows = []
    for brand in brands:
        part = mentions.loc[mentions["brand"] == brand]
        total = len(part)
        scorers = ", ".join(sorted(part["sentiment_scorer"].dropna().astype(str).unique())) or "—"
        for label in labels:
            count = int((part["sentiment"] == label).sum())
            rows.append({"brand": brand, "sentiment": label, "mentions": count,
                         "share": count / total if total else 0.0, "scorer": scorers})
    return pd.DataFrame(rows)


def net_tone(mentions: pd.DataFrame) -> float | None:
    """(positive − negative) / all scored mentions; None without scored mentions. An indicator, not a verdict."""
    scored = mentions.loc[mentions["sentiment"].isin(SENTIMENT_ORDER)]
    if scored.empty:
        return None
    return float(((scored["sentiment"] == "Positive").sum() - (scored["sentiment"] == "Negative").sum()) / len(scored))


def top_sources(mentions: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if mentions.empty:
        return pd.DataFrame(columns=["source", "mentions", "brands"])
    grouped = mentions.groupby("source").agg(mentions=("article_id", "size"), brands=("brand", "nunique"))
    return grouped.sort_values("mentions", ascending=False).head(n).reset_index()


@dataclass(frozen=True)
class SpikeRule:
    threshold: float = SPIKE_THRESHOLD
    window_days: int = SPIKE_WINDOW_DAYS
    min_history_days: int = SPIKE_MIN_HISTORY_DAYS
    min_count: int = SPIKE_MIN_COUNT
    min_sd: float = SPIKE_MIN_SD

    def describe(self) -> str:
        return (
            f"A day is flagged when its mention count is at least {self.min_count} and its z-score is at least "
            f"{self.threshold:g}. z = (count − mean) / SD of the previous {self.window_days} days (that day excluded; "
            f"at least {self.min_history_days} days of history; SD floored at {self.min_sd:g} so quiet brands do not "
            "spike on a single extra mention)."
        )


def spike_scores(daily: pd.DataFrame, rule: SpikeRule = SpikeRule(), coverage_start: date | None = None) -> pd.DataFrame:
    """Long table: date, brand, count, baseline mean, baseline SD, z-score, spike flag.

    Days before ``coverage_start`` (the first collection run) hold only whatever the feeds still carried, so
    they are excluded from baselines and never scored.
    """
    frames = []
    uncovered = np.array([day < coverage_start for day in daily.index]) if coverage_start else None
    for brand in daily.columns:
        counts = daily[brand].astype(float)
        if uncovered is not None:
            counts = counts.mask(uncovered)
        history = counts.shift(1).rolling(rule.window_days, min_periods=rule.min_history_days)
        mean = history.mean()
        sd = history.std(ddof=1)
        sd_used = np.maximum(sd.fillna(0.0), rule.min_sd)
        z = (counts - mean) / sd_used
        frames.append(
            pd.DataFrame(
                {
                    "date": daily.index,
                    "brand": brand,
                    "count": daily[brand].astype(int).to_numpy(),
                    "baseline_mean": mean.to_numpy(),
                    "baseline_sd": sd.to_numpy(),
                    "z": z.to_numpy(),
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=["date", "brand", "count", "baseline_mean", "baseline_sd", "z", "spike"])
    scores = pd.concat(frames, ignore_index=True)
    scores["spike"] = (scores["z"] >= rule.threshold) & (scores["count"] >= rule.min_count) & scores["z"].notna()
    return scores


def detect_spikes(daily: pd.DataFrame, rule: SpikeRule = SpikeRule(), coverage_start: date | None = None) -> pd.DataFrame:
    scores = spike_scores(daily, rule, coverage_start)
    return scores.loc[scores["spike"]].sort_values(["date", "z"], ascending=[False, False]).reset_index(drop=True)


@dataclass(frozen=True)
class WeekWindow:
    this_start: date
    this_end: date
    prev_start: date
    prev_end: date

    @classmethod
    def ending(cls, end: date) -> "WeekWindow":
        return cls(end - timedelta(days=6), end, end - timedelta(days=13), end - timedelta(days=7))

    def label(self) -> str:
        return (
            f"{self.this_start:%d.%m}–{self.this_end:%d.%m.%Y} vs {self.prev_start:%d.%m}–{self.prev_end:%d.%m.%Y}"
        )


def _between(mentions: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    return mentions.loc[(mentions["date"] >= start) & (mentions["date"] <= end)]


def weekly_change(
    mentions: pd.DataFrame,
    brands: list[str],
    window: WeekWindow,
    rule: SpikeRule = SpikeRule(),
    coverage_start: date | None = None,
) -> pd.DataFrame:
    """Per brand: last 7 days vs the 7 days before (mentions, share of voice, tone, spikes).

    ``prev_week_covered`` is False when collection started after the previous week began; the change columns
    are then left empty, because the previous week's count reflects only what the feeds still carried.
    """
    covered = coverage_start is None or coverage_start <= window.prev_start
    this = _between(mentions, window.this_start, window.this_end)
    prev = _between(mentions, window.prev_start, window.prev_end)
    start = window.this_end - timedelta(days=rule.window_days + 13)
    daily = daily_counts(mentions, brands, start, window.this_end)
    spikes = detect_spikes(daily, rule, coverage_start)
    spikes = spikes.loc[(spikes["date"] >= window.this_start) & (spikes["date"] <= window.this_end)]
    total_this, total_prev = len(this), len(prev)
    rows = []
    for brand in brands:
        b_this = this.loc[this["brand"] == brand]
        b_prev = prev.loc[prev["brand"] == brand]
        n_this, n_prev = len(b_this), len(b_prev)
        brand_spikes = spikes.loc[spikes["brand"] == brand]
        rows.append(
            {
                "brand": brand,
                "mentions_this_week": n_this,
                "mentions_prev_week": n_prev,
                "prev_week_covered": covered,
                "change": n_this - n_prev if covered else None,
                "change_pct": (n_this - n_prev) / n_prev if covered and n_prev else None,
                "sov_this_week": n_this / total_this if total_this else 0.0,
                "sov_prev_week": n_prev / total_prev if total_prev else 0.0,
                "negative_share_this_week": float((b_this["sentiment"] == "Negative").mean()) if n_this else None,
                "negative_share_prev_week": float((b_prev["sentiment"] == "Negative").mean()) if n_prev else None,
                "net_tone_this_week": net_tone(b_this),
                "net_tone_prev_week": net_tone(b_prev),
                "spike_days": ", ".join(f"{d:%d.%m}" for d in sorted(brand_spikes["date"])),
                "max_z": float(brand_spikes["z"].max()) if not brand_spikes.empty else None,
                "top_source_this_week": b_this["source"].mode().iat[0] if n_this else "",
            }
        )
    return pd.DataFrame(rows)


def change_headlines(change: pd.DataFrame, rule: SpikeRule = SpikeRule()) -> list[str]:
    """Plain-language bullet points for the 'what changed' panel."""
    notes: list[str] = []
    for row in change.itertuples(index=False):
        if row.spike_days:
            notes.append(
                f"**{row.brand}**: spike on {row.spike_days} (max z = {row.max_z:.1f}; threshold {rule.threshold:g})."
            )
        if not row.prev_week_covered:
            continue  # comparisons with a partly collected week would report collection gaps as news
        if row.mentions_prev_week and row.change_pct is not None and abs(row.change_pct) >= 0.5 and abs(row.change) >= 5:
            direction = "up" if row.change > 0 else "down"
            notes.append(
                f"**{row.brand}**: mentions {direction} {abs(row.change_pct):.0%} "
                f"({row.mentions_prev_week} → {row.mentions_this_week})."
            )
        elif not row.mentions_prev_week and row.mentions_this_week >= 5:
            notes.append(f"**{row.brand}**: {row.mentions_this_week} mentions this week after none the week before.")
        neg_now, neg_before = row.negative_share_this_week, row.negative_share_prev_week
        if neg_now is not None and neg_before is not None and row.mentions_this_week >= 5 and neg_now - neg_before >= 0.15:
            notes.append(
                f"**{row.brand}**: negative share rose from {neg_before:.0%} to {neg_now:.0%} "
                "(headline tone, not tone towards the brand)."
            )
    return notes


def coverage_note(window: WeekWindow, coverage_start: date | None) -> str | None:
    """Explain why week-over-week comparisons are unavailable when collection began recently."""
    if coverage_start is None or coverage_start <= window.prev_start:
        return None
    ready = coverage_start + timedelta(days=13)
    return (
        f"Collection started on {coverage_start:%d.%m.%Y}. Items published before that date are only what the feeds "
        f"still carried, so week-over-week changes and spike baselines need two full collected weeks "
        f"(first complete comparison: week ending {ready:%d.%m.%Y})."
    )
