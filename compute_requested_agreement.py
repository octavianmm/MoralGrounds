#!/usr/bin/env python3
"""Compute the three requested agreement analyses from human and LLM exports.

Run from this directory:
    .venv/bin/python compute_requested_agreement.py \
        --human .. --llm ../ETHICS10k --out ../agreement_results

Uses the accompanying ethics_analysis package. No previous results or API access
are needed. Source data are read-only; the output directory must be new/empty.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

from ethics_analysis.ingest import load_data
from ethics_analysis.io_utils import write_csv, write_json
from ethics_analysis.judgments import (
    DataMatrices, ci_columns, human_baseline, model_human_metrics,
)
from ethics_analysis.metrics import (
    Bootstrap, divide, mean_finite, nominal_table_stats,
)
from ethics_analysis.rationales import (
    FieldMatrices, field_quality, human_reference, item_overlap,
)
from ethics_analysis.reporting import export_audit
from ethics_analysis.schema import FIELDS, PARTITIONS


FIELD_NAMES = {
    "commonsense_principles": "Commonsense principles",
    "deontology_main": "Deontology main category",
    "deontology_principles": "Deontology principles",
    "justice_rationale": "Justice category",
    "utilitarianism_rationales": "Utilitarianism categories",
}


def categorical_agreement(data, humans, llms, bootstrap):
    """Compare each model with individual human sets, with equal item weight."""
    summaries, item_rows = [], []
    for field, spec in FIELDS.items():
        fm = FieldMatrices(field, data, humans, llms)
        p, k = spec.partition, len(spec.categories)
        for model in data.models:
            j = data.model_index[model]
            model_sets = fm.M[:, j, :]
            for scope in ("majority_aligned", "same_judgment"):
                human_sets, eligible_humans = human_reference(fm, data, j, scope)
                mask = fm.Mvalid[:, j] & eligible_humans.any(1)
                if scope == "same_judgment":
                    mask &= (data.M[p][:, j] >= 0) & (data.M[p][:, j] == data.Y[p])
                scores = item_overlap(human_sets, eligible_humans, model_sets, mask)
                row = {
                    "model": model, "partition": p, "field": field,
                    "scope": scope,
                    "response_type": "multi_select" if spec.multi else "single_choice",
                    "n_partition_items": len(mask), "n_items": int(mask.sum()),
                    "n_human_comparisons": int(scores["n_humans"].sum()),
                    "item_coverage": float(mask.mean()),
                    "reference": "majority_aligned_humans_averaged_within_item",
                }
                for metric in ("jaccard", "dice", "exact_set"):
                    row[metric] = float(mean_finite(scores[metric]))
                    ci_columns(row, bootstrap.means(p, scores[metric]), metric)
                if not spec.multi:
                    # Each item contributes one unit of mass across its humans.
                    human_prob = np.nan_to_num(divide(
                        human_sets.sum(1), eligible_humans.sum(1)[:, None]
                    ))
                    joint = human_prob[:, :, None] * model_sets[:, None, :]
                    joint *= mask[:, None, None]
                    row["single_choice_kappa"] = float(
                        nominal_table_stats(joint.sum(0))["kappa"]
                    )
                    sampled = bootstrap.sums(p, joint.reshape(len(mask), k * k))
                    ci_columns(row, nominal_table_stats(
                        sampled.reshape(-1, k, k)
                    )["kappa"], "single_choice_kappa")
                summaries.append(row)
                for i in np.flatnonzero(mask):
                    item_rows.append({
                        "item_id": data.ids[p][i], "partition": p,
                        "field": field, "model": model, "scope": scope,
                        "n_humans": int(scores["n_humans"][i]),
                        **{metric: float(scores[metric][i])
                           for metric in ("jaccard", "dice", "exact_set")},
                    })
    return summaries, item_rows


def percent(value):
    return f"{100 * value:.2f}%" if np.isfinite(value) else "N/A"


def markdown_table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
        *("| " + " | ".join(map(str, row)) + " |" for row in rows),
    ])


def report(out, human, labels, rationale, audit, draws):
    overall = sorted(
        (r for r in labels if r["sample"] == "common_all" and r["partition"] == "overall"),
        key=lambda r: -r["agreement"],
    )
    models = [r["model"] for r in overall]
    parts = ("overall", *PARTITIONS)
    human_by_part = {r["partition"]: r for r in human}
    human_table = markdown_table(
        ["Partition", "Items", "Pairwise agreement", "Fleiss kappa", "Krippendorff alpha"],
        [[p, human_by_part[p]["n_items"], percent(human_by_part[p]["pairwise_item_mean"]),
          f"{human_by_part[p]['fleiss_kappa']:.3f}",
          f"{human_by_part[p]['krippendorff_alpha']:.3f}"] for p in parts],
    )
    label_tables = []
    for sample in ("available", "common_all"):
        lookup = {(r["model"], r["partition"]): r for r in labels if r["sample"] == sample}
        label_tables.append(markdown_table(
            ["Model", "Valid items", *parts],
            [[m, lookup[m, "overall"]["n"],
              *(percent(lookup[m, p]["agreement"]) for p in parts)] for m in models],
        ))
    rationale_tables = []
    for scope, metric in (("majority_aligned", "jaccard"), ("majority_aligned", "exact_set"),
                          ("same_judgment", "jaccard")):
        lookup = {(r["model"], r["field"]): r for r in rationale if r["scope"] == scope}
        rationale_tables.append(markdown_table(
            ["Model", *FIELD_NAMES.values()],
            [[m, *(percent(lookup[m, field][metric]) for field in FIELDS)] for m in models],
        ))
    text = f"""# The three requested agreement analyses

