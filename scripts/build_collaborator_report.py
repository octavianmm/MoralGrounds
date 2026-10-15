#!/usr/bin/env python3
"""Create portable summaries, matched-panel comparisons and disagreement cases."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_inputs import read_csv, write_csv
from ethics_analysis.metrics import reliability, set_scores
from ethics_analysis.schema import PARTITIONS, LABELS, FIELDS, metadata

PANELS = ("all", "frontier", "other_models")
PANEL_NAMES = {"all": "All nine", "frontier": "Frontier trio", "other_models": "Remaining six", "humans": "Humans"}
FIELD_NAMES = {"commonsense_principles": "Commonsense principles", "deontology_main": "Deontology main",
               "deontology_principles": "Deontology moral principles", "justice_rationale": "Justice category",
               "utilitarianism_rationales": "Utilitarianism categories"}


def pct(v):
    return f"{100*float(v):.2f}%"


def count(v):
    return f"{int(float(v)):,}"


def coefficient(v):
    return f"{float(v):.3f}"


def markdown_table(headers, rows):
    cell = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(cell, headers)) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        if len(row) != len(headers):
            raise ValueError("Report table dimensions differ")
        lines.append("| " + " | ".join(map(cell, row)) + " |")
    return "\n".join(lines)


def opposition_tier(row):
    if not row["human_unanimous"]:
        return None
    if row["n_valid_models"] == 9 and row["n_opposing_models"] == 9:
        return 1
    if row["n_valid_models"] == 9 and row["n_opposing_models"] >= 5:
        return 2
    if row["n_valid_frontier"] == 3 and row["n_opposing_frontier"] == 3:
        return 3
    if row["n_valid_models"] >= 7 and row["n_opposing_models"] > row["n_valid_models"]/2:
        return 4
    return None


def selection_key(row):
    return (row["selection_tier"], -row["n_opposing_models"], -row["n_valid_models"],
            -row["n_opposing_frontier"], row["human_ambiguity_votes"], row["human_cultural_flag_votes"],
            len(row["input"].split()), int(row["task_instruction_id"]))


def build(results):
    results = Path(results).resolve()
    relative = lambda path: os.path.relpath(path, results).replace(os.sep, "/")
    config = json.loads((ROOT / "config/model_groups.json").read_text())
    groups = config["groups"]
    models = groups["all"]
    human = read_csv(results / "judgments/human_reliability.csv")
    label = read_csv(results / "judgments/model_vs_human.csv")
    panels = read_csv(results / "judgments/group_reliability.csv")
    overlap = read_csv(results / "rationales/model_human_overlap.csv")
    rationale_panels = read_csv(results / "rationales/group_rationale_agreement.csv")
    quality = read_csv(results / "rationales/field_quality.csv")
    coverage = read_csv(results / "audit/coverage.csv")
    manifest = json.loads((results / "run_manifest.json").read_text())
    model_data = { (r["item_id"],r["model"]): r for p in PARTITIONS for r in read_csv(ROOT / "data/llms" / f"{p}.csv") }
    human_data = {r["item_id"]: r for p in PARTITIONS for r in read_csv(ROOT / "data/humans" / f"{p}.csv")}
    summary_dir = results / "summary"
    summary_dir.mkdir(exist_ok=True)
    comparison = []
    all_case_rows = []
    item_matrices = defaultdict(list)
    for group in PANELS:
        domain_rows = []
        members = groups[group]
        for p in PARTITIONS:
            hc, mc = [], []
            for item in human_data.values():
                if item["partition"] != p:
                    continue
                responses = [model_data.get((item["item_id"],m)) for m in members]
                if not all(r and r["label_status"] == "valid" for r in responses):
                    continue
                hlabels = json.loads(item["individual_labels_json"])
                mlabels = [r["normalized_label"] for r in responses]
                hc.append([hlabels.count(v) for v in LABELS[p]])
                mc.append([mlabels.count(v) for v in LABELS[p]])
            hs, ms = reliability(np.array(hc), 3), reliability(np.array(mc), len(members))
            row = dict(group=group, partition=p, n_items=len(hc), n_models=len(members),
                       human_pairwise=hs["pairwise_item_mean"], model_pairwise=ms["pairwise_item_mean"],
                       gap_pp=100*(ms["pairwise_item_mean"]-hs["pairwise_item_mean"]),
                       human_kappa=hs["fleiss_kappa"], model_kappa=ms["fleiss_kappa"])
            comparison.append(row)
            domain_rows.append(row)
        n = sum(r["n_items"] for r in domain_rows)
        overall = dict(group=group, partition="overall", n_items=n, n_models=len(members))
        for key in ("human_pairwise", "model_pairwise", "gap_pp", "human_kappa", "model_kappa"):
            overall[key] = sum(r[key]*r["n_items"] for r in domain_rows)/n
        comparison.append(overall)
    write_csv(summary_dir / "matched_complete_label_panels.csv", comparison)

    schema = json.loads((ROOT / "docs/schema.json").read_text())
    normalized = read_csv(results / "normalized/annotations.csv")
    observations = defaultdict(dict)
    for row in normalized:
        row["fields"] = json.loads(row["structured_fields"])
        observations[row["item_id"]][row["actor"]] = row
    matched_rationales = []
    for field, spec in FIELDS.items():
        for group in PANELS:
            h_scores, m_scores = [], []
            for key, item in human_data.items():
                if item["partition"] != spec.partition:
                    continue
                actors = ["human:"+c for c in json.loads(item["annotator_codes_json"])]
                pairs = [observations[key].get(a) for a in actors+groups[group]]
                if not all(r and r["fields"].get(field,{}).get("status") == "valid" for r in pairs):
                    continue
                hsets = [set(r["fields"][field]["value"]) for r in pairs[:3]]
                msets = [set(r["fields"][field]["value"]) for r in pairs[3:]]
                def mean_scores(sets):
                    values = [set_scores(a,b) for i,a in enumerate(sets) for b in sets[i+1:]]
                    return [float(np.mean([r[k] for r in values])) for k in ("jaccard", "exact_set")]
                h_scores.append(mean_scores(hsets))
                m_scores.append(mean_scores(msets))
            matched_rationales.append(dict(field=field, partition=spec.partition, group=group,
                n_complete_items=len(h_scores), human_jaccard=float(np.mean([r[0] for r in h_scores])),
                model_jaccard=float(np.mean([r[0] for r in m_scores])),
                human_exact=float(np.mean([r[1] for r in h_scores])), model_exact=float(np.mean([r[1] for r in m_scores]))))
    write_csv(summary_dir / "matched_complete_rationale_panels.csv", matched_rationales)

    for key, item in human_data.items():
        p = item["partition"]
        majority = item["human_majority_label"]
        obs = [model_data.get((key,m)) for m in models]
        valid = [r for r in obs if r and r["label_status"] == "valid"]
        frontier = [model_data.get((key,m)) for m in groups["frontier"]]
        valid_frontier = [r for r in frontier if r and r["label_status"] == "valid"]
        human_evidence = [{**{f: item[f"annotator_{slot}_{f}"] for f in schema["annotator_specific_fields"]},
                           "source_cells": {f:item[f"annotator_{slot}_source_cell_{f}"] for f in schema["source_cell_fields"]}} for slot in (1,2,3)]
        row = dict(item_id=key, partition=p, task_instruction_id=item["task_instruction_id"],
                   original_source_id=metadata(item["meta"])["id"],
                   input=item["input"], human_majority_label=majority, human_unanimous=item["human_unanimous"] == "TRUE",
                   human_labels_json=item["individual_labels_json"], n_valid_models=len(valid),
                   n_opposing_models=sum(r["normalized_label"] != majority for r in valid),
                   n_valid_frontier=len(valid_frontier), n_opposing_frontier=sum(r["normalized_label"] != majority for r in valid_frontier),
                   human_ambiguity_votes=sum(item[f"annotator_{i}_ambiguity"] == "The scenario is ambiguous." for i in (1,2,3)),
                   human_cultural_flag_votes=sum(bool(item[f"annotator_{i}_cultural_specificity"]) for i in (1,2,3)),
                   human_annotations_json=json.dumps(human_evidence, ensure_ascii=False),
                   model_annotations_json=json.dumps({m: model_data.get((key,m)) for m in models}, ensure_ascii=False))
        row["selection_tier"] = opposition_tier(row)
        all_case_rows.append(row)
        matrix = dict(item_id=key, partition=p, input=item["input"], human_majority_label=majority,
                      human_majority_count=item["human_majority_count"], human_labels_json=item["individual_labels_json"])
        for m in models:
            r = model_data.get((key,m))
            matrix[m] = r["normalized_label"] if r else ""
            matrix[m+"__status"] = r["label_status"] if r else "absent_row"
        item_matrices[p].append(matrix)
    for p, rows in item_matrices.items():
        write_csv(results / "per_item_predictions" / f"{p}.csv", rows)
    candidates = [r for r in all_case_rows if r["selection_tier"] is not None]
    selected, selection_summary = [], []
    for p in PARTITIONS:
        subset = sorted((r for r in candidates if r["partition"] == p), key=selection_key)
        chosen = subset[:config["examples_per_partition"]]
        for rank, row in enumerate(chosen,1):
            selected.append(dict(rank_in_partition=rank, **row))
        selection_summary.append(dict(partition=p, human_unanimous_all9_opposite=sum(r["selection_tier"] == 1 for r in subset),
                                     human_unanimous_complete9_majority_opposite=sum(r["n_valid_models"] == 9 and r["n_opposing_models"] >= 5 for r in subset),
                                     human_unanimous_frontier3_opposite=sum(r["n_valid_frontier"] == 3 and r["n_opposing_frontier"] == 3 for r in subset),
                                     n_candidates=len(subset), selected=len(chosen)))
    examples = results / "examples"
    write_csv(examples / "selected_cases.csv", selected)
    write_csv(examples / "selection_summary.csv", selection_summary)
    write_csv(examples / "all_disagreement_candidates.csv", sorted(candidates, key=lambda r:(PARTITIONS.index(r["partition"]),selection_key(r))))
    (examples / "selected_cases.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2)+"\n")
    example_lines = ["# Selected Human-LLM Disagreements", "",
        "All selected cases have three unanimous human labels. Selection is deterministic, not a semantic judgment that either side is wrong.", "",
        "Ranking: (1) complete nine-model unanimous opposition; (2) complete nine-model majority opposition; (3) complete frontier-trio opposition; (4) majority opposition among at least seven valid models. Ties favor more opposing/valid votes, fewer human ambiguity/culture flags, shorter instructions, then instruction ID. Five cases per partition are retained where available.", "",
        "The CSV/JSON contains full text, all three human annotations (including original cell values), and all available model labels/rationales. Excerpts below stop after 180 whitespace-delimited words. They may omit context and should never replace the full input when evaluating a case."]
    for p in PARTITIONS:
        example_lines += ["", "## "+p.title()]
        for row in (r for r in selected if r["partition"] == p):
            example_lines += ["", f"### {row['item_id']} (source {row['original_source_id']})", "",
                              f"Humans: **3/3 {row['human_majority_label']}**. Opposing LLMs: **{row['n_opposing_models']}/{row['n_valid_models']}**; opposing frontier models: **{row['n_opposing_frontier']}/{row['n_valid_frontier']}**. Selection tier: {row['selection_tier']}.", ""]
            words = row["input"].split()
            excerpt = " ".join(words[:180]) + (" [Excerpt ends; see full CSV/JSON.]" if len(words)>180 else "")
            example_lines += ["> "+excerpt, ""]
            md = json.loads(row["model_annotations_json"])
            example_lines.append(markdown_table(["Model", "Label", "Status"], [[m, md[m]["normalized_label"] if md[m] else "", md[m]["label_status"] if md[m] else "absent_row"] for m in models]))
            evidence = json.loads(row["human_annotations_json"])
            example_lines += ["", "Human rationale evidence:"]
            for h in evidence:
                text = h["main_rationale"]+"; "+h["moral_rationale"] if p == "deontology" else h["rationale"]
                example_lines.append(f"- `{h['annotator_code']}`: {text or '[not applicable]'}")
    (examples / "EXAMPLES.md").write_text("\n".join(example_lines)+"\n")

    order = sorted(models, key=lambda m:-float(next(r["agreement"] for r in label if r["model"]==m and r["partition"]=="overall" and r["sample"]=="available")))
    lines = ["# ETHICS 10k Collaborator Analysis", "", "**Dataset snapshot:** 14 October 2026. **Scope:** 9,975 production instructions; 29,925 human ratings; 19 coded annotators; nine supplied LLM conditions.", "",
             "The five human CSVs retain every annotation from all three raters, including dissenting rationales and original annotation-cell values. Final labels are equally weighted human majority votes. Comparison rationales use majority-supporting humans, but the data itself is never majority-filtered.", "",
             "## Corpus and Validity", "", "Each partition has 1,995 items and 5,985 human annotations. Every item has three distinct annotators, and every annotator has 1,575 production ratings. Required categorical fields and applicable Virtue explanations are complete in the normalized human data. This establishes protocol validity, not independently adjudicated ethical correctness.", "",
             "## Human Agreement", ""]
    lines.append(markdown_table(["Partition", "Items", "Unanimous", "Pairwise [95% CI]", "Fleiss kappa", "Nominal alpha"],
        [[p.title(),count(r["n_items"]),count(r["n_unanimous"]), f"{pct(r['pairwise_item_mean'])} [{pct(r['pairwise_item_mean_ci_low'])}, {pct(r['pairwise_item_mean_ci_high'])}]",coefficient(r["fleiss_kappa"]),coefficient(r["krippendorff_alpha"])] for p in PARTITIONS+("overall",) for r in human if r["partition"]==p]))
    lines += ["", "Pairwise agreement counts agreeing pairs, not unanimous items. A three-human unanimous item scores 1; a 2-1 item scores 1/3. There are 8,179 unanimous and 1,796 split items. Overall chance-adjusted scores are within-partition means, not a pooled category system.", "", "## Model Panels", ""]
    for group in ("frontier", "other_models"):
        lines.append(f"**{PANEL_NAMES[group]}:** "+", ".join(f"`{m}`" for m in groups[group])+".")
    lines += ["", "Model names are export identifiers, not independently verified checkpoint provenance. Panel membership is fixed in config/model_groups.json; it is not reselected during reruns.", "", "## LLM Label Coverage", ""]
    lines.append(markdown_table(["Model", "Valid / 9,975", "Absent", "Empty", "Invalid"],
        [[m,count(sum(int(r["n_valid"]) for r in coverage if r["model"]==m)),sum(int(r["n_absent_rows"]) for r in coverage if r["model"]==m),sum(int(r["n_missing_labels"]) for r in coverage if r["model"]==m),sum(int(r["n_invalid_labels"]) for r in coverage if r["model"]==m)] for m in order]))
    lines += ["", "There are 89,752 received rows, 89,723 valid labels, 23 absent rows, two empty labels and 27 invalid labels. Missingness is reported rather than guessed or treated as an ethical error.", "", "## LLM Internal Agreement", ""]
    for group in PANELS:
        lines += ["", "### "+PANEL_NAMES[group], ""]
        lines.append(markdown_table(["Partition","Items with >=2 labels","Complete panels","Pairwise [95% CI]","Fleiss kappa","Nominal alpha"],
            [[p.title(),count(r["n_items_at_least_two"]),count(r["n_complete"]),f"{pct(r['pairwise_item_mean'])} [{pct(r['pairwise_item_mean_ci_low'])}, {pct(r['pairwise_item_mean_ci_high'])}]",coefficient(r["fleiss_kappa"]),coefficient(r["krippendorff_alpha"])] for p in PARTITIONS+("overall",) for r in panels if r["group"]==group and r["partition"]==p]))
    lines += ["", "Raw pairwise agreement averages within-item valid pairs. Fleiss kappa uses complete fixed-size panels; alpha accommodates missing labels. Their denominators can differ. Internal agreement is between different supplied models, not repeat-generation stability of the same model.", "", "### Humans and models on identical complete items", ""]
    lines.append(markdown_table(["Panel","Partition","Matched items","Human pairwise","LLM pairwise","Difference (pp)","Human / LLM kappa"],
        [[PANEL_NAMES[r["group"]],r["partition"],count(r["n_items"]),pct(r["human_pairwise"]),pct(r["model_pairwise"]),f"{r['gap_pp']:+.2f}",f"{coefficient(r['human_kappa'])} / {coefficient(r['model_kappa'])}"] for r in comparison]))
    lines += ["", "## Each Model Versus Human Majority", "", "Cells show available-case main-label agreement and valid paired n. The reference is the majority of the three human ratings, not an expert moral gold standard.", ""]
    lines.append(markdown_table(["Model",*map(str.title,PARTITIONS),"Overall"],
        [[m]+[f"{pct(r['agreement'])} (n={count(r['n'])})" for p in PARTITIONS+("overall",) for r in label if r["sample"]=="available" and r["model"]==m and r["partition"]==p] for m in order]))
    lines += ["", "### Overall uncertainty and chance adjustment", ""]
    lines.append(markdown_table(["Model","Agreement [95% CI]","Weighted domain kappa","Balanced accuracy","Macro-F1"],
        [[m,f"{pct(r['agreement'])} [{pct(r['agreement_ci_low'])}, {pct(r['agreement_ci_high'])}]",coefficient(r["kappa"]),pct(r["balanced_accuracy"]),pct(r["macro_f1"])] for m in order for r in label if r["sample"]=="available" and r["model"]==m and r["partition"]=="overall"]))
    lines += ["", "The machine-readable table additionally provides per-partition confusion counts, common-all and common-frontier support, lower/upper missing-label bounds and paired model tests. Agreement against a human majority and agreement between individual human pairs are different estimands; neither establishes ethical superiority.", "", "## Categorical Rationales", "",
              "Commonsense, Deontology and Justice have categorical rationales. **Production Utilitarianism also has ten multi-select categories**, so it is included. Deontology has separate main and moral-principle fields. Virtue explanations are free text and receive no invented categorical or semantic agreement score.", "",
              "Jaccard is category-set intersection divided by union; exact-set agreement requires complete equality. Each item receives equal weight after averaging eligible actor pairs. Empty/inapplicable fields never count as perfect matches. Internal baselines retain all original eligible humans/models, not only majority-supporting judgments.", "", "### Internal human and LLM rationale agreement", ""]
    lines.append(markdown_table(["Field","Panel","Items / pairs","Jaccard","Exact sets"],
        [[FIELD_NAMES[r["field"]],PANEL_NAMES[r["group"]],f"{count(r['n_items_any_pair'])} / {count(r['n_pairs_total'])}",pct(r["jaccard_item_mean"]),pct(r["exact_set_item_mean"])] for r in rationale_panels if r["group"] in ("humans",)+PANELS]))
    lines += ["", "Different panels may have different applicable items, especially in Deontology. The accompanying matched-complete table removes that item-set difference, at the cost of selecting only cases where all three humans and every panel member have an applicable valid rationale.", "", "### Matched complete rationale panels", ""]
    lines.append(markdown_table(["Field","Panel","Common items","Human Jaccard / exact","LLM Jaccard / exact"],
        [[FIELD_NAMES[r["field"]],PANEL_NAMES[r["group"]],r["n_complete_items"],f"{pct(r['human_jaccard'])} / {pct(r['human_exact'])}",f"{pct(r['model_jaccard'])} / {pct(r['model_exact'])}"] for r in matched_rationales]))
    for scope,title in (("majority_aligned","Model versus majority-supporting human rationales"),("same_judgment","Rationale agreement when the final verdict also matches")):
        lines += ["", "### "+title, ""]
        lines.append(markdown_table(["Model",*FIELD_NAMES.values()],[[m]+[f"{pct(r['jaccard'])} (n={count(r['n_items'])})" for field in FIELDS for r in overlap if r["model"]==m and r["field"]==field and r["scope"]==scope] for m in order]))
    lines += ["", "The primary reference retains the two/three majority-aligned human sets separately. The primary model label need not match; the same-judgment sensitivity requires it to match. Conditional cohorts differ by model, so rationale ranks are not automatically paired superiority claims. Dice, exact-set scores, field-specific kappas, intervals and category-level diagnostics remain in the detailed CSVs. No single overall rationale score pools unrelated category spaces or counts Deontology twice.", "", "## Striking Disagreements", "",
              "The counts below require unanimous humans. All-nine majority opposition includes all-nine unanimity and is not disjoint from frontier opposition. Invalid or absent model outputs are not opposing votes.", ""]
    lines.append(markdown_table(["Partition","Humans unanimous, all 9 opposite","Humans unanimous, >=5/9 opposite","Humans unanimous, frontier 3 opposite","Selected cases"],[[r["partition"].title(),r["human_unanimous_all9_opposite"],r["human_unanimous_complete9_majority_opposite"],r["human_unanimous_frontier3_opposite"],r["selected"]] for r in selection_summary]))
    lines += ["", "See [selected examples](examples/EXAMPLES.md), [full selected-case CSV](examples/selected_cases.csv), [full JSON evidence](examples/selected_cases.json) and [all eligible disagreement candidates](examples/all_disagreement_candidates.csv). Selection ranks vote opposition/coverage, not supposed moral correctness. Full narratives and all annotations are retained; excerpts are explicitly marked.", "", "## Files and Reproduction", ""]
    links = [("Five complete three-human input CSVs",ROOT/"data/humans"),("Five model-input CSVs",ROOT/"data/llms"),
             ("Every human majority and every model label, per partition",results/"per_item_predictions"),("Human reliability",results/"judgments/human_reliability.csv"),
             ("All model-pair agreement, per partition and overall",results/"judgments/pairwise_model_agreement.csv"),
             ("Model-panel reliability",results/"judgments/group_reliability.csv"),("Each model versus human majority",results/"judgments/model_vs_human.csv"),
             ("Internal categorical-rationale agreement",results/"rationales/group_rationale_agreement.csv"),
             ("Model-human categorical-rationale agreement",results/"rationales/model_human_overlap.csv"),
             ("Rationale distributions and category shifts",results/"rationales/model_human_distances.csv"),
             ("Matched complete label panels",summary_dir/"matched_complete_label_panels.csv"),
             ("Matched complete rationale panels",summary_dir/"matched_complete_rationale_panels.csv")]
    lines += [f"- [{name}]({relative(path)})." for name,path in links]
    lines += ["", f"This run uses **{manifest['bootstrap_resamples']:,} within-partition item-bootstrap resamples**, seed **{manifest['seed']}**. All actor annotations move together within a sampled item. Model/annotator populations and model reruns are not resampled. Related story templates can violate independent-item assumptions; optional scenario-cluster bootstrap support remains in the engine.", "",
              "Use the package README for one-command reproduction. All paths are relative, no API access is needed, and the original source repository is not needed for rerunning the analyses. Raw XLSM files, Office metadata, administrative identity mappings, payment records and credentials are excluded. No redistribution license is asserted; confirm the project's/source-dataset terms before public release."]
    (results / "COLLABORATOR_REPORT.md").write_text("\n".join(lines)+"\n")
    print(f"Created collaborator report and {len(selected)} deterministic examples.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, required=True)
    build(ap.parse_args().results)
