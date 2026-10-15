#!/usr/bin/env python3
"""Validate completed outputs, optionally against independent reference libraries.

    python validate_results.py results --reference-checks

The optional reference checks require requirements-dev.txt (scikit-learn and
statsmodels). Default accounting/range/manifest checks need only core packages.
"""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def close(a, b, message, tolerance=1e-9):
    if not np.isclose(a, b, atol=tolerance, rtol=tolerance, equal_nan=True):
        raise ValueError(f"{message}: {a} != {b}")


def validate_majority_rationale_overlap(root):
    """Recompute overlaps with Python sets, independently of matrix scoring."""
    root = Path(root)
    with (root / "normalized" / "items.csv").open(newline="", encoding="utf-8") as handle:
        majority = {r["item_id"]: int(r["human_majority"]) for r in csv.DictReader(handle)}
    humans, models = defaultdict(list), []
    with (root / "normalized" / "annotations.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            row["fields"] = json.loads(row["structured_fields"])
            if row["actor_type"] == "human":
                if int(row["label"]) == majority[row["item_id"]]:
                    humans[row["item_id"]].append(row)
            else:
                models.append(row)
    if set(humans) != set(majority) or any(len(rows) not in (2, 3) for rows in humans.values()):
        raise ValueError("Expected two or three majority-supporting humans for every item")
    cohorts = defaultdict(list)
    for model in models:
        key = model["item_id"]
        for field, result in model["fields"].items():
            if field == "virtue_text" or result["status"] != "valid":
                continue
            m = set(result["value"])
            scores = []
            for human in humans[key]:
                hresult = human["fields"].get(field, {})
                if hresult.get("status") != "valid":
                    continue
                h = set(hresult["value"])
                if not h or not m:
                    continue
                scores.append((len(h & m) / len(h | m),
                               2 * len(h & m) / (len(h) + len(m)), float(h == m)))
            if not scores:
                continue
            item_scores = (*np.mean(scores, axis=0), len(scores))
            scopes = ["majority_aligned"]
            if model["label_status"] == "valid" and int(model["label"]) == majority[key]:
                scopes.append("same_judgment")
            for scope in scopes:
                cohorts[model["actor"], field, scope].append(item_scores)
    summary = root / "rationales" / "model_human_overlap.csv"
    if not summary.exists():
        summary = root / "llm_human_rationale_agreement.csv"
    with summary.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    seen, checks = set(), 1
    for row in rows:
        key = row["model"], row["field"], row["scope"]
        if key in seen or row["scope"] not in ("majority_aligned", "same_judgment"):
            raise ValueError(f"Duplicate or outdated rationale reference: {key}")
        seen.add(key)
        values = cohorts.get(key, [])
        close(len(values), int(row["n_items"]), f"Majority-only item count: {key}")
        close(sum(v[3] for v in values), int(row["n_human_comparisons"]),
              f"Majority-only human count: {key}")
        for i, metric in enumerate(("jaccard", "dice", "exact_set")):
            expected = np.mean([v[i] for v in values]) if values else np.nan
            actual = float(row[metric]) if row[metric] else np.nan
            close(expected, actual, f"Independent majority-only {metric}: {key}", 1e-7)
        checks += 5
    if set(cohorts) - seen:
        raise ValueError("Rationale summaries omit a nonempty cohort")
    return checks


def validate(root, reference_checks=False):
    root = Path(root).resolve()
    audit = json.loads((root / "audit" / "audit_summary.json").read_text())
    manifest = json.loads((root / "run_manifest.json").read_text())
    coverage = pd.read_csv(root / "audit" / "coverage.csv")
    matrix = pd.read_csv(root / "judgments" / "item_label_matrix.csv")
    scores = pd.read_csv(root / "judgments" / "model_vs_human.csv")
    groups = pd.read_csv(root / "judgments" / "group_reliability.csv")
    distances = pd.read_csv(root / "rationales" / "model_human_distances.csv")
    profiles = pd.read_csv(root / "rationales" / "paired_category_profiles.csv")
    quality = pd.read_csv(root / "rationales" / "field_quality.csv")
    checks = validate_majority_rationale_overlap(root)
    if len(matrix) != audit["n_items"] or matrix.item_id.duplicated().any():
        raise ValueError("The item matrix is incomplete or has duplicated keys")
    checks += 1
    close(coverage.n_valid.sum(), audit["llm_label_status"]["valid"], "valid-response count")
    close(coverage.n_absent_rows.sum(), audit["n_missing_llm_rows"], "absent-row count")
    close(coverage.n_items.sum(), audit["n_items"] * audit["n_models"], "expected response count")
    checks += 3
    for _, row in coverage.iterrows():
        close(row.n_present + row.n_absent_rows, row.n_items, "coverage accounting")
        close(row.n_valid + row.n_missing_labels + row.n_invalid_labels, row.n_present, "label-status accounting")
        checks += 2
    for _, row in quality.iterrows():
        close(row.n_valid + row.n_missing + row.n_invalid + row.n_inapplicable + row.n_eligibility_unknown,
              row.n_present, "rationale-status accounting")
        close(row.n_valid + row.n_missing + row.n_invalid, row.n_eligible, "rationale eligibility accounting")
        checks += 2
    if reference_checks:
        from sklearn.metrics import cohen_kappa_score, balanced_accuracy_score, f1_score, matthews_corrcoef
        from statsmodels.stats.inter_rater import fleiss_kappa
    for sample in scores["sample"].unique():
        subset = matrix.copy()
        if sample != "available":
            members = audit["models"] if sample == "common_all" else audit["groups"]["frontier"]
            subset = subset.dropna(subset=members)
        for model in scores.loc[scores["sample"] == sample, "model"].unique():
            evaluated = subset.dropna(subset=[model,"human_majority"])
            rows = scores[(scores["sample"] == sample) & (scores.model == model)]
            for _, row in rows.iterrows():
                selected = evaluated if row.partition == "overall" else evaluated[evaluated.partition == row.partition]
                close(len(selected), row.n, "model/reference paired denominator")
                close((selected[model] == selected.human_majority).mean(), row.agreement, "independent raw agreement")
                checks += 2
                if reference_checks and row.partition != "overall":
                    y,pred=selected.human_majority.to_numpy(),selected[model].to_numpy()
                    close(cohen_kappa_score(y,pred),row.kappa,"scikit-learn Cohen kappa")
                    close(balanced_accuracy_score(y,pred),row.balanced_accuracy,"scikit-learn balanced accuracy")
                    close(f1_score(y,pred,average='macro'),row.macro_f1,"scikit-learn macro F1")
                    close(matthews_corrcoef(y,pred),row.mcc,"scikit-learn MCC")
                    checks += 4
            overall=rows[rows.partition=='overall'].iloc[0]
            domains=rows[rows.partition!='overall']
            close(np.average(domains.kappa,weights=domains.n),overall.kappa,"domain-weighted overall kappa")
            checks += 1
    if reference_checks:
        for _, row in groups[groups.partition!='overall'].iterrows():
            members=audit['groups'][row.group]
            selected=matrix[matrix.partition==row.partition].dropna(subset=members)
            labels=sorted(set(selected[members].to_numpy().ravel()))
            counts=np.column_stack([(selected[members].to_numpy()==label).sum(1) for label in labels])
            close(len(selected),row.n_complete_fleiss,"complete-panel denominator")
            close(fleiss_kappa(counts),row.fleiss_kappa,"statsmodels Fleiss kappa")
            checks += 2
    for metric in ('tv','js_divergence_bits'):
        values=distances[metric].dropna()
        if ((values < -1e-10) | (values > 1+1e-10)).any():
            raise ValueError(f"Out-of-range rationale distance: {metric}")
        checks += 1
    for _, group in profiles.groupby(['model','field','scope','weighting']):
        close(group.human_mention_share.sum(),1,"human mention-share normalization")
        close(group.model_mention_share.sum(),1,"model mention-share normalization")
        close(group.model_minus_human_share_pp.sum(),0,"category share differences sum to zero",1e-7)
        checks += 3
    inventory = pd.read_csv(root / "output_manifest.csv")
    for _, row in inventory.iterrows():
        path = (root / row.path).resolve()
        if root not in path.parents:
            raise ValueError(f"Manifest path escapes output directory: {row.path}")
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row.sha256:
            raise ValueError(f"Output checksum mismatch: {row.path}")
        checks += 1
    result = dict(status="PASS", checks=checks, reference_library_checks=reference_checks,
                  n_items=audit['n_items'], n_models=audit['n_models'], bootstrap_resamples=manifest['bootstrap_resamples'])
    print(json.dumps(result,indent=2))
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('results',type=Path)
    p.add_argument('--reference-checks',action='store_true')
    args=p.parse_args()
    validate(args.results,args.reference_checks)
