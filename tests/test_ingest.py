import csv
import os
from pathlib import Path
import zipfile
import pytest
from ethics_analysis.ingest import Audit, Source, infer_partition, load_data, make_observation, vote
from ethics_analysis.judgments import DataMatrices


def test_strict_majority_ties_and_single_vote():
    assert vote([0,1])["majority"] is None
    assert vote([1])["majority"] is None
    assert vote([1,1,0])["majority"] == 1

def test_semicolon_csv_and_safe_zip_paths(tmp_path):
    path=tmp_path/"data.zip"
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("../escape", "bad")
        z.writestr("inside/test.csv", 'Input;Output;task\n"a;b";YES;virtue\n')
    source=Source(str(path))
    assert "../escape" not in source.names
    assert source.csv("inside/test.csv")[0]["Input"] == "a;b"
    source.close()
    assert not (tmp_path.parent/"escape").exists()

def test_filename_resolves_crossed_virtue_not_fake_partition():
    assert infer_partition("gemma-2-27b-it_annotated_virtue.csv", {"meta":"{'subset':'crossed'}"}) == "virtue"
    with pytest.raises(ValueError):
        infer_partition("m_annotated_virtue.csv", {"task":"justice"})

def test_production_commonsense_includes_not_wrong_principles():
    audit=Audit()
    o=make_observation({"output":"NOT MORALLY WRONG","rationale":"Beneficence"},
                       "commonsense","commonsense:1","model","llm","test",2,audit)
    assert o["label"]==0 and o["fields"]["commonsense_principles"]["status"]=="valid"

def test_deontology_structural_missing_is_not_failure():
    audit=Audit()
    o=make_observation({"output":"NO","main_rationale":"IRRELEVANT","moral_rationale":"[]"},
                       "deontology","deontology:1","model","llm","test",2,audit)
    assert o["fields"]["deontology_principles"]["status"]=="inapplicable"

@pytest.fixture(scope="session")
def supplied(tmp_path_factory):
    a,b=os.environ.get("ETHICS_A"),os.environ.get("ETHICS_B")
    if not a or not b:
        from scripts.prepare_inputs import prepare
        a,b=prepare(tmp_path_factory.mktemp("packaged_inputs"))
    return load_data(a,b)

def test_supplied_archive_counts_and_reconciliation(supplied):
    items,h,l,m,g,a=supplied
    assert len(items)==9975 and len(h)==29925 and len(m)==9
    assert len({o['actor'] for o in h})==19
    assert a.summary["human_majorities_reconciled"]==9975
    assert a.summary["human_rationale_aggregates_reconciled"]==9975
    assert a.summary["human_rationale_selection"] == "majority_aligned"
    assert a.summary["human_rationale_annotations_retained"] == 28129
    assert a.summary["n_missing_llm_rows"]==23
    assert a.summary["llm_label_status"]=={"valid":89723,"missing":2,"invalid":27}

def test_supplied_joins_and_common_panel(supplied):
    items,h,l,m,g,a=supplied
    assert len({(o['actor'],o['item_id']) for o in l})==len(l)
    data=DataMatrices(items,h,l,m)
    assert sum((data.M[p]>=0).all(1).sum() for p in data.ids)==9923
    assert sum(i['human_unanimous'] for i in items.values())==8179
    assert len({i['task_instruction_id'] for i in items.values()}) < len(items)

def test_supplied_final_label_counts_are_not_rationale_counts(supplied):
    items,h,l,m,g,a=supplied
    bad=[o for o in l if o['partition']=='justice' and o['raw_label']=='OTHER']
    assert len(bad)==1 and bad[0]['label'] is None
    assert bad[0]['fields']['justice_rationale']['status']=='valid'
