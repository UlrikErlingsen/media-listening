from datetime import datetime, timezone

from listensignal.storage import canonical_url, clean_snippet, connect, insert_articles, load_articles, title_hash


def _item(url, title, source="VG", summary="Kort ingress."):
    return {"url": url, "title": title, "summary": summary, "source": source,
            "published": datetime(2026, 9, 30, 8, tzinfo=timezone.utc)}


def test_canonical_url_drops_tracking_fragment_and_trailing_slash():
    a = canonical_url("https://www.VG.no/nyheter/i/abc/?utm_source=rss&utm_medium=feed#top")
    b = canonical_url("http://vg.no/nyheter/i/abc")
    assert a == b
    assert canonical_url("https://e24.no/a?id=2") != canonical_url("https://e24.no/a?id=3")


def test_title_hash_ignores_case_spacing_and_punctuation():
    assert title_hash("Tine øker prisene!") == title_hash("  tine   ØKER prisene ")
    assert title_hash("Tine øker prisene") != title_hash("Tine senker prisene")
    assert title_hash("  ") is None


def test_deduplicates_by_url_and_by_title_hash():
    conn = connect(":memory:")
    first = insert_articles(conn, [
        _item("https://vg.no/a?utm_campaign=x", "Kystkraft lanserer ny smak"),
        _item("https://vg.no/a", "Kystkraft lanserer ny smak (oppdatert)"),          # same URL
        _item("https://e24.no/b", "Kystkraft lanserer ny smak", source="E24"),       # same headline, other outlet
        _item("https://e24.no/c", "Helt annen sak", source="E24"),
        _item("", "Mangler lenke"),
    ])
    assert (first.new, first.duplicate_url, first.duplicate_title, first.skipped) == (2, 1, 1, 1)
    again = insert_articles(conn, [_item("https://vg.no/a", "Kystkraft lanserer ny smak")])
    assert again.new == 0 and again.duplicate_url == 1
    stored = load_articles(conn)
    assert len(stored) == 2
    assert set(stored["source"]) == {"VG", "E24"}  # the first outlet keeps the syndicated story


def test_only_short_snippets_are_stored():
    html = "<p>Første&nbsp;setning.</p> " + "ord " * 300
    snippet = clean_snippet(html)
    assert snippet.startswith("Første setning.") and "<p>" not in snippet
    assert len(snippet) <= 402 and snippet.endswith("…")
    conn = connect(":memory:")
    insert_articles(conn, [_item("https://vg.no/x", "Lang sak", summary=html)])
    assert len(load_articles(conn)["summary"].iat[0]) <= 402
    columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
    assert not {"body", "content", "full_text", "author"} & columns
