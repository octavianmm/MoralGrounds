# ETHICS 10k Collaborator Analysis

**Dataset snapshot:** 14 October 2026. **Scope:** 9,975 production instructions; 29,925 human ratings; 19 coded annotators; nine supplied LLM conditions.

The five human CSVs retain every annotation from all three raters, including dissenting rationales and original annotation-cell values. Final labels are equally weighted human majority votes. Comparison rationales use majority-supporting humans, but the data itself is never majority-filtered.

## Corpus and Validity

Each partition has 1,995 items and 5,985 human annotations. Every item has three distinct annotators, and every annotator has 1,575 production ratings. Required categorical fields and applicable Virtue explanations are complete in the normalized human data. This establishes protocol validity, not independently adjudicated ethical correctness.

## Human Agreement

| Partition | Items | Unanimous | Pairwise [95% CI] | Fleiss kappa | Nominal alpha |
| --- | --- | --- | --- | --- | --- |
| Commonsense | 1,995 | 1,444 | 81.59% [80.28%, 82.89%] | 0.631 | 0.631 |
| Deontology | 1,995 | 1,767 | 92.38% [91.45%, 93.28%] | 0.827 | 0.827 |
| Justice | 1,995 | 1,541 | 84.83% [83.62%, 86.10%] | 0.687 | 0.687 |
| Utilitarianism | 1,995 | 1,668 | 89.07% [87.97%, 90.14%] | 0.781 | 0.781 |
| Virtue | 1,995 | 1,759 | 92.11% [91.14%, 93.08%] | 0.842 | 0.842 |
| Overall | 9,975 | 8,179 | 88.00% [87.49%, 88.48%] | 0.754 | 0.754 |

Pairwise agreement counts agreeing pairs, not unanimous items. A three-human unanimous item scores 1; a 2-1 item scores 1/3. There are 8,179 unanimous and 1,796 split items. Overall chance-adjusted scores are within-partition means, not a pooled category system.

## Model Panels

**Frontier trio:** `anthropic/claude-fable-5.1`, `google/gemini-3.8-flash`, `openai/gpt-6-astra`.
**Remaining six:** `GaMS-27B-Instruct`, `GaMS3-12B-Instruct`, `Qwen3.5-27B`, `Qwen3.5-9B`, `gemma-2-27b-it`, `gemma-3-12b-it`.

Model names are export identifiers, not independently verified checkpoint provenance. Panel membership is fixed in config/model_groups.json; it is not reselected during reruns.

## LLM Label Coverage

| Model | Valid / 9,975 | Absent | Empty | Invalid |
| --- | --- | --- | --- | --- |
| anthropic/claude-fable-5.1 | 9,967 | 8 | 0 | 0 |
| google/gemini-3.8-flash | 9,963 | 12 | 0 | 0 |
| openai/gpt-6-astra | 9,972 | 3 | 0 | 0 |
| Qwen3.5-27B | 9,975 | 0 | 0 | 0 |
| Qwen3.5-9B | 9,975 | 0 | 0 | 0 |
| gemma-2-27b-it | 9,952 | 0 | 1 | 22 |
| gemma-3-12b-it | 9,970 | 0 | 0 | 5 |
| GaMS3-12B-Instruct | 9,975 | 0 | 0 | 0 |
| GaMS-27B-Instruct | 9,974 | 0 | 1 | 0 |

There are 89,752 received rows, 89,723 valid labels, 23 absent rows, two empty labels and 27 invalid labels. Missingness is reported rather than guessed or treated as an ethical error.

## LLM Internal Agreement


### All nine

| Partition | Items with >=2 labels | Complete panels | Pairwise [95% CI] | Fleiss kappa | Nominal alpha |
| --- | --- | --- | --- | --- | --- |
| Commonsense | 1,995 | 1,991 | 79.09% [78.10%, 80.04%] | 0.575 | 0.575 |
| Deontology | 1,995 | 1,986 | 87.18% [86.38%, 88.01%] | 0.684 | 0.682 |
| Justice | 1,995 | 1,993 | 80.27% [79.38%, 81.16%] | 0.588 | 0.588 |
| Utilitarianism | 1,995 | 1,958 | 79.86% [78.92%, 80.78%] | 0.600 | 0.597 |
| Virtue | 1,995 | 1,995 | 88.88% [88.15%, 89.59%] | 0.778 | 0.778 |
| Overall | 9,975 | 9,923 | 83.06% [82.66%, 83.43%] | 0.645 | 0.644 |

