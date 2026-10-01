"""Architecture rules for the future Signal Hub: the package is UI-free and storage sits behind one module."""

import ast
from pathlib import Path
import pytest

import listensignal

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_no_file_under_src_imports_streamlit():
    offenders = [
        str(path.relative_to(ROOT))
        for path in SRC.rglob("*.py")
        if any(name == "streamlit" or name.startswith("streamlit.") for name in _imports(path))
    ]
    assert offenders == [], f"Streamlit imported inside the package: {offenders}"
    # Also catch dynamic imports such as importlib.import_module("streamlit").
    for path in SRC.rglob("*.py"):
        assert "import_module(\"streamlit" not in path.read_text(encoding="utf-8")


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
