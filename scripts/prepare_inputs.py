#!/usr/bin/env python3
"""Reconstruct the tested analysis inputs using only this package's ten CSVs."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "support/aggregation"))
from aggregate_majority_labels import aggregate, write_csv_atomic as write_majority
from concatenate_categorical_rationales import concatenate, write_csv_atomic as write_rationales
from ethics_analysis.schema import PARTITIONS


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"Malformed CSV: {path}")
        return rows


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def prepare(destination, data_root=None):
    destination = Path(destination)
    data_root = Path(data_root or ROOT / "data")
    schema = json.loads((ROOT / "docs/schema.json").read_text())
    individual, item_lookup = [], {}
    for p in PARTITIONS:
        rows = read_csv(data_root / "humans" / f"{p}.csv")
        if len(rows) != 1995:
            raise ValueError(f"Wrong item count: {p}")
        for row in rows:
            key = row["item_id"]
            if key != f"{p}:{int(row['task_instruction_id'])}" or key in item_lookup:
                raise ValueError(f"Invalid or duplicate item key: {key}")
            item_lookup[key] = row
            codes, labels = [], []
            for slot in (1, 2, 3):
                obs = {f: row[f] if f in schema["source_fields"] else row[f"annotator_{slot}_{f}"] for f in schema["original_individual_columns"]}
                if obs["partition"] != p or int(obs["annotation_copy"]) != slot:
                    raise ValueError(f"Slot/copy conflict: {key}")
                codes.append(obs["annotator_code"])
                labels.append(obs["main_label"])
                individual.append(obs)
            majority, count = Counter(labels).most_common(1)[0]
            if len(set(codes)) != 3 or count != int(row["human_majority_count"]) or majority != row["human_majority_label"]:
                raise ValueError(f"Invalid human assignment/majority: {key}")
            if json.loads(row["individual_labels_json"]) != labels or json.loads(row["annotator_codes_json"]) != codes:
                raise ValueError(f"Convenience JSON differs from the three annotations: {key}")
    counts = Counter(o["annotator_code"] for o in individual)
    if len(counts) != 19 or set(counts.values()) != {1575}:
        raise ValueError("Expected 19 annotators with 1,575 production ratings each")
    individual.sort(key=lambda r: (PARTITIONS.index(r["partition"]), int(r["task_instruction_id"]), int(r["annotation_copy"])))
    path = destination / "human/data/processed/individual/all_annotations.csv"
    write_csv(path, individual, schema["original_individual_columns"])
    majority_file = destination / "human/data/processed/aggregated/majority_labels.csv"
    write_majority(majority_file, aggregate(path))
    write_rationales(destination / "human/data/processed/aggregated/categorical_rationales.csv", concatenate(path, majority_file))
    model_keys = set()
    for p in PARTITIONS:
        output = []
        for row in read_csv(data_root / "llms" / f"{p}.csv"):
            key = (row["model"], row["item_id"])
            if key in model_keys or row["item_id"] not in item_lookup or row["partition"] != p:
                raise ValueError(f"Invalid or duplicate model/item key: {key}")
            model_keys.add(key)
            item = item_lookup[row["item_id"]]
            output.append(dict(task=p, model=row["model"], input=item["input"], meta=item["meta"],
                               task_instruction_id=item["task_instruction_id"], output=row["raw_output"],
                               rationale=row["raw_rationale"], main_rationale=row["raw_main_rationale"],
                               moral_rationale=row["raw_moral_rationale"]))
        write_csv(destination / "llm" / f"{p}.csv", output)
    if len(model_keys) != 89752:
        raise ValueError("LLM input coverage changed from the frozen package")
    return destination / "human", destination / "llm"


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    prepare(p.parse_args().out)