### Frontier trio

| Partition | Items with >=2 labels | Complete panels | Pairwise [95% CI] | Fleiss kappa | Nominal alpha |
| --- | --- | --- | --- | --- | --- |
| Commonsense | 1,995 | 1,991 | 93.85% [92.98%, 94.65%] | 0.877 | 0.877 |
| Deontology | 1,995 | 1,986 | 97.04% [96.44%, 97.64%] | 0.931 | 0.931 |
| Justice | 1,995 | 1,994 | 91.58% [90.58%, 92.51%] | 0.825 | 0.826 |
| Utilitarianism | 1,995 | 1,986 | 95.92% [95.22%, 96.61%] | 0.920 | 0.919 |
| Virtue | 1,995 | 1,995 | 97.56% [97.03%, 98.06%] | 0.951 | 0.951 |
| Overall | 9,975 | 9,952 | 95.19% [94.85%, 95.52%] | 0.901 | 0.901 |

### Remaining six

| Partition | Items with >=2 labels | Complete panels | Pairwise [95% CI] | Fleiss kappa | Nominal alpha |
| --- | --- | --- | --- | --- | --- |
| Commonsense | 1,995 | 1,995 | 77.64% [76.57%, 78.68%] | 0.540 | 0.540 |
| Deontology | 1,995 | 1,995 | 85.58% [84.68%, 86.47%] | 0.632 | 0.632 |
| Justice | 1,995 | 1,994 | 78.21% [77.21%, 79.21%] | 0.543 | 0.543 |
| Utilitarianism | 1,995 | 1,967 | 76.76% [75.67%, 77.81%] | 0.536 | 0.535 |
| Virtue | 1,995 | 1,995 | 85.74% [84.83%, 86.61%] | 0.714 | 0.714 |
| Overall | 9,975 | 9,946 | 80.79% [80.33%, 81.22%] | 0.593 | 0.593 |

Raw pairwise agreement averages within-item valid pairs. Fleiss kappa uses complete fixed-size panels; alpha accommodates missing labels. Their denominators can differ. Internal agreement is between different supplied models, not repeat-generation stability of the same model.

### Humans and models on identical complete items

| Panel | Partition | Matched items | Human pairwise | LLM pairwise | Difference (pp) | Human / LLM kappa |
| --- | --- | --- | --- | --- | --- | --- |
| All nine | commonsense | 1,991 | 81.62% | 79.09% | -2.52 | 0.632 / 0.575 |
| All nine | deontology | 1,986 | 92.55% | 87.27% | -5.27 | 0.830 / 0.684 |
| All nine | justice | 1,993 | 84.85% | 80.25% | -4.59 | 0.687 / 0.588 |
| All nine | utilitarianism | 1,958 | 89.14% | 79.99% | -9.15 | 0.783 / 0.600 |
| All nine | virtue | 1,995 | 92.11% | 88.88% | -3.23 | 0.842 / 0.778 |
| All nine | overall | 9,923 | 88.05% | 83.11% | -4.94 | 0.755 / 0.645 |
| Frontier trio | commonsense | 1,991 | 81.62% | 93.84% | +12.22 | 0.632 / 0.877 |
| Frontier trio | deontology | 1,986 | 92.55% | 97.08% | +4.53 | 0.830 / 0.931 |
| Frontier trio | justice | 1,994 | 84.82% | 91.57% | +6.75 | 0.687 / 0.825 |
| Frontier trio | utilitarianism | 1,986 | 89.12% | 96.01% | +6.88 | 0.782 / 0.920 |
| Frontier trio | virtue | 1,995 | 92.11% | 97.56% | +5.45 | 0.842 / 0.951 |
| Frontier trio | overall | 9,952 | 88.04% | 95.21% | +7.17 | 0.755 / 0.901 |
| Remaining six | commonsense | 1,995 | 81.59% | 77.64% | -3.95 | 0.631 / 0.540 |
| Remaining six | deontology | 1,995 | 92.38% | 85.58% | -6.80 | 0.827 / 0.632 |
| Remaining six | justice | 1,994 | 84.85% | 78.20% | -6.66 | 0.687 / 0.543 |
| Remaining six | utilitarianism | 1,967 | 89.09% | 76.81% | -12.27 | 0.782 / 0.536 |
| Remaining six | virtue | 1,995 | 92.11% | 85.74% | -6.37 | 0.842 / 0.714 |
| Remaining six | overall | 9,946 | 88.00% | 80.81% | -7.19 | 0.754 / 0.593 |

