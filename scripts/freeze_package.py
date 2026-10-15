#!/usr/bin/env python3
"""Record package hashes and optionally scan against a private annotator roster."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".work", ".venv", "__pycache__", ".pytest_cache"}


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD",value).casefold() if not unicodedata.combining(c))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--private-roster", type=Path, help="Optional local CSV, read only; never copied or disclosed")
    args = ap.parse_args()
    identifiers = []
    if args.private_roster:
        with args.private_roster.open(encoding="utf-8",newline="") as f:
            for row in csv.DictReader(f):
                identifiers.extend(fold(row[k]) for k in ("name","email") if row.get(k))
    findings, reviewed = [], 0
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or EXCLUDED.intersection(p.relative_to(ROOT).parts):
            continue
        if p.suffix not in (".csv",".json",".md",".py",".txt",".html",".svg"):
            continue
        body = p.read_text(encoding="utf-8")
        normalized = fold(body) if identifiers else ""
        if identifiers and any(value in normalized for value in identifiers):
            findings.append(dict(path=str(p.relative_to(ROOT)), issue="private participant identity"))
        if re.search(r"sk-or-v1-[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",body):
            findings.append(dict(path=str(p.relative_to(ROOT)), issue="credential pattern"))
        reviewed += 1
    if findings:
        raise ValueError(json.dumps(findings))
    privacy = dict(status="passed", text_files_scanned=reviewed,
                   participant_identity_scan=bool(identifiers), private_identifiers_published=False,
                   credential_patterns_found=0, roster_copied=False, git_initialized=(ROOT/".git").exists())
    (ROOT / "provenance/PRIVACY_CHECK.json").write_text(json.dumps(privacy,indent=2)+"\n")
    output = ROOT / "provenance/PACKAGE_MANIFEST.csv"
    inventory = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and p != output and not EXCLUDED.intersection(p.relative_to(ROOT).parts):
            inventory.append(dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size,
                                  sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    with output.open("w",encoding="utf-8",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=("path","bytes","sha256"),lineterminator="\n")
        writer.writeheader()
        writer.writerows(inventory)
    print(json.dumps(dict(status="passed",manifest_files=len(inventory),privacy=privacy),indent=2))


if __name__ == "__main__":
    main()
