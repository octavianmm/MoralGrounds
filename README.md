# MoralGrounds: ETHICS 10k Collaborator Package

**9,975 instructions, 29,925 human annotations, 19 annotators and nine LLM conditions.**

Dataset, analysis scripts and results from the Etika LLM annotation project. The scripts reproduce the analyses locally from the CSV files in this repository.

## Start Here

- [Analysis report](results/COLLABORATOR_REPORT.md): agreement among humans, among models and between each model and the human majority, including categorical rationales and model-group comparisons.
- [Disagreement examples](results/examples/EXAMPLES.md), also available as [CSV](results/examples/selected_cases.csv) and [JSON](results/examples/selected_cases.json).
- [Data dictionary](docs/DATA_DICTIONARY.md), [methods](docs/METHODS.md), [protocol summary](docs/PROTOCOL.md) and [validation](provenance/VALIDATION.json).

## Dataset Files

| Partition | Human annotations | LLM responses | Human majority and model labels |
| --- | --- | --- | --- |
| Commonsense | [1,995 items](data/humans/commonsense.csv) | [CSV](data/llms/commonsense.csv) | [CSV](results/per_item_predictions/commonsense.csv) |
| Deontology | [1,995 items](data/humans/deontology.csv) | [CSV](data/llms/deontology.csv) | [CSV](results/per_item_predictions/deontology.csv) |
| Justice | [1,995 items](data/humans/justice.csv) | [CSV](data/llms/justice.csv) | [CSV](results/per_item_predictions/justice.csv) |
| Utilitarianism | [1,995 items](data/humans/utilitarianism.csv) | [CSV](data/llms/utilitarianism.csv) | [CSV](results/per_item_predictions/utilitarianism.csv) |
| Virtue | [1,995 items](data/humans/virtue.csv) | [CSV](data/llms/virtue.csv) | [CSV](results/per_item_predictions/virtue.csv) |

Each human CSV has **one row per instruction with all three annotations** in `annotator_1_*`, `annotator_2_*` and `annotator_3_*` columns. The columns follow the original annotation order and include each annotator's labels and rationales, alongside the majority label. Original cell values and normalized values are stored separately. See the [data dictionary](docs/DATA_DICTIONARY.md) for field definitions.

The LLM CSVs contain the recorded responses, original label and rationale strings, parsed values and parsing status. They link to the instruction text through `item_id` in the human CSVs.

## Reproduce

Use Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/run_analysis.py --out results_reproduced
python scripts/validate_package.py --results results_reproduced
```

On Windows, activate with `.venv\Scripts\activate`. Choose a new or empty output directory. The default is **5,000 stratified item-bootstrap draws**, seed **20260917**. For a quick development run, use `--bootstrap 50 --no-plots`.

The script calculates majority labels and majority-aligned rationale references, computes agreement statistics, checks the outputs, generates the report and selects disagreement examples.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/validate_package.py --results results_reproduced
```

To rebuild the input CSVs from the original XLSM files, install `requirements-export.txt` and run:

```bash
python scripts/export_from_source.py --source /path/to/ETHICS_LLM
```

The exporter creates new input files from spreadsheet cells. Source-file hashes and export counts are recorded in [provenance](provenance/SOURCE_MANIFEST.csv).

## Analysis Coverage

| Question | Main output |
| --- | --- |
| Inter-human final-label agreement, each partition and overall | `results/judgments/human_reliability.csv` |
| All model pairs, each partition and overall | `results/judgments/pairwise_model_agreement.csv` |
| All nine models, the frontier three and the remaining six | `results/judgments/group_reliability.csv` |
| Human/LLM internal agreement on identical complete items | `results/summary/matched_complete_label_panels.csv` |
| Each LLM versus human majority, each partition and overall | `results/judgments/model_vs_human.csv` |
| Every item: human majority and every LLM verdict | `results/per_item_predictions/*.csv` |
| Human/model internal categorical rationale agreement | `results/rationales/group_rationale_agreement.csv` |
| Matched complete rationale panels | `results/summary/matched_complete_rationale_panels.csv` |
| Each LLM versus majority-aligned human rationales | `results/rationales/model_human_overlap.csv` |
| Category distributions, shifts and distance measures | `results/rationales/model_human_distances.csv`, `paired_category_profiles.csv` |
| Selected disagreement examples and annotations | `results/examples/selected_cases.csv`, `selected_cases.json` |

Categorical rationale analysis covers Commonsense, Deontology, Justice and Utilitarianism. Deontology main categories and secondary moral principles are analyzed separately. Virtue explanations are included as free text. Rationale results are reported by field.

## Repository Notes

The repository contains ten dataset CSVs, analysis scripts, reports and summary tables. Large intermediate tables are regenerated by the analysis scripts.

Dataset and annotation licensing is pending confirmation.