Inputs: {audit['n_items']:,} instructions, {audit['n_human_annotations']:,} human
annotations, {audit['n_human_annotators']} annotators, and {audit['n_models']} models.
Confidence intervals in the CSVs use {draws:,} item bootstrap samples within
partitions. Each sampled item retains all its human and model annotations.
All scores are proportions in the CSVs; percentages below are display formatting.

## 1. Inter-human agreement on main binary labels

Pairwise agreement is the fraction of the three human pairs that agree on an
item, averaged over items. A unanimous item scores 1; a 2-1 split scores 1/3.
Fleiss kappa and nominal Krippendorff alpha additionally account for agreement
expected from label frequencies. Overall coefficients are item-weighted means
of the five partition coefficients, not coefficients pooling different labels.

{human_table}

## 2. LLM versus human binary-label agreement

Each model is compared with the majority of the three human labels. Missing or
invalid model labels are excluded from the paired denominator and explicitly
counted. This is agreement with this study's human reference, not moral accuracy.
The CSV also includes Cohen kappa per partition and its weighted overall mean,
confidence intervals, matches, and coverage. Human-pair agreement and agreement
with a human majority use different references and are not directly comparable.

### Primary: all valid items available for each model

{label_tables[0]}

### Sensitivity: exactly the same items for every model

This table uses {overall[0]['n']:,} instructions with valid labels from all models.

{label_tables[1]}

## 3. LLM versus human categorical-rationale agreement

For each instruction, compare the model's category set only with eligible humans
whose binary label matches the human majority, average over those humans, then
average over instructions. Split items retain two humans, unanimous items three,
before field-specific eligibility checks. Dissenting rationales are excluded;
the retained category sets are not reduced to a single consensus category.

- Jaccard overlap = shared categories / categories chosen by either party.
  Human [A, B] versus model [A] gives 1/2, or 50% overlap.
- Exact-set agreement = 1 only if the complete selected sets are identical.
  The same example gives 0. It becomes a proportion after averaging.
- For single-choice fields, both scores equal ordinary category agreement.
  A weighted nominal Cohen kappa is also included for those fields.
- Dice overlap and 95% intervals are included in the CSV.

### Primary: majority-aligned human rationales

Only majority-supporting human rationales contribute. The model need not match
the majority label; the supplementary analysis below adds that requirement.

Jaccard overlap below is a mean similarity score. For multi-select fields it is
not the percentage of instructions with identical rationales.

{rationale_tables[0]}

### Strict agreement: identical category sets

{rationale_tables[1]}

### Supplementary: rationale overlap when the judgment also agrees

Here the model must match the human majority, and only human annotations with
that same binary label contribute. These conditional cohorts differ by model.

{rationale_tables[2]}

### Field eligibility and denominators

