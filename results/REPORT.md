# ETHICS production annotation analysis

## Verified input and protocol

The supplied production exports contain **9,975 instructions**, not 9,875:
1,995 in each of the five partitions. There are **29,925 human ratings**
from **19 annotators**, exactly three distinct annotators per instruction.
All 9,975 reconstructed human majorities match archive A's export;
all 9,975 reconstructed rationale records match its rationale aggregate.
This run consumes A's normalized individual exports; it does not rerun normalization of the 95 original macro-enabled workbooks.

Archive B supplies **9 model conditions** and **89,752 rows**.
There are **23 absent rows**, **2 empty final labels**,
and **27 invalid final labels**.
Every present row is aligned to the human data using partition plus an explicit instruction ID or metadata ID,
and its normalized scenario text is verified. No rows are joined by position or fuzzy text similarity.
Model identifiers below are read from the archive, not independently verified release descriptions.

The **production protocol**, not the preliminary 500-item protocol, governs the analysis:
commonsense principles apply to both judgments; deontology principles apply only to MORALLY RIGHT/WRONG main rationales;
justice is single-choice; utilitarianism now has ten structured multi-select rationale categories;
virtue free text is required only for YES. Inapplicable rationales are not missing data.
Numerical rubric references and exact category names followed by definitions are normalized with an audit trail.
Unrecognized text is never converted to OTHER.

## Human baseline

| Partition | Items | Unanimous | Mean pairwise agreement | Fleiss κ | Nominal α |
|---|---:|---:|---:|---:|---:|
| commonsense | 1,995 | 1,444 | 0.8159 | 0.6313 | 0.6314 |
| deontology | 1,995 | 1,767 | 0.9238 | 0.8268 | 0.8269 |
| justice | 1,995 | 1,541 | 0.8483 | 0.6867 | 0.6867 |
| utilitarianism | 1,995 | 1,668 | 0.8907 | 0.7814 | 0.7814 |
| virtue | 1,995 | 1,759 | 0.9211 | 0.8418 | 0.8418 |
| overall | 9,975 | 8,179 | 0.8800 | 0.7536 | 0.7536 |

Overall chance-adjusted values are weighted means of within-partition coefficients, not coefficients
calculated by treating different domain labels as the same category. Human-majority agreement is a
study-reference concordance measure, not a moral-correctness measure.
The leave-one-out file evaluates held-out humans against the other two raters only when those two agree;
it never evaluates a human against a majority containing their own vote. It is not an ethical ceiling.

## Each model against the human majority

| Model (archive identifier) | Valid / items | Agreement | 95% bootstrap interval | Weighted domain κ |
|---|---:|---:|---:|---:|
| anthropic/claude-fable-5.1 | 9,967 / 9,975 | 0.9355 | 0.9307–0.9403 | 0.8672 |
| google/gemini-3.8-flash | 9,963 / 9,975 | 0.9302 | 0.9252–0.9353 | 0.8556 |
| openai/gpt-6-astra | 9,972 / 9,975 | 0.9235 | 0.9184–0.9287 | 0.8435 |
| Qwen3.5-27B | 9,975 / 9,975 | 0.8919 | 0.8859–0.8980 | 0.7762 |
| Qwen3.5-9B | 9,975 / 9,975 | 0.8370 | 0.8297–0.8440 | 0.6576 |
| gemma-2-27b-it | 9,952 / 9,975 | 0.8326 | 0.8253–0.8400 | 0.6509 |
| gemma-3-12b-it | 9,970 / 9,975 | 0.8266 | 0.8191–0.8339 | 0.6334 |
| GaMS3-12B-Instruct | 9,975 / 9,975 | 0.8059 | 0.7984–0.8137 | 0.5884 |
| GaMS-27B-Instruct | 9,974 / 9,975 | 0.7272 | 0.7183–0.7360 | 0.4495 |

