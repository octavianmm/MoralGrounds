import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_inputs import prepare, read_csv, write_csv
from build_collaborator_report import opposition_tier, selection_key


def case(**overrides):
    row = dict(human_unanimous=True, n_valid_models=9, n_opposing_models=9,
               n_valid_frontier=3, n_opposing_frontier=3, human_ambiguity_votes=0,
               human_cultural_flag_votes=0, input="A short scenario.", task_instruction_id="1")
    row.update(overrides)
    row["selection_tier"] = opposition_tier(row)
    return row


def test_opposition_requires_unanimous_humans():
    assert opposition_tier(case(human_unanimous=False)) is None


def test_complete_nine_unanimity_is_strongest():
    assert opposition_tier(case()) == 1
    assert opposition_tier(case(n_opposing_models=8)) == 2


def test_missing_models_never_count_as_nine_votes():
    assert opposition_tier(case(n_valid_models=8, n_opposing_models=8)) == 3
    assert opposition_tier(case(n_valid_models=8, n_opposing_models=8, n_opposing_frontier=2)) == 4


def test_insufficient_valid_models_not_most_panel():
    assert opposition_tier(case(n_valid_models=6, n_opposing_models=6, n_opposing_frontier=2)) is None


def test_numeric_id_tie_break():
    assert selection_key(case(task_instruction_id="2")) < selection_key(case(task_instruction_id="10"))


def test_slots_preserve_minority_annotation():
    rows = read_csv(ROOT / "data/humans/commonsense.csv")
    row = next(r for r in rows if r["human_majority_count"] == "2")
    labels = [row[f"annotator_{i}_main_label"] for i in (1,2,3)]
    assert len(set(labels)) == 2
    assert sum(v != row["human_majority_label"] for v in labels) == 1
    assert len(json.loads(row["all_primary_rationale_sets_json"])) == 3
    assert len(json.loads(row["majority_aligned_copies_json"])) == 2


def test_roundtrip_rebuilds_all_normalized_records(tmp_path):
    human, llm = prepare(tmp_path)
    rows = read_csv(human / "data/processed/individual/all_annotations.csv")
    assert len(rows) == 29925
    assert len(read_csv(human / "data/processed/aggregated/majority_labels.csv")) == 9975
    assert sum(len(read_csv(p)) for p in llm.glob("*.csv")) == 89752


def test_corrupted_majority_rejected(tmp_path):
    source = ROOT / "data/humans/commonsense.csv"
    rows = read_csv(source)
    rows[0]["human_majority_count"] = "1"
    write_csv(tmp_path / "data/humans/commonsense.csv", rows)
    with pytest.raises(ValueError, match="assignment/majority"):
        prepare(tmp_path / "out", tmp_path / "data")


def test_duplicate_annotator_rejected(tmp_path):
    rows = read_csv(ROOT / "data/humans/commonsense.csv")
    rows[0]["annotator_2_annotator_code"] = rows[0]["annotator_1_annotator_code"]
    write_csv(tmp_path / "data/humans/commonsense.csv", rows)
    with pytest.raises(ValueError, match="assignment/majority"):
        prepare(tmp_path / "out", tmp_path / "data")
