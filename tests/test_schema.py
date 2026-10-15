import json
import pytest
from ethics_analysis.schema import (parse_label, parse_categories, parse_free_text,
                                    metadata, text, PRINCIPLES, JUSTICE, UTILITY)

@pytest.mark.parametrize("partition,raw,expected", [
    ("commonsense", "MORALLY WRONG", 1),
    ("commonsense", "NOT_MORALLY_WRONG", 0),
    ("deontology", "NO, this is not a reasonable/justified excuse.", 0),
    ("justice", "YES; this is a reasonable action", 1),
    ("virtue", "NO-the scenario does not exhibit this virtue/vice", 0),
    ("utilitarianism", "B", 1),
])
def test_label_semantics(partition, raw, expected):
    r = parse_label(partition, raw)
    assert r.status == "valid" and r.value == expected

@pytest.mark.parametrize("raw", ["['A', 'B']", "['B', 'A']", "OTHER", "A or B"])
def test_ambiguous_or_invalid_final_label_not_forced(raw):
    assert parse_label("utilitarianism", raw).status == "invalid"

def test_justice_other_is_valid_rationale_but_invalid_judgment():
    assert parse_categories("other", JUSTICE, False).value == ("OTHER",)
    assert parse_label("justice", "OTHER").status == "invalid"

def test_commas_inside_utility_category_are_not_delimiters():
    raw = "Pleasure/pain, sensory (dis)comfort; Recognition, acknowledgment, appreciation"
    assert parse_categories(raw, UTILITY, True).value == (UTILITY[0], UTILITY[6])

def test_numbered_categories_are_audited_and_consistent():
    parsed = parse_categories('["3", "4"]', UTILITY, True)
    assert parsed.value == (UTILITY[2], UTILITY[3])
    assert "category_number_only" in parsed.changes
    assert parse_categories('["10: Other"]', UTILITY, True).value == (UTILITY[9],)
    assert parse_categories('["9: Other"]', UTILITY, True).status == "invalid"

def test_exact_category_definition_is_mechanical_not_fuzzy():
    assert parse_categories('["Respectfulness: One should treat people respectfully."]', PRINCIPLES, True).value == ("Respectfulness",)
    assert parse_categories('["Be nice"]', PRINCIPLES, True).status == "invalid"

def test_unknown_category_does_not_silently_drop():
    assert parse_categories('["Respectfulness", "unknown"]', PRINCIPLES, True).status == "invalid"

def test_category_duplicates_removed_without_inflating_counts():
    p = parse_categories('["Justice", "Justice"]', PRINCIPLES, True)
    assert p.value == ("Justice",) and "duplicate_category_removed" in p.changes

def test_multivalued_single_choice_invalid():
    assert parse_categories('["DESERVED", "PARTIAL"]', JUSTICE, False).status == "invalid"

def test_virtue_conditional_eligibility():
    assert parse_free_text("/", 0).status == "inapplicable"
    assert parse_free_text("/", 1).status == "missing"
    assert parse_free_text("<required sentence or />", 1).status == "invalid"
    assert parse_free_text("An explanation", None).status == "eligibility_unknown"

def test_literal_parser_never_executes(tmp_path):
    path = tmp_path / "MUST_NOT_EXIST"
    with pytest.raises((ValueError, SyntaxError)):
        metadata(f"__import__('pathlib').Path('{path}').touch()")
    assert not path.exists()
    assert metadata("{'id': 'justice:1'}")["id"] == "justice:1"

def test_only_formatting_changes_in_scenario_crosscheck():
    assert text("one\n two_x000D_ three") == "one two three"
    assert text("not wrong") != text("wrong")
