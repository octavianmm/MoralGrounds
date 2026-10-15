"""Judgment agreement at item, model, group, partition, and overall levels."""
from __future__ import annotations
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np

from .schema import PARTITIONS, LABELS
from .metrics import (NAN, Bootstrap, confusion_counts, confusion_stats, divide,
                      entropy, holm, item_agreement, mcnemar_exact, mean_finite,
                      percentile_ci, reliability, reliability_bootstrap, weighted_domain_bootstrap, wilson)
from .io_utils import write_csv


class DataMatrices:
    def __init__(self, items, humans, llms, models):
        self.items, self.models = items, models
        self.ids = {p: sorted((k for k, i in items.items() if i["partition"] == p),
                              key=lambda k: int(items[k]["task_instruction_id"])) for p in PARTITIONS}
        self.positions = {p: {key: i for i, key in enumerate(ids)} for p, ids in self.ids.items()}
        self.human_actors = sorted({o["actor"] for o in humans})
        self.model_index = {m: j for j, m in enumerate(models)}
        self.model_lookup = {(o["actor"], o["item_id"]): o for o in llms}
        self.H, self.M, self.P, self.Y = {}, {}, {}, {}
        for p, ids in self.ids.items():
            n = len(ids)
            self.H[p] = np.full((n, len(self.human_actors)), -1, dtype=np.int8)
            self.M[p] = np.full((n, len(models)), -1, dtype=np.int8)
            self.P[p] = np.zeros((n, len(models)), dtype=bool)
            self.Y[p] = np.array([items[k]["human_majority"] if items[k]["human_majority"] is not None else -1 for k in ids], dtype=np.int8)
        human_index = {a: j for j, a in enumerate(self.human_actors)}
        for o in humans:
            i = self.positions[o["partition"]][o["item_id"]]
            self.H[o["partition"]][i, human_index[o["actor"]]] = o["label"] if o["label"] is not None else -1
        for o in llms:
            i = self.positions[o["partition"]][o["item_id"]]
            j = self.model_index[o["actor"]]
            self.M[o["partition"]][i, j] = o["label"] if o["label"] is not None else -1
            self.P[o["partition"]][i, j] = True


def to_float(d):
    return {k: float(v) for k, v in d.items()}


def aggregate_domain_rows(rows, partition="overall"):
    """No pooling of different label meanings into a single chance coefficient."""
    n = np.array([r["n"] for r in rows], float)
    result = {"partition": partition, "n": int(n.sum()), "kappa_aggregation": "valid_n_weighted_partition_mean"}
    for metric in ("agreement", "kappa", "balanced_accuracy", "macro_f1", "mcc"):
        values = np.array([r.get(metric, NAN) for r in rows], float)
        valid = np.isfinite(values) & (n > 0)
        result[metric] = float(divide((values[valid] * n[valid]).sum(), n[valid].sum()))
        result["macro_partition_" + metric] = float(mean_finite(values))
        if metric == "kappa":
            result["kappa_defined_partitions"] = int(valid.sum())
            result["kappa_defined_n"] = int(n[valid].sum())
    return result


def ci_columns(row, samples, metric):
    lo, hi, count = percentile_ci(samples)
    row[metric + "_ci_low"], row[metric + "_ci_high"] = lo, hi
    row[metric + "_defined_bootstraps"] = count


