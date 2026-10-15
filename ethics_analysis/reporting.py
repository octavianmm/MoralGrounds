"""Audit exports, investigation queues, portable report, and separate figures."""
from __future__ import annotations
import base64
from collections import Counter, defaultdict
import html
import io
import json
from pathlib import Path
import re
import textwrap

import numpy as np
from .io_utils import write_csv, write_json
from .schema import FIELDS, LABELS, PARTITIONS, text


def export_audit(items, humans, llms, models, audit, out):
    root = Path(out)
    target = root / "audit"
    write_json(target / "audit_summary.json", audit.summary)
    write_csv(target / "normalization_and_quality_events.csv", audit.events)
    write_csv(target / "item_crosswalk.csv", audit.crosswalk)
    write_csv(target / "input_file_manifest.csv", audit.source_manifest)
    coverage, missing = [], []
    observed = {(o["actor"], o["item_id"]): o for o in llms}
    for model in models:
        for p in PARTITIONS:
            ids = [k for k, item in items.items() if item["partition"] == p]
            count = Counter()
            for key in ids:
                obs = observed.get((model, key))
                status = obs["label_status"] if obs else "absent_row"
                count[status] += 1
                if status != "valid":
                    missing.append(dict(model=model, item_id=key, partition=p, status=status,
                                        raw_label=obs["raw_label"] if obs else None))
            coverage.append(dict(model=model, partition=p, n_items=len(ids), n_present=len(ids)-count["absent_row"],
                                 n_valid=count["valid"], n_absent_rows=count["absent_row"],
                                 n_missing_labels=count["missing"], n_invalid_labels=count["invalid"]))
    write_csv(target / "coverage.csv", coverage)
    write_csv(target / "missing_or_invalid_labels.csv", missing)
    item_rows = []
    for key, item in items.items():
        row = {k: v for k, v in item.items() if k not in ("human_observations", "normalized_input")}
        row["human_label_counts"] = {LABELS[item["partition"]][v]: item["human_n" + str(v)] for v in range(2)}
        row["human_majority_label"] = LABELS[item["partition"]][item["human_majority"]] if item["human_majority"] is not None else None
        item_rows.append(row)
    write_csv(root / "normalized" / "items.csv", item_rows)
    # Canonical normalized records retain opaque annotator codes, not workbook metadata.
    records = []
    for o in humans + llms:
        row = {k: v for k, v in o.items() if k != "fields"}
        row["normalized_label"] = LABELS[o["partition"]][o["label"]] if o["label"] is not None else None
        row["structured_fields"] = o["fields"]
        records.append(row)
    write_csv(root / "normalized" / "annotations.csv", records)
    return coverage


def review_queue(data, judgments, rationales, out):
    """Evidence-led queues, not automatic declarations of model/human error."""
    all_items = {r["item_id"]: r for r in judgments["item"] if r["group"] == "all"}
    frontier = {r["item_id"]: r for r in judgments["item"] if r["group"] == "frontier"}
    rationale_scores = defaultdict(list)
    for r in rationales["items"]:
        if r["scope"] == "same_judgment":
            rationale_scores[r["item_id"]].append(r["jaccard"])
    rows = []
    for key, item in data.items.items():
        labels, human_rationales, llm_rationales = {}, [], {}
        for h in item["human_observations"]:
            human_rationales.append(dict(label=LABELS[item["partition"]][h["label"]],
                                         majority_aligned=h["label"] == item["human_majority"],
                                         rationales={f: r["value"] for f, r in h["fields"].items()}))
        for model in data.models:
            obs = data.model_lookup.get((model, key))
            labels[model] = LABELS[item["partition"]][obs["label"]] if obs and obs["label"] is not None else None
            llm_rationales[model] = {f: dict(value=r["value"], status=r["status"]) for f, r in obs["fields"].items()} if obs else None
        consensus = all_items[key]
        fr = frontier.get(key, {})
        scores = rationale_scores[key]
        jaccard = float(np.mean(scores)) if scores else None
        flags = []
        if consensus["complete_unanimous_against_human"]:
            flags.append("all_models_unanimous_against_human_majority")
        if fr.get("complete_unanimous_against_human"):
            flags.append("frontier_unanimous_against_human_majority")
        if consensus["n_invalid_labels"] or consensus["n_missing_rows"]:
            flags.append("incomplete_label_coverage")
        if item["human_unanimous"] and consensus["entropy_bits"] >= .9:
            flags.append("human_unanimous_models_divided")
        if scores and jaccard <= .25:
            flags.append("same_judgment_low_rationale_overlap")
        if item["human_ambiguity_votes"]:
            flags.append("human_ambiguity_flag")
        if item["human_cultural_flag_votes"]:
            flags.append("human_culture_reference_flag")
        rows.append(dict(item_id=key, partition=item["partition"], task_instruction_id=item["task_instruction_id"],
                         meta_id=item["meta_id"], input=item["input"], source_split=item["source_split"],
                         human_majority=LABELS[item["partition"]][item["human_majority"]],
                         human_unanimous=item["human_unanimous"], human_vote_counts=consensus["human_vote_split"],
                         llm_pairwise_agreement=consensus["pairwise_agreement"], llm_entropy_bits=consensus["entropy_bits"],
                         all_models_unanimous_against_human=consensus["complete_unanimous_against_human"],
                         frontier_unanimous_against_human=fr.get("complete_unanimous_against_human", False),
                         same_judgment_mean_rationale_jaccard=jaccard, review_flags=flags,
                         model_labels=labels, human_rationales=human_rationales, model_rationales=llm_rationales))
    rows.sort(key=lambda r: (not r["all_models_unanimous_against_human"],
                            not r["frontier_unanimous_against_human"],
                            -(len(r["review_flags"])), r["item_id"]))
    write_csv(Path(out) / "review" / "all_items_with_evidence.csv", rows)
    write_csv(Path(out) / "review" / "priority_review.csv", [r for r in rows if r["review_flags"]])
    write_csv(Path(out) / "review" / "first_100_review_cases.csv", [r for r in rows if r["review_flags"]][:100])
    return rows