## Each Model Versus Human Majority

Cells show available-case main-label agreement and valid paired n. The reference is the majority of the three human ratings, not an expert moral gold standard.

| Model | Commonsense | Deontology | Justice | Utilitarianism | Virtue | Overall |
| --- | --- | --- | --- | --- | --- | --- |
| anthropic/claude-fable-5.1 | 88.20% (n=1,992) | 96.49% (n=1,992) | 91.32% (n=1,994) | 95.79% (n=1,994) | 95.94% (n=1,995) | 93.55% (n=9,967) |
| google/gemini-3.8-flash | 88.01% (n=1,994) | 95.88% (n=1,989) | 89.97% (n=1,995) | 95.23% (n=1,990) | 96.04% (n=1,995) | 93.02% (n=9,963) |
| openai/gpt-6-astra | 87.37% (n=1,995) | 96.39% (n=1,995) | 88.82% (n=1,995) | 93.42% (n=1,992) | 95.74% (n=1,995) | 92.35% (n=9,972) |
| Qwen3.5-27B | 83.96% (n=1,995) | 93.38% (n=1,995) | 85.46% (n=1,995) | 92.38% (n=1,995) | 90.78% (n=1,995) | 89.19% (n=9,975) |
| Qwen3.5-9B | 75.99% (n=1,995) | 88.47% (n=1,995) | 79.80% (n=1,995) | 87.77% (n=1,995) | 86.47% (n=1,995) | 83.70% (n=9,975) |
| gemma-2-27b-it | 79.35% (n=1,995) | 87.82% (n=1,995) | 78.69% (n=1,994) | 74.66% (n=1,973) | 95.69% (n=1,995) | 83.26% (n=9,952) |
| gemma-3-12b-it | 72.38% (n=1,995) | 84.16% (n=1,995) | 81.40% (n=1,995) | 81.61% (n=1,990) | 93.73% (n=1,995) | 82.66% (n=9,970) |
| GaMS3-12B-Instruct | 68.12% (n=1,995) | 83.61% (n=1,995) | 81.45% (n=1,995) | 76.04% (n=1,995) | 93.73% (n=1,995) | 80.59% (n=9,975) |
| GaMS-27B-Instruct | 74.39% (n=1,995) | 80.60% (n=1,995) | 70.23% (n=1,995) | 63.34% (n=1,994) | 75.04% (n=1,995) | 72.72% (n=9,974) |

### Overall uncertainty and chance adjustment

| Model | Agreement [95% CI] | Weighted domain kappa | Balanced accuracy | Macro-F1 |
| --- | --- | --- | --- | --- |
| anthropic/claude-fable-5.1 | 93.55% [93.07%, 94.03%] | 0.867 | 93.25% | 93.36% |
| google/gemini-3.8-flash | 93.02% [92.52%, 93.53%] | 0.856 | 92.62% | 92.78% |
| openai/gpt-6-astra | 92.35% [91.84%, 92.87%] | 0.843 | 92.20% | 92.17% |
| Qwen3.5-27B | 89.19% [88.59%, 89.80%] | 0.776 | 88.56% | 88.79% |
| Qwen3.5-9B | 83.70% [82.97%, 84.40%] | 0.658 | 82.35% | 82.71% |
| gemma-2-27b-it | 83.26% [82.53%, 84.00%] | 0.651 | 82.11% | 82.48% |
| gemma-3-12b-it | 82.66% [81.91%, 83.39%] | 0.633 | 81.20% | 81.45% |
| GaMS3-12B-Instruct | 80.59% [79.84%, 81.37%] | 0.588 | 78.78% | 79.09% |
| GaMS-27B-Instruct | 72.72% [71.83%, 73.60%] | 0.450 | 73.10% | 72.28% |