def model_human_metrics(data, bootstrap, groups, out):
    result, confusions, soft_rows = [], [], []
    samples = {"available": data.models, "common_all": data.models}
    if groups.get("frontier"):
        samples["common_frontier"] = groups["frontier"]
    for sample, actors in samples.items():
        common_members = (data.models if sample == "common_all" else groups.get("frontier", []))
        for model in actors:
            j = data.model_index[model]
            domain_rows, bs_rows = [], []
            for p in PARTITIONS:
                y, pred = data.Y[p], data.M[p][:, j]
                mask = y >= 0
                if sample != "available":
                    inds = [data.model_index[m] for m in common_members]
                    mask &= (data.M[p][:, inds] >= 0).all(1)
                count = confusion_counts(y, pred, mask)
                stats = to_float(confusion_stats(count))
                n = int(stats["n"])
                row = dict(model=model, sample=sample, partition=p,
                           label_0=LABELS[p][0], label_1=LABELS[p][1],
                           kappa_aggregation="within_partition", **stats,
                           n_universe=len(y), n_human_reference=int((y >= 0).sum()),
                           n_selected=int(mask.sum()), n_present=int((data.P[p][:, j] & mask).sum()),
                           n_missing_rows=int((~data.P[p][:, j] & mask).sum()),
                           n_invalid_or_missing_labels=int((data.P[p][:, j] & (pred < 0) & mask).sum()))
                row["n"] = n
                row["matches"] = int(count[0] + count[3])
                row["coverage"] = float(divide(n, mask.sum()))
                row["small_sample"] = n < 30
                row["agreement_wilson_low"], row["agreement_wilson_high"] = wilson(row["matches"], n)
                row["all_selected_lower_bound"] = float(divide(row["matches"], mask.sum()))
                row["all_selected_upper_bound"] = float(divide(row["matches"] + mask.sum() - n, mask.sum()))
                valid = mask & (pred >= 0)
                h = data.H[p]
                hn = (h >= 0).sum(1)
                support = divide((h == pred[:, None]).sum(1), hn)
                row["mean_human_vote_support"] = float(mean_finite(support[valid]))
                row["any_human_support_rate"] = float(mean_finite((support[valid] > 0).astype(float)))
                row["human_reference_majority_class_baseline"] = float(divide(max(count[0] + count[1], count[2] + count[3]), n))
                bs = bootstrap.confusion(p, y, pred, mask)
                for metric in ("agreement", "kappa"):
                    ci_columns(row, bs[metric], metric)
                result.append(row)
                domain_rows.append(row)
                bs_rows.append(bs)
                if sample == "available":
                    for reference in range(2):
                        for prediction in range(2):
                            confusions.append(dict(model=model, partition=p, human_label=LABELS[p][reference],
                                                   model_label=LABELS[p][prediction], n=int(count[2 * reference + prediction])))
            overall = aggregate_domain_rows(domain_rows)
            overall.update(model=model, sample=sample)
            for k in ("n_universe", "n_human_reference", "n_selected", "n_present", "n_missing_rows", "n_invalid_or_missing_labels", "matches"):
                overall[k] = sum(r[k] for r in domain_rows)
            overall["coverage"] = float(divide(overall["n"], overall["n_selected"]))
            overall["all_selected_lower_bound"] = float(divide(overall["matches"], overall["n_selected"]))
            overall["all_selected_upper_bound"] = float(divide(overall["matches"] + overall["n_selected"] - overall["n"], overall["n_selected"]))
            for metric in ("mean_human_vote_support", "any_human_support_rate", "human_reference_majority_class_baseline"):
                overall[metric] = float(divide(sum(r[metric] * r["n"] for r in domain_rows if r["n"]), overall["n"]))
            overall["agreement_wilson_low"], overall["agreement_wilson_high"] = wilson(overall["matches"], overall["n"])
            for metric in ("agreement", "kappa"):
                ci_columns(overall, weighted_domain_bootstrap(bs_rows, metric), metric)
            result.append(overall)
    write_csv(out / "model_vs_human.csv", result)
    write_csv(out / "model_human_confusion.csv", confusions)
    return result