def _short(model):
    return model.split("/")[-1]


def plots_from_csv(out):
    """One plot per figure; matplotlib defaults, no prescribed colors/styles."""
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root = Path(out)
    figures = root / "figures"
    figures.mkdir(exist_ok=True)
    produced = []

    def save(fig, name):
        fig.tight_layout()
        for ext in ("png", "svg"):
            fig.savefig(figures / f"{name}.{ext}", dpi=180, bbox_inches="tight")
        plt.close(fig)
        produced.append(name)

    mh = pd.read_csv(root / "judgments" / "model_vs_human.csv")
    avail = mh[(mh["sample"] == "available") & (mh["partition"] == "overall")].sort_values("agreement")
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    low = avail["agreement"] - avail["agreement_ci_low"]
    high = avail["agreement_ci_high"] - avail["agreement"]
    ax.hlines(np.arange(len(avail)), avail["agreement_ci_low"], avail["agreement_ci_high"])
    ax.plot(avail["agreement"], np.arange(len(avail)), "o")
    ax.set_yticks(np.arange(len(avail)), [_short(m) for m in avail["model"]])
    ax.set_xlabel("Agreement with human majority (95% stratified item-bootstrap interval)")
    ax.set_title("Judgment agreement · available valid responses")
    ax.grid(axis="x", alpha=.25)
    save(fig, "model_human_agreement")

    table = mh[(mh["sample"] == "available") & (mh["partition"] != "overall")].pivot(index="model", columns="partition", values="agreement")
    table = table.reindex(index=list(avail["model"])[::-1], columns=PARTITIONS)
    fig, ax = plt.subplots(figsize=(10.8, 6.3))
    image = ax.imshow(table.values, vmin=0, vmax=1, aspect="auto")
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            ax.text(j, i, f"{table.iloc[i,j]:.3f}", ha="center", va="center",
                    fontsize=10)
    ax.set_xticks(np.arange(len(PARTITIONS)), [p.capitalize() for p in PARTITIONS], rotation=20, ha="right")
    ax.set_yticks(np.arange(len(table)), [_short(m) for m in table.index])
    ax.set_title("Human-majority agreement by partition")
    fig.colorbar(image, ax=ax, label="Agreement")
    save(fig, "agreement_by_partition")

    pair = pd.read_csv(root / "judgments" / "pairwise_model_agreement.csv")
    pair = pair[pair["partition"] == "overall"]
    models = list(avail["model"])[::-1]
    matrix = np.eye(len(models))
    for _, r in pair.iterrows():
        i, j = models.index(r.model_a), models.index(r.model_b)
        matrix[i,j] = matrix[j,i] = r.agreement
    fig, ax = plt.subplots(figsize=(10, 8.6))
    im = ax.imshow(matrix, vmin=0, vmax=1)
    ax.set_xticks(range(len(models)), [_short(m) for m in models], rotation=55, ha="right")
    ax.set_yticks(range(len(models)), [_short(m) for m in models])
    for i in range(len(models)):
        for j in range(len(models)):
            ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Pairwise model judgment agreement · overall paired cases")
    fig.colorbar(im, ax=ax, fraction=.046, pad=.04)
    save(fig, "pairwise_model_agreement")

    distances = pd.read_csv(root / "rationales" / "model_human_distances.csv")
    for field in FIELDS:
        sub = distances[(distances.field == field) & (distances.scope == "same_judgment") & (distances.weighting == "item_balanced")].sort_values("tv", ascending=False)
        fig, ax = plt.subplots(figsize=(10.5, 5.4))
        errs = np.maximum(0, np.array([sub.tv-sub.tv_ci_low, sub.tv_ci_high-sub.tv]))
        ax.hlines(np.arange(len(sub)), sub.tv_ci_low, sub.tv_ci_high)
        ax.plot(sub.tv, np.arange(len(sub)), "o")
        ax.set_yticks(np.arange(len(sub)), [_short(m) for m in sub.model])
        ax.set_xlabel("Total variation of principle/category mention shares (95% interval)")
        ax.set_title(field.replace("_", " ").capitalize() + "\nSame final judgment · item-balanced human reference")
        ax.grid(axis="x", alpha=.25)
        save(fig, "rationale_tv_" + field)

    strata = pd.read_csv(root / "judgments" / "stratified_model_vs_human.csv")
    sub = strata[strata.stratum.isin(["human_unanimous", "human_split"])]
    fig, ax = plt.subplots(figsize=(10.5, 6))
    for s, title in (("human_unanimous", "Unanimous humans"), ("human_split", "Split humans (2–1)")):
        vals = []
        for m in models:
            v = sub[(sub.model == m) & (sub.stratum == s)]
            vals.append(np.average(v.agreement, weights=v.n))
        ax.plot(vals, np.arange(len(models)), "o", label=title)
    ax.set_yticks(np.arange(len(models)), [_short(m) for m in models])
    ax.set_xlabel("Item-weighted agreement with human majority")
    ax.set_title("Judgment agreement by human consensus strength")
    ax.legend(loc="best")
    ax.grid(axis="x", alpha=.25)
    save(fig, "human_consensus_strata")
    return produced


