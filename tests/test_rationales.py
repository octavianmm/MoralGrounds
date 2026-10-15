import numpy as np
import pytest
from ethics_analysis.rationales import distribution_features, distribution_stats, item_overlap


def test_mention_shares_and_prevalence_have_distinct_denominators():
    # Human selects both categories; model selects one. Prevalence sums 2 vs 1.
    h=np.array([[[1.,1.]]]); hv=np.array([[True]]); m=np.array([[1.,0.]])
    f=distribution_features(h,hv,m,np.array([True]),"item_balanced")
    s=distribution_stats(f.sum(0),2)
    assert s['human_prevalence'].sum()==2
    assert s['human_share'].sum()==1
    assert s['tv']==.5

def test_item_balance_does_not_weight_three_humans_more_than_one():
    h=np.array([[[1.,0.],[1.,0.],[1.,0.]],[[0.,1.],[0.,0.],[0.,0.]]])
    hv=np.array([[True,True,True],[True,False,False]])
    m=np.array([[1.,0.],[0.,1.]])
    balanced=distribution_stats(distribution_features(h,hv,m,np.array([True,True]),"item_balanced").sum(0),2)
    pooled=distribution_stats(distribution_features(h,hv,m,np.array([True,True]),"annotation_pooled").sum(0),2)
    assert balanced['tv']==0 and pooled['tv']==.25

def test_overlap_macroaverages_people_within_items():
    h=np.array([[[1.,0.],[0.,1.]],[[1.,1.],[0.,0.]]])
    hv=np.array([[True,True],[True,False]])
    m=np.array([[1.,0.],[1.,0.]])
    scores=item_overlap(h,hv,m,np.array([True,True]))
    assert scores['jaccard'].tolist()==pytest.approx([.5,.5])
    assert scores['n_humans'].tolist()==[2,1]

def test_distribution_comparison_excludes_nonpaired_items():
    h=np.array([[[1.,0.]],[[0.,1.]]]); hv=np.ones((2,1),bool)
    m=np.array([[1.,0.],[1.,0.]])
    f=distribution_features(h,hv,m,np.array([True,False]),"item_balanced")
    assert distribution_stats(f.sum(0),2)['tv']==0
