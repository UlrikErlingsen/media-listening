import pandas as pd
import pytest

from listensignal.config import Brand, parse_brands
from listensignal.matching import find_matches, match_articles, match_brands, mentions_brand

TINE = Brand("Tine", ("Tine", "TINE", "TINE SA"), ("Tine Sundt",), "own", case_sensitive=True)
NORDLYS = Brand("Nordlys Energi", ("Nordlys Energi", "Nordlys"), ("nordlyset", "sterkt nordlys"))
KYST = Brand("Kystkraft", ("Kystkraft",))


@pytest.mark.parametrize(
    "text",
    [
        "Tine øker prisene",                    # base form
        "Tines nye ost får skryt",              # genitive -s
        "Tine-sjefen går av",                   # hyphenated compound
        "Kritikk mot TINE SA",                  # multi-word alias
        "Bøndene leverer til Tine.",            # punctuation boundary
        "«Tine» svarer på kritikken",           # quotes
    ],
)
def test_alias_matches_inflected_forms(text):
    assert mentions_brand(text, TINE)


@pytest.mark.parametrize(
    "text",
    [
        "Kystkrafts nye smak",       # genitive
        "Kystkraften lanseres",      # Bokmål definite -en
        "Kystkrafta er populær",     # Nynorsk definite -a
        "Kystkraftene og konkurrentane",  # plural definite -ene
        "Kystkraftane sel godt",     # Nynorsk plural definite -ane
        "Kystkraft's resultat",      # English-style genitive
        "Kystkraft’s resultat",      # typographic apostrophe
        "kystkraft er billig",       # case-insensitive by default
    ],
)
def test_bokmal_and_nynorsk_suffixes(text):
    assert mentions_brand(text, KYST)


@pytest.mark.parametrize("text", ["Platine er et metall", "Ristine Kafe", "Kystkraftverket stenges", "Tinemelk er godt"])
def test_word_boundaries_and_closed_compounds_do_not_match(text):
    assert not mentions_brand(text, TINE)
    assert not mentions_brand(text, KYST)


def test_exclusion_blocks_overlapping_hit_only():
    assert not mentions_brand("Tine Sundt vant gull i Oslo", TINE)
    assert not mentions_brand("Tine Sundts rekord", TINE)  # exclusions are inflected too
    matches = find_matches("Tine Sundt roser Tine-sjefen", TINE)
    assert [(m.text, m.excluded_by) for m in matches] == [("Tine", "Tine Sundt"), ("Tine-sjefen", None)]
    assert mentions_brand("Tine Sundt roser Tine-sjefen", TINE)


def test_case_sensitive_brand_ignores_common_word():
    # "tine" is also a verb ("to thaw"); the example brand is case-sensitive.
    assert not mentions_brand("Husk å tine kjøttet i kjøleskapet", TINE)
    assert mentions_brand("TINE melder om vekst", TINE)


def test_multiword_alias_accepts_hyphen_and_longest_alias_wins():
    assert mentions_brand("Nordlys-Energi øker", NORDLYS)
    matches = find_matches("Nordlys Energis lansering", NORDLYS)
    assert [m.alias for m in matches] == ["Nordlys Energi"]


def test_inflected_decoy_is_excluded():
    assert not mentions_brand("Turistene strømmer til for å se nordlyset", NORDLYS)
    assert not mentions_brand("Sterkt nordlys over Tromsø", NORDLYS)
    assert mentions_brand("Nordlys lanserer ny drikk", NORDLYS)


def test_inflection_can_be_turned_off():
    strict = Brand("Kystkraft", ("Kystkraft",), inflect=False)
    assert mentions_brand("Kystkraft lanserer", strict)
    assert not mentions_brand("Kystkraften lanserer", strict)


def test_match_brands_and_articles_long_table():
    assert match_brands("Kystkraft og Nordlys Energi kjemper", [TINE, NORDLYS, KYST]) == ["Nordlys Energi", "Kystkraft"]
    articles = pd.DataFrame(
        {"article_id": [1, 2, 3], "title": ["Kystkraft vokser", "Været i dag", "Tine-sjefen"],
         "summary": ["Også Nordlys Energi", "", None]}
    )
    pairs = match_articles(articles, [TINE, NORDLYS, KYST])
    assert sorted(map(tuple, pairs.to_numpy())) == [(1, "Kystkraft"), (1, "Nordlys Energi"), (3, "Tine")]


def test_brand_config_validation():
    brands = parse_brands({"brands": [{"name": "Tine", "role": "own", "exclude": "Tine Sundt"}]})
    assert brands[0].aliases == ("Tine",) and brands[0].exclude == ("Tine Sundt",)
    with pytest.raises(ValueError):
        parse_brands({"brands": [{"name": "A", "role": "partner"}]})
    with pytest.raises(ValueError):
        parse_brands({"brands": [{"name": "A"}, {"name": "a"}]})
