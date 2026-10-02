from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from listensignal import (
    DataProblem,
    brands_to_yaml,
    demo_workspace,
    parse_brands_yaml,
    period_comparison,
    weekly_tone,
)
from listensignal.config import Brand
from listensignal.demo import DEMO_START, make_demo_articles

ROOT = Path(__file__).resolve().parents[1]
MONDAY = date(2026, 8, 3)


def _mentions(rows):
    return pd.DataFrame(rows, columns=["article_id", "brand", "date", "sentiment"])


def test_weekly_tone_buckets_monday_to_sunday():
    mentions = _mentions([
        (1, "A", MONDAY, "Positive"), (2, "A", MONDAY + timedelta(days=6), "Negative"),
        (3, "A", MONDAY + timedelta(days=7), "Positive"), (4, "B", MONDAY, "Neutral"),
    ])
    weeks = weekly_tone(mentions, ["A", "B"], MONDAY, MONDAY + timedelta(days=13))
    a = weeks.loc[weeks["brand"] == "A"].reset_index(drop=True)
    assert list(a["week"]) == [MONDAY, MONDAY + timedelta(days=7)]
    assert list(a["mentions"]) == [2, 1]
    assert a.at[0, "net_tone"] == 0.0 and a.at[1, "net_tone"] == 1.0
    b = weeks.loc[weeks["brand"] == "B"].reset_index(drop=True)
    assert b.at[1, "mentions"] == 0 and pd.isna(b.at[1, "net_tone"])


def test_period_comparison_and_coverage():
    mentions = _mentions(
        [(i, "A", MONDAY + timedelta(days=i % 14), "Positive" if i % 2 else "Neutral") for i in range(28)]
        + [(100 + i, "B", MONDAY + timedelta(days=7 + i), "Negative") for i in range(7)]
    )
    start, end = MONDAY + timedelta(days=7), MONDAY + timedelta(days=13)
    table = period_comparison(mentions, ["A", "B"], start, end).set_index("brand")
    assert table.at["A", "mentions"] == 14 and table.at["A", "mentions_before"] == 14
    assert table.at["B", "mentions_before"] == 0
    assert abs(table["sov"].sum() - 1) < 1e-9
    uncovered = period_comparison(mentions, ["A"], start, end, coverage_start=start).set_index("brand")
    assert pd.isna(uncovered.at["A", "mentions_before"]) and pd.isna(uncovered.at["A", "net_tone_before"])


def test_brand_yaml_round_trip_and_validation():
    brands = (
        Brand("Tine", ("Tine", "TINE SA"), ("Tine Sundt",), "own", case_sensitive=True),
        Brand("Q-Meieriene", ("Q-Meieriene",), (), "competitor", inflect=False),
        Brand("Synnøve Finden", ("Synnøve Finden", "Synnøve")),
    )
    assert parse_brands_yaml(brands_to_yaml(brands)) == brands
    assert "Synnøve" in brands_to_yaml(brands)  # unicode kept readable
    with pytest.raises(DataProblem):
        parse_brands_yaml("brands: [unclosed")
    with pytest.raises(DataProblem):
        parse_brands_yaml("- just a list")


def test_with_brands_rematches_the_same_items():
    ws = demo_workspace()
    custom = ws.with_brands((Brand("Turisme", ("turister", "turistene", "hotellene")),))
    assert len(custom.articles) == len(ws.articles)
    assert set(custom.mentions["brand"]) == {"Turisme"} and len(custom.mentions) > 0
    assert custom.coverage_start == ws.coverage_start == DEMO_START
    assert "custom brands" in custom.label


def test_demo_headlines_are_varied_not_suffixed():
    articles = make_demo_articles()
    suffixed = articles["title"].str.contains("oppdatert kl").mean()
    assert suffixed < 0.05


def _app() -> AppTest:
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    app.run()
    return app


def test_brand_profile_page_renders():
    app = _app()
    app.switch_page("pages/brand.py")
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    assert app.selectbox[0].value == "Fjellbrus"
    assert [m.label for m in app.metric][:3] == ["Mentions", "Share of voice", "Net tone"]


def test_session_brand_editor_rematches_every_page():
    app = _app()
    app.switch_page("pages/sources.py")
    app.run()
    app.text_area(key="listen:custom_brands_demo_editor").set_value(
        "brands:\n  - name: Turisme\n    role: own\n    aliases: [turistene, hotellene]\n"
    ).run()
    next(b for b in app.button if b.label == "Apply for this session").click().run()
    assert not app.exception, [e.value for e in app.exception]
    assert "Turisme" in app.dataframe[0].value["brand"].tolist()
    app.switch_page("pages/overview.py")
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("Turisme share of voice" == m.label for m in app.metric)
    captions = "\n".join(str(c.value) for c in app.caption)
    assert "Custom brand list active" in captions
