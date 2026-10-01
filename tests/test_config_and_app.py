from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from listensignal.config import load_brands, load_sources

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")
PAGES = ["overview", "what_changed", "mentions", "topics", "pulse", "sources", "methods"]


def test_seeded_sources_are_verified_and_at_least_five_enabled():
    config = load_sources(ROOT / "sources.yaml")
    enabled = config.enabled
    assert len(enabled) >= 5
    assert all(source.verified for source in config.sources)
    assert all(source.note for source in config.sources if not source.enabled)
    names = {s.name for s in config.sources}
    assert {"NRK toppsaker", "Reddit r/norge", "Google News (no)"} <= names
    google = next(s for s in config.sources if s.name == "Google News (no)")
    assert "hl=no" in google.url and "gl=NO" in google.url
    assert config.min_interval_minutes >= 30


def test_example_brands_file_is_valid_and_shows_exclusions():
    brands = load_brands(ROOT / "brands.yaml")
    assert any(b.role == "own" for b in brands)
    tine = next(b for b in brands if b.name == "Tine")
    assert "Tine Sundt" in tine.exclude


def _run(page: str | None = None) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=180)
    app.run()
    if page:
        app.switch_page(f"pages/{page}.py")
        app.run()
    return app


def test_app_opens_on_the_fictional_demo():
    app = _run()
    assert not app.exception, [e.value for e in app.exception]
    body = "\n".join(str(m.value) for m in app.markdown)
    assert "Fictional demo." in body
    assert "Who is talking about the brand" in body
    assert "ListenSignal v1.0.0" in body and "AGPL-3.0-or-later" in body
    assert app.sidebar.radio[0].value == "demo"


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_error(page):
    app = _run(page)
    assert not app.exception, [e.value for e in app.exception]
    assert not app.error, [e.value for e in app.error]


def test_what_changed_shows_rule_and_spike():
    app = _run("what_changed")
    body = "\n".join(str(m.value) for m in app.markdown)
    assert "z-score is at least 3" in body
    assert "Fjellbrus: spike on 22.09" in body


def test_app_source_keeps_suite_shell_and_accessibility():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert ":focus-visible" in source and "@media (max-width:760px)" in source
    assert "prefers-reduced-motion" in source and "show_error" in source
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in config
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER listensignal" in docker and "HEALTHCHECK" in docker
    launcher = (ROOT / "run_app.bat").read_text(encoding="utf-8")
    assert "--browser.gatherUsageStats=false" in launcher and "LISTENSIGNAL_PORT" in launcher