def pairwise_models(data, bootstrap, out):
    results, comparisons, error_rows = [], [], []
    for ma, mb in combinations(data.models, 2):
        ja, jb = data.model_index[ma], data.model_index[mb]
        domain_rows, bs_rows, test_domain = [], [], []
        for p in PARTITIONS:
            a, b, y = data.M[p][:, ja], data.M[p][:, jb], data.Y[p]
            stats = to_float(confusion_stats(confusion_counts(a, b)))
            row = dict(model_a=ma, model_b=mb, partition=p, kappa_aggregation="within_partition", **stats)
            row["n"] = int(row["n"])
            bs = bootstrap.confusion(p, a, b)
            for metric in ("agreement", "kappa"):
                ci_columns(row, bs[metric], metric)
            results.append(row)
            domain_rows.append(row)
            bs_rows.append(bs)
            valid = (a >= 0) & (b >= 0) & (y >= 0)
            ca, cb = a[valid] == y[valid], b[valid] == y[valid]
            a_only, b_only, pval = mcnemar_exact(ca, cb)
            diff = np.full(len(y), np.nan)
            diff[valid] = ca.astype(float) - cb.astype(float)
            boot_sum = bootstrap.sums(p, np.nan_to_num(diff))
            boot_n = bootstrap.sums(p, valid.astype(float))
            delta_bs = divide(boot_sum, boot_n)
            test = dict(model_a=ma, model_b=mb, partition=p, n=int(valid.sum()),
                        a_agrees_b_disagrees=a_only, a_disagrees_b_agrees=b_only,
                        agreement_difference_a_minus_b=float(mean_finite(diff)),
                        mcnemar_exact_p=pval if not bootstrap.clustered else NAN,
                        mcnemar_note="not reported for cluster bootstrap" if bootstrap.clustered else "item-independence assumption")
            ci_columns(test, delta_bs, "difference")
            comparisons.append(test)
            test_domain.append((test, boot_sum, boot_n))
            ea, eb = (~ca).astype(int), (~cb).astype(int)
            es = confusion_stats(confusion_counts(ea, eb))
            error_rows.append(dict(model_a=ma, model_b=mb, partition=p, n=int(valid.sum()),
                                   both_disagree_human_rate=float(mean_finite((ea & eb).astype(float))),
                                   error_phi=float(es["mcc"]),
                                   either_matches_human_rate=float(mean_finite((ca | cb).astype(float))),
                                   a_only_matches_rate=float(divide(a_only, valid.sum())),
                                   b_only_matches_rate=float(divide(b_only, valid.sum()))))
        overall = aggregate_domain_rows(domain_rows)
        overall.update(model_a=ma, model_b=mb)
        for metric in ("agreement", "kappa"):
            ci_columns(overall, weighted_domain_bootstrap(bs_rows, metric), metric)
        results.append(overall)
        a_only = sum(r[0]["a_agrees_b_disagrees"] for r in test_domain)
        b_only = sum(r[0]["a_disagrees_b_agrees"] for r in test_domain)
        # McNemar uses correctness, whose meaning is shared across partitions.
        from scipy.stats import binomtest
        pval = binomtest(a_only, a_only + b_only, .5).pvalue if a_only + b_only else 1.
        n = sum(r[0]["n"] for r in test_domain)
        test = dict(model_a=ma, model_b=mb, partition="overall", n=n,
                    a_agrees_b_disagrees=a_only, a_disagrees_b_agrees=b_only,
                    agreement_difference_a_minus_b=float(divide(a_only - b_only, n)), mcnemar_exact_p=float(pval) if not bootstrap.clustered else NAN,
                    mcnemar_note="not reported for cluster bootstrap" if bootstrap.clustered else "item-independence assumption")
        ci_columns(test, divide(sum(r[1] for r in test_domain), sum(r[2] for r in test_domain)), "difference")
        comparisons.append(test)
    adjusted = holm([r["mcnemar_exact_p"] for r in comparisons])
    for r, value in zip(comparisons, adjusted):
        r["holm_p_all_pairs_and_partitions"] = float(value)
        r["holm_family_size"] = len(comparisons)
    write_csv(out / "pairwise_model_agreement.csv", results)
    write_csv(out / "paired_model_comparisons.csv", comparisons)
    write_csv(out / "correlated_disagreements.csv", error_rows)
    return results, comparisons


