"""Read the supplied archives/directories and construct a verified item crosswalk."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .schema import (PARTITIONS, LABELS, PRINCIPLES, UTILITY, DEONTOLOGY, JUSTICE,
                     FIELDS, MORALIZED, Parsed, metadata, parse_categories,
                     parse_free_text, parse_label, text)


class Source:
    """A read-only view of a directory or ZIP; never extracts or runs archived code."""
    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        if self.path.is_dir():
            self.zip = None
            self.names = [str(p.relative_to(self.path)) for p in self.path.rglob("*") if p.is_file()]
        elif zipfile.is_zipfile(self.path):
            self.zip = zipfile.ZipFile(self.path)
            self.names = [n for n in self.zip.namelist() if not n.endswith("/")]
        else:
            raise ValueError(f"Expected a ZIP archive or directory: {path}")
        self.names = sorted(n for n in self.names if not any(
            v.startswith(".") or v == "__MACOSX" or v == ".." for v in Path(n).parts))
        self.manifest = []

    def read(self, name: str) -> str:
        raw = self.zip.read(name) if self.zip else (self.path / name).read_bytes()
        self.manifest.append({"source": self.path.name, "file": name, "bytes": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest()})
        return raw.decode("utf-8-sig")

    def one(self, suffix: str) -> str:
        found = [n for n in self.names if n.endswith(suffix)]
        if len(found) != 1:
            raise ValueError(f"Expected exactly one {suffix!r}; found {found}")
        return found[0]

    def csv(self, name: str) -> list[dict]:
        content = self.read(name)
        header = content.splitlines()[0]
        delim = ";" if header.count(";") > header.count(",") else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=delim)
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"Malformed CSV row / unexpected columns in {name}")
        return rows

    def close(self):
        if self.zip:
            self.zip.close()


def normalized_header(row: dict) -> dict:
    return {re.sub(r"[^a-z0-9]+", "_", k.strip().lower()).strip("_"): v for k, v in row.items()}


class Audit:
    def __init__(self):
        self.events = []
        self.crosswalk = []
        self.source_manifest = []
        self.summary = {}

    def event(self, actor: str, item: str, field: str, kind: str, detail: str = "", source_file: str = "", source_row: Any = ""):
        self.events.append(dict(actor=actor, item_id=item, field=field, kind=kind,
                                detail=detail, source_file=source_file, source_row=source_row))

    def parsed(self, obs: dict, field: str, result: Parsed, raw: str):
        for change in result.changes:
            self.event(obs["actor"], obs["item_id"], field, "normalization", change,
                       obs["source_file"], obs["source_row"])
        if result.status in ("invalid", "missing", "eligibility_unknown") or result.detail:
            self.event(obs["actor"], obs["item_id"], field, result.status,
                       f"{result.detail}; raw={raw}", obs["source_file"], obs["source_row"])


def make_observation(row: dict, partition: str, item_id: str, actor: str, actor_type: str,
                     source_file: str, source_row: int, audit: Audit) -> dict:
    rawlabel = row.get("main_label", row.get("output", ""))
    result = parse_label(partition, rawlabel)
    obs = dict(item_id=item_id, partition=partition, actor=actor, actor_type=actor_type,
               label=result.value, label_status=result.status, raw_label=rawlabel,
               source_file=source_file, source_row=source_row, fields={},
               ambiguity=row.get("ambiguity", "") == "The scenario is ambiguous.",
               cultural_flag=row.get("cultural_specificity", "") == "The scenario DOES contain a culture-specific reference that I do not understand.")
    audit.parsed(obs, "label", result, rawlabel)
    fields = obs["fields"]

    def add(name: str, raw: str, parsed: Parsed):
        fields[name] = dict(value=parsed.value, status=parsed.status, raw=raw)
        audit.parsed(obs, name, parsed, raw)

    if partition == "commonsense":
        raw = row.get("rationale", "")
        add("commonsense_principles", raw, parse_categories(raw, PRINCIPLES, True))
    elif partition == "deontology":
        raw = row.get("main_rationale", row.get("main_rationales", ""))
        main = parse_categories(raw, DEONTOLOGY, False)
        add("deontology_main", raw, main)
        raw = row.get("moral_rationale", "")
        if main.status != "valid":
            moral = Parsed(None, "eligibility_unknown")
        elif main.value[0] not in MORALIZED:
            moral = Parsed(None, "inapplicable", detail=("extra_inapplicable_principles" if text(raw) not in ("", "[]", "/", "None", "null") else ""))
        else:
            moral = parse_categories(raw, PRINCIPLES, True)
        add("deontology_principles", raw, moral)
    elif partition == "justice":
        raw = row.get("rationale", "")
        add("justice_rationale", raw, parse_categories(raw, JUSTICE, False))
    elif partition == "utilitarianism":
        raw = row.get("rationale", "")
        add("utilitarianism_rationales", raw, parse_categories(raw, UTILITY, True))
    elif partition == "virtue":
        raw = row.get("rationale", "")
        add("virtue_text", raw, parse_free_text(raw, result.value))
    for key in ("model", "response_model", "openrouter_provider", "generation_id", "prompt_tokens",
                "completion_tokens", "total_tokens", "cost_usd"):
        if row.get(key, "") != "":
            obs[key] = row[key]
    return obs


def vote(labels: list[int], min_votes: int = 2) -> dict:
    count = Counter(labels)
    n = len(labels)
    winner = max(count, key=count.get) if n else None
    top = count.get(winner, 0)
    majority = winner if n >= min_votes and top > n / 2 else None
    return dict(n=n, n0=count[0], n1=count[1], majority=majority, top=top,
                unanimous=n >= min_votes and top == n, tie=n >= min_votes and count[0] == count[1])


def load_humans(source: Source, audit: Audit) -> tuple[dict, list]:
    filename = source.one("data/processed/individual/all_annotations.csv")
    rows = source.csv(filename)
    items, humans = {}, []
    seen = set()
    for line, original in enumerate(rows, 2):
        row = normalized_header(original)
        p = row["partition"]
        if p not in PARTITIONS:
            raise ValueError(f"Unknown human partition: {p}")
        tid = str(int(row["task_instruction_id"]))
        key = f"{p}:{tid}"
        meta = metadata(row["meta"])
        item = dict(item_id=key, partition=p, task_instruction_id=tid,
                    instruction_id=row.get("instruction_id", ""), input=row["input"],
                    normalized_input=text(row["input"]), meta_id=str(meta["id"]),
                    meta_subset=meta.get("subset", ""), source_split=row.get("source_split", ""),
                    source_position_within_task=row.get("source_position_within_task", ""),
                    source_csv_row=row.get("source_csv_row", ""), human_observations=[])
        if key not in items:
            items[key] = item
        elif any(items[key][f] != item[f] for f in ("normalized_input", "meta_id", "source_split", "instruction_id")):
            raise ValueError(f"Human item metadata conflict: {key}")
        actor = "human:" + row["annotator_code"]
        if (key, actor) in seen:
            raise ValueError(f"Duplicate human rating: {key}, {actor}")
        seen.add((key, actor))
        obs = make_observation(row, p, key, actor, "human", filename, line, audit)
        if obs["label_status"] != "valid":
            raise ValueError(f"Invalid normalized human label at {key}, {actor}")
        obs["annotation_copy"] = row.get("annotation_copy", "")
        obs["batch_id"] = row.get("batch_id", "")
        items[key]["human_observations"].append(obs)
        humans.append(obs)
    for item in items.values():
        obs = item["human_observations"]
        result = vote([o["label"] for o in obs])
        item.update({"human_" + k: v for k, v in result.items()})
        item["human_ambiguity_votes"] = sum(o["ambiguity"] for o in obs)
        item["human_cultural_flag_votes"] = sum(o["cultural_flag"] for o in obs)
    # Recompute from individual ratings and reconcile the exact supplied majority export.
    supplied = source.csv(source.one("data/processed/aggregated/majority_labels.csv"))
    checked = set()
    for row in supplied:
        key = f"{row['partition']}:{int(row['task_instruction_id'])}"
        if key not in items or key in checked:
            raise ValueError(f"Unexpected/duplicate key in majority export: {key}")
        checked.add(key)
        label = parse_label(row["partition"], row["majority_label"])
        item = items[key]
        if label.value != item["human_majority"] or int(row["majority_count"]) != item["human_top"]:
            raise ValueError(f"Recomputed majority differs from provided aggregate: {key}")
        if text(row["input"]) != item["normalized_input"]:
            raise ValueError(f"Majority-export text mismatch: {key}")
    if checked != set(items):
        raise ValueError("Human majority export and individual annotations cover different item sets")
    audit.summary["human_majorities_reconciled"] = len(checked)
    rationale_file = source.one("data/processed/aggregated/categorical_rationales.csv")
    rationale_rows = source.csv(rationale_file)
    rationale_keys = set()
    for row in rationale_rows:
        key = f"{row['partition']}:{int(row['task_instruction_id'])}"
        if key not in items or key in rationale_keys:
            raise ValueError(f"Unexpected/duplicate rationale-aggregate key: {key}")
        rationale_keys.add(key)
        byactor = {o["actor"]: o for o in items[key]["human_observations"]}
        actors = ["human:" + a for a in json.loads(row["annotator_codes"])]
        if len(actors) != 3 or set(actors) != set(byactor):
            raise ValueError(f"Rationale aggregate annotators disagree: {key}")
        selected = sorted(
            (o for o in byactor.values() if o["label"] == items[key]["human_majority"]),
            key=lambda o: int(o["annotation_copy"]),
        )
        expected_actors = [o["actor"] for o in selected]
        actors = ["human:" + a for a in json.loads(row["rationale_annotator_codes"])]
        if (row["rationale_selection"] != "majority_aligned" or actors != expected_actors
                or len(selected) not in (2, 3) or int(row["rationale_count"]) != len(selected)
                or json.loads(row["rationale_annotation_copies"]) != [int(o["annotation_copy"]) for o in selected]):
            raise ValueError(f"Rationale aggregate is not majority-aligned: {key}")
        p = row["partition"]
        for field in ("categorical_rationales", "secondary_categorical_rationales", "free_text_rationales"):
            expected_count = 0 if field == "free_text_rationales" and p != "virtue" else len(selected)
            if len(json.loads(row[field])) != expected_count:
                raise ValueError(f"Rationale aggregate length conflict: {key}, {field}")
        for j, actor in enumerate(actors):
            obs = byactor[actor]
            if p == "virtue":
                expected = json.loads(row["free_text_rationales"])[j]
                if text(expected) != text(obs["fields"]["virtue_text"]["raw"]):
                    raise ValueError(f"Free-text rationale aggregate conflict: {key}")
            else:
                field = {"commonsense": "commonsense_principles", "deontology": "deontology_main",
                         "justice": "justice_rationale", "utilitarianism": "utilitarianism_rationales"}[p]
                expected = json.loads(row["categorical_rationales"])[j]
                spec = FIELDS[field]
                parsed = parse_categories(expected, spec.categories, spec.multi)
                if parsed.value != obs["fields"][field]["value"]:
                    raise ValueError(f"Categorical rationale aggregate conflict: {key}, {field}")
                if p == "deontology":
                    expected = json.loads(row["secondary_categorical_rationales"])[j]
                    parsed = parse_categories(expected, PRINCIPLES, True)
                    actual = obs["fields"]["deontology_principles"]["value"]
                    if (parsed.value or ()) != (actual or ()):
                        raise ValueError(f"Secondary rationale aggregate conflict: {key}")
    if rationale_keys != set(items):
        raise ValueError("Rationale aggregate covers a different item set")
    audit.summary["human_rationale_aggregates_reconciled"] = len(rationale_keys)
    audit.summary["human_rationale_selection"] = "majority_aligned"
    audit.summary["human_rationale_annotations_retained"] = sum(i["human_top"] for i in items.values())
    return items, humans


def infer_partition(filename: str, row: dict) -> str:
    p = row.get("task", "").lower().strip()
    file_p = next((v for v in PARTITIONS if re.search(r"(?:_|\b)" + v + r"(?:\.|_|\b)", Path(filename).name.lower())), None)
    if p in PARTITIONS:
        if file_p and p != file_p:
            raise ValueError(f"Partition filename/content conflict in {filename}")
        return p
    if file_p:
        return file_p
    meta_p = metadata(row.get("meta", "{}" )).get("subset", "")
    if meta_p in PARTITIONS:
        return meta_p
    raise ValueError(f"Cannot determine partition in {filename}")


def infer_model(filename: str, row: dict) -> str:
    if text(row.get("model", "")):
        return text(row["model"])
    name = Path(filename).stem
    match = re.match(r"(.+)_annotated_(?:" + "|".join(PARTITIONS) + r")$", name, re.I)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot identify model in {filename}; provide expected export names")


def default_groups(models: list[str]) -> dict[str, list[str]]:
    groups = {"all": sorted(models)}
    prefixes = {"frontier": ("openai/gpt", "anthropic/claude", "google/gemini"),
                "gams": ("gams",), "gemma": ("gemma",), "qwen": ("qwen",)}
    for group, starts in prefixes.items():
        selected = [m for m in sorted(models) if m.lower().startswith(starts)]
        if selected:
            groups[group] = selected
    others = [m for m in sorted(models) if m not in groups.get("frontier", [])]
    if others:
        groups["other_models"] = others
    return groups


def load_llms(source: Source, items: dict, audit: Audit) -> list:
    bymeta, bytext = defaultdict(list), defaultdict(list)
    for key, item in items.items():
        bymeta[item["partition"], item["meta_id"]].append(key)
        bytext[item["partition"], item["normalized_input"]].append(key)
    observations, seen = [], {}
    for filename in source.names:
        if not filename.lower().endswith(".csv"):
            continue
        rows = source.csv(filename)
        for line, original in enumerate(rows, 2):
            row = normalized_header(original)
            p = infer_partition(filename, row)
            model = infer_model(filename, row)
            meta = metadata(row.get("meta", "{}"))
            meta_id = str(meta.get("id", ""))
            target = None
            tid = text(row.get("task_instruction_id", ""))
            if tid:
                key = f"{p}:{int(tid)}"
                if key in items:
                    target, method = key, "partition+task_instruction_id"
                else:
                    raise ValueError(f"Unknown explicit item ID {key} in {filename}:{line}")
            elif len(bymeta[p, meta_id]) == 1:
                target, method = bymeta[p, meta_id][0], "partition+meta.id"
            elif len(bytext[p, text(row.get("input", ""))]) == 1:
                target, method = bytext[p, text(row["input"])][0], "partition+unique_normalized_input"
            if target is None:
                raise ValueError(f"Missing or ambiguous item match in {filename}:{line}; never joined by row order")
            item = items[target]
            if meta_id and meta_id != item["meta_id"]:
                raise ValueError(f"Metadata ID disagreement at {filename}:{line} -> {target}")
            if text(row.get("input", "")) != item["normalized_input"]:
                raise ValueError(f"Scenario text disagreement at {filename}:{line} -> {target}")
            if row.get("source_split") and row["source_split"] != item["source_split"]:
                raise ValueError(f"Source split disagreement at {filename}:{line} -> {target}")
            audit.crosswalk.append(dict(model=model, item_id=target, partition=p, meta_id=meta_id,
                                        join_method=method, input_exact=row.get("input", "") == item["input"],
                                        source_file=filename, source_row=line))
            obs = make_observation(row, p, target, model, "llm", filename, line, audit)
            duplicate_key = (model, target)
            if duplicate_key in seen:
                previous = seen[duplicate_key]
                comparable = lambda o: (o["raw_label"], json.dumps(o["fields"], sort_keys=True))
                if comparable(previous) != comparable(obs):
                    raise ValueError(f"Conflicting duplicate model annotations for {model}, {target}")
                audit.event(model, target, "row", "exact_duplicate_removed", source_file=filename, source_row=line)
                continue
            seen[duplicate_key] = obs
            observations.append(obs)
    if not observations:
        raise ValueError("No LLM annotation CSV files were found")
    return observations


def load_data(human_path: str, llm_path: str, config: dict | None = None) -> tuple:
    audit = Audit()
    human_source, llm_source = Source(human_path), Source(llm_path)
    try:
        items, humans = load_humans(human_source, audit)
        llms = load_llms(llm_source, items, audit)
        audit.source_manifest = human_source.manifest + llm_source.manifest
    finally:
        human_source.close()
        llm_source.close()
    models = sorted({o["actor"] for o in llms})
    groups = default_groups(models)
    if config and "groups" in config:
        groups.update(config["groups"])
    if set(groups["all"]) != set(models):
        raise ValueError("The reserved all panel must contain all discovered models; use a different name for subsets")
    for g, members in groups.items():
        if not members:
            raise ValueError(f"Configured model panel {g} is empty")
        if len(set(members)) != len(members) or any(m not in models for m in members):
            raise ValueError(f"Unknown or duplicated model in configured group {g}: {members}")
    audit.summary.update(
        n_items=len(items), items_by_partition=dict(Counter(i["partition"] for i in items.values())),
        n_human_annotations=len(humans), n_human_annotators=len({o["actor"] for o in humans}),
        human_annotations_per_item=dict(Counter(i["human_n"] for i in items.values())),
        human_unanimous_items=sum(i["human_unanimous"] for i in items.values()),
        human_split_items=sum(not i["human_unanimous"] for i in items.values()),
        n_models=len(models), models=models, groups=groups, n_llm_rows=len(llms),
        n_missing_llm_rows=len(items) * len(models) - len(llms),
        llm_label_status=dict(Counter(o["label_status"] for o in llms)),
        all_matched_input_normalized=True,
        crosswalk_methods=dict(Counter(r["join_method"] for r in audit.crosswalk)),
        normalization_and_quality_events=dict(Counter(e["kind"] for e in audit.events)),
    )
    return items, humans, llms, models, groups, audit
