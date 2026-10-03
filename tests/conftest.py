from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _local_mode(monkeypatch):
    """Tests run as the downloaded app does (no demo limits) unless a test opts into a public demo itself."""
    monkeypatch.delenv("SIGNAL_PUBLIC", raising=False)
    monkeypatch.delenv("LISTENSIGNAL_PUBLIC_DEMO", raising=False)