def group_and_item_metrics(data, bootstrap, groups, out):
    item_rows, group_rows, ensemble_rows, selection_rows = [], [], [], []
    for group, members in groups.items():
        inds = [data.model_index[m] for m in members]
        domain_summaries, ensemble_domains, ensemble_boot, group_boot = [], [], [], []
        for p in PARTITIONS:
            matrix = data.M[p][:, inds]
            present = data.P[p][:, inds].sum(1)
            counts = np.stack([(matrix == v).sum(1) for v in range(2)], axis=1)
            n = counts.sum(1)
            top = counts.max(1)
            majority = np.where((n >= 2) & (top > n / 2), counts.argmax(1), -1)
            agreement = item_agreement(counts)
            proportion = divide(top, n)
            ent = entropy(divide(counts, n[:, None]))
            complete = n == len(members)
            complete_unanimous = complete & (n >= 2) & (top == n)
            unanimous_available = (n >= 2) & (top == n)
            y = data.Y[p]
            any_matches = ((matrix == y[:, None]) & (y[:, None] >= 0)).any(1)
            summary = dict(group=group, partition=p, n_expected_models=len(members), n_items=len(n),
                           **reliability(counts, expected_raters=len(members)),
                           n_complete=int(complete.sum()),
                           complete_unanimous_rate=float(mean_finite(complete_unanimous[complete].astype(float))),
                           available_unanimous_rate=float(mean_finite(unanimous_available[n >= 2].astype(float))),
                           mean_vote_entropy_bits=float(mean_finite(ent[n >= 2])),
                           n_complete_unanimous_against_human=int((complete_unanimous & (majority != y) & (y >= 0)).sum()),
                           n_any_member_matches_human=int((any_matches & (n >= 1) & (y >= 0)).sum()),
                           n_items_any_valid_human_pair=int(((n >= 1) & (y >= 0)).sum()))
            rb = reliability_bootstrap(bootstrap, p, counts, len(members))
            for metric in ("pairwise_item_mean", "fleiss_kappa", "krippendorff_alpha"):
                ci_columns(summary, rb[metric], metric)
            group_boot.append(rb)
            group_rows.append(summary)
            domain_summaries.append(summary)
            for i, key in enumerate(data.ids[p]):
                item = data.items[key]
                row = dict(item_id=key, partition=p, task_instruction_id=item["task_instruction_id"],
                           group=group, n_expected=len(members), n_present=int(present[i]),
                           n_valid=int(n[i]), n_missing_rows=len(members) - int(present[i]),
                           n_invalid_labels=int(present[i] - n[i]),
                           label_counts={LABELS[p][v]: int(counts[i, v]) for v in range(2)},
                           majority_label=LABELS[p][majority[i]] if majority[i] >= 0 else None,
                           majority_count=int(top[i]), majority_fraction=float(proportion[i]),
                           tie=bool(n[i] >= 2 and counts[i, 0] == counts[i, 1]),
                           pairwise_agreement=float(agreement[i]), entropy_bits=float(ent[i]),
                           complete_panel=bool(complete[i]), unanimous_available=bool(unanimous_available[i]),
                           unanimous_complete=bool(complete_unanimous[i]),
                           human_majority=LABELS[p][y[i]] if y[i] >= 0 else None,
                           human_vote_split=f"{item['human_top']}-{item['human_n']-item['human_top']}",
                           human_unanimous=item["human_unanimous"],
                           fraction_models_matching_human=float(divide(counts[i, y[i]], n[i])) if y[i] >= 0 else NAN,
                           complete_unanimous_against_human=bool(complete_unanimous[i] and y[i] >= 0 and majority[i] != y[i]),
                           any_model_matches_human=bool(any_matches[i]),
                           source_split=item["source_split"], human_ambiguity_votes=item["human_ambiguity_votes"],
                           human_cultural_flag_votes=item["human_cultural_flag_votes"])
                item_rows.append(row)
            erow = dict(group=group, partition=p, **to_float(confusion_stats(confusion_counts(y, majority))),
                        n_universe=len(y), n_abstain=int((majority < 0).sum()),
                        coverage=float(mean_finite((majority >= 0).astype(float))), kappa_aggregation="within_partition")
            bs = bootstrap.confusion(p, y, majority)
            for metric in ("agreement", "kappa"):
                ci_columns(erow, bs[metric], metric)
            ensemble_rows.append(erow)
            ensemble_domains.append(erow)
            ensemble_boot.append(bs)
            # Coverage/agreement curves use complete model panels to avoid changing panel size.
            for threshold in (.5, 2/3, .75, .8, .9, 1.0):
                selected = complete & (majority >= 0) & (proportion >= threshold) & (y >= 0)
                matches = int((majority[selected] == y[selected]).sum())
                lo, hi = wilson(matches, int(selected.sum()))
                selection_rows.append(dict(group=group, partition=p, threshold=threshold,
                                            n_selected=int(selected.sum()), n_universe=len(y),
                                            coverage=float(mean_finite(selected.astype(float))),
                                            agreement=float(divide(matches, selected.sum())),
                                            agreement_wilson_low=lo, agreement_wilson_high=hi))
        overall = dict(group=group, partition="overall", n_expected_models=len(members),
                       n_items=sum(r["n_items"] for r in domain_summaries))
        for metric, denom in (("pairwise_item_mean", "n_items_at_least_two"),
                               ("fleiss_kappa", "n_complete_fleiss"),
                               ("krippendorff_alpha", "n_items_at_least_two"),
                               ("mean_vote_entropy_bits", "n_items_at_least_two"),
                               ("complete_unanimous_rate", "n_complete"),
                               ("available_unanimous_rate", "n_items_at_least_two")):
            v = np.array([r[metric] for r in domain_summaries])
            w = np.array([r[denom] for r in domain_summaries])
            valid = np.isfinite(v) & (w > 0)
            overall[metric] = float(divide((v[valid] * w[valid]).sum(), w[valid].sum()))
        for metric in ("n_ratings_alpha", "n_items_at_least_two", "n_complete_fleiss", "n_complete", "n_complete_unanimous_against_human", "n_any_member_matches_human", "n_items_any_valid_human_pair"):
            overall[metric] = sum(r[metric] for r in domain_summaries)
        overall["coefficient_aggregation"] = "eligible_item_weighted_partition_mean"
        for metric in ("pairwise_item_mean", "fleiss_kappa", "krippendorff_alpha"):
            bs_stats = [dict(n=r["n_complete"] if metric == "fleiss_kappa" else r["n"], **{metric:r[metric]}) for r in group_boot]
            ci_columns(overall, weighted_domain_bootstrap(bs_stats, metric), metric)
        group_rows.append(overall)
        erow = aggregate_domain_rows(ensemble_domains)
        erow.update(group=group, n_universe=sum(r["n_universe"] for r in ensemble_domains),
                    n_abstain=sum(r["n_abstain"] for r in ensemble_domains))
        erow["coverage"] = float(divide(erow["n"], erow["n_universe"]))
        for metric in ("agreement", "kappa"):
            ci_columns(erow, weighted_domain_bootstrap(ensemble_boot, metric), metric)
        ensemble_rows.append(erow)
    write_csv(out / "item_consensus.csv", item_rows)
    write_csv(out / "group_reliability.csv", group_rows)
    write_csv(out / "ensemble_vs_human.csv", ensemble_rows)
    write_csv(out / "consensus_selection_curves.csv", selection_rows)
    return item_rows, group_rows, ensemble_rows


