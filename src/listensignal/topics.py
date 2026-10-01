"""Explainable topic grouping: TF-IDF on headlines + snippets, k-means clusters, top terms per cluster."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.preprocessing import normalize

from .matching import normalize_text

LSA_DIMENSIONS = 20
_TOKEN_PATTERN = r"(?u)\b[^\W\d_][\w-]*[^\W\d_]\b"


@lru_cache(maxsize=1)
def stopwords() -> frozenset[str]:
    text = (Path(__file__).resolve().parent / "lexicon" / "stopwords.txt").read_text(encoding="utf-8")
    words = " ".join(line for line in text.splitlines() if not line.startswith("#"))
    return frozenset(words.casefold().split())


def _strip_terms(text: str, remove: tuple[str, ...]) -> str:
    clean = normalize_text(text)
    for term in remove:
        clean = re.sub(rf"(?<!\w){re.escape(term)}\w*", " ", clean, flags=re.IGNORECASE)
    return clean


def default_k(n_docs: int) -> int:
    """Rule of thumb: about sqrt(n/2) clusters, between 2 and 12."""
    return int(min(12, max(2, round(math.sqrt(max(n_docs, 1) / 2)))))


@dataclass(frozen=True)
class TopicResult:
    assignments: np.ndarray
    clusters: pd.DataFrame  # cluster, size, top_terms, example
    method: str


def cluster_topics(
    texts: list[str],
    *,
    k: int | None = None,
    remove_terms: tuple[str, ...] = (),
    top_n: int = 8,
    random_state: int = 0,
) -> TopicResult:
    """Group texts into k clusters. Brand names in ``remove_terms`` are stripped so topics describe *what* is said."""
    docs = [_strip_terms(text, remove_terms) for text in texts]
    if len(docs) < 4:
        raise ValueError("Topic grouping needs at least 4 mentions in the selected period.")
    vectorizer = TfidfVectorizer(
        lowercase=True,
        token_pattern=_TOKEN_PATTERN,
        stop_words=sorted(stopwords()),
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.6,
        sublinear_tf=True,
    )
    try:
        matrix = vectorizer.fit_transform(docs)
    except ValueError as exc:
        raise ValueError("Too few repeated words to form topics; widen the period or include more brands.") from exc
    k = max(1, min(k or default_k(len(docs)), matrix.shape[0] - 1, matrix.shape[1]))
    # LSA: k-means on raw sparse TF-IDF tends to dump most short headlines into one catch-all cluster,
    # so cluster in a 20-dimensional SVD space and describe clusters back in the original word space.
    dims = min(LSA_DIMENSIONS, matrix.shape[1] - 1, matrix.shape[0] - 1)
    space = normalize(TruncatedSVD(dims, random_state=random_state).fit_transform(matrix)) if dims >= 2 else matrix
    labels = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit_predict(space)
    terms = np.array(vectorizer.get_feature_names_out())
    rows = []
    for cluster in range(k):
        members = np.flatnonzero(labels == cluster)
        if not len(members):
            continue
        centroid = np.asarray(matrix[members].mean(axis=0)).ravel()
        top = terms[np.argsort(centroid)[::-1][:top_n]]
        sims = matrix[members] @ centroid  # example: the member closest to the cluster's mean word profile
        example = texts[members[int(np.argmax(sims))]]
        rows.append({"cluster": cluster + 1, "size": int(len(members)), "top_terms": ", ".join(top),
                     "example": normalize_text(example)[:160]})
    clusters = pd.DataFrame(rows).sort_values("size", ascending=False).reset_index(drop=True)
    method = (
        f"TF-IDF (1–2-grams, min_df=2, max_df=0.6) → LSA ({dims} dimensions) → k-means (k={k}, seed {random_state}); "
        "top terms = highest mean TF-IDF within the cluster"
    )
    return TopicResult(labels + 1, clusters, method)


def rising_terms(
    this_texts: list[str], prev_texts: list[str], *, remove_terms: tuple[str, ...] = (), top_n: int = 10
) -> pd.DataFrame:
    """Terms used in more items this week than last, ranked by smoothed log ratio of document frequency."""
    if not this_texts:
        return pd.DataFrame(columns=["term", "this_week", "prev_week", "log_ratio"])
    vectorizer = CountVectorizer(
        lowercase=True, token_pattern=_TOKEN_PATTERN, stop_words=sorted(stopwords()), binary=True, ngram_range=(1, 2)
    )
    docs = [_strip_terms(text, remove_terms) for text in this_texts + prev_texts]
    try:
        matrix = vectorizer.fit_transform(docs)
    except ValueError:
        return pd.DataFrame(columns=["term", "this_week", "prev_week", "log_ratio"])
    n_this = len(this_texts)
    this_df = np.asarray(matrix[:n_this].sum(axis=0)).ravel()
    prev_df = np.asarray(matrix[n_this:].sum(axis=0)).ravel()
    ratio = np.log((this_df + 0.5) / (max(n_this, 1))) - np.log((prev_df + 0.5) / max(len(prev_texts), 1))
    frame = pd.DataFrame({"term": vectorizer.get_feature_names_out(), "this_week": this_df, "prev_week": prev_df,
                          "log_ratio": ratio})
    frame = frame.loc[(frame["this_week"] >= 2) & (frame["this_week"] > frame["prev_week"])]
    return frame.sort_values(["log_ratio", "this_week"], ascending=False).head(top_n).reset_index(drop=True)