The machine-readable table additionally provides per-partition confusion counts, common-all and common-frontier support, lower/upper missing-label bounds and paired model tests. Agreement against a human majority and agreement between individual human pairs are different estimands; neither establishes ethical superiority.

## Categorical Rationales

Commonsense, Deontology and Justice have categorical rationales. **Production Utilitarianism also has ten multi-select categories**, so it is included. Deontology has separate main and moral-principle fields. Virtue explanations are free text and receive no invented categorical or semantic agreement score.

Jaccard is category-set intersection divided by union; exact-set agreement requires complete equality. Each item receives equal weight after averaging eligible actor pairs. Empty/inapplicable fields never count as perfect matches. Internal baselines retain all original eligible humans/models, not only majority-supporting judgments.

### Internal human and LLM rationale agreement

| Field | Panel | Items / pairs | Jaccard | Exact sets |
| --- | --- | --- | --- | --- |
| Commonsense principles | Humans | 1,995 / 5,985 | 41.53% | 26.02% |
| Commonsense principles | All nine | 1,995 / 71,788 | 54.49% | 31.95% |
| Commonsense principles | Frontier trio | 1,995 / 5,977 | 72.19% | 46.20% |
| Commonsense principles | Remaining six | 1,995 / 29,925 | 53.28% | 33.76% |
| Deontology main | Humans | 1,995 / 5,985 | 72.33% | 72.33% |
| Deontology main | All nine | 1,995 / 71,748 | 66.76% | 66.76% |
| Deontology main | Frontier trio | 1,995 / 5,967 | 86.10% | 86.10% |
| Deontology main | Remaining six | 1,995 / 29,925 | 63.48% | 63.48% |
| Deontology moral principles | Humans | 1,165 / 2,779 | 43.41% | 26.38% |
| Deontology moral principles | All nine | 1,675 / 33,282 | 52.66% | 33.04% |
| Deontology moral principles | Frontier trio | 1,091 / 2,929 | 72.06% | 47.14% |
| Deontology moral principles | Remaining six | 1,613 / 14,190 | 51.05% | 32.48% |
| Justice category | Humans | 1,995 / 5,985 | 59.18% | 59.18% |
| Justice category | All nine | 1,995 / 71,812 | 67.23% | 67.23% |
| Justice category | Frontier trio | 1,995 / 5,983 | 82.96% | 82.96% |
| Justice category | Remaining six | 1,995 / 29,925 | 64.34% | 64.34% |
| Utilitarianism categories | Humans | 1,995 / 5,985 | 42.82% | 27.15% |
| Utilitarianism categories | All nine | 1,995 / 71,725 | 51.86% | 21.30% |
| Utilitarianism categories | Frontier trio | 1,995 / 5,967 | 65.45% | 32.38% |
| Utilitarianism categories | Remaining six | 1,995 / 29,910 | 50.06% | 20.21% |

Different panels may have different applicable items, especially in Deontology. The accompanying matched-complete table removes that item-set difference, at the cost of selecting only cases where all three humans and every panel member have an applicable valid rationale.

### Matched complete rationale panels

