"""Fetch configured RSS/Atom feeds into the local SQLite store.

    python -m listensignal.collect [--sources sources.yaml] [--db data/listensignal.db]

Politeness rules enforced in code:

* every request sends ListenSignal's User-Agent;
* robots.txt is checked for every feed URL, and a disallowed or unreachable robots.txt skips the feed;
* each feed is fetched at most once per 30 minutes (``min_interval_minutes`` can only raise this);
* conditional requests (ETag / Last-Modified) avoid re-downloading unchanged feeds;
* only what the feed publishes (headline, snippet, link, time) is stored — article pages are never fetched.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import calendar
from pathlib import Path
import sys
from typing import Callable
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urlsplit

import feedparser

from . import USER_AGENT
from .config import DEFAULT_DB, DEFAULT_SOURCES, Source, load_sources
from .sentiment import get_scorer
from .storage import (
    Connection,
    InsertResult,
    connect,
    count_articles,
    count_known,
    fetch_state,
    insert_articles,
    record_fetch,
    save_sentiment,
    unscored,
    utc_now,
)

MAX_FEED_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class FetchResponse:
    status: int
    body: bytes = b""
    etag: str | None = None
    modified: str | None = None


Fetcher = Callable[[str, dict[str, str]], FetchResponse]


def http_fetch(url: str, headers: dict[str, str]) -> FetchResponse:
    """GET with ListenSignal's User-Agent, a timeout and a size cap."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_FEED_BYTES + 1)
            if len(body) > MAX_FEED_BYTES:
                raise ValueError(f"feed larger than {MAX_FEED_BYTES // (1024 * 1024)} MB")
            return FetchResponse(response.status, body, response.headers.get("ETag"), response.headers.get("Last-Modified"))
    except urllib.error.HTTPError as exc:
        return FetchResponse(exc.code)


class RobotsCache:
    """robots.txt verdicts per host, for ListenSignal's User-Agent."""

    def __init__(self, fetch: Fetcher = http_fetch) -> None:
        self._fetch = fetch
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> tuple[bool, str]:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._parsers:
            try:
                response = self._fetch(f"{host}/robots.txt", {})
            except Exception as exc:  # network error: be conservative
                self._parsers[host] = None
                return False, f"robots.txt unreachable ({type(exc).__name__})"
            parser = urllib.robotparser.RobotFileParser()
            if response.status == 200:
                parser.parse(response.body.decode("utf-8", "replace").splitlines())
            elif 400 <= response.status < 500:
                parser.parse([])  # no robots.txt: everything allowed (RFC 9309)
            else:
                self._parsers[host] = None
                return False, f"robots.txt returned HTTP {response.status}"
            self._parsers[host] = parser
        parser = self._parsers[host]
        if parser is None:
            return False, "robots.txt unreachable earlier in this run"
        if parser.can_fetch(USER_AGENT, url):
            return True, "allowed by robots.txt"
        return False, "disallowed by robots.txt for ListenSignal's User-Agent"


