#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


PARTITIONS = ("commonsense", "deontology", "justice", "utilitarianism", "virtue")
PARTITION_ORDER = {partition: position for position, partition in enumerate(PARTITIONS)}
SOURCE_FIELDS = (
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
    *SOURCE_FIELDS,
    "annotator_codes",
    "annotation_copies",
    "individual_labels",
    "individual_outputs",
    "vote_distribution",
    "majority_label",
    "majority_output",
    "majority_count",
    "vote_split",
    "unanimous",
)


class AggregationFailure(RuntimeError):
    pass


def compact_json(value: object, *, sort_keys: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=sort_keys,
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        *SOURCE_FIELDS,
        "annotator_code",
        "annotation_copy",
        "main_label",
        "output",
    }
    missing = sorted(required - set(rows[0] if rows else ()))
    if missing:
        raise AggregationFailure(f"Input CSV is missing columns: {missing}")
    return rows


def ordered_annotations(
    group_key: tuple[str, str], rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    try:
        ordered = sorted(rows, key=lambda row: int(row["annotation_copy"]))
        copies = [int(row["annotation_copy"]) for row in ordered]
    except ValueError as exc:
        raise AggregationFailure(f"{group_key}: non-integer annotation_copy") from exc
    if copies != [1, 2, 3]:
        raise AggregationFailure(f"{group_key}: expected annotation_copy [1,2,3], found {copies}")
    codes = [row["annotator_code"] for row in ordered]
    if len(set(codes)) != 3:
        raise AggregationFailure(f"{group_key}: annotators are not distinct: {codes}")
    return ordered


def aggregate(input_file: Path) -> list[dict[str, object]]:
    rows = read_rows(input_file)
    if len(rows) != 29_925:
        raise AggregationFailure(f"Expected 29,925 annotations, found {len(rows)}")

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        partition = row["partition"]
        if partition not in PARTITION_ORDER:
            raise AggregationFailure(f"Unknown partition: {partition!r}")
        groups[(partition, row["task_instruction_id"])].append(row)
    if len(groups) != 9_975:
        raise AggregationFailure(f"Expected 9,975 instruction groups, found {len(groups)}")

    result: list[dict[str, object]] = []
    for group_key, group_rows in groups.items():
        ordered = ordered_annotations(group_key, group_rows)
        first = ordered[0]
        for field in SOURCE_FIELDS:
            values = {row[field] for row in ordered}
            if len(values) != 1:
                raise AggregationFailure(f"{group_key}: inconsistent source field {field}")

        labels = [row["main_label"] for row in ordered]
        label_counts = Counter(labels)
        majority_label, majority_count = label_counts.most_common(1)[0]
        if majority_count < 2:
            raise AggregationFailure(f"{group_key}: no majority label in {labels}")
        majority_outputs = {
            row["output"] for row in ordered if row["main_label"] == majority_label
        }
        if len(majority_outputs) != 1:
            raise AggregationFailure(
                f"{group_key}: majority label maps to inconsistent outputs {majority_outputs}"
            )

        result.append(
            {
                **{field: first[field] for field in SOURCE_FIELDS},
                "annotator_codes": compact_json([row["annotator_code"] for row in ordered]),
                "annotation_copies": compact_json([1, 2, 3]),
                "individual_labels": compact_json(labels),
                "individual_outputs": compact_json([row["output"] for row in ordered]),
                "vote_distribution": compact_json(dict(label_counts), sort_keys=True),
                "majority_label": majority_label,
                "majority_output": next(iter(majority_outputs)),
                "majority_count": majority_count,
                "vote_split": "3-0" if majority_count == 3 else "2-1",
                "unanimous": "TRUE" if majority_count == 3 else "FALSE",
            }
        )

    def sort_key(row: dict[str, object]) -> tuple[int, int, int]:
        try:
            source_row = int(str(row["source_csv_row"]))
            instruction_id = int(str(row["task_instruction_id"]))
        except ValueError as exc:
            raise AggregationFailure("Non-integer source or instruction identifier") from exc
        return PARTITION_ORDER[str(row["partition"])], source_row, instruction_id

    result.sort(key=sort_key)
    per_partition = Counter(str(row["partition"]) for row in result)
    for partition in PARTITIONS:
        if per_partition[partition] != 1_995:
            raise AggregationFailure(
                f"{partition}: expected 1,995 aggregated rows, found {per_partition[partition]}"
            )
    return result


def write_csv_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    if path.exists():
        raise AggregationFailure(f"Refusing to overwrite existing output: {path}")
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
        description="Aggregate three annotations into one majority label per instruction."
    )
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = aggregate(args.input_file.resolve())
    output_file = args.output_file.resolve()
    write_csv_atomic(output_file, rows)
    unanimous = sum(row["unanimous"] == "TRUE" for row in rows)
    print(
        json.dumps(
            {
                "output_file": str(output_file),
                "aggregated_instructions": len(rows),
                "unanimous_3_0": unanimous,
                "majority_2_1": len(rows) - unanimous,
                "unresolved": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