def human_baseline(data, out, bootstrap):
    rows, loo, pairs, boot_rows = [], [], [], []
    for p in PARTITIONS:
        h = data.H[p]
        counts = np.stack([(h == v).sum(1) for v in range(2)], 1)
        row = dict(partition=p, n_items=len(h), **reliability(counts, expected_raters=3))
        row["n_unanimous"] = int((counts.max(1) == counts.sum(1)).sum())
        bs = reliability_bootstrap(bootstrap, p, counts, 3)
        for metric in ("pairwise_item_mean", "fleiss_kappa", "krippendorff_alpha"):
            ci_columns(row, bs[metric], metric)
        boot_rows.append(bs)
        rows.append(row)
        candidates, matches, excluded, unique = 0, 0, 0, set()
        model_n, model_matches = Counter(), Counter()
        for i in range(len(h)):
            for held_out in np.flatnonzero(h[i] >= 0):
                other = np.delete(h[i], held_out)
                other = other[other >= 0]
                candidates += 1
                if len(other) < 2 or not np.all(other == other[0]):
                    excluded += 1
                    continue
                ref = other[0]
                unique.add(i)
                matches += int(h[i, held_out] == ref)
                for j, model in enumerate(data.models):
                    pred = data.M[p][i, j]
                    if pred >= 0:
                        model_n[model] += 1
                        model_matches[model] += int(pred == ref)
        loo.append(dict(partition=p, actor="held_out_human", n=candidates - excluded,
                        n_unique_items=len(unique), n_excluded_reference_ties=excluded,
                        agreement=float(divide(matches, candidates - excluded)),
                        interpretation="held-out ratings; reference excludes evaluated annotator; not a ceiling"))
        for model in data.models:
            loo.append(dict(partition=p, actor=model, n=model_n[model],
                            n_unique_items=None, n_excluded_reference_ties=excluded,
                            agreement=float(divide(model_matches[model], model_n[model])),
                            interpretation="same held-out-reference occasions; items can appear more than once"))
        for a, b in combinations(range(h.shape[1]), 2):
            stats = to_float(confusion_stats(confusion_counts(h[:, a], h[:, b])))
            if stats["n"]:
                pairs.append(dict(partition=p, annotator_a=data.human_actors[a], annotator_b=data.human_actors[b], **stats))
    overall = dict(partition="overall", n_items=sum(r["n_items"] for r in rows),
                   n_unanimous=sum(r["n_unanimous"] for r in rows),
                   coefficient_aggregation="eligible_item_weighted_partition_mean")
    for metric in ("pairwise_item_mean", "fleiss_kappa", "krippendorff_alpha"):
        overall[metric] = sum(r[metric] * r["n_items"] for r in rows) / overall["n_items"]
    for metric in ("pairwise_item_mean", "fleiss_kappa", "krippendorff_alpha"):
        bs_stats = [dict(n=r["n_complete"] if metric == "fleiss_kappa" else r["n"], **{metric:r[metric]}) for r in boot_rows]
        ci_columns(overall, weighted_domain_bootstrap(bs_stats, metric), metric)
    rows.append(overall)
    write_csv(out / "human_reliability.csv", rows)
    write_csv(out / "human_leave_one_out_baseline.csv", loo)
    write_csv(out / "human_pairwise_overlap.csv", pairs)
    return rows


