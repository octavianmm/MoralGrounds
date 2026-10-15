"""Structured ethical-attention distributions and active-set overlap.

Production fields: commonsense principles (both judgments), hierarchical
 deontology, justice categories, NEW structured utility categories, virtue text.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import re
import numpy as np

from .schema import FIELDS, LABELS, PARTITIONS, text
from .metrics import (NAN, cohen_nominal, confusion_stats, divide, entropy,
                      js_divergence, mean_finite, percentile_ci, reliability, nominal_table_stats)
from .io_utils import write_csv
from .judgments import ci_columns


class FieldMatrices:
    def __init__(self, field, data, humans, llms):
        self.field = field
        self.spec = FIELDS[field]
        self.partition = self.spec.partition
        n, k = len(data.ids[self.partition]), len(self.spec.categories)
        nh, nm = len(data.human_actors), len(data.models)
        self.H = np.zeros((n, nh, k), dtype=np.float32)
        self.M = np.zeros((n, nm, k), dtype=np.float32)
        self.Hvalid = np.zeros((n, nh), bool)
        self.Mvalid = np.zeros((n, nm), bool)
        catindex = {v: i for i, v in enumerate(self.spec.categories)}
        hi = {a: j for j, a in enumerate(data.human_actors)}
        for o in humans + llms:
            if o["partition"] != self.partition:
                continue
            result = o["fields"].get(field)
            if not result or result["status"] != "valid":
                continue
            i = data.positions[self.partition][o["item_id"]]
            is_human = o["actor_type"] == "human"
            j = hi[o["actor"]] if is_human else data.model_index[o["actor"]]
            matrix = self.H if is_human else self.M
            valid = self.Hvalid if is_human else self.Mvalid
            matrix[i, j, [catindex[c] for c in result["value"]]] = 1
            valid[i, j] = True


def field_quality(humans, llms, data, out):
    observations = defaultdict(list)
    for o in humans + llms:
        actor = "humans" if o["actor_type"] == "human" else o["actor"]
        for field, result in o["fields"].items():
            observations[actor, field].append(result)
    rows = []
    for (actor, field), results in observations.items():
        counts = Counter(r["status"] for r in results)
        n_eligible = sum(counts[s] for s in ("valid", "missing", "invalid"))
        p = "virtue" if field == "virtue_text" else FIELDS[field].partition
        expected = len(data.ids[p]) * (3 if actor == "humans" else 1)
        row = dict(actor=actor, partition=p, field=field, n_expected_slots=expected,
                   n_present=len(results), n_absent_rows=expected - len(results),
                   n_eligible=n_eligible, n_valid=counts["valid"],
                   n_missing=counts["missing"], n_invalid=counts["invalid"],
                   n_inapplicable=counts["inapplicable"],
                   n_extra_inapplicable=sum(r["status"] == "inapplicable" and text(r["raw"]) not in ("", "/", "[]", "null", "None") for r in results),
                   n_eligibility_unknown=counts["eligibility_unknown"],
                   eligible_completion_rate=float(divide(counts["valid"], n_eligible)))
        if field in FIELDS:
            cards = [len(r["value"]) for r in results if r["status"] == "valid"]
            row.update(mean_selected_categories=float(mean_finite(cards)),
                       n_selects_all_categories=sum(v == len(FIELDS[field].categories) for v in cards),
                       all_categories_rate=float(mean_finite(np.array(cards) == len(FIELDS[field].categories))))
        rows.append(row)
    write_csv(out / "field_quality.csv", rows)
    return rows


def all_available_profiles(fm, data, outrows):
    h, hv = human_reference(fm, data, 0, "majority_aligned")
    actors = [("humans", h, hv)] + [
        (m, fm.M[:, j:j+1, :], fm.Mvalid[:, j:j+1]) for j, m in enumerate(data.models)]
    for actor, x, valid in actors:
        counts = x.sum(axis=(0, 1))
        n = int(valid.sum())
        shares = divide(counts, counts.sum())
        prevalence = divide(counts, n)
        cardinality = x.sum(2)
        fractional = divide(x, cardinality[:, :, None])
        frac_shares = divide(np.nan_to_num(fractional).sum((0, 1)), n)
        for j, category in enumerate(fm.spec.categories):
            outrows.append(dict(field=fm.field, partition=fm.partition, actor=actor, category=category,
                                n_valid_responses=n, n_items_with_valid_response=int(valid.any(1).sum()),
                                category_mentions=float(counts[j]), total_mentions=float(counts.sum()),
                                mention_share=float(shares[j]), selection_prevalence=float(prevalence[j]),
                                fractional_response_share=float(frac_shares[j]),
                                mean_selected_categories=float(divide(counts.sum(), n)),
                                mention_entropy_bits=float(entropy(shares)),
                                effective_number_categories=float(2 ** entropy(shares))))


def human_reference(fm, data, model_index, scope):
    if scope not in ("majority_aligned", "same_judgment"):
        raise ValueError(f"Unknown rationale reference scope: {scope}")
    majority = data.Y[fm.partition]
    valid = fm.Hvalid & (majority[:, None] >= 0)
    valid &= data.H[fm.partition] == majority[:, None]
    if scope == "same_judgment":
        pred = data.M[fm.partition][:, model_index]
        valid &= data.H[fm.partition] == pred[:, None]
    return fm.H * valid[:, :, None], valid


def distribution_features(h, hvalid, model, mask, weighting):
    hsum = h.sum(1)
    hn = hvalid.sum(1)
    if weighting == "item_balanced":
        hv = np.nan_to_num(divide(hsum, hn[:, None]))
        hdenom = (hn > 0).astype(float)
    elif weighting == "annotation_pooled":
        hv = hsum
        hdenom = hn.astype(float)
    else:
        raise ValueError(weighting)
    hv, mv = hv * mask[:, None], model * mask[:, None]
    hd, md = hdenom * mask, mask.astype(float)
    # The whole paired comparison is recomputed on each identical set of item weights.
    features = np.column_stack([hv, mv, hd, md])
    return features


def distribution_stats(totals, k):
    t = np.asarray(totals, float)
    h, m, hn, mn = t[..., :k], t[..., k:2*k], t[..., 2*k], t[..., 2*k+1]
    hs, ms = divide(h, h.sum(-1)[..., None]), divide(m, m.sum(-1)[..., None])
    hp, mp = divide(h, hn[..., None]), divide(m, mn[..., None])
    delta = ms - hs
    return dict(tv=.5 * np.abs(delta).sum(-1), js_divergence_bits=js_divergence(hs, ms),
                mean_absolute_share_deviation=np.abs(delta).mean(-1),
                human_share=hs, model_share=ms, share_delta=delta,
                human_prevalence=hp, model_prevalence=mp, prevalence_delta=mp-hp,
                human_mean_cardinality=divide(h.sum(-1), hn),
                model_mean_cardinality=divide(m.sum(-1), mn))


def item_overlap(h, hvalid, m, mask):
    """Average over eligible human ratings within each item, then across items."""
    intersection = (h * m[:, None, :]).sum(2)
    hc, mc = h.sum(2), m.sum(1)[:, None]
    union = hc + mc - intersection
    active = hvalid & (union > 0) & mask[:, None]
    j = np.where(active, divide(intersection, union), np.nan)
    dice = np.where(active, divide(2 * intersection, hc + mc), np.nan)
    exact = np.where(active, (h == m[:, None, :]).all(2).astype(float), np.nan)
    return {"jaccard": mean_finite(j, 1), "dice": mean_finite(dice, 1),
            "exact_set": mean_finite(exact, 1), "n_humans": active.sum(1)}


def model_human_field(fm, data, bootstrap, distances, paired_profiles, overlap_summary,
                      overlap_items, principle_kappa):
    p, k = fm.partition, len(fm.spec.categories)
    for model in data.models:
        j = data.model_index[model]
        m = fm.M[:, j, :]
        for scope in ("majority_aligned", "same_judgment"):
            h, hv = human_reference(fm, data, j, scope)
            mask = fm.Mvalid[:, j] & hv.any(1)
            if scope == "same_judgment":
                mask &= (data.M[p][:, j] >= 0) & (data.M[p][:, j] == data.Y[p])
            n_items, n_human = int(mask.sum()), int(hv[mask].sum())
            overlap = item_overlap(h, hv, m, mask)
            summary = dict(field=fm.field, partition=p, model=model, scope=scope,
                           n_items=n_items, n_human_comparisons=n_human)
            for metric in ("jaccard", "dice", "exact_set"):
                summary[metric] = float(mean_finite(overlap[metric]))
                ci_columns(summary, bootstrap.means(p, overlap[metric]), metric)
            overlap_summary.append(summary)
            hmean = np.nan_to_num(divide(h.sum(1), hv.sum(1)[:, None]))
            for i in np.flatnonzero(mask):
                overlap_items.append(dict(item_id=data.ids[p][i], partition=p, field=fm.field,
                                          model=model, scope=scope, n_humans=int(overlap["n_humans"][i]),
                                          exact_set=float(overlap["exact_set"][i]), jaccard=float(overlap["jaccard"][i]),
                                          dice=float(overlap["dice"][i]),
                                          model_categories=[fm.spec.categories[c] for c in np.flatnonzero(m[i])],
                                          human_category_prevalence={c: float(hmean[i, t]) for t, c in enumerate(fm.spec.categories) if hmean[i, t] > 0}))
            # Fractional pair-count table gives one unit of mass to each paired item.
            # This is a weighted model–random-human comparison, not a hard gold rationale.
            category_kappas = []
            for c, category in enumerate(fm.spec.categories):
                hprob, mpred = hmean[mask, c], m[mask, c]
                counts = np.array([((1-hprob)*(1-mpred)).sum(), ((1-hprob)*mpred).sum(),
                                   (hprob*(1-mpred)).sum(), (hprob*mpred).sum()])
                cs = confusion_stats(counts)
                category_kappas.append(float(cs["kappa"]))
                principle_kappa.append(dict(field=fm.field, partition=p, model=model, scope=scope,
                                            category=category, n_items=n_items,
                                            binary_kappa=float(cs["kappa"]), binary_agreement=float(cs["agreement"]),
                                            positive_agreement=float(divide(2*counts[3], 2*counts[3]+counts[1]+counts[2])),
                                            human_prevalence=float(mean_finite(hprob)),
                                            model_prevalence=float(mean_finite(mpred))))
            summary["mean_binary_category_kappa"] = float(mean_finite(category_kappas))
            summary["n_defined_category_kappas"] = int(np.isfinite(category_kappas).sum())
            if not fm.spec.multi:
                joint = (hmean[:, :, None] * m[:, None, :]) * mask[:, None, None]
                nominal = nominal_table_stats(joint.sum(0))
                summary["single_choice_kappa"] = float(nominal["kappa"])
                joint_bs = bootstrap.sums(p, joint.reshape(len(mask), k*k)).reshape(-1, k, k)
                ci_columns(summary, nominal_table_stats(joint_bs)["kappa"], "single_choice_kappa")
            for weighting in ("item_balanced", "annotation_pooled"):
                features = distribution_features(h, hv, m, mask, weighting)
                point = distribution_stats(features.sum(0), k)
                bs = distribution_stats(bootstrap.sums(p, features), k)
                row = dict(model=model, field=fm.field, partition=p, scope=scope, weighting=weighting,
                           n_items=n_items, n_human_responses=n_human, small_sample=n_items < 30,
                           human_mean_cardinality=float(point["human_mean_cardinality"]),
                           model_mean_cardinality=float(point["model_mean_cardinality"]))
                for metric in ("tv", "js_divergence_bits", "mean_absolute_share_deviation"):
                    row[metric] = float(point[metric])
                    ci_columns(row, bs[metric], metric)
                # Each response can also cast total mass 1 divided among its selections.
                hfrac = np.nan_to_num(divide(h, h.sum(2)[:, :, None]))
                mf = np.nan_to_num(divide(m, m.sum(1)[:, None]))
                hf = np.nan_to_num(divide(hfrac.sum(1), hv.sum(1)[:, None]))
                if n_items:
                    ph, pm = hf[mask].mean(0), mf[mask].mean(0)
                    row["fractional_response_tv"] = float(.5 * np.abs(ph-pm).sum())
                    row["fractional_response_js_bits"] = float(js_divergence(ph, pm))
                distances.append(row)
                for c, category in enumerate(fm.spec.categories):
                    lo, hi, defined = percentile_ci(bs["share_delta"][:, c])
                    plo, phi, _ = percentile_ci(bs["prevalence_delta"][:, c])
                    paired_profiles.append(dict(model=model, field=fm.field, partition=p, scope=scope,
                                                weighting=weighting, category=category, n_items=n_items,
                                                human_mention_share=float(point["human_share"][c]),
                                                model_mention_share=float(point["model_share"][c]),
                                                model_minus_human_share_pp=float(point["share_delta"][c]*100),
                                                share_difference_ci_low_pp=lo*100, share_difference_ci_high_pp=hi*100,
                                                human_selection_prevalence=float(point["human_prevalence"][c]),
                                                model_selection_prevalence=float(point["model_prevalence"][c]),
                                                prevalence_difference_pp=float(point["prevalence_delta"][c]*100),
                                                prevalence_difference_ci_low_pp=plo*100,
                                                prevalence_difference_ci_high_pp=phi*100,
                                                defined_bootstraps=defined))


def internal_field(fm, data, groups, pair_rows, group_rows, item_rows):
    p, k = fm.partition, len(fm.spec.categories)
    actor_groups = {"humans": (fm.H, fm.Hvalid, data.human_actors)}
    for group, members in groups.items():
        inds = [data.model_index[m] for m in members]
        actor_groups[group] = (fm.M[:, inds, :], fm.Mvalid[:, inds], members)
    for group, (matrix, valid, names) in actor_groups.items():
        n = len(matrix)
        sums = {metric: np.zeros(n) for metric in ("jaccard", "dice", "exact_set")}
        comparisons = np.zeros(n, int)
        binary_coefficients = []
        for a, b in combinations(range(len(names)), 2):
            pairvalid = valid[:, a] & valid[:, b]
            xa, xb = matrix[:, a, :], matrix[:, b, :]
            union = np.maximum(xa, xb).sum(1)
            pairvalid &= union > 0
            intersection = np.minimum(xa, xb).sum(1)
            scores = dict(jaccard=divide(intersection, union),
                          dice=divide(2 * intersection, xa.sum(1) + xb.sum(1)),
                          exact_set=(xa == xb).all(1).astype(float))
            for metric, values in scores.items():
                sums[metric] += np.where(pairvalid, values, 0)
            comparisons += pairvalid
            # Pairwise table: each LLM pair only once (the all group), all human pairs.
            if group in ("all", "humans"):
                scopes = ("all_jointly_eligible", "same_pair_judgment")
                for scope in scopes:
                    pmask = pairvalid.copy()
                    labels = data.H[p] if group == "humans" else data.M[p]
                    if scope == "same_pair_judgment":
                        ai = data.human_actors.index(names[a]) if group == "humans" else data.model_index[names[a]]
                        bi = data.human_actors.index(names[b]) if group == "humans" else data.model_index[names[b]]
                        pmask &= (labels[:, ai] >= 0) & (labels[:, ai] == labels[:, bi])
                    r = dict(field=fm.field, partition=p, group=group, actor_a=names[a], actor_b=names[b],
                             scope=scope, n_items=int(pmask.sum()))
                    for metric, values in scores.items():
                        r[metric] = float(mean_finite(values[pmask]))
                    kappas = []
                    for c in range(k):
                        cs = confusion_stats(np.bincount((2*xa[pmask, c]+xb[pmask, c]).astype(int), minlength=4))
                        kappas.append(float(cs["kappa"]))
                    r["mean_binary_category_kappa"] = float(mean_finite(kappas))
                    r["n_defined_category_kappas"] = int(np.isfinite(kappas).sum())
                    if not fm.spec.multi:
                        ks = cohen_nominal(xa[pmask].argmax(1), xb[pmask].argmax(1), k)
                        r["single_choice_kappa"] = ks["kappa"]
                    pair_rows.append(r)
            if pairvalid.any():
                for c in range(k):
                    cs = confusion_stats(np.bincount((2*xa[pairvalid, c]+xb[pairvalid, c]).astype(int), minlength=4))
                    binary_coefficients.append(float(cs["kappa"]))
        row = dict(field=fm.field, partition=p, group=group, n_items_any_pair=int((comparisons > 0).sum()),
                   n_pairs_total=int(comparisons.sum()),
                   mean_pair_category_binary_kappa=float(mean_finite(binary_coefficients)),
                   n_defined_pair_category_kappas=int(np.isfinite(binary_coefficients).sum()))
        means = {}
        for metric in sums:
            means[metric] = divide(sums[metric], comparisons)
            row[metric + "_item_mean"] = float(mean_finite(means[metric]))
            row[metric + "_pair_weighted"] = float(divide(sums[metric].sum(), comparisons.sum()))
        if not fm.spec.multi:
            category_counts = matrix.sum(1)
            row.update(reliability(category_counts, expected_raters=3 if group == "humans" else len(names)))
        group_rows.append(row)
        # Human per-item baseline and all/frontier panels keep this file compact.
        if group in ("all", "frontier", "humans"):
            for i, key in enumerate(data.ids[p]):
                selected = matrix[i].sum(0)
                item_rows.append(dict(item_id=key, partition=p, field=fm.field, group=group,
                                      n_valid_rationales=int(valid[i].sum()), n_active_pairs=int(comparisons[i]),
                                      mean_pairwise_jaccard=float(means["jaccard"][i]),
                                      mean_pairwise_dice=float(means["dice"][i]),
                                      mean_exact_set_agreement=float(means["exact_set"][i]),
                                      category_vote_counts={c: int(selected[j]) for j, c in enumerate(fm.spec.categories)}))


def rationale_comparisons(fm, data, bootstrap, groups, rows):
    """Targeted paired differences in TV on IDENTICAL items for both models.

    Descriptive 95% intervals, no unadjusted bootstrap tail 'p-values'.
    Default contrasts: within-panel pairs and named Gemma/GaMS pairs.
    """
    pairs = sorted(set(pair for group in ("frontier", "gemma", "gams", "qwen")
                       for pair in combinations(sorted(groups.get(group, [])), 2)))
    # Explicit descriptive Gemma/GaMS contrasts motivated by the supplied papers.
    # Matching size/name is not claimed to establish a controlled causal adaptation study.
    extra = [("gemma-2-27b-it", "GaMS-27B-Instruct"),
             ("gemma-3-12b-it", "GaMS3-12B-Instruct")]
    pairs = sorted(set(pairs) | {tuple(sorted(pair)) for pair in extra if set(pair).issubset(data.models)})
    p, k = fm.partition, len(fm.spec.categories)
    for ma, mb in pairs:
        ja, jb = data.model_index[ma], data.model_index[mb]
        for scope in ("majority_aligned", "same_judgment"):
            h, hv = human_reference(fm, data, ja, scope)
            mask = fm.Mvalid[:, ja] & fm.Mvalid[:, jb] & hv.any(1)
            if scope == "same_judgment":
                mask &= (data.Y[p] >= 0) & (data.M[p][:, ja] == data.Y[p]) & (data.M[p][:, jb] == data.Y[p])
            fa = distribution_features(h, hv, fm.M[:, ja, :], mask, "item_balanced")
            fb = distribution_features(h, hv, fm.M[:, jb, :], mask, "item_balanced")
            pa, pb = distribution_stats(fa.sum(0), k), distribution_stats(fb.sum(0), k)
            ba, bb = distribution_stats(bootstrap.sums(p, fa), k), distribution_stats(bootstrap.sums(p, fb), k)
            row = dict(field=fm.field, partition=p, model_a=ma, model_b=mb, scope=scope,
                       n_shared_items=int(mask.sum()), tv_a=float(pa["tv"]), tv_b=float(pb["tv"]),
                       delta_tv_a_minus_b=float(pa["tv"]-pb["tv"]),
                       interpretation="positive delta: A farther from human profile; descriptive unadjusted interval")
            ci_columns(row, ba["tv"]-bb["tv"], "delta_tv")
            rows.append(row)


def deontology_moralization(data, out):
    rows, transitions = [], []
    p = "deontology"
    for model in data.models:
        item_indicators = []
        for key in data.ids[p]:
            llm = data.model_lookup.get((model, key))
            if not llm:
                continue
            result = llm["fields"].get("deontology_main")
            if not result or result["status"] != "valid":
                continue
            cat = result["value"][0]
            hobs = [h for h in data.items[key]["human_observations"]
                    if h["label"] == data.items[key]["human_majority"]]
            relevant = []
            for h in hobs:
                hr = h["fields"]["deontology_main"]
                if hr["status"] != "valid":
                    continue
                hc = hr["value"][0]
                transitions.append(dict(model=model, item_id=key, human_category=hc, model_category=cat,
                                        judgment_match=h["label"] == llm["label"],
                                        human_weight=1/len(hobs)))
                if hc == "IRRELEVANT" and h["label"] == llm["label"]:
                    relevant.append(cat in ("MORALLY RIGHT", "MORALLY WRONG"))
            if relevant:
                item_indicators.append(float(np.mean(relevant)))
        rows.append(dict(model=model, n_items_human_irrelevant_same_judgment=len(item_indicators),
                         model_moralized_rate=float(mean_finite(item_indicators))))
    counts = defaultdict(float)
    for row in transitions:
        counts[row["model"], row["human_category"], row["model_category"], row["judgment_match"]] += row["human_weight"]
    table = [dict(model=m, human_category=h, model_category=l, judgment_match=j,
                  item_weighted_human_response_count=n) for (m, h, l, j), n in counts.items()]
    write_csv(out / "deontology_main_transitions.csv", table)
    write_csv(out / "deontology_moralization.csv", rows)


def virtue_descriptives(humans, llms, data, out):
    groups = defaultdict(list)
    for o in humans + llms:
        if o["partition"] != "virtue":
            continue
        if o["actor_type"] == "human" and o["label"] != data.items[o["item_id"]]["human_majority"]:
            continue
        actor = "humans" if o["actor_type"] == "human" else o["actor"]
        groups[actor].append(o)
    rows, items = [], []
    for actor, obs in groups.items():
        valid = [o for o in obs if o["fields"]["virtue_text"]["status"] == "valid"]
        texts = [o["fields"]["virtue_text"]["value"] for o in valid]
        words = [len(re.findall(r"\b[\w'-]+\b", t, flags=re.UNICODE)) for t in texts]
        duplicates = Counter(t.casefold() for t in texts)
        row = dict(actor=actor, n_present=len(obs), n_yes=sum(o["label"] == 1 for o in obs),
                   n_valid_yes_rationale=len(valid), mean_words=float(mean_finite(words)),
                   median_words=float(np.median(words)) if words else NAN,
                   sd_words=float(np.std(words, ddof=1)) if len(words) > 1 else NAN,
                   min_words=min(words) if words else None, max_words=max(words) if words else None,
                   n_one_word=sum(w == 1 for w in words),
                   repeated_text_excess=sum(v - 1 for v in duplicates.values()),
                   interpretation="YES-eligible text only; length/repetition are descriptive, not semantic alignment")
        rows.append(row)
        for o, wordcount in zip(valid, words):
            items.append(dict(actor=actor, item_id=o["item_id"], words=wordcount,
                              characters=len(o["fields"]["virtue_text"]["value"]),
                              repeated_text_frequency=duplicates[o["fields"]["virtue_text"]["value"].casefold()]))
    write_csv(out / "virtue_text_descriptives.csv", rows)
    write_csv(out / "virtue_text_lengths.csv", items)
    return rows


def run(data, bootstrap, groups, humans, llms, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    quality = field_quality(humans, llms, data, out)
    profiles, distances, paired, overlaps, items, kappas = [], [], [], [], [], []
    pair_rows, group_rows, item_consensus, contrasts = [], [], [], []
    for field in FIELDS:
        print(f"  rationale field: {field}", flush=True)
        fm = FieldMatrices(field, data, humans, llms)
        all_available_profiles(fm, data, profiles)
        model_human_field(fm, data, bootstrap, distances, paired, overlaps, items, kappas)
        internal_field(fm, data, groups, pair_rows, group_rows, item_consensus)
        rationale_comparisons(fm, data, bootstrap, groups, contrasts)
    write_csv(out / "all_available_category_profiles.csv", profiles)
    write_csv(out / "model_human_distances.csv", distances)
    write_csv(out / "paired_category_profiles.csv", paired)
    write_csv(out / "model_human_overlap.csv", overlaps)
    write_csv(out / "item_model_human_overlap.csv", items)
    write_csv(out / "model_human_binary_category_kappa.csv", kappas)
    write_csv(out / "pairwise_rationale_agreement.csv", pair_rows)
    write_csv(out / "group_rationale_agreement.csv", group_rows)
    write_csv(out / "item_rationale_consensus.csv", item_consensus)
    write_csv(out / "paired_rationale_distance_contrasts.csv", contrasts)
    deontology_moralization(data, out)
    virtue = virtue_descriptives(humans, llms, data, out)
    return dict(quality=quality, profiles=profiles, distances=distances, overlaps=overlaps,
                group=group_rows, contrasts=contrasts, virtue=virtue, items=items)