def _entry_time(entry: dict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
    return None


def parse_feed(body: bytes, source: str, now: datetime | None = None) -> list[dict]:
    """Headline, snippet, link and time for each feed entry. Entries without a link or title are dropped."""
    parsed = feedparser.parse(body)
    now = now or utc_now()
    records = []
    for entry in parsed.entries:
        link = entry.get("link") or ""
        title = entry.get("title") or ""
        if not link or not title:
            continue
        published = _entry_time(entry) or now
        # Feed timestamps in the future (time-zone mistakes) are clamped to the collection time.
        records.append(
            {
                "url": link,
                "title": title,
                "summary": entry.get("summary") or entry.get("description") or "",
                "source": source,
                "published": min(published, now),
            }
        )
    return records


@dataclass(frozen=True)
class SourceOutcome:
    source: str
    status: str
    seen: int = 0
    inserted: InsertResult = InsertResult()


def collect_source(
    conn: Connection,
    source: Source,
    *,
    min_interval_minutes: int,
    robots: RobotsCache,
    fetch: Fetcher = http_fetch,
    now: datetime | None = None,
) -> SourceOutcome:
    now = now or utc_now()
    state = fetch_state(conn, source.name)
    if state and state["last_attempt"]:
        last = datetime.fromisoformat(state["last_attempt"])
        wait = last + timedelta(minutes=min_interval_minutes) - now
        if wait > timedelta(0):
            minutes = int(wait.total_seconds() // 60) + 1
            return SourceOutcome(source.name, f"skipped: polled less than {min_interval_minutes} min ago (retry in {minutes} min)")
    allowed, reason = robots.allowed(source.url)
    if not allowed:
        record_fetch(conn, source.name, source.url, status=f"skipped: {reason}", success=False)
        return SourceOutcome(source.name, f"skipped: {reason}")
    headers: dict[str, str] = {}
    if state and state["etag"]:
        headers["If-None-Match"] = state["etag"]
    if state and state["modified"]:
        headers["If-Modified-Since"] = state["modified"]
    try:
        response = fetch(source.url, headers)
    except Exception as exc:
        status = f"error: {type(exc).__name__}: {exc}"[:200]
        record_fetch(conn, source.name, source.url, status=status, success=False)
        return SourceOutcome(source.name, status)
    if response.status == 304:
        record_fetch(conn, source.name, source.url, status="not modified", success=True,
                     etag=state["etag"] if state else None, modified=state["modified"] if state else None)
        return SourceOutcome(source.name, "not modified")
    if response.status != 200:
        record_fetch(conn, source.name, source.url, status=f"HTTP {response.status}", success=False)
        return SourceOutcome(source.name, f"HTTP {response.status}")
    records = parse_feed(response.body, source.name, now=now)
    known_before = count_known(conn, (record["url"] for record in records))
    inserted = insert_articles(conn, records)
    status = "ok" if records else "ok (feed had no usable entries)"
    if records and state and state["last_success"] and known_before == 0:
        # Feeds are a sliding window of the latest N items. If none of them was seen before, older items probably
        # scrolled out of the feed between polls and were never collected.
        status = f"ok, possible gap: all {len(records)} items were new since the last poll; poll this feed more often"
    record_fetch(conn, source.name, source.url, status=status, success=True, etag=response.etag,
                 modified=response.modified, seen=len(records), new=inserted.new)
    return SourceOutcome(source.name, status, len(records), inserted)


def score_pending(conn: Connection, mode: str = "auto", *, rescore: bool = False) -> tuple[int, str]:
    """Score every stored item that has no sentiment yet (or, with rescore, a different scorer's label)."""
    if not rescore and unscored(conn).empty:
        return 0, "Nothing new to score."  # do not load the model for nothing (scheduled runs)
    scorer, note = get_scorer(mode)
    pending = unscored(conn, rescore_scorer_other_than=scorer.name if rescore else None)
    if pending.empty:
        return 0, note
    results = scorer.score_items(pending["title"].tolist(), pending["summary"].tolist())
    count = save_sentiment(
        conn, ((row_id, r.label, r.confidence, r.scorer) for row_id, r in zip(pending["article_id"], results))
    )
    return count, note


def run(
    sources_path: Path | str = DEFAULT_SOURCES,
    db_path: Path | str = DEFAULT_DB,
    *,
    only: list[str] | None = None,
    sentiment: str = "auto",
    rescore: bool = False,
    fetch: Fetcher = http_fetch,
    out=sys.stdout,
) -> list[SourceOutcome]:
    config = load_sources(sources_path)
    chosen = [s for s in config.sources if (s.name in only if only else s.enabled)]
    if only:
        unknown = sorted(set(only) - {s.name for s in config.sources})
        if unknown:
            raise SystemExit("Unknown source name(s): " + ", ".join(unknown))
    conn = connect(db_path)
    robots = RobotsCache(fetch)
    outcomes = []
    print(f"ListenSignal collector · {len(chosen)} feed(s) · at most one poll per {config.min_interval_minutes} min", file=out)
    for source in chosen:
        outcome = collect_source(conn, source, min_interval_minutes=config.min_interval_minutes, robots=robots, fetch=fetch)
        outcomes.append(outcome)
        ins = outcome.inserted
        detail = (
            f" · {outcome.seen} items · {ins.new} new · {ins.duplicate_url} same URL · {ins.duplicate_title} same headline"
            if outcome.seen
            else ""
        )
        print(f"  {source.name:<22} {outcome.status}{detail}", file=out)
    scored, note = score_pending(conn, sentiment, rescore=rescore)
    print(f"Sentiment: {note} Scored {scored} item(s).", file=out)
    total = count_articles(conn)
    print(f"Database: {Path(db_path)} · {total} stored item(s).", file=out)
    conn.close()
    return outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m listensignal.collect", description="Fetch configured RSS/Atom feeds.")
    parser.add_argument("--sources", default=str(DEFAULT_SOURCES), help="path to sources.yaml")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="path to the SQLite database")
    parser.add_argument("--only", action="append", help="collect only this source name (repeatable; may be disabled)")
    parser.add_argument("--sentiment", choices=("auto", "norbert", "lexicon"), default="auto")
    parser.add_argument("--rescore", action="store_true", help="re-score items labelled by a different scorer")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run(args.sources, args.db, only=args.only, sentiment=args.sentiment, rescore=args.rescore)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
