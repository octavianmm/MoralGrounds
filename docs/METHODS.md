# Methods

## Boundary and Provenance

The scientific boundary is the verified normalized production human export and the supplied nine-model response CSVs. The human package preserves the full normalized records and original annotation-cell values from 95 submitted XLSM files. Workbooks were read without executing VBA; no source file was changed. The original workbook files and their identity-bearing Office metadata are not distributed.

The frozen package inputs reconstruct the original human data and model annotation fields. Majority labels and rationale references are rebuilt, not copied as unquestioned truth. Source-relative hashes are in `provenance/SOURCE_MANIFEST.csv`; input/code hashes and numerical environment are also recorded for each analysis.

## Human Decisions

Three independent human votes determine the unweighted majority. All original individual annotations remain in `data/humans/`, including dissenting judgments/rationales. Calibration MACE scores do not weight production votes.

Pairwise agreement averages the three possible human comparisons per item. Fleiss kappa and nominal Krippendorff alpha adjust for category prevalence. Coefficients are calculated within each task because the label meanings differ. Overall coefficients average the within-domain results with the exported eligible denominators; they do not collapse YES/NO, moral wrongness and A/B into one universal category space.

## Model Decisions and Panels

The nine supplied model identifiers are compared with the human majority using available valid paired labels. Missing rows, empty labels and invalid labels are separate, reported states. Available-case, common-all and common-frontier cohorts are exported. Per-model/per-partition confusion counts, Cohen kappa, balanced accuracy, macro-F1 and MCC accompany raw agreement.

Internal comparisons include all 36 model pairs, per partition and overall. Fixed panels are all nine, three commercial/frontier conditions and the remaining six; smaller family panels are supplementary. Raw within-item model-pair agreement uses available pairs, Fleiss uses complete fixed-size panels, and alpha permits missingness. Their denominator differences are explicit.

Additional tables compare human and model internal agreement on the **same complete-panel item set**. Thus incomplete model answers do not quietly change the human baseline. More-member panel unanimity is not directly comparable with three-human unanimity. All measures concern the supplied outputs, not test-retest reliability from repeated generations.

## Categorical Rationales

Fields are Commonsense moral principles, Deontology main rationale, Deontology moral principles, Justice categories and production Utilitarianism categories. Virtue is free text and is excluded from categorical agreement.

Human-human and model-model internal baselines retain every original valid/applicable field. They are not majority-filtered. For model-human comparisons, retain only humans whose final judgment supports the majority, averaging model-human overlaps within item and then across items. The `majority_aligned` scope does not require the model judgment to agree. The `same_judgment` sensitivity does require agreement, preventing comparison of reasons for opposing judgments.

Report Jaccard, Dice and exact-set agreement. Single-choice rationale fields also have nominal coefficients. Empty or inapplicable sets are excluded; they never create agreement. Deontology secondary principles require moral main categories. Matched-complete rationale panels select the same items where all three humans and every panel member have valid/applicable values; this is a narrower conditional cohort, not a universal superiority comparison.

Distributional analyses distinguish normalized category mention shares from response-level selection prevalence. Total variation/Jensen-Shannon apply to normalized distributions, not prevalence vectors that can sum above one. Item-balanced and annotation-pooled sensitivities and category-set size diagnostics are retained. No global rationale agreement pools incomparable fields or counts Deontology twice.

## Disagreement Selection

Candidates require **three unanimous human judgments**. Priorities are: complete all-nine unanimous opposition; complete all-nine majority opposition; complete frontier-trio opposition; majority opposition among at least seven valid models. Missing/invalid labels are not opposing votes. Tie-breaking is transparent and stable: more opposing and valid model votes, more frontier opposition, fewer human ambiguity/culture flags, shorter input, then numeric task ID.

Five examples per partition are selected when available. Full text, all three human annotations and every available model response/rationale are included in CSV/JSON. Markdown excerpts stop after 180 whitespace-delimited words and are marked as excerpts. Selected cases illustrate contrast; they are neither representative prevalence estimates nor automatic moral-error labels. The complete eligible-candidate list is supplied.

## Uncertainty and Limits

The default is 5,000 seeded within-partition item-bootstrap draws. All human/model information for an item moves together; paired comparisons reuse the draws. These intervals condition on the fixed humans/models and items, not geographical model populations or future participants. Related narratives can create dependence beyond individual items; the engine supports an optional full scenario-cluster map.

Human-majority concordance is not independent ethical correctness. The fixed frontier panel is not selected afresh to maximize results. Model provenance/settings not present in the original exports are not inferred. Multi-select rationale overlap does not reveal models' internal causal reasoning, and free-text explanation semantics are not quantified. No redistribution license or public-release approval is asserted.
