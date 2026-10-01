"""SQLite storage: headlines, feed snippets, links, sources, timestamps and sentiment labels.

Only what the feed itself publishes is stored. Full article text is never fetched or stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd

from .matching import normalize_text

Connection = sqlite3.Connection  # the only storage handle other modules see
SNIPPET_MAX_CHARS = 400
_TRACKING_PARAMS = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|xtor|ref|referrer|src|cmpid|ns_.*)$", re.IGNORECASE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    url_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    title_hash TEXT UNIQUE,
    summary TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    published TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    sentiment TEXT,
    sentiment_confidence REAL,
    sentiment_scorer TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published);
CREATE TABLE IF NOT EXISTS fetch_log (
    source TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    last_attempt TEXT,
    last_success TEXT,
    etag TEXT,
    modified TEXT,
    last_status TEXT,
    items_seen INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0
);
"""

ARTICLE_COLUMNS = [
    "article_id", "url", "title", "summary", "source", "published", "collected_at",
    "sentiment", "sentiment_confidence", "sentiment_scorer",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def canonical_url(url: str) -> str:
    """URL key for de-duplication: lower-case host, no fragment, no tracking parameters, no trailing slash."""
    parts = urlsplit(str(url).strip())
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(key)]
    path = parts.path.rstrip("/") or "/"
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunsplit(("https" if parts.scheme in ("http", "https") else parts.scheme, host, path, urlencode(sorted(query)), ""))


def title_hash(title: str) -> str | None:
    """Hash of a headline with case, punctuation and spacing removed; None for empty headlines."""
    letters = re.sub(r"[\W_]+", " ", normalize_text(title).casefold()).strip()
    if not letters:
        return None
    return hashlib.sha1(letters.encode("utf-8")).hexdigest()


def clean_snippet(text: object, limit: int = SNIPPET_MAX_CHARS) -> str:
    """Strip markup from a feed summary and cap it to a short snippet."""
    plain = re.sub(r"<[^>]+>", " ", str(text or ""))
    plain = re.sub(r"&nbsp;|&#160;", " ", plain)
    plain = normalize_text(plain)
    if len(plain) <= limit:
        return plain
    cut = plain[:limit].rsplit(" ", 1)[0]
    return cut + " …"


@dataclass(frozen=True)
class InsertResult:
    new: int = 0
    duplicate_url: int = 0
    duplicate_title: int = 0
    skipped: int = 0

    def __add__(self, other: "InsertResult") -> "InsertResult":
        return InsertResult(
            self.new + other.new,
            self.duplicate_url + other.duplicate_url,
            self.duplicate_title + other.duplicate_title,
            self.skipped + other.skipped,
        )


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    if str(db_path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_articles(conn: sqlite3.Connection, records: Iterable[dict]) -> InsertResult:
    """Insert feed items, skipping any whose URL key or headline hash is already stored."""
    result = InsertResult()
    collected = iso(utc_now())
    with conn:
        for record in records:
            url = str(record.get("url") or "").strip()
            title = normalize_text(record.get("title"))
            if not url or not title:
                result += InsertResult(skipped=1)
                continue
            key = canonical_url(url)
            digest = title_hash(title)
            if conn.execute("SELECT 1 FROM articles WHERE url_key = ?", (key,)).fetchone():
                result += InsertResult(duplicate_url=1)
                continue
            if digest and conn.execute("SELECT 1 FROM articles WHERE title_hash = ?", (digest,)).fetchone():
                result += InsertResult(duplicate_title=1)
                continue
            published = record.get("published")
            published_iso = iso(published) if isinstance(published, datetime) else str(published or collected)
            conn.execute(
                "INSERT INTO articles (url, url_key, title, title_hash, summary, source, published, collected_at,"
                " sentiment, sentiment_confidence, sentiment_scorer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    url, key, title, digest, clean_snippet(record.get("summary")), str(record.get("source") or ""),
                    published_iso, str(record.get("collected_at") or collected), record.get("sentiment"),
                    record.get("sentiment_confidence"), record.get("sentiment_scorer"),
                ),
            )
            result += InsertResult(new=1)
    return result


def count_articles(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0])


def load_articles(conn: sqlite3.Connection) -> pd.DataFrame:
    frame = pd.read_sql_query(f"SELECT {', '.join(ARTICLE_COLUMNS)} FROM articles ORDER BY published", conn)
    frame["published"] = pd.to_datetime(frame["published"], utc=True, errors="coerce", format="ISO8601")
    return frame


def unscored(conn: sqlite3.Connection, rescore_scorer_other_than: str | None = None) -> pd.DataFrame:
    query = "SELECT article_id, title, summary FROM articles WHERE sentiment IS NULL"
    params: tuple = ()
    if rescore_scorer_other_than:
        query += " OR sentiment_scorer IS NOT ?"
        params = (rescore_scorer_other_than,)
    return pd.read_sql_query(query, conn, params=params)


def save_sentiment(conn: sqlite3.Connection, rows: Iterable[tuple[int, str, float | None, str]]) -> int:
    rows = list(rows)
    with conn:
        conn.executemany(
            "UPDATE articles SET sentiment = ?, sentiment_confidence = ?, sentiment_scorer = ? WHERE article_id = ?",
            [(label, confidence, scorer, int(article_id)) for article_id, label, confidence, scorer in rows],
        )
    return len(rows)


def fetch_state(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM fetch_log WHERE source = ?", (source,)).fetchone()


def record_fetch(
    conn: sqlite3.Connection,
    source: str,
    url: str,
    *,
    status: str,
    success: bool,
    etag: str | None = None,
    modified: str | None = None,
    seen: int = 0,
    new: int = 0,
) -> None:
    now = iso(utc_now())
    previous = fetch_state(conn, source)
    last_success = now if success else (previous["last_success"] if previous else None)
    etag = etag if success else (previous["etag"] if previous else None)
    modified = modified if success else (previous["modified"] if previous else None)
    with conn:
        conn.execute(
            "INSERT INTO fetch_log (source, url, last_attempt, last_success, etag, modified, last_status, items_seen,"
            " items_new) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(source) DO UPDATE SET url = excluded.url,"
            " last_attempt = excluded.last_attempt, last_success = excluded.last_success, etag = excluded.etag,"
            " modified = excluded.modified, last_status = excluded.last_status, items_seen = excluded.items_seen,"
            " items_new = excluded.items_new",
            (source, url, now, last_success, etag, modified, status, seen, new),
        )


def load_fetch_log(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM fetch_log ORDER BY source", conn)