def stratified_metrics(data, out):
    rows = []
    for model in data.models:
        j = data.model_index[model]
        for p in PARTITIONS:
            ids = data.ids[p]
            items = [data.items[k] for k in ids]
            strata = {
                "human_unanimous": np.array([i["human_unanimous"] for i in items]),
                "human_split": np.array([not i["human_unanimous"] for i in items]),
                "ambiguity_any_flag": np.array([i["human_ambiguity_votes"] > 0 for i in items]),
                "ambiguity_no_flag": np.array([i["human_ambiguity_votes"] == 0 for i in items]),
                "culture_any_flag": np.array([i["human_cultural_flag_votes"] > 0 for i in items]),
                "culture_no_flag": np.array([i["human_cultural_flag_votes"] == 0 for i in items]),
            }
            for split in sorted({i["source_split"] for i in items}):
                strata["source_" + split] = np.array([i["source_split"] == split for i in items])
            for subset in sorted({i["meta_subset"] for i in items}):
                strata["meta_subset_" + subset] = np.array([i["meta_subset"] == subset for i in items])
            for stratum, mask in strata.items():
                count = confusion_counts(data.Y[p], data.M[p][:, j], mask)
                stats = to_float(confusion_stats(count))
                lo, hi = wilson(int(count[0] + count[3]), int(stats["n"]))
                rows.append(dict(model=model, partition=p, stratum=stratum, n_selected=int(mask.sum()),
                                 **stats, agreement_wilson_low=lo, agreement_wilson_high=hi,
                                 small_sample=stats["n"] < 30))
    write_csv(out / "stratified_model_vs_human.csv", rows)
    return rows


def logged_usage(llms, out):
    groups = defaultdict(list)
    for o in llms:
        if "cost_usd" in o or "total_tokens" in o:
            groups[o["actor"], o["partition"]].append(o)
    rows = []
    for (actor, p), observations in groups.items():
        row = dict(model=actor, partition=p, n_logged_rows=len(observations))
        for key in ("cost_usd", "prompt_tokens", "completion_tokens", "total_tokens"):
            values = []
            for o in observations:
                try:
                    values.append(float(o[key]))
                except (KeyError, ValueError, TypeError):
                    pass
            row[key + "_n"] = len(values)
            row[key + "_sum"] = sum(values) if values else NAN
            row[key + "_mean"] = float(mean_finite(values))
        row["scope"] = "logged returned rows only; not total experiment expenditure"
        rows.append(row)
    write_csv(out / "logged_model_usage.csv", rows)


def run(data, bootstrap, groups, out, llms):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    human = human_baseline(data, out, bootstrap)
    model = model_human_metrics(data, bootstrap, groups, out)
    pairwise, comparisons = pairwise_models(data, bootstrap, out)
    item, group, ensemble = group_and_item_metrics(data, bootstrap, groups, out)
    strata = stratified_metrics(data, out)
    logged_usage(llms, out)
    matrix_rows = []
    for p in PARTITIONS:
        for i, key in enumerate(data.ids[p]):
            y = data.Y[p][i]
            row = dict(item_id=key, partition=p, task_instruction_id=data.items[key]["task_instruction_id"],
                       human_majority=LABELS[p][y] if y >= 0 else None,
                       human_unanimous=data.items[key]["human_unanimous"], input=data.items[key]["input"])
            for j, model_id in enumerate(data.models):
                v = data.M[p][i,j]
                row[model_id] = LABELS[p][v] if v >= 0 else None
            matrix_rows.append(row)
    write_csv(out / "item_label_matrix.csv", matrix_rows)
    return dict(human=human, model=model, pairwise=pairwise, comparisons=comparisons,
                item=item, group=group, ensemble=ensemble, strata=strata)
