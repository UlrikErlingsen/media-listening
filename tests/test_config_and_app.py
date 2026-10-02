from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from listensignal import __version__
from listensignal.config import load_brands, load_sources

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")
UI = ROOT / "src" / "listensignal" / "ui"
PAGES = ["overview", "what_changed", "brand", "mentions", "topics", "pulse", "sources", "methods"]


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
    assert f"Listen Signal v{__version__}" in body and "AGPL-3.0-or-later" in body
    assert "counts what feeds published, not what people think" in body
    assert "LISTEN → COMPARE → FLAG" in body
    assert "sg-mast" in body and "sg-hero" in body and "sg-foot" in body  # the shared Signal shell
    sidebar = "\n".join(str(m.value) for m in app.sidebar.markdown)
    assert "sg-side" in sidebar and "Norwegian media listening without the monitoring subscription." in sidebar
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
    assert "<strong>Fjellbrus</strong>: spike on 22.09" in body


def test_app_uses_shared_signal_theme_and_keeps_accessibility():
    standalone = (ROOT / "app.py").read_text(encoding="utf-8")
    # The page code lives in the package (listensignal.ui), so Signal Hub's render() and app.py share it.
    pages = "\n".join(path.read_text(encoding="utf-8") for path in sorted(UI.rglob("*.py"))
                      if path.name not in ("signal_theme.py", "signal_font.py"))
    theme = (UI / "signal_theme.py").read_text(encoding="utf-8")
    assert 'st.set_page_config(**sig.page_config(NS, "Norwegian media listening"))' in standalone
    assert "sig.apply(NS)" in standalone and "show_error" in standalone
    assert "sig.apply(NS)" in pages and "show_error" in pages  # render() in listensignal.ui.app
    assert "from listensignal.ui import signal_theme as sig" in standalone
    assert 'NS = "listen"' in pages and "sig.template(NS)" in pages
    assert "sig.chart(NS, " in pages and "st.plotly_chart" not in pages  # theme=None + per-app template
    assert "<style>" not in standalone + pages
    for old_colour in ("#173c3a", "#d95b40", "#83d2b4", "#f2c66d", "#17322e", "#102c2a", "#2a78d6", "#e34948"):
        assert old_colour not in (standalone + pages).lower(), old_colour
    assert (UI / "assets" / "marks" / "listensignal-mark-64.png").exists()
    assert ":focus-visible" in theme and "@media (max-width:760px)" in theme
    assert "@media (prefers-reduced-motion:reduce)" in theme
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in config
    assert 'primaryColor = "#728157"' in config  # Signal Market family, 600 step
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER listensignal" in docker and "HEALTHCHECK" in docker
    launcher = (ROOT / "run_app.bat").read_text(encoding="utf-8")
    assert "--browser.gatherUsageStats=false" in launcher and "LISTENSIGNAL_PORT" in launcher


def test_brand_palette_comes_from_the_signal_theme():
    import listensignal.ui.common as ui
    from listensignal.ui import signal_theme as sig

    assert sig.app(ui.NS)["name"] == "Listen Signal" and sig.app(ui.NS)["family"] == "market"
    assert ui.BRAND_PALETTE[0] == sig.FAMILIES["market"]["600"] == "#728157"  # own brand = family colour
    assert set(ui.BRAND_PALETTE) <= set(sig.colorway(ui.NS))
    assert ui.SENTIMENT_COLORS["Positive"] in sig.DIVERGING and ui.SENTIMENT_COLORS["Negative"] in sig.DIVERGING


def test_readme_follows_signal_template_and_states_limits():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # Signal README template order: readers find the same section in the same place in every repo.
    sections = [
        "## Read this first", "## Scope", "## Try the demo in three minutes", "## Data contract", "## Methods",
        "## Exports", "## Run locally", "## Privacy", "## Development", "## Where this fits in Signal",
        "## References", "## Originality and license",
    ]
    positions = [readme.find(f"\n{heading}\n") for heading in sections]
    assert all(position >= 0 for position in positions), dict(zip(sections, positions))
    assert positions == sorted(positions)
    assert readme.startswith('<p align="center">\n  <img src="assets/listensignal-banner.png"')
    assert "assets/listensignal-banner.svg" not in readme
    assert "Signal-Market-728157" in readme  # family badge in the Market 600 colour
    assert "github.com/UlrikErlingsen/media-listening/actions" in readme  # tests badge
    assert "**Listen Signal**" in readme and '<img src="assets/listensignal-mark-64.png"' in readme  # suite footer
    assert "Creator Signal" not in readme
    assert "**The demo is fictional.**" in readme
    assert "has not been measured" in readme
    assert "Treat the name as provisional." in readme
    for name in ["PRIVACY.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md"]:
        assert (ROOT / name).exists()
    for image in ["screenshot-overview-charts.png", "screenshot-spikes.png"]:
        assert (ROOT / "assets" / image).exists() and f"assets/{image}" in readme
    for path in ("listensignal-banner.png", "listensignal-mark-64.png", "listensignal-social.png"):
        assert (ROOT / "assets" / path).exists()
    assert not (ROOT / "assets" / "listensignal-banner.svg").exists()


def test_issue_templates_use_display_name_and_keep_data_safety():
    templates = ROOT / ".github" / "ISSUE_TEMPLATE"
    bug = (templates / "bug_report.yml").read_text(encoding="utf-8")
    idea = (templates / "feature_request.yml").read_text(encoding="utf-8")
    config = (templates / "config.yml").read_text(encoding="utf-8")
    assert "Listen Signal" in bug and "Listen Signal" in idea
    assert "ListenSignal" not in bug + idea
    assert "required: true" in bug and "credentials" in bug
    assert "github.com/UlrikErlingsen/media-listening/blob/main/SECURITY.md" in config


def test_public_demo_mode_hides_collection(monkeypatch):
    monkeypatch.setenv("LISTENSIGNAL_PUBLIC_DEMO", "1")  # read on every rerun, so no module reload is needed
    app = _run("sources")
    assert not app.exception, [e.value for e in app.exception]
    assert not app.sidebar.radio  # no data-source switch
    assert not [b for b in app.button if b.label == "Fetch enabled feeds"]
    assert any("switched off in this public demo" in str(i.value) for i in app.info)
