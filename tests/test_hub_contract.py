"""Signal Hub contract: importable UI entry point, Streamlit only under ui/, slug-namespaced state, and hub mode
(SIGNAL_HUB=1): fictional demo only, nothing written to disk, no outbound network requests."""

import ast
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import urllib.request

import pytest
from streamlit.testing.v1 import AppTest

from listensignal import __version__

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "listensignal"
UI = PACKAGE / "ui"
UI_ONLY_LIBRARIES = {"streamlit", "plotly"}
CORE_MODULES = (
    "listensignal", "listensignal.analysis", "listensignal.collect", "listensignal.config", "listensignal.demo",
    "listensignal.errors", "listensignal.matching", "listensignal.pulse", "listensignal.sentiment",
    "listensignal.storage", "listensignal.topics", "listensignal.workspace",
)
PAGES = ["overview", "what_changed", "brand", "mentions", "topics", "pulse", "sources", "methods"]
# Files a normal (non-editable) install ships: every module plus the declared package data.
PACKAGE_DATA = ("lexicon/*.txt", "seed_sources.yaml", "ui/assets/marks/*")
RENDER_SCRIPT = """
from listensignal.ui import render

render()
"""
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _render_app(timeout: int = 180) -> AppTest:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=timeout)
    app.run()
    return app


def _page_radio(app: AppTest):
    return next(radio for radio in app.sidebar.radio if radio.key == "listen:page")


# ------------------------------------------------------------------------------------------------ contract


def test_ui_entry_point_matches_the_hub_contract() -> None:
    from listensignal.ui import APP_INFO, render

    assert callable(render)
    assert APP_INFO == {"product": "Listen Signal", "version": __version__, "repo": "media-listening", "slug": "listen"}


def test_only_the_ui_package_imports_streamlit_or_plotly() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): sorted(_imported_roots(path) & UI_ONLY_LIBRARIES)
        for path in PACKAGE.rglob("*.py")
        if UI not in path.parents and _imported_roots(path) & UI_ONLY_LIBRARIES
    }
    assert not offenders, offenders