These are **available-case** results. `judgments/model_vs_human.csv` additionally supplies
`common_all` comparisons using the exact common valid item set for all nine models, and
`common_frontier` comparisons for the three-model frontier panel. It reports coverage, confusion matrices,
balanced accuracy, macro-F1, MCC, reference prevalence, agreement with the full human vote distribution,
and lower/upper agreement bounds for missing or invalid labels.
Overall balanced accuracy, macro-F1, MCC, and κ are valid-item-weighted domain means.
Use `judgments/paired_model_comparisons.csv` for paired differences on identical items:
exact McNemar tests in item-bootstrap mode, stratified paired-bootstrap intervals, and Holm adjustment across all model-pair/domain tests.
In cluster-bootstrap mode, item-independent McNemar p-values are suppressed.

## Agreement inside model panels

| Panel | Complete items | Mean pair agreement | Domain-weighted Fleiss κ | All panel agrees against human majority |
|---|---:|---:|---:|---:|
| all | 9,923 | 0.8306 | 0.6452 | 84 |
| frontier | 9,952 | 0.9519 | 0.9008 | 371 |
| gams | 9,974 | 0.7296 | 0.4305 | 980 |
| gemma | 9,947 | 0.8545 | 0.6842 | 972 |
| qwen | 9,975 | 0.8829 | 0.7477 | 768 |
| other_models | 9,946 | 0.8079 | 0.5933 | 222 |

`judgments/item_consensus.csv` includes each instruction's label votes, strict majority or tie,
valid-panel size, unanimity among available responses, complete-panel unanimity,
mean pairwise agreement, entropy in bits, and relation to the human majority.
Group Fleiss κ uses complete panels; nominal Krippendorff α uses all items with at least two valid ratings.
The overall Fleiss denominator may therefore differ from the overall raw-agreement denominator.
Ensemble majority labels abstain on ties and require at least two valid votes.
Vote entropy is panel disagreement, not calibrated model uncertainty.

## Rationale agreement and ethical attention

All model-human rationale references retain only human annotators whose binary
label matches the human majority: two humans for split items and three for
unanimous items, before field eligibility checks. The primary
`majority_aligned` scope does not require the model's label to match.

For the **same-judgment** analysis, a model must agree with the human-majority judgment;
only eligible human rationale annotations carrying that same final judgment enter its reference.
Both actors therefore express the same judgment before their rationale distributions are compared.
The primary human reference is item-balanced: average eligible human category vectors within each item,
then sum over the same paired items as the model. Annotation-pooled versions reproduce the earlier
response-pooling convention as a sensitivity analysis.

| Field | Lowest TV | Highest TV |
|---|---|---|
| commonsense_principles | GaMS3-12B-Instruct: 0.1135 (n=1,359) | GaMS-27B-Instruct: 0.2882 (n=1,484) |
| deontology_main | gemma-2-27b-it: 0.0294 (n=1,752) | Qwen3.5-9B: 0.3144 (n=1,765) |
| deontology_principles | anthropic/claude-fable-5.1: 0.1909 (n=1,102) | GaMS-27B-Instruct: 0.5090 (n=800) |
| justice_rationale | gemma-2-27b-it: 0.0739 (n=1,569) | GaMS3-12B-Instruct: 0.1882 (n=1,625) |
| utilitarianism_rationales | openai/gpt-6-astra: 0.1153 (n=1,861) | gemma-2-27b-it: 0.2219 (n=1,473) |

The displayed extrema describe actor-specific eligible cohorts and are **not** paired superiority tests.
`rationales/paired_rationale_distance_contrasts.csv` recomputes selected model-pair TV differences
on an identical eligible cohort and identical bootstrap draws. All rationale intervals are descriptive,
pointwise 95% intervals, not multiplicity-adjusted confirmatory tests.

For multi-select fields, **mention shares** sum to one and support total variation (TV),
Jensen–Shannon divergence in bits, and entropy. **Selection prevalence** is the fraction of eligible
responses selecting each category; its sum may exceed one. Both are exported, but TV is never
misapplied to unnormalized prevalence vectors. Fractional-response profiles and cardinality statistics
show whether apparent profile differences are driven by selecting more categories per response.

