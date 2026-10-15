#!/usr/bin/env python3
"""Analyze archive A's human exports and archive B's LLM annotations.

Example:
    python analyze_ethics.py --human A.zip --llm B.zip --out results --bootstrap 5000

Inputs are read-only; no model/API calls, no macros, no code from the archives.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import sys
import time
import traceback

# Limit numerical thread overhead consistently, without changing analysis results.
from threadpoolctl import threadpool_limits

from ethics_analysis import __version__
from ethics_analysis.ingest import load_data, Source
from ethics_analysis.io_utils import write_csv, write_json
from ethics_analysis.judgments import DataMatrices
from ethics_analysis.metrics import Bootstrap
from ethics_analysis.schema import PARTITIONS, text
from ethics_analysis import judgments, rationales, reporting


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--human", required=True, help="Archive A.zip or the extracted ETHICS_LLM-main repository root")
    p.add_argument("--llm", required=True, help="Archive B.zip or the extracted ETHICS10k directory")
    p.add_argument("--out", required=True, help="New/empty output directory (existing results are never overwritten)")
    p.add_argument("--bootstrap", type=int, default=2000, help="Shared within-partition bootstrap draws (default: 2000; final: 5000)")
    p.add_argument("--seed", type=int, default=20260917)
    p.add_argument("--config", type=Path, help="Optional JSON containing model groups")
    p.add_argument("--cluster-map", type=Path, help="Optional full CSV crosswalk: item_id,cluster_id; clusters must remain within a partition")
    p.add_argument("--no-plots", action="store_true")
    p.add_argument("--audit-only", action="store_true", help="Only validate inputs, normalize rows, and export audit tables")
    p.add_argument("--threads", type=int, default=1, help="Numerical-library threads (default: 1)")
    args = p.parse_args()
    if args.bootstrap < 1 or args.threads < 1:
        p.error("--bootstrap and --threads must be positive integers")
    if not args.audit_only and args.bootstrap < 500:
        print("WARNING: fewer than 500 draws is a smoke test, not a publication run.", file=sys.stderr)
    return args


def cluster_suggestion(items, out):
    """Only exact duplicate scenario text; not a claim to recover all dependencies."""
    import re
    from collections import Counter
    rows = []
    for key, item in items.items():
        scenario = item["input"]
        if item["partition"] == "virtue":
            scenario = re.split(r"\bTrait\s*:", scenario, maxsplit=1, flags=re.I)[0]
        scenario = text(scenario)
        cluster = item["partition"] + ":" + hashlib.sha256(scenario.encode()).hexdigest()[:20]
        rows.append(dict(item_id=key, cluster_id=cluster, partition=item["partition"],
                         rule="exact_scenario_without_trait" if item["partition"] == "virtue" else "exact_full_input"))
    sizes = Counter(r["cluster_id"] for r in rows)
    for row in rows:
        row["cluster_size"] = sizes[row["cluster_id"]]
    write_csv(out / "audit" / "suggested_exact_scenario_clusters.csv", rows)
    return dict(n_suggested_clusters=len(sizes), n_repeated_clusters=sum(n > 1 for n in sizes.values()),
                n_items_in_repeated_clusters=sum(n for n in sizes.values() if n > 1),
                maximum_cluster_size=max(sizes.values()),
                interpretation="Exact duplicate scenario audit only; not automatically used by default")


def read_clusters(path, data):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapping, partition_by_cluster = {}, {}
    for row in rows:
        key, cluster = row["item_id"], row["cluster_id"]
        if not cluster or key in mapping or key not in data.items:
            raise ValueError(f"Invalid or duplicate cluster-map row: {row}")
        p = data.items[key]["partition"]
        if cluster in partition_by_cluster and partition_by_cluster[cluster] != p:
            raise ValueError(f"Cluster {cluster} crosses partitions; this stratified cluster bootstrap requires nested clusters")
        mapping[key] = cluster
        partition_by_cluster[cluster] = p
    if set(mapping) != set(data.items):
        raise ValueError("The cluster map must contain exactly one row for every canonical item_id")
    return {p: [mapping[key] for key in ids] for p, ids in data.ids.items()}


def reconcile_human_reliability(human_path, computed, out):
    source = Source(human_path)
    try:
        filenames = [n for n in source.names if n.endswith("data/processed/aggregated/human_label_agreement_by_partition.csv")]
        if not filenames:
            return {"status": "reference_summary_not_present"}
        rows = source.csv(filenames[0])
    finally:
        source.close()
    comparison = []
    lookup = {r["partition"]: r for r in computed}
    # Field names differ between A's earlier pipeline and this package.
    aliases = {"pairwise_observed_agreement": "pairwise_item_mean", "fleiss_kappa": "fleiss_kappa",
               "krippendorff_alpha_nominal": "krippendorff_alpha"}
    for row in rows:
        p = row.get("partition", "")
        if p not in lookup:
            continue
        for source_field, target_field in aliases.items():
            if source_field not in row or not row[source_field]:
                continue
            ref, value = float(row[source_field]), lookup[p][target_field]
            delta = value-ref
            decimals = len(row[source_field].partition(".")[2])
            tolerance = .5 * 10**(-decimals) + 1e-12
            comparison.append(dict(partition=p, metric=target_field, provided=ref, recomputed=value,
                                   difference=delta, rounding_tolerance=tolerance, agrees=abs(delta)<=tolerance))
            if abs(delta) > tolerance:
                raise ValueError(f"Human reliability differs from A: {p}, {source_field}: {ref} vs {value}")
    write_csv(out / "audit" / "human_reliability_reconciliation.csv", comparison)
    return {"n_reconciled_statistics": len(comparison), "all_match": all(r["agrees"] for r in comparison)}


def main():
    args = parse_args()
    out = Path(args.out).expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"Refusing to mix with existing files: {out}. Choose a new output directory.")
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else None
    print("1/6  Validating and aligning archive contents ...", flush=True)
    items, humans, llms, models, groups, audit = load_data(args.human, args.llm, config)
    audit.summary["exact_scenario_cluster_audit"] = cluster_suggestion(items, out)
    coverage = reporting.export_audit(items, humans, llms, models, audit, out)
    manifest = dict(analysis_version=__version__, seed=args.seed, bootstrap_resamples=args.bootstrap,
                    bootstrap_unit="nested_cluster" if args.cluster_map else "instruction",
                    cluster_map_sha256=hashlib.sha256(args.cluster_map.read_bytes()).hexdigest() if args.cluster_map else None,
                    python=sys.version, platform=platform.platform(), groups=groups,
                    software={name: importlib.metadata.version(name) for name in ("numpy", "scipy", "pandas", "matplotlib", "threadpoolctl")},
                    arguments={k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
                    input_paths_read_only=True, network_or_api_calls=False)
    code_root = Path(__file__).resolve().parent
    excluded_code_dirs = {".venv", ".work", ".git", ".pytest_cache", "__pycache__"}
    manifest["code_sha256"] = {str(p.relative_to(code_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(code_root.rglob("*.py"))
                               if not excluded_code_dirs.intersection(p.relative_to(code_root).parts)}
    if args.audit_only:
        manifest["elapsed_seconds"] = time.perf_counter()-start
        write_json(out / "run_manifest.json", manifest)
        print(f"Audit complete: {len(items):,} items; {len(models)} model conditions; {out}")
        return
    data = DataMatrices(items, humans, llms, models)
    clusters = read_clusters(args.cluster_map, data) if args.cluster_map else None
    print(f"2/6  Preparing {args.bootstrap:,} shared stratified bootstrap draws ...", flush=True)
    with threadpool_limits(limits=args.threads):
        bootstrap = Bootstrap(data.ids, args.bootstrap, args.seed, cluster_labels=clusters)
        print("3/6  Judgment agreement, human baselines, panels, and paired tests ...", flush=True)
        jr = judgments.run(data, bootstrap, groups, out / "judgments", llms)
        manifest["human_reliability_reconciliation"] = reconcile_human_reliability(args.human, jr["human"], out)
        print("4/6  Structured rationales, same-judgment comparisons, and text diagnostics ...", flush=True)
        rr = rationales.run(data, bootstrap, groups, humans, llms, out / "rationales")
    print("5/6  Assembling item-level review evidence and figures ...", flush=True)
    review = reporting.review_queue(data, jr, rr, out)
    figures = [] if args.no_plots else reporting.plots_from_csv(out)
    manifest["elapsed_seconds"] = time.perf_counter()-start
    manifest["bootstrap_draws_shared_across_actors"] = True
    print("6/6  Writing the report and reproducibility manifest ...", flush=True)
    reporting.make_report(out, audit, jr, rr, manifest, coverage, review, figures)
    write_json(out / "run_manifest.json", manifest)
    output_inventory = [dict(path=str(p.relative_to(out)), bytes=p.stat().st_size,
                             sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob("*")) if p.is_file()]
    write_csv(out / "output_manifest.csv", output_inventory)
    print(f"Complete in {manifest['elapsed_seconds']:.1f} seconds. Report: {out / 'REPORT.html'}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
