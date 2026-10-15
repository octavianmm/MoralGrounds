#!/usr/bin/env python3
"""Run a relocated copy from package inputs alone and compare point estimates."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_inputs import read_csv


def main():
    with tempfile.TemporaryDirectory(prefix="ethics10k_portable_") as tmp:
        clone = Path(tmp) / "package"
        clone.mkdir()
        for p in ROOT.iterdir():
            if p.name in ("results", "results_final", ".work", ".git", ".venv", "__pycache__", ".pytest_cache"):
                continue
            if p.is_dir():
                shutil.copytree(p,clone/p.name,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
            elif p.is_file():
                shutil.copy2(p,clone/p.name)
        environment = dict(os.environ, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([sys.executable,"-B",str(clone/"scripts/run_analysis.py"),"--bootstrap","50","--no-plots"],
                       cwd=clone,env=environment,check=True)
        subprocess.run([sys.executable,"-B",str(clone/"scripts/validate_package.py")],cwd=clone,env=environment,check=True)
        comparisons = 0
        for rel, keys, metrics in (("judgments/model_vs_human.csv",("model","sample","partition"),("n","agreement","kappa")),
                                  ("rationales/model_human_overlap.csv",("model","field","scope"),("n_items","jaccard","exact_set")),
                                  ("judgments/group_reliability.csv",("group","partition"),("pairwise_item_mean","fleiss_kappa","krippendorff_alpha"))):
            expected = {tuple(r[k] for k in keys):r for r in read_csv(ROOT/"results"/rel)}
            actual = read_csv(clone/"results"/rel)
            for row in actual:
                reference = expected[tuple(row[k] for k in keys)]
                for metric in metrics:
                    if abs(float(row[metric])-float(reference[metric])) > 1e-10:
                        raise ValueError("Relocation changed a scientific point estimate")
                    comparisons += 1
        selected = "examples/selected_cases.csv"
        if (clone/"results"/selected).read_bytes() != (ROOT/"results"/selected).read_bytes():
            raise ValueError("Relocation changed selected-case evidence or ordering")
        result = dict(status="passed", original_repository_needed=False, package_relocated=True,
                      analysis_bootstrap_draws=50, intervals_publication_quality=False,
                      point_estimates_compared=comparisons, selected_case_bytes_identical=True,
                      network_or_api_calls=False)
    (ROOT/"provenance/PORTABILITY_CHECK.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
