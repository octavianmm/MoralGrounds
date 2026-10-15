from types import SimpleNamespace

import numpy as np
import pytest

import compute_requested_agreement as requested
from ethics_analysis.metrics import Bootstrap
from ethics_analysis.schema import FIELDS


def fixture_data(partition, field, human_sets, model_sets):
    actors = ["human:a", "human:b", "human:c"]
    ids = [f"{partition}:1", f"{partition}:2"]
    data = SimpleNamespace(
        ids={partition: ids},
        positions={partition: {key: i for i, key in enumerate(ids)}},
        human_actors=actors, models=["model"], model_index={"model": 0},
        H={partition: np.array([[1, 1, 0], [1, 0, 0]])},
        M={partition: np.array([[1], [1]])},
        Y={partition: np.array([1, 0])},
    )

    def observation(key, actor, actor_type, value):
        return dict(item_id=key, partition=partition, actor=actor,
                    actor_type=actor_type, fields={field: {
                        "status": "valid" if value else "missing", "value": value,
                    }})

    humans = [observation(key, actor, "human", human_sets[i][j])
              for i, key in enumerate(ids) for j, actor in enumerate(actors)]
    llms = [observation(key, "model", "llm", model_sets[i])
            for i, key in enumerate(ids)]
    return data, humans, llms


def test_partial_overlap_item_weight_and_matching_judgment(monkeypatch):
    field = "commonsense_principles"
    monkeypatch.setattr(requested, "FIELDS", {field: FIELDS[field]})
    a, b = "Veracity", "Justice"
    data, humans, llms = fixture_data("commonsense", field,
        [[[a], [a, b], [b]], [[a], [b], None]], [[a], [b]])
    rows, item_rows = requested.categorical_agreement(
        data, humans, llms, Bootstrap(data.ids, 20, 42))
    primary, conditional = rows
    # Majority-only: item 1 scores (1 + 1/2)/2; item 2 scores 1.
    assert primary["scope"] == "majority_aligned"
    assert primary["jaccard"] == pytest.approx(.875)
    assert primary["exact_set"] == pytest.approx(.75)
    assert primary["n_items"] == 2
    assert primary["n_human_comparisons"] == 3
    # Only item 1 matches the majority; its two same-label humans contribute.
    assert conditional["jaccard"] == pytest.approx(.75)
    assert conditional["exact_set"] == pytest.approx(.5)
    assert conditional["n_items"] == 1
    assert conditional["n_human_comparisons"] == 2
    assert len(item_rows) == 3


def test_missing_model_set_is_excluded(monkeypatch):
    field = "commonsense_principles"
    monkeypatch.setattr(requested, "FIELDS", {field: FIELDS[field]})
    a, b = "Veracity", "Justice"
    data, humans, llms = fixture_data("commonsense", field,
        [[[a], [a, b], [b]], [None, None, None]], [[a], None])
    rows, _ = requested.categorical_agreement(
        data, humans, llms, Bootstrap(data.ids, 20, 42))
    assert rows[0]["n_items"] == 1
    assert rows[0]["jaccard"] == pytest.approx(.75)
    assert rows[0]["exact_set"] == pytest.approx(.5)


def test_single_choice_overlap_equals_exact_category_agreement(monkeypatch):
    field = "justice_rationale"
    monkeypatch.setattr(requested, "FIELDS", {field: FIELDS[field]})
    a, b, c = "DESERVED", "NOT DESERVED", "PARTIAL"
    data, humans, llms = fixture_data("justice", field,
        [[[a], [a], [c]], [[b], [b], [b]]], [[a], [c]])
    rows, _ = requested.categorical_agreement(
        data, humans, llms, Bootstrap(data.ids, 20, 42))
    assert rows[0]["jaccard"] == pytest.approx(.5)
    assert rows[0]["jaccard"] == rows[0]["exact_set"] == rows[0]["dice"]
    assert np.isfinite(rows[0]["single_choice_kappa"])


def test_dissenting_only_rationale_does_not_create_reference(monkeypatch):
    field = "commonsense_principles"
    monkeypatch.setattr(requested, "FIELDS", {field: FIELDS[field]})
    a = "Veracity"
    data, humans, llms = fixture_data("commonsense", field,
        [[None, None, [a]], [[a], None, None]], [[a], [a]])
    rows, items = requested.categorical_agreement(
        data, humans, llms, Bootstrap(data.ids, 20, 42))
    assert all(r["n_items"] == r["n_human_comparisons"] == 0 for r in rows)
    assert all(np.isnan(r["jaccard"]) for r in rows)
    assert items == []


def test_unanimous_items_keep_three_rationales(monkeypatch):
    field = "commonsense_principles"
    monkeypatch.setattr(requested, "FIELDS", {field: FIELDS[field]})
    a, b = "Veracity", "Justice"
    data, humans, llms = fixture_data("commonsense", field,
        [[[a], [a, b], [b]], [[b], [b], [b]]], [[a], [b]])
    data.H["commonsense"] = np.array([[1, 1, 1], [0, 0, 0]])
    rows, _ = requested.categorical_agreement(
        data, humans, llms, Bootstrap(data.ids, 20, 42))
    assert rows[0]["jaccard"] == pytest.approx(.75)
    assert rows[0]["n_human_comparisons"] == 6
    assert rows[1]["n_human_comparisons"] == 3