| Field | Panel | Common items | Human Jaccard / exact | LLM Jaccard / exact |
| --- | --- | --- | --- | --- |
| Commonsense principles | All nine | 1991 | 41.55% / 26.02% | 54.46% / 31.92% |
| Commonsense principles | Frontier trio | 1991 | 41.55% / 26.02% | 72.20% / 46.24% |
| Commonsense principles | Remaining six | 1995 | 41.53% / 26.02% | 53.28% / 33.76% |
| Deontology main | All nine | 1986 | 72.54% / 72.54% | 66.86% / 66.86% |
| Deontology main | Frontier trio | 1986 | 72.54% / 72.54% | 86.24% / 86.24% |
| Deontology main | Remaining six | 1995 | 72.33% / 72.33% | 63.48% / 63.48% |
| Deontology moral principles | All nine | 448 | 41.96% / 19.05% | 58.16% / 32.34% |
| Deontology moral principles | Frontier trio | 688 | 44.02% / 23.11% | 72.25% / 45.83% |
| Deontology moral principles | Remaining six | 472 | 41.67% / 19.07% | 54.32% / 29.31% |
| Justice category | All nine | 1994 | 59.16% / 59.16% | 67.21% / 67.21% |
| Justice category | Frontier trio | 1994 | 59.16% / 59.16% | 82.95% / 82.95% |
| Justice category | Remaining six | 1995 | 59.18% / 59.18% | 64.34% / 64.34% |
| Utilitarianism categories | All nine | 1984 | 42.91% / 27.20% | 51.90% / 21.34% |
| Utilitarianism categories | Frontier trio | 1986 | 42.93% / 27.24% | 65.44% / 32.38% |
| Utilitarianism categories | Remaining six | 1992 | 42.81% / 27.11% | 50.05% / 20.20% |

### Model versus majority-supporting human rationales

| Model | Commonsense principles | Deontology main | Deontology moral principles | Justice category | Utilitarianism categories |
| --- | --- | --- | --- | --- | --- |
| anthropic/claude-fable-5.1 | 42.34% (n=1,992) | 75.33% (n=1,992) | 44.34% (n=1,127) | 68.07% (n=1,994) | 44.22% (n=1,994) |
| google/gemini-3.8-flash | 45.48% (n=1,994) | 76.28% (n=1,989) | 48.29% (n=1,024) | 68.00% (n=1,995) | 41.85% (n=1,990) |
| openai/gpt-6-astra | 47.78% (n=1,995) | 76.28% (n=1,995) | 46.70% (n=959) | 67.94% (n=1,995) | 50.43% (n=1,992) |
| Qwen3.5-27B | 46.41% (n=1,995) | 70.48% (n=1,995) | 44.26% (n=1,153) | 62.87% (n=1,995) | 43.01% (n=1,995) |
| Qwen3.5-9B | 41.20% (n=1,995) | 56.38% (n=1,995) | 37.18% (n=1,371) | 53.19% (n=1,995) | 40.85% (n=1,995) |
| gemma-2-27b-it | 41.98% (n=1,995) | 68.55% (n=1,995) | 43.02% (n=1,071) | 60.00% (n=1,995) | 38.38% (n=1,995) |
| gemma-3-12b-it | 40.38% (n=1,995) | 61.80% (n=1,995) | 41.91% (n=1,163) | 56.88% (n=1,995) | 34.79% (n=1,995) |
| GaMS3-12B-Instruct | 41.01% (n=1,995) | 61.24% (n=1,995) | 30.70% (n=641) | 62.27% (n=1,995) | 40.03% (n=1,995) |
| GaMS-27B-Instruct | 33.49% (n=1,995) | 60.21% (n=1,995) | 32.15% (n=972) | 51.20% (n=1,995) | 40.98% (n=1,992) |

### Rationale agreement when the final verdict also matches

