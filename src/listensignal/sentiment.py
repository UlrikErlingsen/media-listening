"""Norwegian sentence-level sentiment: NorBERT3 when installed, a transparent lexicon otherwise.

Both scorers label each *sentence* of a headline + snippet as Positive, Negative, Neutral or Mixed,
then combine sentences into one item label with the same rule:

* any Mixed sentence, or both Positive and Negative sentences  -> Mixed
* otherwise any Positive sentence                              -> Positive
* otherwise any Negative sentence                              -> Negative
* otherwise                                                    -> Neutral

The label describes the tone of the headline and snippet, *not* the tone towards a particular brand
mentioned in it. Every stored score records which scorer produced it.

Model: ``ltg/norbert3-base_sentence-sentiment`` (Language Technology Group, University of Oslo;
CC-BY-4.0), fine-tuned on the sentence-level NoReC "mixed" subset. Its model card reports a weighted F1
of 0.764 on that dataset's own test data (Negative 0.58, Positive 0.78, Neutral 0.83, Mixed 0.65).
ListenSignal's own run on that test split measured 0.749 for NorBERT3 and 0.496 for the lexicon fallback
(docs/sentiment-evaluation.md). Those are review sentences, not news headlines; accuracy on news is unmeasured.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import sys
from typing import Protocol, Sequence

from .matching import normalize_text

LABELS = ("Positive", "Negative", "Neutral", "Mixed")
MODEL_ID = "ltg/norbert3-base_sentence-sentiment"
# Pinned revision: the model needs trust_remote_code=True, so ListenSignal only ever runs this reviewed commit.
MODEL_REVISION = "a6f56334e237664a30573cf2c4b9f94a28934425"
NORBERT_NAME = f"norbert3@{MODEL_REVISION[:7]}"
LEXICON_NAME = "lexicon-v1"

_LEXICON_DIR = Path(__file__).resolve().parent / "lexicon"
_INFLECTIONS = ("", "e", "t", "en", "et", "er", "a", "ar", "ene", "ane", "s", "es", "ens", "ets")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[\"«(]?[A-ZÆØÅ0-9])")
_TOKEN = re.compile(r"[a-zæøåéèüöäA-ZÆØÅÉÈÜÖÄ]+")


@dataclass(frozen=True)
class SentimentResult:
    label: str
    confidence: float | None
    scorer: str


class Scorer(Protocol):
    name: str

    def score(self, texts: Sequence[str]) -> list[SentimentResult]: ...


def split_sentences(text: object) -> list[str]:
    """Split headline/snippet text into sentences with a simple punctuation rule."""
    clean = normalize_text(text)
    if not clean:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT.split(clean) if part.strip()]


def item_text(title: object, summary: object) -> list[str]:
    """Sentences for one feed item: the headline is always its own sentence."""
    sentences = split_sentences(title)
    headline = " ".join(sentences)
    snippet = [sentence for sentence in split_sentences(summary) if sentence != headline]
    return sentences + snippet


def combine(labels: Sequence[str]) -> str:
    present = set(labels)
    if "Mixed" in present or {"Positive", "Negative"} <= present:
        return "Mixed"
    if "Positive" in present:
        return "Positive"
    if "Negative" in present:
        return "Negative"
    return "Neutral"


# --------------------------------------------------------------------------------------------- lexicon


def _read_terms(name: str) -> tuple[frozenset[str], tuple[str, ...]]:
    exact: set[str] = set()
    prefixes: list[str] = []
    for line in (_LEXICON_DIR / name).read_text(encoding="utf-8").splitlines():
        term = line.strip().casefold()
        if not term or term.startswith("#"):
            continue
        if term.endswith("*"):
            prefixes.append(term[:-1])
        else:
            exact.update(term + suffix for suffix in _INFLECTIONS)
    return frozenset(exact), tuple(sorted(prefixes, key=len, reverse=True))


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, tuple[frozenset[str], tuple[str, ...]]]:
    return {
        "positive": _read_terms("positive.txt"),
        "negative": _read_terms("negative.txt"),
        "negators": _read_terms("negators.txt"),
    }


def _hit(token: str, terms: tuple[frozenset[str], tuple[str, ...]]) -> bool:
    exact, prefixes = terms
    return token in exact or any(token.startswith(prefix) for prefix in prefixes)


def lexicon_hits(sentence: str) -> tuple[list[str], list[str]]:
    """Positive and negative words found in a sentence, after negation within the next three words."""
    lex = _lexicon()
    positive: list[str] = []
    negative: list[str] = []
    negate_until = -1
    for index, token in enumerate(token.casefold() for token in _TOKEN.findall(sentence)):
        if _hit(token, lex["negators"]):
            negate_until = index + 3
            continue
        is_pos = _hit(token, lex["positive"])
        is_neg = _hit(token, lex["negative"])
        if is_pos == is_neg:
            continue
        flipped = index <= negate_until
        if is_pos != flipped:
            positive.append(("ikke " if flipped else "") + token)
        else:
            negative.append(("ikke " if flipped else "") + token)
    return positive, negative


def lexicon_sentence_label(sentence: str) -> str:
    positive, negative = lexicon_hits(sentence)
    if positive and negative:
        return "Mixed"
    if positive:
        return "Positive"
    if negative:
        return "Negative"
    return "Neutral"


class LexiconScorer:
    """Word-list fallback: transparent and fast, but blind to irony, context and most phrasing."""

    name = LEXICON_NAME

    def score(self, texts: Sequence[str]) -> list[SentimentResult]:
        results = []
        for text in texts:
            sentences = split_sentences(text) or [""]
            results.append(SentimentResult(combine([lexicon_sentence_label(s) for s in sentences]), None, self.name))
        return results

    def score_items(self, titles: Sequence[object], summaries: Sequence[object]) -> list[SentimentResult]:
        results = []
        for title, summary in zip(titles, summaries):
            sentences = item_text(title, summary) or [""]
            results.append(SentimentResult(combine([lexicon_sentence_label(s) for s in sentences]), None, self.name))
        return results


# --------------------------------------------------------------------------------------------- NorBERT3


class NorbertScorer:
    """Local NorBERT3 sentence-sentiment classifier on CPU (optional ``[sentiment]`` extra)."""

    name = NORBERT_NAME

    def __init__(self, *, allow_download: bool = False, batch_size: int = 16) -> None:
        # Imported lazily: the extra is optional.
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

        self.batch_size = batch_size
        options = {"revision": MODEL_REVISION, "trust_remote_code": True, "local_files_only": not allow_download}
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, **options)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, **options)
        model.eval()
        self._pipe = pipeline("text-classification", model=model, tokenizer=tokenizer, device="cpu")

    def _sentences(self, sentences: Sequence[str]) -> list[tuple[str, float]]:
        if not sentences:
            return []
        output = self._pipe(list(sentences), batch_size=self.batch_size, truncation=True, max_length=256)
        return [(row["label"], float(row["score"])) for row in output]

    def score(self, texts: Sequence[str]) -> list[SentimentResult]:
        return self._score_groups([split_sentences(text) or [""] for text in texts])

    def score_items(self, titles: Sequence[object], summaries: Sequence[object]) -> list[SentimentResult]:
        return self._score_groups([item_text(title, summary) or [""] for title, summary in zip(titles, summaries)])

    def _score_groups(self, groups: list[list[str]]) -> list[SentimentResult]:
        flat = [sentence for group in groups for sentence in group]
        scored = self._sentences(flat)
        results: list[SentimentResult] = []
        position = 0
        for group in groups:
            part = scored[position : position + len(group)]
            position += len(group)
            label = combine([item_label for item_label, _ in part])
            confidence = sum(probability for _, probability in part) / len(part) if part else None
            results.append(SentimentResult(label, round(confidence, 4) if confidence is not None else None, self.name))
        return results


def norbert_available() -> tuple[bool, str]:
    """Whether the optional packages are importable (does not load or download the model)."""
    try:
        import torch  # noqa: F401
        import transformers
    except ImportError:
        return False, "transformers/torch are not installed (install the optional [sentiment] extra)."
    major = int(transformers.__version__.split(".")[0])
    if major >= 5:
        return False, (
            f"transformers {transformers.__version__} is installed, but the model's remote code needs transformers 4.x "
            "(pip install 'transformers>=4.36,<5')."
        )
    return True, "transformers and torch are installed."


def get_scorer(mode: str = "auto", *, allow_download: bool = False) -> tuple[Scorer, str]:
    """Return (scorer, note). ``auto`` tries NorBERT3 from the local cache and falls back to the lexicon."""
    if mode not in ("auto", "norbert", "lexicon"):
        raise ValueError("Sentiment mode must be auto, norbert or lexicon.")
    if mode == "lexicon":
        return LexiconScorer(), "Lexicon scorer selected."
    available, why = norbert_available()
    if available:
        try:
            return NorbertScorer(allow_download=allow_download), f"NorBERT3 loaded locally ({MODEL_ID}@{MODEL_REVISION[:7]})."
        except Exception as exc:  # model missing from cache, incompatible versions, ...
            why = (
                f"NorBERT3 could not be loaded ({type(exc).__name__}). Download it once with "
                "`python -m listensignal.sentiment --download`."
            )
    if mode == "norbert":
        raise RuntimeError(why)
    return LexiconScorer(), f"Using the lexicon fallback: {why}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m listensignal.sentiment", description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", action="store_true", help="download the pinned NorBERT3 model into the local cache")
    parser.add_argument("text", nargs="*", help="Norwegian text to score")
    args = parser.parse_args(argv)
    if args.download:
        try:  # Use the operating system's certificate store when available (helps behind TLS-inspecting proxies).
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass
        print(f"Downloading {MODEL_ID} at revision {MODEL_REVISION} (about 0.5 GB) ...")
        scorer, note = get_scorer("norbert", allow_download=True)
        print(note)
    else:
        scorer, note = get_scorer("auto")
        print(note, file=sys.stderr)
    for text, result in zip(args.text, scorer.score(args.text)):
        confidence = "" if result.confidence is None else f" ({result.confidence:.2f})"
        print(f"{result.label}{confidence} [{result.scorer}]  {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
