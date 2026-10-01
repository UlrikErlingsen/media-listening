from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest

from listensignal import USER_AGENT
from listensignal.collect import FetchResponse, RobotsCache, collect_source, parse_feed, run
from listensignal.config import Source, parse_sources
from listensignal.storage import connect, load_articles, record_fetch

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Testavis</title>
<item><title>Kystkraft lanserer ny smak</title><link>https://test.invalid/a?utm_source=rss</link>
<description>&lt;p&gt;Ny brus i butikkene.&lt;/p&gt;</description><pubDate>Wed, 30 Sep 2026 08:00:00 +0200</pubDate></item>
<item><title>Kystkraft lanserer ny smak</title><link>https://test.invalid/b</link>
<pubDate>Wed, 30 Sep 2026 09:00:00 +0200</pubDate></item>
<item><title>Fremtidig sak</title><link>https://test.invalid/c</link><pubDate>Wed, 30 Sep 2099 09:00:00 +0200</pubDate></item>
<item><title></title><link>https://test.invalid/d</link></item>
</channel></rss>""".encode()
ROBOTS_OK = b"User-agent: *\nAllow: /\n"
ROBOTS_BLOCK = b"User-agent: *\nDisallow: /\n"
NOW = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
SOURCE = Source("Testavis", "https://test.invalid/rss")


class FakeWeb:
    """Stands in for the network: serves robots.txt and one feed, and records every request."""

    def __init__(self, robots=ROBOTS_OK, feed=RSS, status=200):
        self.robots, self.feed, self.status = robots, feed, status
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        if url.endswith("/robots.txt"):
            return FetchResponse(200, self.robots) if self.robots is not None else FetchResponse(404)
        return FetchResponse(self.status, self.feed if self.status == 200 else b"", etag='"v1"')


def test_parse_feed_keeps_headline_snippet_link_time_and_clamps_future_dates():
    records = parse_feed(RSS, "Testavis", now=NOW)
    assert [r["title"] for r in records] == ["Kystkraft lanserer ny smak", "Kystkraft lanserer ny smak", "Fremtidig sak"]
    assert records[0]["published"] == datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)
    assert records[2]["published"] == NOW
    assert set(records[0]) == {"url", "title", "summary", "source", "published"}


def test_collect_source_stores_new_items_and_deduplicates():
    conn = connect(":memory:")
    web = FakeWeb()
    outcome = collect_source(conn, SOURCE, min_interval_minutes=30, robots=RobotsCache(web), fetch=web, now=NOW)
    assert outcome.status == "ok"
    assert (outcome.inserted.new, outcome.inserted.duplicate_title) == (2, 1)
    assert len(load_articles(conn)) == 2


def test_poll_interval_floor_is_enforced():
    conn = connect(":memory:")
    record_fetch(conn, SOURCE.name, SOURCE.url, status="ok", success=True)
    web = FakeWeb()
    outcome = collect_source(conn, SOURCE, min_interval_minutes=30, robots=RobotsCache(web), fetch=web)
    assert outcome.status.startswith("skipped: polled less than 30 min ago")
    assert web.calls == []
    later = datetime.now(timezone.utc) + timedelta(minutes=31)
    assert collect_source(conn, SOURCE, min_interval_minutes=30, robots=RobotsCache(web), fetch=web, now=later).status == "ok"


def test_config_cannot_lower_the_30_minute_floor():
    one = [{"name": "A", "url": "https://a.no/rss"}]
    assert parse_sources({"defaults": {"min_interval_minutes": 5}, "sources": one}).min_interval_minutes == 30
    assert parse_sources({"defaults": {"min_interval_minutes": 60}, "sources": one}).min_interval_minutes == 60
    with pytest.raises(ValueError):
        parse_sources({"sources": [{"name": "A", "url": "ftp://a.no/rss"}]})


def test_robots_disallow_skips_feed_without_fetching_it():
    conn = connect(":memory:")
    web = FakeWeb(robots=ROBOTS_BLOCK)
    outcome = collect_source(conn, SOURCE, min_interval_minutes=30, robots=RobotsCache(web), fetch=web, now=NOW)
    assert "disallowed by robots.txt" in outcome.status
    assert [url for url, _ in web.calls] == ["https://test.invalid/robots.txt"]


def test_missing_robots_txt_allows_and_unreachable_robots_blocks():
    assert RobotsCache(FakeWeb(robots=None)).allowed(SOURCE.url)[0] is True

    def broken(url, headers):
        raise TimeoutError("no answer")

    assert RobotsCache(broken).allowed(SOURCE.url)[0] is False


def test_conditional_request_and_not_modified():
    conn = connect(":memory:")
    web = FakeWeb()
    collect_source(conn, SOURCE, min_interval_minutes=30, robots=RobotsCache(web), fetch=web, now=NOW)
    web304 = FakeWeb(status=304)
    later = datetime.now(timezone.utc) + timedelta(hours=1)
    outcome = collect_source(conn, SOURCE, min_interval_minutes=30, robots=RobotsCache(web304), fetch=web304, now=later)
    assert outcome.status == "not modified"
    assert web304.calls[-1][1].get("If-None-Match") == '"v1"'


def test_user_agent_is_descriptive():
    assert USER_AGENT.startswith("ListenSignal/") and "github.com" in USER_AGENT


def test_run_end_to_end_with_lexicon(tmp_path):
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        "sources:\n  - name: Testavis\n    url: https://test.invalid/rss\n"
        "  - name: Av\n    url: https://off.invalid/rss\n    enabled: false\n",
        encoding="utf-8",
    )
    db = tmp_path / "test.db"
    log = StringIO()
    outcomes = run(sources, db, sentiment="lexicon", fetch=FakeWeb(), out=log)
    assert [o.source for o in outcomes] == ["Testavis"]  # disabled feeds are never fetched
    conn = connect(db)
    stored = load_articles(conn)
    conn.close()
    assert stored["sentiment_scorer"].eq("lexicon-v1").all()
    assert "Scored 2 item(s)" in log.getvalue()