def make_report(out, audit, judgments, rationales, manifest, coverage, review, figures):
    root = Path(out)
    summary = audit.summary
    models = sorted([r for r in judgments["model"] if r["sample"] == "available" and r["partition"] == "overall"], key=lambda r: -r["agreement"])
    table = ["| Model (archive identifier) | Valid / items | Agreement | 95% bootstrap interval | Weighted domain κ |",
             "|---|---:|---:|---:|---:|"]
    for r in models:
        table.append(f"| {r['model']} | {r['n']:,} / {summary['n_items']:,} | {r['agreement']:.4f} | {r['agreement_ci_low']:.4f}–{r['agreement_ci_high']:.4f} | {r['kappa']:.4f} |")
    human_table = ["| Partition | Items | Unanimous | Mean pairwise agreement | Fleiss κ | Nominal α |", "|---|---:|---:|---:|---:|---:|"]
    for r in judgments["human"]:
        human_table.append(f"| {r['partition']} | {r['n_items']:,} | {r['n_unanimous']:,} | {r['pairwise_item_mean']:.4f} | {r['fleiss_kappa']:.4f} | {r['krippendorff_alpha']:.4f} |")
    group_table = ["| Panel | Complete items | Mean pair agreement | Domain-weighted Fleiss κ | All panel agrees against human majority |", "|---|---:|---:|---:|---:|"]
    for r in judgments["group"]:
        if r["partition"] == "overall":
            group_table.append(f"| {r['group']} | {r['n_complete']:,} | {r['pairwise_item_mean']:.4f} | {r['fleiss_kappa']:.4f} | {r['n_complete_unanimous_against_human']:,} |")
    same = [r for r in rationales["distances"] if r["scope"] == "same_judgment" and r["weighting"] == "item_balanced"]
    rationale_table = ["| Field | Lowest TV | Highest TV |", "|---|---|---|"]
    for field in FIELDS:
        rows = sorted([r for r in same if r["field"] == field], key=lambda r: r["tv"])
        lo, hi = rows[0], rows[-1]
        rationale_table.append(f"| {field} | {lo['model']}: {lo['tv']:.4f} (n={lo['n_items']:,}) | {hi['model']}: {hi['tv']:.4f} (n={hi['n_items']:,}) |")
    invalid_fields = [r for r in rationales["quality"] if r["actor"] != "humans" and (r["n_invalid"] or r["n_missing"])]
    quality_lines = [f"- `{r['actor']}` / `{r['field']}`: {r['n_missing']} missing, {r['n_invalid']} invalid among {r['n_eligible']:,} eligible present responses." for r in invalid_fields]
    bootstrap_description = ("nested scenario clusters" if manifest["bootstrap_unit"] == "nested_cluster" else "instructions")
    report = f'''# ETHICS production annotation analysis

## Verified input and protocol

The supplied production exports contain **{summary['n_items']:,} instructions**, not 9,875:
1,995 in each of the five partitions. There are **{summary['n_human_annotations']:,} human ratings**
from **{summary['n_human_annotators']} annotators**, exactly three distinct annotators per instruction.
All {summary['human_majorities_reconciled']:,} reconstructed human majorities match archive A's export;
all {summary['human_rationale_aggregates_reconciled']:,} reconstructed rationale records match its rationale aggregate.
This run consumes A's normalized individual exports; it does not rerun normalization of the 95 original macro-enabled workbooks.

Archive B supplies **{summary['n_models']} model conditions** and **{summary['n_llm_rows']:,} rows**.
There are **{summary['n_missing_llm_rows']} absent rows**, **{summary['llm_label_status'].get('missing', 0)} empty final labels**,
and **{summary['llm_label_status'].get('invalid', 0)} invalid final labels**.
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

{chr(10).join(human_table)}

Overall chance-adjusted values are weighted means of within-partition coefficients, not coefficients
calculated by treating different domain labels as the same category. Human-majority agreement is a
study-reference concordance measure, not a moral-correctness measure.
The leave-one-out file evaluates held-out humans against the other two raters only when those two agree;
it never evaluates a human against a majority containing their own vote. It is not an ethical ceiling.

## Each model against the human majority

{chr(10).join(table)}

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

{chr(10).join(group_table)}

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

{chr(10).join(rationale_table)}

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

{chr(10).join(quality_lines)}

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

This run used **{manifest['bootstrap_resamples']:,} percentile bootstrap resamples**, seed
**{manifest['seed']}**, sampling {bootstrap_description} within ethical partitions and preserving the complete
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
'''
    (root / "REPORT.md").write_text(report, encoding="utf-8")
    # A dependency-free, self-contained HTML report with tables and embedded plots.
    lines = report.splitlines()
    body, in_list, in_table = [], False, False
    for line in lines:
        if line.startswith("|"):
            if not in_table:
                body.append("<table>")
                in_table = True
            if set(line.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
                continue
            cells = line.strip("|").split("|")
            body.append("<tr>" + "".join("<td>" + html.escape(c.strip()) + "</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            body.append("</table>")
            in_table = False
        safe = html.escape(line)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
        safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)
        if line.startswith("## "):
            body.append("<h2>" + safe[3:] + "</h2>")
        elif line.startswith("# "):
            body.append("<h1>" + safe[2:] + "</h1>")
        elif line.startswith("- "):
            body.append("<p class='file'>" + safe[2:] + "</p>")
        elif line:
            body.append(safe + " ")
        else:
            body.append("<p></p>")
    body.append("<h2>Figures</h2>")
    for name in figures:
        image = (root / "figures" / (name + ".png")).read_bytes()
        body.append(f"<figure><img alt='{html.escape(name)}' src='data:image/png;base64,{base64.b64encode(image).decode()}'></figure>")
    document = """<!doctype html><html lang="en"><meta charset="utf-8"><title>ETHICS production analysis</title>
<style>body{font:17px/1.6 system-ui,sans-serif;max-width:1150px;margin:45px auto;padding:0 25px}h1{font-size:34px}h2{margin-top:40px}table{border-collapse:collapse;width:100%;font-size:14px;margin:22px 0}td{border-bottom:1px solid;padding:8px;text-align:left}tr:first-child{font-weight:bold}code{font-size:14px;overflow-wrap:anywhere}img{max-width:100%;height:auto}.file{margin:4px 0}</style><body>""" + "\n".join(body) + "</body></html>"
    (root / "REPORT.html").write_text(document, encoding="utf-8")
    return report
