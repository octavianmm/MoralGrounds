import pytest

from ethics_analysis.io_utils import write_csv
from validate_results import validate_majority_rationale_overlap


def example_run(root):
    field = "commonsense_principles"
    keys = ["commonsense:1", "commonsense:2"]
    write_csv(root / "normalized/items.csv", [
        dict(item_id=keys[0], human_majority=1),
        dict(item_id=keys[1], human_majority=0),
    ])
    annotations = []
    choices = [[["A"], ["A", "B"], ["B"]], [["B"], ["B"], ["B"]]]
    labels = [[1, 1, 0], [1, 0, 0]]
    for i, key in enumerate(keys):
        for j in range(3):
            annotations.append(dict(
                item_id=key, actor_type="human", actor=f"human:{j}",
                label=labels[i][j], label_status="valid",
                structured_fields={field: dict(status="valid", value=choices[i][j])},
            ))
        annotations.append(dict(
            item_id=key, actor_type="llm", actor="model", label=1, label_status="valid",
            structured_fields={field: dict(status="valid", value=["A" if i == 0 else "B"])},
        ))
    write_csv(root / "normalized/annotations.csv", annotations)
    return [
        dict(model="model", field=field, scope="majority_aligned", n_items=2,
             n_human_comparisons=4, jaccard=.875, dice=11 / 12, exact_set=.75),
        dict(model="model", field=field, scope="same_judgment", n_items=1,
             n_human_comparisons=2, jaccard=.75, dice=5 / 6, exact_set=.5),
    ]


def test_independent_majority_overlap_validation(tmp_path):
    rows = example_run(tmp_path)
    write_csv(tmp_path / "llm_human_rationale_agreement.csv", rows)
    assert validate_majority_rationale_overlap(tmp_path) == 11


@pytest.mark.parametrize("field,value", [
    ("n_human_comparisons", 6),
    ("n_items", 1),
    ("jaccard", .75),
    ("scope", "paired_items"),
])
def test_independent_validator_rejects_unfiltered_or_corrupt_results(tmp_path, field, value):
    rows = example_run(tmp_path)
    rows[0][field] = value
    write_csv(tmp_path / "llm_human_rationale_agreement.csv", rows)
    with pytest.raises(ValueError):
        validate_majority_rationale_overlap(tmp_path)
