# Sentiment evaluation

Measured on **1 October 2026** with ListenSignal 1.0.0. Reproduce with:

```bash
python scripts/evaluate_sentiment.py
```

The script downloads the NoReC_sentence test split to `data/eval/` (gitignored). The data are CC BY-NC 4.0
(University of Oslo, Language Technology Group) and are not redistributed with this repository.

## What was measured

**Data:** NoReC_sentence, `mixed` configuration, **test split**: 1,272 Norwegian (Bokmål) sentences from
professional reviews (Neutral 598, Positive 401, Negative 182, Mixed 91). Each sentence was scored on its own.

**Not measured:** accuracy on Norwegian *news headlines*, on Nynorsk, on forum posts, or on tone *towards a
brand*. There is no labelled Norwegian headline set in this repository. Treat the dashboard's sentiment as an
indicator with known limits, not as a measured truth about news coverage.

## Results (test split, n = 1,272)

| Scorer | Accuracy | Macro F1 | Weighted F1 | F1 Positive | F1 Negative | F1 Neutral | F1 Mixed |
|---|---|---|---|---|---|---|---|
| NorBERT3 (`norbert3@a6f5633`, transformers 4.57.6, CPU) | 0.754 | 0.687 | **0.749** | 0.768 | 0.547 | 0.817 | 0.615 |
| Lexicon fallback (`lexicon-v1`) | 0.553 | 0.356 | **0.498** | 0.448 | 0.159 | 0.690 | 0.128 |
| Baseline: always "Neutral" | 0.470 | 0.160 | 0.301 | 0 | 0 | 0.640 | 0 |

The model card reports a weighted F1 of 0.764 on the same split; ListenSignal's integration (pinned revision,
transformers 4.57.6) measures 0.749. The small gap is most likely library-version or tokenization differences; it
was not investigated further.

**Reading the lexicon row:** the fallback is clearly better than guessing but much weaker than NorBERT3. It finds
only about one in ten negative sentences (Negative recall 0.11) and almost never detects Mixed. Use it to get the
dashboard working without the optional extra, not to report tone.

### How the lexicon was developed (to keep the test split honest)

1. The first lexicon was written by hand from general Norwegian knowledge, before any evaluation.
2. It scored weighted F1 0.459 on the **validation** split.
3. Around 80 general evaluative words (e.g. *kjedelig, dessverre, nydelig, herlig*) were added, again from
   language knowledge, not by mining the data. Validation weighted F1 rose to 0.507.
4. The test split was then scored once (0.496). An earlier test-split run of the first lexicon gave 0.434; no change
   was made in response to either test result.
5. Later, a few entries were found to match unrelated words in news text: `hyll*` (to praise) also matched
   *hylleplass* (shelf space), and automatic inflection turned `ros` into *rosa* (pink), `god` into *gods* (goods)
   and `fare` into *faren* (the father). These were made exact-match (`ros!`, `god!`, `fare!` …). Validation
   weighted F1: 0.510. The test split was scored again for the table above (0.498).

## Scorer agreement on real headlines (not accuracy)

On 215 headlines collected from six live feeds on 1 October 2026 (VG, E24, Aftenposten, Nettavisen, Kampanje,
Teknisk Ukeblad), with headline + snippet scored as an item (lexicon as of step 4 above):

| NorBERT3 \ lexicon | Negative | Neutral | Positive | Total |
|---|---|---|---|---|
| Mixed | 2 | 0 | 2 | 4 |
| Negative | 8 | 6 | 0 | 14 |
| Neutral | 32 | 126 | 12 | 170 |
| Positive | 1 | 16 | 10 | 27 |
| **Total** | 43 | 148 | 24 | 215 |

The scorers agreed on 67 % of items. NorBERT3 labelled 79 % of headlines Neutral, including clearly bad news
such as an accident report ("Motorsyklist kritisk skadet i ulykke …"). The model was trained to judge *opinion*
in reviews, and news reports events in neutral language, so this is expected. The lexicon labels such headlines
Negative because of words like *ulykke* and *skadet*. Neither behaviour is "correct" for brand monitoring without a
definition of what tone you want to track; without gold labels, no accuracy can be stated.

## Practical guidance

- Install the `[sentiment]` extra if you report tone at all.
- Read the items behind any change in tone before acting; the dashboard links every mention.
- Compare tone *over time for the same sources and scorer*. Do not compare a NorBERT3 period with a lexicon period;
  the dashboard shows which scorer produced each label, and `collect --rescore` re-labels old items with the
  current scorer.
