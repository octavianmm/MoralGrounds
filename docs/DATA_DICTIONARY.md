# Data Dictionary

## Human CSVs

Files in `data/humans/` each contain 1,995 instruction rows. CSV is UTF-8 with quoted fields; quoted cells can contain line breaks. Use a CSV parser rather than counting physical lines or splitting on commas.

| Field family | Meaning |
| --- | --- |
| `item_id` | Stable package key: `partition:task_instruction_id`. |
| `partition`, `task` | One of the five ethical tasks. |
| `input` | Complete normalized instruction text. |
| `meta` | Original ETHICS metadata object, preserved as supplied. Use `ethics_analysis.schema.metadata`, which safely handles JSON/Python literal formats; never use `eval`. |
| `task_instruction_id` | Numeric identifier reused across partitions; not globally unique alone. |
| `instruction_id` | Original production instruction identifier. |
| `source_split`, `source_position_within_task`, `source_csv_row` | ETHICS provenance, not a new held-out evaluation partition. |
| `human_majority_label`, `human_majority_count` | Ordinary equally weighted majority, with support 2 or 3. |
| `human_unanimous` | `TRUE` for a 3-0 human vote, `FALSE` for a 2-1 vote. |
| `individual_labels_json`, `annotator_codes_json` | Three-element JSON arrays in annotation-copy order. |
| `all_primary_rationale_sets_json` | Every human's primary categorical selection, including dissenters. Empty lists mean inapplicable fields, not an agreed absence of moral grounds. |
| `all_secondary_rationale_sets_json` | All three Deontology secondary selections, in the same order. |
| `all_free_text_rationales_json` | All three normalized Virtue explanations; empty array outside Virtue. Original source-cell explanations remain separately preserved. |
| `majority_aligned_copies_json` | Which two or three annotation copies support the majority. This does not remove other columns. |

For **each** slot `annotator_1_`, `annotator_2_`, `annotator_3_`, all original normalized annotation-specific columns are preserved:

- `annotator_code`: six-character project pseudonym.
- `main_label`: canonical partition-specific label.
- `output`: normalized workbook output string.
- `rationale`: Commonsense/Justice/Utilitarianism rationale, or Virtue text.
- `main_rationale`, `moral_rationale`: separate Deontology levels.
- `ambiguity`, `cultural_specificity`: original normalized flag strings; blank culture field means no flag was supplied, not proven cultural neutrality.
- `annotation_copy`: 1, 2 or 3, agreeing with the slot.
- Source-row and assignment provenance, including coded workbook filename, original Excel row, batch positions and sequence values. Numeric `annotator_id` is the original sequence number, not a published identity mapping.

Each slot additionally has `source_cell_input`, `source_cell_output`, `source_cell_rationale`, `source_cell_main_rationale`, `source_cell_moral_rationale`, `source_cell_ambiguity` and `source_cell_cultural_specificity`. These are the original worksheet cell values, before deterministic normalization. Non-applicable column families are empty. Original placeholders, spelling variants and non-required explanations are preserved here rather than being silently discarded.

`docs/schema.json` lists the precise original column names and the shared/annotator-specific division. The prepared long table reconstructed from these CSVs retains all 29,925 normalized annotation records. Source-cell values are for inspection, not an instruction to override the tested normalization or infer a new judgment.

## Model CSVs

Files in `data/llms/` contain one row per **received model/item response**, across nine models. There are 89,752 rows overall, including unusable labels. Missing responses are absent rather than replaced by empty invented records.

| Column | Meaning |
| --- | --- |
| `item_id`, `partition`, `model` | Stable instruction identity and exact supplied model identifier. |
| `raw_output` | Original final-label string. |
| `raw_rationale`, `raw_main_rationale`, `raw_moral_rationale` | Original rationale strings used by the tested parser. |
| `normalized_label`, `label_status` | Canonical label if valid; status `valid`, `missing` or `invalid`. |
| `structured_fields_json` | Each field's parsed value, validity/applicability status and original raw string. |
| `source_export`, `source_row` | Original research CSV path relative to the model archive and CSV record number. No machine-specific path is required. |

Instruction text/metadata are joined from the matching human row. The original exporter verified source text equality after whitespace/Unicode normalization and checked explicit instruction/metadata IDs before consolidating model records. The package does not contain full HTTP journals, retries, credentials or undocumented checkpoint settings.

## Results

Model-label matrices under `results/per_item_predictions/` provide every human majority and all nine canonical model labels, plus one `__status` column per model. `absent_row` differs from `missing` and `invalid`. Blank labels never become opposing votes.

Most metric CSVs store proportions in [0,1], not percentages. Reports format percentages. Cohen/Fleiss kappa and alpha are chance-adjusted coefficients; undefined values remain blank/NaN, not zero. `gap_pp` denotes percentage points. Multi-select Jaccard is a similarity score, not the fraction of identical whole rationales.

Counts/eligibility are field-, panel-, model- and scope-specific. `n_items` counts instructions; `n_human_comparisons` counts model-human pairs; these are different denominators. Rationale fields marked `inapplicable` are not missing required annotations. A blank JSON set must not be scored as perfectly agreeing with another empty set.
