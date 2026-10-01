"""Brand alias matching for Norwegian (Bokmål and Nynorsk) headlines and snippets.

Rules, in order:

1. Text is normalized (non-breaking spaces, typographic apostrophes and dashes).
2. Each alias matches on word boundaries, case-insensitively unless the brand says otherwise.
   Spaces inside an alias also match hyphens ("Nordlys Energi" ~ "Nordlys-Energi").
3. With ``inflect`` (the default) an alias may carry one common inflectional suffix: genitive
   (-s, -'s), definite and plural forms in Bokmål and Nynorsk (-en, -et, -a, -ene, -ane, -er, -ar,
   and their genitives), or a hyphenated compound ("Tine-sjefen"). Closed compounds without a hyphen
   ("Tinemelk") are deliberately *not* matched; add them as aliases if you want them.
4. A match is discarded when it overlaps an exclusion phrase ("Tine" inside "Tine Sundt").
   Exclusions are matched with the same rules, so "Tine Sundts" is excluded as well.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re

import pandas as pd

from .config import Brand

# Longest first so the regex engine prefers the fuller suffix.
_SUFFIXES = (
    "enes", "anes", "ene", "ane", "ens", "ets", "ers", "ars", "'s", "’s",
    "en", "et", "er", "ar", "ne", "s", "a", "e", "n",
)
_SUFFIX_PATTERN = "(?:" + "|".join(re.escape(suffix) for suffix in _SUFFIXES) + ")?(?:-\\w+)?"
_TRANSLATE = str.maketrans({" ": " ", "’": "'", "‘": "'", "‐": "-", "‑": "-", "–": "-"})


def normalize_text(text: object) -> str:
    """Normalize whitespace and punctuation variants that break word-boundary matching."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return re.sub(r"\s+", " ", str(text).translate(_TRANSLATE)).strip()


@lru_cache(maxsize=1024)
def _compile(term: str, case_sensitive: bool, inflect: bool) -> re.Pattern[str]:
    words = [re.escape(word) for word in normalize_text(term).split(" ") if word]
    body = r"[\s-]+".join(words)
    suffix = _SUFFIX_PATTERN if inflect else ""
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<!\w){body}{suffix}(?!\w)", flags)


@dataclass(frozen=True)
class Match:
    brand: str
    alias: str
    text: str
    start: int
    end: int
    excluded_by: str | None = None


def _spans(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [match.span() for match in pattern.finditer(text)]


def find_matches(text: object, brand: Brand) -> list[Match]:
    """Every alias hit for one brand, including hits discarded by an exclusion (with the reason)."""
    clean = normalize_text(text)
    if not clean:
        return []
    exclusions = [
        (phrase, span)
        for phrase in brand.exclude
        for span in _spans(_compile(phrase, False, brand.inflect), clean)
    ]
    found: dict[tuple[int, int], Match] = {}
    for alias in sorted(brand.aliases, key=len, reverse=True):
        for start, end in _spans(_compile(alias, brand.case_sensitive, brand.inflect), clean):
            if any(start < other_end and other_start < end for other_start, other_end in found):
                continue  # A longer alias already covers this text.
            blocker = next((phrase for phrase, (s, e) in exclusions if start < e and s < end), None)
            found[(start, end)] = Match(brand.name, alias, clean[start:end], start, end, blocker)
    return sorted(found.values(), key=lambda match: match.start)


def mentions_brand(text: object, brand: Brand) -> bool:
    return any(match.excluded_by is None for match in find_matches(text, brand))


def match_brands(text: object, brands: tuple[Brand, ...] | list[Brand]) -> list[str]:
    """Names of brands with at least one non-excluded match, in configuration order."""
    return [brand.name for brand in brands if mentions_brand(text, brand)]


def match_articles(articles: pd.DataFrame, brands: tuple[Brand, ...] | list[Brand]) -> pd.DataFrame:
    """Long table of (article_id, brand) for every article mentioning a brand in its headline or snippet."""
    rows: list[tuple[object, str]] = []
    if articles.empty:
        return pd.DataFrame(columns=["article_id", "brand"])
    texts = articles["title"].fillna("").astype(str) + " \n " + articles["summary"].fillna("").astype(str)
    for article_id, text in zip(articles["article_id"], texts):
        for name in match_brands(text, brands):
            rows.append((article_id, name))
    return pd.DataFrame(rows, columns=["article_id", "brand"])