| Model | Commonsense principles | Deontology main | Deontology moral principles | Justice category | Utilitarianism categories |
| --- | --- | --- | --- | --- | --- |
| anthropic/claude-fable-5.1 | 44.62% (n=1,757) | 78.03% (n=1,922) | 44.95% (n=1,102) | 74.28% (n=1,821) | 44.82% (n=1,910) |
| google/gemini-3.8-flash | 48.58% (n=1,755) | 79.49% (n=1,907) | 49.05% (n=1,002) | 75.23% (n=1,795) | 42.70% (n=1,895) |
| openai/gpt-6-astra | 51.15% (n=1,743) | 78.97% (n=1,923) | 47.18% (n=946) | 75.79% (n=1,772) | 52.25% (n=1,861) |
| Qwen3.5-27B | 50.42% (n=1,675) | 75.17% (n=1,863) | 44.96% (n=1,095) | 73.12% (n=1,705) | 44.05% (n=1,843) |
| Qwen3.5-9B | 45.79% (n=1,516) | 63.19% (n=1,765) | 37.58% (n=1,203) | 65.75% (n=1,592) | 41.91% (n=1,751) |
| gemma-2-27b-it | 47.24% (n=1,583) | 75.30% (n=1,752) | 42.47% (n=949) | 73.45% (n=1,569) | 38.96% (n=1,473) |
| gemma-3-12b-it | 47.22% (n=1,444) | 71.95% (n=1,679) | 41.00% (n=977) | 68.64% (n=1,624) | 35.73% (n=1,624) |
| GaMS3-12B-Instruct | 47.17% (n=1,359) | 72.83% (n=1,668) | 30.65% (n=615) | 75.47% (n=1,625) | 40.80% (n=1,517) |
| GaMS-27B-Instruct | 38.12% (n=1,484) | 73.85% (n=1,608) | 31.89% (n=800) | 71.82% (n=1,401) | 40.95% (n=1,262) |

The primary reference retains the two/three majority-aligned human sets separately. The primary model label need not match; the same-judgment sensitivity requires it to match. Conditional cohorts differ by model, so rationale ranks are not automatically paired superiority claims. Dice, exact-set scores, field-specific kappas, intervals and category-level diagnostics remain in the detailed CSVs. No single overall rationale score pools unrelated category spaces or counts Deontology twice.

## Striking Disagreements

The counts below require unanimous humans. All-nine majority opposition includes all-nine unanimity and is not disjoint from frontier opposition. Invalid or absent model outputs are not opposing votes.

| Partition | Humans unanimous, all 9 opposite | Humans unanimous, >=5/9 opposite | Humans unanimous, frontier 3 opposite | Selected cases |
| --- | --- | --- | --- | --- |
| Commonsense | 6 | 117 | 36 | 5 |
| Deontology | 1 | 66 | 6 | 5 |
| Justice | 5 | 85 | 14 | 5 |
| Utilitarianism | 4 | 63 | 12 | 5 |
| Virtue | 1 | 24 | 9 | 5 |

See [selected examples](examples/EXAMPLES.md), [full selected-case CSV](examples/selected_cases.csv), [full JSON evidence](examples/selected_cases.json) and [all eligible disagreement candidates](examples/all_disagreement_candidates.csv). Selection ranks vote opposition/coverage, not supposed moral correctness. Full narratives and all annotations are retained; excerpts are explicitly marked.

## Files and Reproduction

- [Five complete three-human input CSVs](../data/humans).
- [Five model-input CSVs](../data/llms).
- [Every human majority and every model label, per partition](per_item_predictions).
- [Human reliability](judgments/human_reliability.csv).
- [All model-pair agreement, per partition and overall](judgments/pairwise_model_agreement.csv).
- [Model-panel reliability](judgments/group_reliability.csv).
- [Each model versus human majority](judgments/model_vs_human.csv).
- [Internal categorical-rationale agreement](rationales/group_rationale_agreement.csv).
- [Model-human categorical-rationale agreement](rationales/model_human_overlap.csv).
- [Rationale distributions and category shifts](rationales/model_human_distances.csv).
- [Matched complete label panels](summary/matched_complete_label_panels.csv).
- [Matched complete rationale panels](summary/matched_complete_rationale_panels.csv).

This run uses **5,000 within-partition item-bootstrap resamples**, seed **20260917**. All actor annotations move together within a sampled item. Model/annotator populations and model reruns are not resampled. Related story templates can violate independent-item assumptions; optional scenario-cluster bootstrap support remains in the engine.

Use the package README for one-command reproduction. All paths are relative, no API access is needed, and the original source repository is not needed for rerunning the analyses. Raw XLSM files, Office metadata, administrative identity mappings, payment records and credentials are excluded. No redistribution license is asserted; confirm the project's/source-dataset terms before public release.
