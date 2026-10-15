#!/usr/bin/env python3
"""Reproduce all analyses, reports and selected disagreement examples offline."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_inputs import prepare


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    ap.add_argument("--bootstrap", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args()
    config = json.loads((ROOT / "config/model_groups.json").read_text())
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose a new/empty results directory; existing results are never replaced")
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "data").rglob("*.csv"))}
    environment = dict(os.environ, OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory(prefix="ethics10k_inputs_") as tmp:
        human, llm = prepare(Path(tmp))
        command = [sys.executable, "-B", str(ROOT / "analyze_ethics.py"), "--human", str(human), "--llm", str(llm),
                   "--out", str(out), "--bootstrap", str(config["bootstrap"] if args.bootstrap is None else args.bootstrap),
                   "--seed", str(config["seed"] if args.seed is None else args.seed), "--config", str(ROOT / "config/model_groups.json")]
        if args.no_plots:
            command.append("--no-plots")
        subprocess.run(command, check=True, env=environment, cwd=ROOT)
    subprocess.run([sys.executable, "-B", str(ROOT / "validate_results.py"), str(out)], check=True, env=environment, cwd=ROOT)
    subprocess.run([sys.executable, "-B", str(ROOT / "scripts/build_collaborator_report.py"), "--results", str(out)], check=True, env=environment, cwd=ROOT)
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "data").rglob("*.csv"))}
    if before != after:
        raise ValueError("Analysis modified a frozen package input")
    (out / "PACKAGE_INPUT_CHECKSUMS.json").write_text(json.dumps(before, indent=2, sort_keys=True)+"\n")
    manifest = json.loads((out / "run_manifest.json").read_text())
    manifest["arguments"].update(human="reconstructed from data/humans/*.csv", llm="reconstructed from data/llms/*.csv",
                                  out="this results directory", config="config/model_groups.json")
    excluded_code_dirs = {".venv", ".work", ".git", ".pytest_cache", "__pycache__"}
    manifest["code_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(ROOT.rglob("*.py"))
                               if not excluded_code_dirs.intersection(p.relative_to(ROOT).parts)}
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    inventory = [dict(path=str(p.relative_to(out)), bytes=p.stat().st_size,
                      sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob("*"))
                 if p.is_file() and p.name != "output_manifest.csv"]
    with (out / "output_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("path", "bytes", "sha256"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(inventory)
    subprocess.run([sys.executable, "-B", str(ROOT / "validate_results.py"), str(out)], check=True, env=environment, cwd=ROOT)
    print(f"Completed offline collaborator analysis: {out / 'COLLABORATOR_REPORT.md'}")


if __name__ == "__main__":
    main()
