#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path


KEY_FIELDS = (
    "partition",
    "task",
    "meta",
    "input",
    "instruction_id",
    "task_instruction_id",
    "source_split",
    "source_position_within_task",
    "source_csv_row",
)
OUTPUT_FIELDS = (
    *KEY_FIELDS,
    "annotator_codes",
    "annotation_copies",
    "rationale_selection",
    "rationale_annotator_codes",
    "rationale_annotation_copies",
    "rationale_count",
    "rationale_mode",
    "primary_rationale_field",
    "categorical_rationales",
    "secondary_rationale_field",
    "secondary_categorical_rationales",
    "free_text_rationale_field",
    "free_text_rationales",
)


class RationaleFailure(RuntimeError):
    pass


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_categories(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def ordered_annotations(
    key: tuple[str, str], rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    try:
        ordered = sorted(rows, key=lambda row: int(row["annotation_copy"]))
        copies = [int(row["annotation_copy"]) for row in ordered]
    except ValueError as exc:
        raise RationaleFailure(f"{key}: non-integer annotation_copy") from exc
    if copies != [1, 2, 3]:
        raise RationaleFailure(f"{key}: expected annotation_copy [1,2,3], found {copies}")
    if len({row["annotator_code"] for row in ordered}) != 3:
        raise RationaleFailure(f"{key}: expected three distinct annotators")
    return ordered


def categorical_structure(
    partition: str, rows: list[dict[str, str]]
) -> dict[str, object]:
    empty = [[] for _ in rows]
    if partition == "commonsense":
        return {
            "rationale_mode": "categorical_multiselect",
            "primary_rationale_field": "rationale",
            "categorical_rationales": [split_categories(row["rationale"]) for row in rows],
            "secondary_rationale_field": "",
            "secondary_categorical_rationales": empty,
            "free_text_rationale_field": "",
            "free_text_rationales": [],
        }
    if partition == "deontology":
        return {
            "rationale_mode": "hierarchical_categorical",
            "primary_rationale_field": "main_rationale",
            "categorical_rationales": [[row["main_rationale"]] for row in rows],
            "secondary_rationale_field": "moral_rationale",
            "secondary_categorical_rationales": [
                split_categories(row["moral_rationale"]) for row in rows
            ],
            "free_text_rationale_field": "",
            "free_text_rationales": [],
        }
    if partition == "justice":
        return {
            "rationale_mode": "categorical_single",
            "primary_rationale_field": "rationale",
            "categorical_rationales": [[row["rationale"]] for row in rows],
            "secondary_rationale_field": "",
            "secondary_categorical_rationales": empty,
            "free_text_rationale_field": "",
            "free_text_rationales": [],
        }
    if partition == "utilitarianism":
        return {
            "rationale_mode": "categorical_multiselect",
            "primary_rationale_field": "rationale",
            "categorical_rationales": [split_categories(row["rationale"]) for row in rows],
            "secondary_rationale_field": "",
            "secondary_categorical_rationales": empty,
            "free_text_rationale_field": "",
            "free_text_rationales": [],
        }
    if partition == "virtue":
        return {
            "rationale_mode": "free_text",
            "primary_rationale_field": "",
            "categorical_rationales": empty,
            "secondary_rationale_field": "",
            "secondary_categorical_rationales": empty,
            "free_text_rationale_field": "rationale",
            "free_text_rationales": [row["rationale"] for row in rows],
        }
    raise RationaleFailure(f"Unknown partition: {partition!r}")


def concatenate(
    input_file: Path, majority_file: Path
) -> list[dict[str, object]]:
    annotations = read_rows(input_file)
    majority_rows = read_rows(majority_file)
    if len(annotations) != 29_925:
        raise RationaleFailure(f"Expected 29,925 annotations, found {len(annotations)}")
    if len(majority_rows) != 9_975:
        raise RationaleFailure(f"Expected 9,975 majority rows, found {len(majority_rows)}")

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in annotations:
        groups[(row["partition"], row["task_instruction_id"])].append(row)
    if len(groups) != 9_975:
        raise RationaleFailure(f"Expected 9,975 instruction groups, found {len(groups)}")

    seen: set[tuple[str, str]] = set()
    result: list[dict[str, object]] = []
    for majority in majority_rows:
        key = (majority["partition"], majority["task_instruction_id"])
        if key in seen:
            raise RationaleFailure(f"Duplicate majority row: {key}")
        seen.add(key)
        if key not in groups:
            raise RationaleFailure(f"Majority row has no annotation group: {key}")
        ordered = ordered_annotations(key, groups[key])
        codes = [row["annotator_code"] for row in ordered]
        try:
            majority_codes = json.loads(majority["annotator_codes"])
        except json.JSONDecodeError as exc:
            raise RationaleFailure(f"{key}: invalid annotator_codes JSON") from exc
        if majority_codes != codes:
            raise RationaleFailure(f"{key}: annotator order differs from majority output")
        for field in KEY_FIELDS:
            if majority[field] != ordered[0][field]:
                raise RationaleFailure(f"{key}: majority metadata field {field} differs")
            if len({row[field] for row in ordered}) != 1:
                raise RationaleFailure(f"{key}: annotation metadata field {field} differs")

        selected = [row for row in ordered if row["main_label"] == majority["majority_label"]]
        if len(selected) not in (2, 3) or len(selected) != int(majority["majority_count"]):
            raise RationaleFailure(f"{key}: majority label/count disagrees with source annotations")
        structure = categorical_structure(majority["partition"], selected)
        result.append(
            {
                **{field: majority[field] for field in KEY_FIELDS},
                "annotator_codes": compact_json(codes),
                "annotation_copies": compact_json([1, 2, 3]),
                "rationale_selection": "majority_aligned",
                "rationale_annotator_codes": compact_json([row["annotator_code"] for row in selected]),
                "rationale_annotation_copies": compact_json([int(row["annotation_copy"]) for row in selected]),
                "rationale_count": len(selected),
                "rationale_mode": structure["rationale_mode"],
                "primary_rationale_field": structure["primary_rationale_field"],
                "categorical_rationales": compact_json(structure["categorical_rationales"]),
                "secondary_rationale_field": structure["secondary_rationale_field"],
                "secondary_categorical_rationales": compact_json(
                    structure["secondary_categorical_rationales"]
                ),
                "free_text_rationale_field": structure["free_text_rationale_field"],
                "free_text_rationales": compact_json(structure["free_text_rationales"]),
            }
        )
    if seen != set(groups):
        raise RationaleFailure("Some annotation groups are absent from the majority file")
    return result


def write_csv_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    if path.exists():
        raise RationaleFailure(f"Refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Concatenate only rationale choices supporting each instruction's majority label."
    )
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--majority-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = concatenate(args.input_file.resolve(), args.majority_file.resolve())
    output_file = args.output_file.resolve()
    write_csv_atomic(output_file, rows)
    print(
        json.dumps(
            {
                "output_file": str(output_file),
                "instructions_with_rationale_records": len(rows),
                "categorical_instructions": sum(
                    row["rationale_mode"] != "free_text" for row in rows
                ),
                "free_text_instructions": sum(
                    row["rationale_mode"] == "free_text" for row in rows
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