Itemwise overlap averages Jaccard, Dice, and exact-set match over valid model–human pairs within
an item, then averages across items. Empty/inapplicable sets never manufacture perfect agreement.
Single-choice fields additionally have weighted nominal κ; category-level binary κ exposes the
influence of nonselection. Human and model internal rationale baselines are provided separately.
Internal human reliability and raw field-quality diagnostics retain all original
individual annotations; they are not majority-filtered reference measures.
These are properties of expressed categories, not evidence about internal causal reasoning.

## Output-quality findings

- `Qwen3.5-27B` / `deontology_principles`: 1 missing, 0 invalid among 1,307 eligible present responses.
- `gemma-2-27b-it` / `deontology_principles`: 2 missing, 0 invalid among 1,176 eligible present responses.
- `gemma-3-12b-it` / `deontology_principles`: 8 missing, 0 invalid among 1,402 eligible present responses.
- `GaMS-27B-Instruct` / `utilitarianism_rationales`: 1 missing, 2 invalid among 1,995 eligible present responses.
- `GaMS-27B-Instruct` / `virtue_text`: 0 missing, 2 invalid among 888 eligible present responses.

The detailed log distinguishes absent rows, invalid labels, unrecognized categories, unfilled templates,
missing eligible rationales, and extra inapplicable rationales. Legitimate justice OTHER choices remain
distinct from invalid final-label OTHER. The old pilot's GaMS justice parsing exclusion is not imported
into the new dataset: quality decisions are based on the present files.

## Investigation and descriptive analyses

`review/all_items_with_evidence.csv` joins every scenario, human vote/rationale evidence,
model judgments/rationales, and transparent review flags. `priority_review.csv` and
`first_100_review_cases.csv` focus on coverage issues, unanimous model–human disagreements,
human ambiguity flags, and low rationale overlap despite matching judgments.
Flags prioritize human inspection; they do not automatically label either side as erroneous.

Source train/test, human unanimity, ambiguity flags, and culture-reference flags are reported in
`judgments/stratified_model_vs_human.csv`. These are descriptive strata; unflagged does not mean
culturally neutral, and the ETHICS source split is not evidence of model-pretraining separation.
Virtue YES-rationale lengths and repetition are analyzed descriptively, without inventing a semantic
similarity score. Logged frontier token/cost totals concern supplied returned rows only, not failed
requests, retries, or complete experiment expenditure.

## Reproducibility and inference scope

This run used **5,000 percentile bootstrap resamples**, seed
**20260917**, sampling instructions within ethical partitions and preserving the complete
human/model bundle for each selected instruction. The same bootstrap weights support paired
comparisons. Input hashes, software versions, configuration, timing, source-code hashes,
and detailed denominator/status exports accompany the results.

The bootstrap is conditional on these annotated items and this fixed annotator/model pool.
It does not quantify variation across new human populations, model reruns, temperatures, or prompts.
Potential dependence among related source scenarios should be assessed with the optional cluster-map
bootstrap rather than claiming universal independent sampling. No API requests are made.

## Principal files

- `audit/audit_summary.json`, `audit/coverage.csv`: counts, reconciliation, and missingness.
- `judgments/model_vs_human.csv`: per-model, per-partition, overall, and common-item results.
- `judgments/item_consensus.csv`: every instruction's model consensus.
- `judgments/pairwise_model_agreement.csv`, `group_reliability.csv`: model–model agreement.
- `judgments/paired_model_comparisons.csv`: paired statistical comparisons.
- `rationales/model_human_distances.csv`, `paired_category_profiles.csv`: ethical-attention distributions.
- `rationales/model_human_overlap.csv`, `item_model_human_overlap.csv`: active-set and same-judgment overlap.
- `rationales/field_quality.csv`: eligibility-aware rationale quality.
- `review/priority_review.csv`: auditable disagreement cases with source text.

## Methodological continuity

The supplied preliminary papers motivate separating final-judgment agreement from expressed moral
grounds, preserving individual human rationale choices, using active-set overlap for multi-select fields,
and using paired item bootstraps for distributional distances. Their older model releases, 500-item sample,
and older utilitarianism rationale format are not substituted for the present production data.
