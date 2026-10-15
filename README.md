# MoralGrounds: ETHICS 10k Collaborator Package

**9,975 instructions, 29,925 human annotations, 19 annotators and nine LLM conditions.**

This self-contained snapshot supports offline analysis of the Etika LLM production corpus. No source repository, Excel installation, API key or model inference is required to reproduce the analyses.

## Start Here

- [Detailed collaborator report](results/COLLABORATOR_REPORT.md): human agreement, model agreement, frontier-versus-remaining panels, every model versus human majority, categorical rationale comparisons and disagreement counts.
- [Selected disagreement examples](results/examples/EXAMPLES.md), with [full CSV evidence](results/examples/selected_cases.csv) and [full JSON evidence](results/examples/selected_cases.json).
- [Data dictionary](docs/DATA_DICTIONARY.md), [methods](docs/METHODS.md), [protocol summary](docs/PROTOCOL.md) and [validation](provenance/VALIDATION.json).

## Dataset Files

| Partition | Human item CSV | LLM response CSV | Human-majority versus every model |
| --- | --- | --- | --- |
| Commonsense | [1,995 complete item rows](data/humans/commonsense.csv) | [model responses](data/llms/commonsense.csv) | [per-item labels](results/per_item_predictions/commonsense.csv) |
| Deontology | [1,995 complete item rows](data/humans/deontology.csv) | [model responses](data/llms/deontology.csv) | [per-item labels](results/per_item_predictions/deontology.csv) |
| Justice | [1,995 complete item rows](data/humans/justice.csv) | [model responses](data/llms/justice.csv) | [per-item labels](results/per_item_predictions/justice.csv) |
| Utilitarianism | [1,995 complete item rows](data/humans/utilitarianism.csv) | [model responses](data/llms/utilitarianism.csv) | [per-item labels](results/per_item_predictions/utilitarianism.csv) |
| Virtue | [1,995 complete item rows](data/humans/virtue.csv) | [model responses](data/llms/virtue.csv) | [per-item labels](results/per_item_predictions/virtue.csv) |

Each human CSV has **one row per instruction and all three complete annotations**, stored in `annotator_1_*`, `annotator_2_*` and `annotator_3_*` columns. Slots follow the original annotation-copy order, not participant ranking. Dissenting labels and rationales are retained. Normalized values and original annotation-cell values are distinct columns. Metadata, majority labels and JSON conveniences are documented in the dictionary.

Model files contain the supplied response records, not invented rows for missing responses. Original final-label/rationale strings and their parsed values/statuses are preserved. Instruction text is stored once in the human item files and joined by `item_id`. Model identifiers are those recorded in the exports.

## Reproduce

Python 3.12 or newer is required by the pinned numerical environment used for this snapshot.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/run_analysis.py --out results_reproduced
python scripts/validate_package.py --results results_reproduced
```

On Windows, activate with `.venv\Scripts\activate`. Always use a new/empty output directory; previous analyses are not overwritten. The default is **5,000 stratified item-bootstrap draws**, seed **20260917**. There are no network/API calls after dependencies are installed. A development smoke test can use `--bootstrap 50 --no-plots`; its intervals are not publication results.

The normal run rebuilds majority labels and majority-aligned rationale references from the complete three-human input files, computes all statistics, runs independent output checks, writes the collaborator report and selects disagreement examples. Optional direct commands remain in the tested analysis engine for audit-only runs and scenario-cluster bootstrap sensitivity.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/validate_package.py --results results_reproduced
```

The input exporter is a separate one-time provenance tool. Only rebuilding the frozen package from the original repository requires the source XLSM files and `requirements-export.txt`; ordinary analysis never does:

```bash
python scripts/export_from_source.py --source /path/to/ETHICS_LLM
```

The exporter refuses to replace existing input files. It reads spreadsheet cells without executing macros or exporting Office metadata. Source hashes and export accounting are in [provenance](provenance/SOURCE_MANIFEST.csv).

## Analysis Coverage

| Question | Main output |
| --- | --- |
| Inter-human final-label agreement, each partition and overall | `results/judgments/human_reliability.csv` |
| All model pairs, each partition and overall | `results/judgments/pairwise_model_agreement.csv` |
| All nine, fixed frontier three and remaining six | `results/judgments/group_reliability.csv` |
| Human/LLM internal agreement on identical complete items | `results/summary/matched_complete_label_panels.csv` |
| Each LLM versus human majority, each partition and overall | `results/judgments/model_vs_human.csv` |
| Every item: human majority and every LLM verdict | `results/per_item_predictions/*.csv` |
| Human/model internal categorical rationale agreement | `results/rationales/group_rationale_agreement.csv` |
| Matched complete rationale panels | `results/summary/matched_complete_rationale_panels.csv` |
| Each LLM versus majority-aligned human rationales | `results/rationales/model_human_overlap.csv` |
| Category distributions, shifts and distance measures | `results/rationales/model_human_distances.csv`, `paired_category_profiles.csv` |
| Full auditable disagreement evidence | `results/examples/selected_cases.csv`, `selected_cases.json` |

The three requested domains are included; **production Utilitarianism also has categorical rationales** and is analyzed. Deontology main categories and secondary moral principles remain separate. Virtue explanations are preserved as text, without an invented semantic agreement score. No overall rationale number pools different field meanings.

## Privacy, Scope and Git

Student names, contact details, administrative identity mappings, payment records, API credentials, original Office files and Office identity metadata are excluded. Annotator codes remain pseudonyms; this is not a claim that identities cannot be linked by someone holding the private administrative mapping. Ethical source narratives and full annotation text may include sensitive or offensive subject matter.

This repository publishes the frozen **ETHICS 10k collaborator-package snapshot**. The `.gitignore` excludes environments, work directories and large reproducible intermediate tables. All ten frozen dataset CSVs, analysis scripts, reports and compact scientific summaries are retained. Run the reproduction commands above to regenerate omitted intermediates, then validate `results_reproduced`; the saved `results/` summaries remain unchanged. Historical provenance records describe the original snapshot and its pre-publication checks.

No redistribution license is asserted. The original dataset and project annotation terms must be resolved before public release. Agreement with the human majority is a study-reference measure, not an external moral-correctness guarantee.
