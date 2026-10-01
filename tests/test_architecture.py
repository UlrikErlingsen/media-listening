"""Architecture rules for Signal Hub: the package is UI-free except src/listensignal/ui/, and storage sits behind one
module."""

import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest

import listensignal

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
UI = SRC / "listensignal" / "ui"  # the one place under src/ allowed to import Streamlit (Signal Hub contract)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _core_files() -> list[Path]:
    return [path for path in SRC.rglob("*.py") if UI not in path.parents]


def test_no_file_under_src_imports_streamlit_except_ui():
    offenders = [
        str(path.relative_to(ROOT))
        for path in _core_files()
        if any(name == "streamlit" or name.startswith("streamlit.") for name in _imports(path))
    ]
    assert offenders == [], f"Streamlit imported inside the package outside ui/: {offenders}"
    # Also catch dynamic imports such as importlib.import_module("streamlit").
    for path in _core_files():
        assert "import_module(\"streamlit" not in path.read_text(encoding="utf-8")
    # Nothing in the core may reach into ui/ either, so the analysis stays importable without Streamlit.
    for path in _core_files():
        assert not any(name.startswith("listensignal.ui") for name in _imports(path)), path
        assert "from .ui" not in path.read_text(encoding="utf-8"), path


def test_core_package_imports_without_streamlit():
    code = (
        "import sys; sys.modules['streamlit'] = None; "
        "import listensignal, listensignal.analysis, listensignal.collect, listensignal.pulse, listensignal.topics"
    )
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_only_storage_module_touches_sqlite():
    users = sorted(path.name for path in SRC.rglob("*.py") if "sqlite3" in _imports(path))
    assert users == ["storage.py"]
    collect_source = (SRC / "listensignal" / "collect.py").read_text(encoding="utf-8")
    assert "execute(" not in collect_source  # collect only passes connections through to storage


def test_public_api_resolves_every_name():
    for name in listensignal.__all__:
        assert getattr(listensignal, name) is not None, name


def test_streamlit_code_lives_only_in_app_and_pages():
    ui_files = {path.relative_to(ROOT).as_posix() for path in ROOT.glob("*.py")} | {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "pages").glob("*.py")
    }
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv", "build", "src/", "tests/", "scripts/")):
            continue
        assert rel in ui_files, rel


def test_package_is_pip_installable_metadata():
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["name"] == "listensignal"
    assert project["license"] == "AGPL-3.0-or-later"
    assert project["authors"] == [{"name": "Ulrik Erlingsen"}]
    assert project["version"] == listensignal.__version__
    assert "sentiment" in project["optional-dependencies"]
    assert not any(dep.startswith(("torch", "transformers")) for dep in project["dependencies"])
