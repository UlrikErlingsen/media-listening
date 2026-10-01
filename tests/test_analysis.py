from datetime import date, timedelta

import numpy as np
import pandas as pd

from listensignal.analysis import (
    SpikeRule,
    WeekWindow,
    change_headlines,
    coverage_note,
    daily_counts,
    detect_spikes,
    net_tone,
    share_of_voice,
    spike_scores,
    weekly_change,
)

START = date(2026, 8, 1)


def _daily(values, brand="A"):
    index = [START + timedelta(days=i) for i in range(len(values))]
    return pd.DataFrame({brand: values}, index=pd.Index(index, name="date"))


def _mentions(counts: dict[str, list[int]], sentiment="Neutral"):
    rows = []
    for brand, values in counts.items():
        for offset, n in enumerate(values):
            rows += [
                {"article_id": len(rows) + i + 1, "brand": brand, "date": START + timedelta(days=offset),
                 "sentiment": sentiment, "source": "S"}
                for i in range(n)
            ]
    return pd.DataFrame(rows)


def test_spike_is_flagged_on_engineered_day_only():
    values = [2, 3, 4, 3] * 10  # steady baseline around 3 per day
    values[35] = 20
    spikes = detect_spikes(_daily(values))
    assert list(spikes["date"]) == [START + timedelta(days=35)]
    assert spikes["z"].iat[0] >= SpikeRule().threshold


def test_spike_rule_respects_min_count_threshold_and_history():
    flat = [1] * 30 + [4]
    assert detect_spikes(_daily(flat)).empty  # z = 3 but only 4 mentions (< 5)
    assert not detect_spikes(_daily(flat), SpikeRule(min_count=3)).empty
    scores = spike_scores(_daily([0, 0, 0, 9] + [0] * 12))
    assert scores["z"].iloc[:14].isna().all()  # needs 14 days of history
    assert not detect_spikes(_daily([2] * 30 + [7]), SpikeRule(threshold=4.0)).empty
    assert detect_spikes(_daily([2] * 30 + [7]), SpikeRule(threshold=6.0)).empty


def test_sd_floor_stops_quiet_brands_spiking_on_one_mention():
    scores = spike_scores(_daily([0] * 30 + [1]))
    assert scores["z"].iat[-1] == 1.0  # (1 - 0) / SD floor of 1


def test_days_before_coverage_start_are_not_scored_or_used_as_baseline():
    values = [0] * 20 + [6] * 3
    scores = spike_scores(_daily(values), coverage_start=START + timedelta(days=20))
    assert scores["z"].isna().all()
    assert scores["count"].tolist() == values  # counts are still reported


def test_daily_counts_zero_fill_and_share_of_voice():
    mentions = _mentions({"A": [2, 0, 1], "B": [0, 0, 3]})
    daily = daily_counts(mentions, ["A", "B", "C"])
    assert daily.shape == (3, 3)
    assert daily["C"].sum() == 0 and daily.loc[START + timedelta(days=1)].sum() == 0
    sov = share_of_voice(mentions, ["A", "B", "C"])
    assert np.isclose(sov["share"].sum(), 1.0) and sov.set_index("brand").at["A", "mentions"] == 3


def test_net_tone_range():
    assert net_tone(pd.DataFrame({"sentiment": ["Positive", "Positive", "Negative", "Neutral"]})) == 0.25
    assert net_tone(pd.DataFrame({"sentiment": ["Unscored"]})) is None


def test_weekly_change_and_notes():
    mentions = _mentions({"A": [1] * 21 + [6] * 7, "B": [2] * 28})
    window = WeekWindow.ending(START + timedelta(days=27))
    change = weekly_change(mentions, ["A", "B"], window)
    by_brand = change.set_index("brand")
    assert by_brand.at["A", "mentions_this_week"] == 42 and by_brand.at["A", "mentions_prev_week"] == 7
    assert by_brand.at["B", "change"] == 0
    notes = change_headlines(change)
    assert any("mentions up" in note and "**A**" in note for note in notes)
    assert not any("**B**" in note for note in notes)


def test_weekly_change_suppressed_when_previous_week_not_collected():
    mentions = _mentions({"A": [0] * 21 + [6] * 7})
    window = WeekWindow.ending(START + timedelta(days=27))
    coverage = START + timedelta(days=24)
    change = weekly_change(mentions, ["A"], window, coverage_start=coverage)
    assert not change["prev_week_covered"].iat[0]
    assert change["change"].isna().all()
    assert change_headlines(change) == []
    assert "Collection started" in coverage_note(window, coverage)
    assert coverage_note(window, START) is None
