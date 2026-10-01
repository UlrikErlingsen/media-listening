"""Evaluate ListenSignal's sentiment scorers on the NoReC_sentence "mixed" test split.

    python scripts/evaluate_sentiment.py [--parquet path] [--scorers lexicon norbert]

The test split (1,272 Norwegian review sentences; CC BY-NC 4.0, University of Oslo LTG) is downloaded once to
data/eval/ and is never committed or redistributed. NoReC is review text, not news: these numbers say how the
scorers behave on the data NorBERT3 was trained for, not how accurate they are on Norwegian headlines.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import urllib.request

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listensignal.sentiment import LABELS, NorbertScorer, lexicon_sentence_label  # noqa: E402

URL = "https://huggingface.co/api/datasets/ltg/norec_sentence/parquet/mixed/test/0.parquet"
DEFAULT_PATH = ROOT / "data" / "eval" / "norec_sentence_mixed_test.parquet"


def gold_label(value) -> str:
    codes = sorted(int(v) for v in value)
    if codes == [0, 1]:
        return "Mixed"
    return {0: "Negative", 1: "Positive", 2: "Neutral"}[codes[0]]


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading the NoReC_sentence test split to {path} …")
        urllib.request.urlretrieve(URL, path)
    frame = pd.read_parquet(path)
    frame["gold"] = frame["sentiment"].map(gold_label)
    return frame


def report(name: str, gold: pd.Series, predicted: list[str]) -> None:
    labels = list(LABELS)
    print(f"\n=== {name} · n = {len(gold)} ===")
    print(f"accuracy {accuracy_score(gold, predicted):.3f} · macro F1 {f1_score(gold, predicted, labels=labels, average='macro'):.3f}"
          f" · weighted F1 {f1_score(gold, predicted, labels=labels, average='weighted'):.3f}")
    print(classification_report(gold, predicted, labels=labels, digits=3, zero_division=0))
    matrix = pd.DataFrame(confusion_matrix(gold, predicted, labels=labels), index=[f"gold {x}" for x in labels], columns=labels)
    print(matrix.to_string())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--scorers", nargs="+", default=["lexicon", "norbert"], choices=["lexicon", "norbert"])
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = load(args.parquet)
    print("Gold label counts:", data["gold"].value_counts().to_dict())
    if "lexicon" in args.scorers:
        report("lexicon-v1", data["gold"], [lexicon_sentence_label(text) for text in data["review"]])
    if "norbert" in args.scorers:
        try:
            scorer = NorbertScorer()
        except Exception as exc:  # noqa: BLE001
            print(f"\nNorBERT3 skipped: {type(exc).__name__}: {exc}")
        else:
            predicted = [label for label, _ in scorer._sentences(data["review"].tolist())]
            report(scorer.name, data["gold"], predicted)
    majority = data["gold"].mode().iat[0]
    report(f"baseline: always '{majority}'", data["gold"], [majority] * len(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