def test_core_package_imports_without_streamlit_or_plotly() -> None:
    # A fresh interpreter, so modules already imported by other tests cannot hide a stray import.
    code = (
        f"import sys\nsys.path.insert(0, {str(ROOT / 'src')!r})\n"
        f"import importlib\nfor name in {CORE_MODULES!r}:\n    importlib.import_module(name)\n"
        "loaded = sorted(name for name in ('streamlit', 'plotly') if name in sys.modules)\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr


def test_render_never_sets_page_config_navigation_or_stop() -> None:
    for path in UI.rglob("*.py"):
        if path.name in ("signal_theme.py", "signal_font.py"):
            continue
        source = path.read_text(encoding="utf-8")
        for call in ("st.set_page_config(", "st.navigation(", "st.Page(", "st.stop("):
            assert call not in source, (path.name, call)


def test_standalone_pages_are_thin_wrappers_over_the_package() -> None:
    from listensignal.ui.app import PAGES as REGISTRY

    assert [page.slug for page in REGISTRY] == PAGES
    for slug in PAGES:
        wrapper = (ROOT / "pages" / f"{slug}.py").read_text(encoding="utf-8")
        assert f"from listensignal.ui.pages import {slug}\n" in wrapper and f"{slug}.show()" in wrapper
        assert len(wrapper.splitlines()) <= 6, slug
    assert not (ROOT / "pages" / "_ui.py").exists()


def test_render_runs_from_a_script_without_set_page_config() -> None:
    app = _render_app()

    assert not app.exception, [error.value for error in app.exception]
    assert _page_radio(app).value == "overview"
    assert "listen:period" in app.session_state and "period" not in app.session_state
    assert "listen:data_mode" in app.session_state and "data_mode" not in app.session_state
    body = "\n".join(str(item.value) for item in app.markdown)
    assert "Who is talking about the brand" in body and "Fictional demo." in body
    assert f"Listen Signal v{__version__}" in body
    assert "sg-mast" in body and "sg-foot" in body


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_and_every_widget_key_is_namespaced(page: str) -> None:
    app = _render_app()
    _page_radio(app).set_value(page).run()

    assert not app.exception, [error.value for error in app.exception]
    assert not app.error, [error.value for error in app.error]
    widgets = [
        *app.radio, *app.selectbox, *app.multiselect, *app.slider, *app.date_input, *app.text_input,
        *app.text_area, *app.button, *app.checkbox,
    ]
    assert widgets
    unkeyed = [(type(widget).__name__, widget.label) for widget in widgets if widget.key is None]
    assert not unkeyed, unkeyed
    assert all(widget.key.startswith("listen:") for widget in widgets), [w.key for w in widgets]
    assert all(str(key).startswith("listen:") for key in list(app.session_state)), app.session_state


def test_session_state_and_widget_keys_go_through_the_namespace_helper() -> None:
    sources = {path: path.read_text(encoding="utf-8") for path in UI.rglob("*.py")
               if path.name not in ("signal_theme.py", "signal_font.py")}
    allowed_names = {"key", "editor_key", "custom_brands_key("}  # built with k() in common.custom_brands_key
    for path, source in sources.items():
        state_keys = re.findall(r"session_state(?:\[|\.get\(|\.pop\()\s*([^,\])]+)", source)
        widget_keys = re.findall(r"\bkey=([^,)\n]+)", source)
        bad = [key for key in state_keys + widget_keys if not key.startswith("k(") and key not in allowed_names]
        assert not bad, (path.name, bad)
    common = (UI / "common.py").read_text(encoding="utf-8")
    assert 'NS = "listen"' in common and 'return k(f"custom_brands_{data_mode()}")' in common


# ------------------------------------------------------------------------------------------------ hub mode


def _forbid(*_args, **_kwargs):
    raise AssertionError("Outbound network or disk access attempted in Signal Hub mode")


@pytest.fixture
def hub(monkeypatch):
    """SIGNAL_HUB=1 with every network path and every local-database path rigged to fail the test."""
    import feedparser

    import listensignal.collect as collect
    import listensignal.ui.common as common
    import listensignal.workspace as workspace

    monkeypatch.setenv("SIGNAL_HUB", "1")
    monkeypatch.delenv("LISTENSIGNAL_PUBLIC_DEMO", raising=False)
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOOPBACK:
            _forbid()
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", _forbid)
    monkeypatch.setattr(urllib.request, "urlopen", _forbid)
    monkeypatch.setattr(feedparser, "parse", _forbid)
    monkeypatch.setattr(collect, "run", _forbid)
    monkeypatch.setattr(collect, "http_fetch", _forbid)
    try:
        import requests

        monkeypatch.setattr(requests.Session, "request", _forbid)
    except ImportError:
        pass
    monkeypatch.setattr(workspace, "connect", _forbid)  # the only route to the SQLite database
    monkeypatch.setattr(common, "database_workspace", _forbid)
    monkeypatch.setattr(common, "database_has_items", _forbid)


@pytest.mark.parametrize("page", PAGES)
def test_hub_mode_renders_every_page_without_network_or_database(hub, page: str) -> None:
    app = _render_app()
    _page_radio(app).set_value(page).run()

    assert not app.exception, [error.value for error in app.exception]
    assert not app.error, [error.value for error in app.error]
    assert [radio.key for radio in app.sidebar.radio] == ["listen:page"]  # no switch to a local database
    sidebar = "\n".join(str(item.value) for item in app.sidebar.caption)
    assert "Live feed collection is off in Signal Hub" in sidebar
    if page not in ("sources", "methods"):
        body = "\n".join(str(item.value) for item in app.markdown)
        assert "Fictional demo." in body


def test_hub_mode_sources_page_switches_collection_off_and_uses_the_packaged_feed_list(hub, monkeypatch) -> None:
    import listensignal.ui.pages.sources as sources_page
    from listensignal.config import SEED_SOURCES

    read: list[Path] = []
    original = sources_page.load_sources
    monkeypatch.setattr(sources_page, "load_sources", lambda path: read.append(Path(path)) or original(path))
    monkeypatch.setattr(sources_page, "norbert_available", _forbid)  # no torch import in the Hub
    app = _render_app()
    _page_radio(app).set_value("sources").run()

    assert not app.exception, [error.value for error in app.exception]
    assert read == [SEED_SOURCES]
    assert not [button for button in app.button if button.label == "Fetch enabled feeds"]
    body = "\n".join(str(item.value) for item in app.markdown)
    assert "Live feed collection is off in Signal Hub." in body
    assert any("lexicon scorer" in str(caption.value) for caption in app.caption)


def test_hub_mode_session_brand_editor_stays_in_memory(hub) -> None:
    app = _render_app()
    _page_radio(app).set_value("sources").run()
    app.text_area(key="listen:custom_brands_demo_editor").set_value(
        "brands:\n  - name: Turisme\n    role: own\n    aliases: [turistene, hotellene]\n"
    ).run()
    next(b for b in app.button if b.key == "listen:brands_apply").click().run()

    assert not app.exception, [e.value for e in app.exception]
    assert "Turisme" in app.session_state["listen:custom_brands_demo"]
    assert "Turisme" in app.dataframe[0].value["brand"].tolist()


def test_packaged_seed_sources_match_the_project_file() -> None:
    from listensignal.config import SEED_SOURCES

    project = (ROOT / "sources.yaml").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert SEED_SOURCES.read_text(encoding="utf-8").replace("\r\n", "\n") == project
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'listensignal = ["lexicon/*.txt", "seed_sources.yaml"]' in pyproject
    assert '"listensignal.ui" = ["assets/marks/*"]' in pyproject


HUB_SCRIPT = r'''
import socket, sys, urllib.request
sys.dont_write_bytecode = True
sys.path.insert(0, SITE)
from pathlib import Path


def forbid(*args, **kwargs):
    raise RuntimeError("network access attempted in Signal Hub mode")


original_connect = socket.socket.connect


def guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in ("127.0.0.1", "::1", "localhost"):
        forbid()
    return original_connect(self, address)


socket.socket.connect = guarded_connect
socket.create_connection = forbid
urllib.request.urlopen = forbid
import feedparser
feedparser.parse = forbid
try:
    import requests
    requests.Session.request = forbid
except ImportError:
    pass

from streamlit.testing.v1 import AppTest
import listensignal
assert Path(listensignal.__file__).is_relative_to(SITE), listensignal.__file__
from listensignal.ui import signal_theme as sig
assert Path(sig.page_config("listen")["page_icon"]).exists()

app = AppTest.from_string("from listensignal.ui import render\nrender()\n", default_timeout=180)
app.run()
assert not app.exception, [e.value for e in app.exception]
for page in PAGES:
    radio = next(r for r in app.sidebar.radio if r.key == "listen:page")
    radio.set_value(page).run()
    assert not app.exception, (page, [e.value for e in app.exception])
    assert not app.error, (page, [e.value for e in app.error])
print("rendered", len(PAGES), "pages")
'''


def test_hub_mode_renders_from_the_packaged_files_and_writes_nothing(tmp_path: Path) -> None:
    # Signal Hub installs the release as a normal package: only src/listensignal/**/*.py and the declared package
    # data exist there, so render() must not read sources.yaml, brands.yaml, data/ or assets/ at the repo root.
    site = tmp_path / "site"
    for path in PACKAGE.rglob("*"):
        relative = path.relative_to(PACKAGE)
        packaged = path.suffix == ".py" or any(relative.match(pattern) for pattern in PACKAGE_DATA)
        if path.is_file() and packaged and "__pycache__" not in relative.parts:
            target = site / "listensignal" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    shipped = sorted(p.relative_to(site) for p in site.rglob("*"))
    work, home = tmp_path / "work", tmp_path / "home"
    work.mkdir()
    home.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith(("LISTENSIGNAL_", "XDG_"))}
    env.update(
        SIGNAL_HUB="1", PYTHONDONTWRITEBYTECODE="1", HOME=str(home), USERPROFILE=str(home),
        APPDATA=str(home / "AppData" / "Roaming"), LOCALAPPDATA=str(home / "AppData" / "Local"),
        XDG_CONFIG_HOME=str(home / ".config"), XDG_CACHE_HOME=str(home / ".cache"),
        XDG_DATA_HOME=str(home / ".local" / "share"), HF_HOME=str(home / "hf"),
    )
    code = f"SITE = {str(site)!r}\nPAGES = {PAGES!r}\n" + HUB_SCRIPT
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600, cwd=work,
                            env=env)

    assert result.returncode == 0, result.stderr[-4000:]
    assert f"rendered {len(PAGES)} pages" in result.stdout
    assert list(work.rglob("*")) == [], "files written to the working directory"
    assert list(home.rglob("*")) == [], "files written to the home / app-data directories"
    assert sorted(p.relative_to(site) for p in site.rglob("*")) == shipped, "files written inside the package"