- Commonsense principles apply to both binary labels.
- Deontology has two fields: a single main category and multi-select moral
  principles. Principles are compared only when both parties supplied valid,
  applicable principle sets; they are inapplicable for IRRELEVANT or
  IMPOSSIBLE TO FULFIL. Different main categories can reduce that cohort.
- Justice has a single categorical rationale, including OTHER; any accompanying
  free text is outside this categorical score.
- Utilitarianism has ten categories and permits multiple selections.
- Virtue has free-text rationales and is excluded from categorical agreement.
- Missing, invalid, or inapplicable sets do not count as matching empty sets.
  The primary rationale score can use a valid rationale even if that model's
  binary label is unusable. The two fields are assessed separately.
- Each model/field/scope has its own n_items and n_human_comparisons in the CSV.
  Raw counts and excluded-field statuses are in details/field_quality.csv.
- There is no single pooled rationale score: the fields have different response
  rules, and pooling would count deontology twice.

## Outputs and limitations

The three main files are human_label_agreement.csv,
llm_human_label_agreement.csv, and llm_human_rationale_agreement.csv.
The details directory includes item-level rationale scores, human pair results,
label confusion counts, field quality, and run metadata. Audit files record
source hashes, item matching, and normalization decisions.

This script computes itemwise rationale agreement, not similarity of overall
category-frequency distributions. It does not infer semantic equivalence of
free-text explanations. Intervals are conditional on the fixed human/model
panels and supplied items; model rerun variability is not measured.
"""
    (out / "AGREEMENT_REPORT.md").write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--human", required=True, help="Human repository root or ZIP")
    parser.add_argument("--llm", required=True, help="ETHICS10k directory or ZIP")
    parser.add_argument("--out", required=True, type=Path, help="New or empty output directory")
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260917)
    args = parser.parse_args()
    if args.bootstrap < 1:
        parser.error("--bootstrap must be positive")
    if args.bootstrap < 500:
        print("WARNING: fewer than 500 resamples is a test run, not a final analysis.")
    out = args.out.expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        parser.error("Output directory must be new or empty")
    print("Validating and aligning human and LLM annotations ...", flush=True)
    items, humans, llms, models, _, audit = load_data(args.human, args.llm)
    if any(item["human_n"] != 3 for item in items.values()):
        raise ValueError("This study requires exactly three distinct human annotators per item")
    out.mkdir(parents=True, exist_ok=True)
    export_audit(items, humans, llms, models, audit, out)
    data = DataMatrices(items, humans, llms, models)
    with threadpool_limits(limits=1):
        bootstrap = Bootstrap(data.ids, args.bootstrap, args.seed)
        print("1/3: Inter-human binary-label agreement ...", flush=True)
        human = human_baseline(data, out / "details" / "human", bootstrap)
        write_csv(out / "human_label_agreement.csv", human)
        print("2/3: LLM versus human-majority binary labels ...", flush=True)
        labels = model_human_metrics(data, bootstrap, {"all": models}, out / "details" / "labels")
        write_csv(out / "llm_human_label_agreement.csv", labels)
        print("3/3: LLM versus individual-human categorical rationales ...", flush=True)
        rationale, item_scores = categorical_agreement(data, humans, llms, bootstrap)
        write_csv(out / "llm_human_rationale_agreement.csv", rationale)
        write_csv(out / "details" / "item_rationale_agreement.csv", item_scores)
        field_quality(humans, llms, data, out / "details")
    report(out, human, labels, rationale, audit.summary, args.bootstrap)
    code_root = Path(__file__).resolve().parent
    code_files = [Path(__file__).resolve(), *sorted((code_root / "ethics_analysis").glob("*.py"))]
    write_json(out / "run_manifest.json", {
        "arguments": {k: str(v) if isinstance(v, Path) else v
                      for k, v in vars(args).items()}, "python": sys.version,
        "software": {name: importlib.metadata.version(name)
                     for name in ("numpy", "scipy", "pandas", "threadpoolctl")},
        "code_sha256": {str(p.relative_to(code_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in code_files},
        "bootstrap_unit": "instruction_within_partition",
        "network_or_api_calls": False,
    })
    write_csv(out / "output_manifest.csv", [
        {"path": str(p.relative_to(out)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(out.rglob("*")) if p.is_file()
    ])
    print(f"Complete. Read {out / 'AGREEMENT_REPORT.md'}", flush=True)


if __name__ == "__main__":
    main()
