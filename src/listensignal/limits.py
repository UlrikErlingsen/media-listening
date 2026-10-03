"""Data limits: none when Listen Signal runs locally; hard caps only in a public demo.

Run on someone's own computer (standalone, a local Signal Hub, or an internal company deployment), the app has no
built-in limit on the number of stored items, brands, or the text you paste: memory and disk are the limit. A public
demo sets ``SIGNAL_PUBLIC=1`` (Signal Hub's public Docker image does; the older ``LISTENSIGNAL_PUBLIC_DEMO=1`` still
works), and then the caps below protect the shared server. Every cap lives in this module and is read at call time.

``collect.MAX_FEED_BYTES`` is a network guard for a single RSS response, not a data limit, so it stays in collect.py.
"""

from __future__ import annotations

import os

DEMO_MAX_BRANDS = 12
DEMO_MAX_BRAND_YAML_CHARS = 20_000
DEMO_MAX_SAMPLE_CHARS = 2_000

# Display choice, not a data limit: the browser draws at most this many table rows; counts and exports use all rows.
TABLE_DISPLAY_ROWS = 1_000
# Excel's sheet limit (minus the header row); an export larger than this is split into further sheets.
EXCEL_SHEET_ROWS = 1_048_575

DEMO_NOTE = "This is a limit of the public demo; the downloaded app has no such limit."
MEMORY_MESSAGE = (
    "There is not enough memory for this step on this computer. Close other programs, choose a shorter period, or "
    "track fewer brands, and try again."
)


def is_public() -> bool:
    """True only in a public demo deployment (``SIGNAL_PUBLIC=1``, or the older ``LISTENSIGNAL_PUBLIC_DEMO=1``)."""
    return os.environ.get("SIGNAL_PUBLIC") == "1" or os.environ.get("LISTENSIGNAL_PUBLIC_DEMO") == "1"


def _cap(value: int) -> int | None:
    return value if is_public() else None


def max_brands() -> int | None:
    return _cap(DEMO_MAX_BRANDS)


def max_brand_yaml_chars() -> int | None:
    return _cap(DEMO_MAX_BRAND_YAML_CHARS)


def max_sample_chars() -> int | None:
    return _cap(DEMO_MAX_SAMPLE_CHARS)


def collection_allowed() -> bool:
    """Feed collection writes a database and makes network requests: off in a public demo."""
    return not is_public()


def exceeds(value: int, limit: int | None) -> bool:
    return limit is not None and value > limit


def demo_message(what: str) -> str:
    """A capped message: names the demo limit and says the downloaded app has none."""
    return f"{what} {DEMO_NOTE}"
