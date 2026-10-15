"""Small, independently tested statistics with explicit missing-data semantics."""
from __future__ import annotations

import hashlib
import math
from typing import Optional
import numpy as np
from scipy.stats import binomtest, norm

NAN = float("nan")


def divide(a, b):
    a, b = np.broadcast_arrays(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    return np.divide(a, b, out=np.full(a.shape, np.nan), where=b != 0)


def mean_finite(a, axis=None):
    a = np.asarray(a, dtype=float)
    valid = np.isfinite(a)
    return divide(np.where(valid, a, 0).sum(axis=axis), valid.sum(axis=axis))


def confusion_counts(a, b, mask=None):
    a, b = np.asarray(a), np.asarray(b)
    valid = (a >= 0) & (b >= 0)
    if mask is not None:
        valid &= np.asarray(mask, dtype=bool)
    return np.bincount(2 * a[valid].astype(int) + b[valid].astype(int), minlength=4)


def confusion_stats(counts):
    """Binary reference-by-prediction table in [00,01,10,11] order; vectorized."""
    c = np.asarray(counts, dtype=float)
    a, b, c10, d = (c[..., i] for i in range(4))
    n = c.sum(axis=-1)
    accuracy = divide(a + d, n)
    pe = divide((a + b) * (a + c10) + (c10 + d) * (b + d), n * n)
    kappa = divide(accuracy - pe, 1 - pe)
    sensitivity = divide(d, c10 + d)
    specificity = divide(a, a + b)
    balanced = mean_finite(np.stack([specificity, sensitivity], axis=-1), axis=-1)
    f0, f1 = divide(2 * a, 2 * a + b + c10), divide(2 * d, 2 * d + b + c10)
    f1macro = mean_finite(np.stack([f0, f1], axis=-1), axis=-1)
    mcc = divide(a * d - b * c10, np.sqrt((a + b) * (a + c10) * (c10 + d) * (b + d)))
    return {"n": n, "agreement": accuracy, "kappa": kappa, "balanced_accuracy": balanced,
            "macro_f1": f1macro, "mcc": mcc, "reference_positive_rate": divide(c10 + d, n),
            "predicted_positive_rate": divide(b + d, n)}


def cohen_nominal(a, b, k):
    a, b = np.asarray(a, dtype=int), np.asarray(b, dtype=int)
    valid = (a >= 0) & (b >= 0)
    n = int(valid.sum())
    if not n:
        return dict(n=0, agreement=NAN, kappa=NAN)
    count = np.bincount(k * a[valid] + b[valid], minlength=k * k).reshape(k, k)
    agreement = np.trace(count) / n
    pe = np.dot(count.sum(0), count.sum(1)) / n ** 2
    return dict(n=n, agreement=float(agreement), kappa=float(divide(agreement - pe, 1 - pe)))


def item_agreement(counts):
    counts = np.asarray(counts, dtype=float)
    n = counts.sum(axis=-1)
    return divide((counts * (counts - 1)).sum(axis=-1), n * (n - 1))


def entropy(prob, base=2):
    p = np.asarray(prob, dtype=float)
    out = np.zeros_like(p)
    np.log(p, out=out, where=p > 0)
    return -(p * out).sum(axis=-1) / math.log(base)


def reliability(counts, expected_raters=None):
    """Available-case nominal alpha; Fleiss only on fixed-size complete rows.

    Singleton items contribute to neither alpha's coincidences nor its marginals.
    Undefined degenerate coefficients are NaN, not zero or perfect agreement.
    """
    c = np.asarray(counts, dtype=float)
    n = c.sum(1)
    valid = n >= 2
    cv, nv = c[valid], n[valid]
    raw = item_agreement(cv)
    pair_num = (cv * (cv - 1)).sum()
    pair_den = (nv * (nv - 1)).sum()
    total = nv.sum()
    if total > 1:
        observed_disagreement = ((nv * nv - (cv * cv).sum(1)) / (nv - 1)).sum() / total
        category_total = cv.sum(0)
        expected_disagreement = (total * total - np.dot(category_total, category_total)) / (total * (total - 1))
        alpha = 1 - float(divide(observed_disagreement, expected_disagreement))
    else:
        alpha = NAN
    if expected_raters is None:
        unique = np.unique(nv)
        expected_raters = int(unique[0]) if len(unique) == 1 else None
    complete = (n == expected_raters) & (n >= 2) if expected_raters else np.zeros(len(n), bool)
    cc = c[complete]
    if len(cc):
        pbar = float(np.mean(item_agreement(cc)))
        marginal = cc.sum(0) / cc.sum()
        pe = np.dot(marginal, marginal)
        fleiss = float(divide(pbar - pe, 1 - pe))
    else:
        fleiss = NAN
    return dict(n_items_at_least_two=int(valid.sum()), n_ratings_alpha=int(total),
                pairwise_item_mean=float(mean_finite(raw)),
                pairwise_pair_weighted=float(divide(pair_num, pair_den)),
                krippendorff_alpha=alpha, n_complete_fleiss=int(complete.sum()),
                fleiss_kappa=fleiss, fleiss_expected_raters=expected_raters)


def wilson(matches, n, confidence=.95):
    if n <= 0:
        return NAN, NAN
    z = norm.ppf(.5 + confidence / 2)
    p = matches / n
    divisor = 1 + z * z / n
    center = (p + z * z / (2 * n)) / divisor
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / divisor
    return (0.0 if matches == 0 else max(0, center - radius)), (1.0 if matches == n else min(1, center + radius))


def percentile_ci(samples):
    s = np.asarray(samples, dtype=float)
    s = s[np.isfinite(s)]
    if not len(s):
        return NAN, NAN, 0
    lo, hi = np.quantile(s, [.025, .975])
    return float(lo), float(hi), len(s)


def holm(pvalues):
    p = np.asarray(pvalues, dtype=float)
    result = np.full_like(p, np.nan)
    valid = np.flatnonzero(np.isfinite(p))
    order = valid[np.argsort(p[valid], kind="stable")]
    if len(order):
        adjusted = np.maximum.accumulate((len(order) - np.arange(len(order))) * p[order])
        result[order] = np.minimum(1, adjusted)
    return result


def mcnemar_exact(a_correct, b_correct):
    a, b = np.asarray(a_correct, bool), np.asarray(b_correct, bool)
    a_only, b_only = int((a & ~b).sum()), int((~a & b).sum())
    p = binomtest(a_only, a_only + b_only, .5).pvalue if a_only + b_only else 1.0
    return a_only, b_only, float(p)


def js_divergence(p, q):
    """Jensen-Shannon divergence in bits, not its square-root distance."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    m = (p + q) / 2
    # Entropy identity handles zeros without pseudocounts.
    return np.maximum(0, entropy(m) - .5 * entropy(p) - .5 * entropy(q))


def set_scores(a, b):
    a, b = set(a), set(b)
    union = len(a | b)
    if not union:
        return {"exact_set": NAN, "jaccard": NAN, "dice": NAN}
    intersection = len(a & b)
    return dict(exact_set=float(a == b), jaccard=intersection / union,
                dice=2 * intersection / (len(a) + len(b)))


class Bootstrap:
    """Shared item resamples within partitions, preserving human/model pairing.

    Weights are multinomial draws of the original number of items. The same row
    of weights is used for every model, rationale, and human observation on an
    item. Human raters themselves are not resampled. Seed depends only on the
    partition name and master seed, not Python's randomized hash or model order.
    """
    def __init__(self, partition_ids, n_resamples=2000, seed=20260917, cluster_labels=None):
        self.n_resamples = n_resamples
        self.clustered = cluster_labels is not None
        self.weights = {}
        for p, ids in partition_ids.items():
            n = len(ids)
            if not n:
                self.weights[p] = np.empty((n_resamples, 0), dtype=np.float64)
                continue
            if cluster_labels is not None:
                labels = cluster_labels[p]
                if len(labels) != n:
                    raise ValueError("Cluster labels must align one-to-one with item IDs")
                units, inverse = np.unique(np.asarray(labels, dtype=str), return_inverse=True)
                n_units = len(units)
            else:
                n_units, inverse = n, np.arange(n)
            digest = int.from_bytes(hashlib.sha256(p.encode()).digest()[:4], "little")
            rng = np.random.default_rng(np.random.SeedSequence([seed, digest]))
            w = np.empty((n_resamples, n), dtype=np.float64)
            for start in range(0, n_resamples, 128):
                stop = min(n_resamples, start + 128)
                w[start:stop] = rng.multinomial(n_units, np.full(n_units, 1 / n_units), size=stop - start)[:, inverse]
            self.weights[p] = w

    def sums(self, partition, values):
        return self.weights[partition] @ np.asarray(values, np.float64)

    def means(self, partition, values):
        x = np.asarray(values, dtype=float)
        good = np.isfinite(x)
        return divide(self.sums(partition, np.where(good, x, 0)), self.sums(partition, good.astype(float)))

    def confusion(self, partition, a, b, mask=None):
        a, b = np.asarray(a), np.asarray(b)
        valid = (a >= 0) & (b >= 0)
        if mask is not None:
            valid &= mask
        features = np.zeros((len(a), 4), dtype=np.float64)
        features[np.flatnonzero(valid), (2 * a[valid] + b[valid]).astype(int)] = 1
        return confusion_stats(self.sums(partition, features))


def weighted_domain_bootstrap(stats, metric):
    """Each resample recomputes domain weights from its valid paired denominators."""
    values = np.stack([s[metric] for s in stats])
    weights = np.stack([s["n"] for s in stats])
    valid = np.isfinite(values) & (weights > 0)
    return divide(np.where(valid, values * weights, 0).sum(0), np.where(valid, weights, 0).sum(0))


def nominal_table_stats(tables):
    """Nominal weighted contingency matrices, shape (..., K, K)."""
    t = np.asarray(tables, dtype=float)
    n = t.sum(axis=(-2, -1))
    agreement = divide(np.trace(t, axis1=-2, axis2=-1), n)
    pe = divide((t.sum(-2) * t.sum(-1)).sum(-1), n * n)
    return dict(n=n, agreement=agreement, kappa=divide(agreement - pe, 1 - pe))


def reliability_bootstrap(bootstrap, partition, counts, expected_raters):
    """Vectorized bootstrap of both chance and observed multirater agreement."""
    c = np.asarray(counts, float)
    n = c.sum(1)
    valid = n >= 2
    complete = valid & (n == expected_raters)
    raw = item_agreement(c)
    features = np.column_stack([
        valid.astype(float), np.where(valid, raw, 0),
        np.where(valid, n, 0),
        np.where(valid, divide(n*n-(c*c).sum(1), n-1), 0),
        complete.astype(float), np.where(complete, raw, 0),
        c * valid[:, None], c * complete[:, None],
    ])
    totals = bootstrap.sums(partition, features)
    k = c.shape[1]
    nitems, nratings = totals[:,0], totals[:,2]
    avcounts, fullcounts = totals[:,6:6+k], totals[:,6+k:6+2*k]
    do = divide(totals[:,3], nratings)
    de = divide(nratings*nratings - (avcounts*avcounts).sum(1), nratings*(nratings-1))
    fullp = divide(fullcounts, fullcounts.sum(1)[:,None])
    pe = (fullp*fullp).sum(1)
    pbar = divide(totals[:,5], totals[:,4])
    return dict(n=nitems, n_complete=totals[:,4], pairwise_item_mean=divide(totals[:,1],nitems),
                krippendorff_alpha=1-divide(do,de), fleiss_kappa=divide(pbar-pe,1-pe))
