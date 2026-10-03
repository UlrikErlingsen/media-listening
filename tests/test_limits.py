"""No limits locally, demo caps with SIGNAL_PUBLIC=1, upload settings, full exports and English app text."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from listensignal import limits
from listensignal.analysis import mention_table
from listensignal.demo import DEMO_BRANDS, DEMO_NOTICE, make_demo_articles
from listensignal.errors import friendly_message
from listensignal.matching import match_brands
from listensignal.pulse import build_pulse, pulse_xlsx
from listensignal.workspace import demo_workspace

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")


def _brands_yaml(count: int) -> str:
    return "brands:\n" + "\n".join(
        f"  - name: Brand{n}\n    aliases: [Brand{n}]\n    role: {'own' if n == 0 else 'competitor'}" for n in range(count)
    )


def _apply_brands(text: str) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=180)
    app.run()
    app.switch_page("pages/sources.py")
    app.run()
    next(area for area in app.text_area if area.label == "Brand list (YAML)").set_value(text)
    next(button for button in app.button if button.label == "Apply for this session").click().run()
    return app


def test_local_mode_has_no_limits() -> None:
    assert not limits.is_public()
    assert limits.max_brands() is None and limits.max_brand_yaml_chars() is None and limits.max_sample_chars() is None
    assert limits.collection_allowed()


def test_local_mode_accepts_more_brands_than_the_demo_cap() -> None:
    app = _apply_brands(_brands_yaml(limits.DEMO_MAX_BRANDS + 2))
    assert not app.exception, [e.value for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    assert app.session_state["listen:custom_brands_demo"].count("- name:") == limits.DEMO_MAX_BRANDS + 2


@pytest.mark.parametrize("variable", ["SIGNAL_PUBLIC", "LISTENSIGNAL_PUBLIC_DEMO"])
def test_public_demo_enforces_its_caps(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv(variable, "1")
    assert limits.is_public() and not limits.collection_allowed()
    app = _apply_brands(_brands_yaml(limits.DEMO_MAX_BRANDS + 2))
    assert any("at most 12 brands here" in str(e.value) and "downloaded app has no such limit" in str(e.value)
               for e in app.error)


def test_memory_errors_become_a_plain_message() -> None:
    assert "not enough memory" in friendly_message(MemoryError())


def test_prefiltered_matching_finds_exactly_what_item_by_item_matching_finds() -> None:
    articles = make_demo_articles()
    extra = articles.head(50).copy()
    extra["article_id"] = extra["article_id"].astype(str) + "-x"
    extra["title"] = "Ingen merkevare her " + extra["article_id"].astype(str)
    extra["summary"] = "Fjell brus og kyst kraft, men ikke navnene."
    corpus = pd.concat([articles, extra], ignore_index=True)
    table = mention_table(corpus, DEMO_BRANDS)
    expected = [
        (article_id, name)
        for article_id, title, summary in zip(corpus["article_id"], corpus["title"].fillna(""), corpus["summary"].fillna(""))
        for name in match_brands(f"{title} \n {summary}", DEMO_BRANDS)
    ]
    assert sorted(zip(table["article_id"], table["brand"])) == sorted(expected)


def test_pulse_workbook_lists_every_mention_of_the_week() -> None:
    report = build_pulse(demo_workspace())
    assert len(report.latest) == len(report.latest.drop_duplicates()) > 0
    workbook = pd.read_excel(pd.io.common.BytesIO(pulse_xlsx(report)), sheet_name="Mentions")
    assert len(workbook) == len(report.latest)


def test_upload_cap_is_10000_mb_in_config_launchers_and_docker() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    windows = (ROOT / "run_app.bat").read_text(encoding="utf-8")
    mac = (ROOT / "run_app.command").read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "maxUploadSize = 10000" in config
    assert "set LISTENSIGNAL_MAX_UPLOAD_MB=10000" in windows
    assert "--server.maxUploadSize=%LISTENSIGNAL_MAX_UPLOAD_MB%" in windows
    assert '--server.maxUploadSize="${LISTENSIGNAL_MAX_UPLOAD_MB:-10000}"' in mac
    assert "STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10000" in docker
    assert "--server.maxUploadSize" not in docker


def test_demo_notice_explains_the_norwegian_headlines_in_english() -> None:
    assert "headlines are in Norwegian because Listen Signal analyses Norwegian-language media" in DEMO_NOTICE
