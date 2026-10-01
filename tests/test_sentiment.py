import pytest

from listensignal import sentiment
from listensignal.sentiment import (
    LEXICON_NAME,
    LexiconScorer,
    combine,
    get_scorer,
    item_text,
    lexicon_hits,
    split_sentences,
)


@pytest.mark.parametrize(
    "text, label",
    [
        ("Fjellbrus lanserer en fantastisk ny smak", "Positive"),
        ("Kunder er skuffet over prisen", "Negative"),
        ("Selskapet holder generalforsamling i Bergen", "Neutral"),
        ("God smak, men skuffende pris", "Mixed"),
        ("Eg er nøgd med brusen", "Positive"),            # Nynorsk
        ("Lesarane meiner prisen er dårleg", "Negative"),  # Nynorsk
        ("Prisen er ikke god", "Negative"),               # negation flips
        ("Resultatet var ikkje dårleg", "Positive"),      # Nynorsk negation
        ("Tilbakekallingen skaper uro", "Negative"),      # prefix entry
    ],
)
def test_lexicon_fallback_labels(text, label):
    assert LexiconScorer().score([text])[0].label == label


def test_lexicon_reports_which_words_drove_the_label():
    positive, negative = lexicon_hits("Prisen er ikke god, men smaken er strålende")
    assert positive == ["strålende"] and negative == ["ikke god"]


def test_every_result_is_labelled_with_its_scorer():
    results = LexiconScorer().score_items(["Ny rekordsalg"], ["Kundene er fornøyde."])
    assert results[0].scorer == LEXICON_NAME and results[0].confidence is None


def test_sentence_combination_rule():
    assert combine(["Neutral", "Positive"]) == "Positive"
    assert combine(["Negative", "Neutral"]) == "Negative"
    assert combine(["Positive", "Negative"]) == "Mixed"
    assert combine(["Mixed"]) == "Mixed"
    assert combine([]) == "Neutral"


def test_sentence_splitting_keeps_headline_separate():
    assert split_sentences("Første setning. Andre setning! «Tredje» her.") == [
        "Første setning.", "Andre setning!", "«Tredje» her."
    ]
    assert item_text("Kystkraft vokser", "Salget øker. Ny fabrikk.") == ["Kystkraft vokser", "Salget øker.", "Ny fabrikk."]
    assert item_text("Samme tekst", "Samme tekst") == ["Samme tekst"]


def test_auto_falls_back_to_lexicon_when_extra_missing(monkeypatch):
    monkeypatch.setattr(sentiment, "norbert_available", lambda: (False, "transformers/torch are not installed."))
    scorer, note = get_scorer("auto")
    assert scorer.name == LEXICON_NAME
    assert "lexicon fallback" in note
    with pytest.raises(RuntimeError):
        get_scorer("norbert")


def test_auto_falls_back_when_model_cannot_load(monkeypatch):
    monkeypatch.setattr(sentiment, "norbert_available", lambda: (True, "ok"))

    def fail(**kwargs):
        raise OSError("not in cache")

    monkeypatch.setattr(sentiment, "NorbertScorer", fail)
    scorer, note = get_scorer("auto")
    assert scorer.name == LEXICON_NAME and "--download" in note


def _norbert_cached() -> bool:
    available, _ = sentiment.norbert_available()
    if not available:
        return False
    try:
        sentiment.NorbertScorer()
    except Exception:
        return False
    return True


@pytest.mark.skipif(not _norbert_cached(), reason="NorBERT3 extra or cached model not available")
def test_norbert3_scores_clear_cases_locally():
    scorer = sentiment.NorbertScorer()
    results = scorer.score(["Fjellbrus lanserer en fantastisk ny smak.", "Prisen er ikke god."])
    assert [r.label for r in results] == ["Positive", "Negative"]
    assert all(r.scorer.startswith("norbert3@") and 0 < r.confidence <= 1 for r in results)
