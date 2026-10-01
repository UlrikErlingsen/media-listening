"""Load the data the dashboard and exports work on: the fictional demo or the local database."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pandas as pd

from .analysis import TIMEZONE, mention_table
from .config import DEFAULT_BRANDS, DEFAULT_DB, Brand, load_brands
from .demo import DEMO_BRANDS, DEMO_NOTICE, DEMO_START, make_demo_articles
from .storage import connect, count_articles, load_articles, load_fetch_log


@dataclass(frozen=True)
class Workspace:
    label: str
    is_demo: bool
    brands: tuple[Brand, ...]
    articles: pd.DataFrame
    mentions: pd.DataFrame
    fetch_log: pd.DataFrame
    notice: str = ""
    coverage_start: date | None = None  # first day with complete coverage; None = unknown/complete

    @property
    def brand_names(self) -> list[str]:
        return [brand.name for brand in self.brands]

    def with_brands(self, brands: tuple[Brand, ...]) -> "Workspace":
        """The same feed items re-matched against a different brand list."""
        return replace(self, brands=tuple(brands), mentions=mention_table(self.articles, brands),
                       label=self.label + " · custom brands")


def demo_workspace() -> Workspace:
    articles = make_demo_articles()
    return Workspace(
        label="Fictional demo",
        is_demo=True,
        brands=DEMO_BRANDS,
        articles=articles,
        mentions=mention_table(articles, DEMO_BRANDS),
        fetch_log=pd.DataFrame(),
        notice=DEMO_NOTICE,
        coverage_start=DEMO_START,  # nothing exists before the demo starts; comparisons must not reach back
    )


def database_workspace(db_path: Path | str = DEFAULT_DB, brands_path: Path | str = DEFAULT_BRANDS) -> Workspace:
    brands = load_brands(brands_path)
    conn = connect(db_path)
    try:
        articles = load_articles(conn)
        fetch_log = load_fetch_log(conn)
    finally:
        conn.close()
    collected = pd.to_datetime(articles["collected_at"], utc=True, errors="coerce", format="ISO8601").dropna()
    coverage_start = collected.min().tz_convert(TIMEZONE).date() if not collected.empty else None
    return Workspace(
        label=f"Local database ({Path(db_path).name})",
        is_demo=False,
        brands=brands,
        articles=articles,
        mentions=mention_table(articles, brands),
        fetch_log=fetch_log,
        coverage_start=coverage_start,
    )


def database_has_items(db_path: Path | str = DEFAULT_DB) -> int:
    path = Path(db_path)
    if not path.exists():
        return 0
    conn = connect(path)
    try:
        return count_articles(conn)
    finally:
        conn.close()
