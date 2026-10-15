import numpy as np
import pytest
from ethics_analysis.metrics import (Bootstrap, confusion_counts, confusion_stats, cohen_nominal,
    entropy, holm, item_agreement, js_divergence, mcnemar_exact, nominal_table_stats,
    percentile_ci, reliability, set_scores, weighted_domain_bootstrap, wilson)
from ethics_analysis.judgments import aggregate_domain_rows


def test_item_pairwise_agreement_not_majority_fraction():
    assert item_agreement([[3,0]])[0] == 1
    assert item_agreement([[2,1]])[0] == pytest.approx(1/3)
    assert item_agreement([[1,1]])[0] == 0
    assert np.isnan(item_agreement([[1,0]])[0])

def test_missing_labels_excluded_per_pair():
    c = confusion_counts(np.array([0,1,-1,1]), np.array([0,-1,0,0]))
    assert c.tolist() == [1,0,1,0]
    assert confusion_stats(c)["agreement"] == .5

def test_cohen_and_classification_against_sklearn():
    sk = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(713)
    for _ in range(20):
        a, b = rng.integers(0,2,(2,400))
        s = confusion_stats(confusion_counts(a,b))
        assert s["kappa"] == pytest.approx(sk.cohen_kappa_score(a,b))
        assert s["mcc"] == pytest.approx(sk.matthews_corrcoef(a,b))
        assert s["balanced_accuracy"] == pytest.approx(sk.balanced_accuracy_score(a,b))
        assert s["macro_f1"] == pytest.approx(sk.f1_score(a,b,average="macro"))

def test_fleiss_against_statsmodels():
    sm = pytest.importorskip("statsmodels.stats.inter_rater")
    counts = np.array([[3,0],[2,1],[0,3],[1,2],[3,0]])
    assert reliability(counts,3)["fleiss_kappa"] == pytest.approx(sm.fleiss_kappa(counts))

def test_variable_rater_alpha_and_singleton_exclusion():
    # Coincidences [[2,1],[1,1]], N=5, Do=.4, De=.6.
    r = reliability([[2,0],[1,2],[0,1]],expected_raters=3)
    assert r["krippendorff_alpha"] == pytest.approx(1/3)
    assert r["n_ratings_alpha"] == 5
    assert r["n_complete_fleiss"] == 1
    assert r["fleiss_kappa"] == pytest.approx(-.5)

def test_degenerate_coefficients_are_undefined_not_zero():
    r = reliability([[3,0],[3,0]],3)
    assert r["pairwise_item_mean"] == 1
    assert np.isnan(r["fleiss_kappa"]) and np.isnan(r["krippendorff_alpha"])
    assert np.isnan(confusion_stats([5,0,0,0])["kappa"])

def test_empty_sets_do_not_manufacture_perfect_overlap():
    assert np.isnan(set_scores([],[])["jaccard"])
    s = set_scores(["a","b"],["b","c"])
    assert s["jaccard"] == pytest.approx(1/3)
    assert s["dice"] == .5 and s["exact_set"] == 0

def test_jensen_shannon_is_divergence_in_bits():
    assert js_divergence([1,0],[0,1]) == pytest.approx(1)
    assert js_divergence([.2,.8],[.2,.8]) == pytest.approx(0)
    assert entropy([.5,.5]) == pytest.approx(1)

def test_holm_preserves_order_and_monotone_adjustment():
    assert holm([.01,.04,.03]).tolist() == pytest.approx([.03,.06,.06])
    assert np.isnan(holm([np.nan])[0])

def test_mcnemar_uses_discordant_pairs_only():
    _,_,p=mcnemar_exact([1,1,1,1],[0,0,0,0])
    assert p == .125
    assert mcnemar_exact([1,0],[1,0])[2] == 1

def test_overall_kappa_not_artificially_pooled():
    a1=np.array([0]*9+[1]); b1=np.zeros(10,dtype=int)
    a2=1-a1; b2=1-b1
    rows=[confusion_stats(confusion_counts(a,b)) for a,b in [(a1,b1),(a2,b2)]]
    r=aggregate_domain_rows(rows)
    assert r["agreement"] == .9 and r["kappa"] == pytest.approx(0)
    pooled=confusion_stats(confusion_counts(np.r_[a1,a2],np.r_[b1,b2]))
    assert pooled["kappa"] == pytest.approx(.8)

def test_bootstrap_seed_and_shared_pairs():
    ids={"a": ["1","2","3","4"]}
    a=Bootstrap(ids,100,47); b=Bootstrap(ids,100,47)
    assert np.array_equal(a.weights["a"], b.weights["a"])
    assert np.all(a.weights["a"].sum(1)==4)
    x=np.array([0,1,0,1])
    s=a.confusion("a",x,x)
    assert np.all(s["agreement"]==1)

def test_cluster_bootstrap_keeps_related_items_together():
    b=Bootstrap({"p":["1","2","3"]},100,1,cluster_labels={"p":["x","x","y"]})
    assert np.array_equal(b.weights["p"][:,0],b.weights["p"][:,1])
    assert len(np.unique(b.weights["p"].sum(1)))>1

def test_nominal_weighted_contingencies():
    table=np.array([[2,.5,0],[.5,1,0],[0,0,1]])
    s=nominal_table_stats(table)
    assert s["agreement"] == pytest.approx(4/5)
    assert nominal_table_stats(np.stack([table,table]))["n"].tolist()==[5,5]

def test_wilson_respects_bounds():
    lo,hi=wilson(0,10); assert lo==0 and 0<hi<1
    lo,hi=wilson(10,10); assert 0<lo<1 and hi==1
    assert np.isnan(wilson(0,0)[0])

def test_undefined_bootstraps_counted():
    assert percentile_ci([np.nan, .2, .4])[2] == 2
    assert percentile_ci([])[2] == 0


def test_reliability_bootstrap_matches_manual_resampled_rows():
    from ethics_analysis.metrics import reliability_bootstrap
    counts=np.array([[3,0],[2,1],[0,2],[1,0],[0,3]])
    b=Bootstrap({'p':list('abcde')},20,98)
    result=reliability_bootstrap(b,'p',counts,3)
    for i in range(20):
        repeated=np.repeat(counts,b.weights['p'][i].astype(int),axis=0)
        manual=reliability(repeated,3)
        for field in ('pairwise_item_mean','fleiss_kappa','krippendorff_alpha'):
            assert result[field][i] == pytest.approx(manual[field],nan_ok=True)
