import argparse
import csv
import importlib.metadata
import json
import math
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

from inference import bootstrap, decisions, holm4, rank_interval, sign_test
from metrics import descriptive, run_metrics
from raw import ROOT, digest, read, require, rows, validate_raw, write
from schedule import PROFILES, block_runs, seeds
from series import measurement_lock

AUDIT_FIELDS = ("block_id", "session_id", "attempt_id", "profile", "order_index", "modes", "seed",
                "status", "reason", "replacement_of", "design", "evidence_sha256")


def json_numbers(value):
    if isinstance(value, float) and not math.isfinite(value):
        require(not math.isnan(value), "NaN result")
        return "+inf" if value > 0 else "-inf"
    if isinstance(value, dict):
        return {k: json_numbers(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_numbers(v) for v in value]
    return value


def csv_table(path, records, fields=None):
    fields = fields or list(dict.fromkeys(k for record in records for k in record))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for record in records:
            writer.writerow({k: "NA" if v is None else v for k,v in record.items()})


def attempt_snapshot(archived, current):
    require({k:v for k,v in archived.items() if k not in ("status","reason")} ==
            {k:v for k,v in current.items() if k not in ("status","reason")}, "schedule attempt changed")
    require(archived["status"] in ("planned","complete","quarantined") and
            (archived["status"] != "quarantined" or
             (current["status"],current["reason"]) == ("quarantined",archived["reason"])), "schedule status regression")


def schedule_snapshot(archived, current):
    require(set(archived) == set(current) and all(archived[k] == current[k] for k in
            ("schema_version","series","series_id","master_seed")), "schedule snapshot identity")
    require([dict(a,status=None,reason=None) for a in archived["blocks"] if a["replacement_of"] is None] ==
            [dict(a,status=None,reason=None) for a in current["blocks"] if a["replacement_of"] is None],
            "original schedule membership changed")
    require(len(archived["blocks"]) <= len(current["blocks"]) and
            archived["runs"] == current["runs"][:len(archived["runs"])], "schedule extension changed")
    for a,b in zip(archived["blocks"],current["blocks"]):
        attempt_snapshot(a,b)
    require(archived["runs"] == [r for i,b in enumerate(archived["blocks"]) for r in block_runs(archived,b,i)],
            "schedule snapshot runs changed")


def run_identity(folder, run):
    require(folder.is_dir(), "missing raw/audit member")
    manifest = read(folder/"manifest.json")
    require(folder.name == manifest["run_id"] == run["run_id"] and
            all(manifest.get(k) == v for k,v in run.items()), "raw directory/run attribution mismatch")
    return manifest


def validate_series(directory, design="comparison"):
    for name in ("STOP", "PENDING_REPLACEMENT", "replacement.json"):
        require(not (directory/name).exists(), f"series blocked: {name}")
    schedule = read(directory/"schedule.json")
    ledger = read(directory/"ledger.json")
    require(set(schedule) == {"schema_version","series","series_id","master_seed","blocks","runs"} and
            schedule["schema_version"] == 1 and schedule["master_seed"] == 20261108, "schedule version/master seed")
    Draft202012Validator(read(ROOT/"docs/schemas/ledger.schema.json")).validate(ledger)
    require(schedule["series_id"] == ledger["series_id"], "series ledger mismatch")
    require(schedule["series"] != "smoke", "smoke is diagnostic only; comparison analysis forbidden")
    require(schedule["series"] in ("verify", "diagnostic", "pilot", "main"), "unknown series")
    attempts = ledger["attempts"]
    ids = [a["attempt_id"] for a in attempts]
    require(len(ids) == len(set(ids)), "duplicate attempt")
    require(len(schedule["blocks"]) == len(attempts), "schedule ledger length")
    for a,b in zip(attempts, schedule["blocks"]):
        require({k:v for k,v in a.items() if k != "status"} == {k:v for k,v in b.items() if k != "status"}, "schedule ledger mismatch")
        require(a["design"] == design, "unexpected series design")
        require(a["status"] in ("complete", "quarantined"), "incomplete series")
        require(all(Path(a[k]).name == a[k] for k in ("attempt_id", "block_id", "session_id")), "unsafe identity")
    run_ids = [r["run_id"] for r in schedule["runs"]]
    require(len(run_ids) == len(set(run_ids)), "duplicate run")
    require(set(r["attempt_id"] for r in schedule["runs"]) == set(ids), "foreign run attempt")
    require(schedule["runs"] == [r for i,b in enumerate(schedule["blocks"]) for r in block_runs(schedule,b,i)],
            "pair metadata/seed mismatch")
    active = [a for a in attempts if a["status"] == "complete"]
    require(active and len({a["block_id"] for a in active}) == len(active), "duplicate active block")
    require(design != "comparison" or len({tuple(sorted(a["modes"])) for a in active}) == 1, "inconsistent modes")
    if (directory/"queue.json").exists():
        require(read(directory/"queue.json") == [], "unfinished queue")
    audit = []
    for a in attempts:
        parent = a["replacement_of"]
        if parent is not None:
            require(parent in ids and ids.index(parent) < ids.index(a["attempt_id"]), "replacement chain")
            old = attempts[ids.index(parent)]
            require(old["status"] == "quarantined" and all(a[k] == old[k] for k in
                    ("block_id", "profile", "session_id", "order_index")), "replacement identity")
        if a["status"] != "quarantined":
            continue
        require(sum(b["replacement_of"] == a["attempt_id"] for b in attempts) == 1, "missing block replacement")
        folder = directory/"audit"/a["attempt_id"]
        transaction = read(folder/"transaction.json")
        proof = read(folder/"evidence.json")
        require(transaction["attempt_id"] == a["attempt_id"] and
                transaction["evidence_sha256"] == digest(folder/"evidence.json") and
                proof["attempt_id"] == a["attempt_id"] and proof["reason"] == a["reason"], "audit evidence mismatch")
        archived = read(folder/"schedule.json")
        schedule_snapshot(archived,schedule)
        schedule_snapshot(transaction["schedule"],schedule)
        require(len(transaction["schedule"]["blocks"]) == len(archived["blocks"])+1 and
                transaction["replacement"] == transaction["schedule"]["blocks"][-1] and
                transaction["replacement"]["replacement_of"] == a["attempt_id"], "audit replacement mismatch")
        replacement = next(b for b in attempts if b["attempt_id"] == transaction["replacement"]["attempt_id"])
        attempt_snapshot(transaction["replacement"],replacement)
        Draft202012Validator(read(ROOT/"docs/schemas/ledger.schema.json")).validate(transaction["ledger"])
        require(transaction["ledger"]["series_id"] == ledger["series_id"] and
                len(transaction["ledger"]["attempts"]) == len(transaction["schedule"]["blocks"]), "audit ledger mismatch")
        for old,current in zip(transaction["ledger"]["attempts"],attempts):
            attempt_snapshot(old,current)
        members = {r["run_id"]:r for r in schedule["runs"] if r["attempt_id"] == a["attempt_id"]}
        destinations = [after for before,after in transaction["moves"]]
        require(len(destinations) == len(set(destinations)) and
                {p.name for p in folder.iterdir() if p.is_dir()} == {Path(p).name for p in destinations}, "audit member inventory mismatch")
        require(proof["run_id"] in {Path(p).name for p in destinations}, "audit proof member missing")
        for before,after in transaction["moves"]:
            name = Path(after).name
            require(name in members and after == f"audit/{a['attempt_id']}/{name}" and
                    before == (proof["folder"] if name == proof["run_id"] else f"raw/{name}"), "audit member path mismatch")
            run_identity(folder/name,members[name])
            if name != proof["run_id"] or proof["reason"] != "hash":
                schedule_snapshot(read(folder/name/"schedule.json"),schedule)
            if name != proof["run_id"]:
                validate_raw(folder/name,directory/"schedule.json")
        source = folder/proof["run_id"]
        require(Path(proof["run_id"]).name == proof["run_id"], "unsafe audit identity")
        require(proof["files"] == {p.name:digest(p) for p in source.iterdir()}, "audit source changed")
        manifest = read(source/"manifest.json")
        require(proof["identity"] == {k:manifest[k] for k in ("run_id","attempt_id","block_id","session_id","series_id","series")} and
                proof["context_sha256"] == digest(source/"context.json") == digest(directory/"context.json") and
                proof["schedule_sha256"] == digest(folder/"schedule.json"), "foreign audit proof")
        from violation import detect
        require(detect(source,directory/"schedule.json") == (proof["reason"],proof["error"]), "audit violation not reproducible")
        audit.append(dict(a, evidence_sha256=digest(folder/"evidence.json")))
    selected = [r for r in schedule["runs"] if r["attempt_id"] in {a["attempt_id"] for a in active}]
    require({p.name for p in (directory/"raw").iterdir()} == {r["run_id"] for r in selected}, "raw series membership")
    versions = []
    times = {}
    for run in selected:
        manifest = run_identity(directory/"raw"/run["run_id"],run)
        validate_raw(directory/"raw"/run["run_id"], directory/"schedule.json")
        schedule_snapshot(read(directory/"raw"/run["run_id"]/"schedule.json"),schedule)
        times[run["run_id"]] = tuple(datetime.fromisoformat(manifest[k].replace("Z","+00:00")) for k in ("started_utc","ended_utc"))
        versions.append(tuple(manifest[k] for k in ("commit","dirty","protocol_version","protocol_sha256","config_sha256")))
        def finite(value):
            if isinstance(value,dict):
                return all(finite(v) for v in value.values())
            if isinstance(value,list):
                return all(finite(v) for v in value)
            return not isinstance(value,float) or math.isfinite(value)
        for path in (directory/"raw"/run["run_id"]).iterdir():
            if path.suffix in (".json", ".jsonl"):
                values = rows(path) if path.suffix == ".jsonl" else [read(path)]
                require(finite(values), "nonfinite raw number")
    require(len(set(versions)) == 1, "mixed release/config/protocol versions")
    selected.sort(key=lambda r:times[r["run_id"]][0])
    for index,run in enumerate(selected):
        start,end = times[run["run_id"]]
        require(start < end and (index == 0 or times[selected[index-1]["run_id"]][1] <= start),
                "overlapping/ambiguous execution times")
    return schedule, selected, audit


def compute(directory, output):
    schedule, selected, audit = validate_series(directory)
    config = read(directory/"raw"/selected[0]["run_id"]/"config.json")
    thresholds = config["thresholds"]
    runs, rtt_records, raw_hashes = [], [], {}
    for index, run in enumerate(selected):
        folder = directory/"raw"/run["run_id"]
        manifest = read(folder/"manifest.json")
        metrics, rtts = run_metrics(rows(folder/"slots.jsonl"), rows(folder/"events.jsonl"), rows(folder/"resources.jsonl"),
                                    thresholds["deadline_ms"], thresholds["horizon_ms"])
        runs.append(dict(series_id=schedule["series_id"], series=schedule["series"], **run, run_order=index,
                         started_utc=manifest["started_utc"],ended_utc=manifest["ended_utc"],
                         technical_valid=True, **metrics))
        rtt_records.extend(dict(run_id=run["run_id"], mode=run["mode"], profile=run["profile"], RTT_ms=rtt) for rtt in rtts)
        raw_hashes[run["run_id"]] = dict(manifest=digest(folder/"manifest.json"), raw_checksums=digest(folder/"SHA256SUMS"),
                                        commit=manifest["commit"], dirty=manifest["dirty"])
    pairs = []
    for attempt in dict.fromkeys(r["attempt_id"] for r in runs):
        sides = {r["mode"]:r for r in runs if r["attempt_id"] == attempt}
        ws, wt = sides["WS"], sides["WT-S"]
        pairs.append({k:ws[k] for k in ("series_id", "session_id", "profile", "block_id", "attempt_id", "replacement_of")} |
                     dict(WS_run=ws["run_id"], WT_S_run=wt["run_id"], Q_WS_ms=ws["Q_ms"], Q_WT_S_ms=wt["Q_ms"],
                          D_ms=wt["Q_ms"]-ws["Q_ms"] if wt["Q_ms"] is not None and ws["Q_ms"] is not None else None,
                          S_WS_pct=ws["S_pct"], S_WT_S_pct=wt["S_pct"], delta_S_pp=wt["S_pct"]-ws["S_pct"]))
    profiles, index_files, summaries = [], {}, []
    for j, profile in enumerate(PROFILES):
        members = [p for p in pairs if p["profile"] == profile]
        n = len(members)
        effect = [p["D_ms"] for p in members]
        available = n > 0 and None not in effect
        result = dict(profile=profile, n=n, latency_available=available, n_null=sum(d is None for d in effect),
                      theta_ms=float(np.median(effect)) if available else None,
                      sign=sign_test(effect) if available else dict(n=n, p_raw=1., placeholder=True),
                      CI95=rank_interval(effect) if available else None,
                      CI9875=rank_interval(effect,.0125) if available else None)
        if n:
            rng = seeds(schedule["series"],schedule["series_id"],6,j)
            state = rng.bit_generator.state
            indices = rng.integers(0,n,size=(config["plan"]["bootstrap_replicates"],n))
            filename = f"bootstrap-{profile}.npz"
            np.savez_compressed(output/filename, indices=indices)
            index_files[profile] = dict(path=filename, sha256=digest(output/filename), generator="PCG64", state_before=state,
                                        seed_branch=6, profile_index=j, blocks=[p["attempt_id"] for p in members])
            result["fullness"] = bootstrap([p["delta_S_pp"] for p in members],indices)
            datagrams = {r["attempt_id"]:r for r in runs if r["profile"] == profile and r["mode"] == "WT-D"}
            if datagrams:
                d = [datagrams[p["attempt_id"]] for p in members]
                result["WT_D"] = dict(descriptive_only=True, n=n, n_null_Q=sum(r["Q_ms"] is None for r in d),
                    S=bootstrap([r["S_pct"] for r in d],indices,.95),
                    Q=bootstrap([r["Q_ms"] for r in d],indices,.95,"median") if all(r["Q_ms"] is not None for r in d) else None,
                    Q_reason="null_in_block" if any(r["Q_ms"] is None for r in d) else None)
        else:
            result["fullness"] = None
        for mode in ("WS", "WT-S", "WT-D"):
            sample = [r for r in runs if r["profile"] == profile and r["mode"] == mode]
            if sample:
                summaries.append(dict(profile=profile, mode=mode, Q=descriptive([r["Q_ms"] for r in sample]),
                                      S=descriptive([r["S_pct"] for r in sample]), U=descriptive([r["U_pct"] for r in sample])))
        profiles.append(result)
    for result, adjusted in zip(profiles,holm4([p["sign"]["p_raw"] for p in profiles])):
        result["sign"]["p_Holm"] = adjusted
        members = [r for r in runs if r["profile"] == result["profile"] and r["mode"] in ("WS","WT-S")]
        complete = bool(members) and all(r["U_pct"] <= thresholds["max_uncompleted_pct"] and r["disconnects"] == 0 for r in members)
        result.update(decisions(result["CI9875"]["bounds"] if result["latency_available"] else None,
                                result["fullness"]["bounds"] if result["fullness"] else None, adjusted,
                                result["latency_available"],complete,thresholds))
    report = dict(schema_version=1, series=schedule["series"], series_id=schedule["series_id"],
                  synthetic=(directory/"SYNTHETIC.json").exists(), profiles=profiles, descriptive=summaries, audit=audit,
                  units=dict(Q="ms", theta="ms", S="percent", U="percent", delta_S="percentage_points"), thresholds=thresholds,
                  limitations=["Independent blocks assumed; seeds do not establish independence.",
                    "Conditional RTT excludes uncompleted slots; Q must be read with S/U.",
                    "Degenerate bootstrap intervals do not exclude rare failures.",
                    "No overall winner across profiles; WT-D is descriptive.",
                    "Development analysis does not pass experimental gates."],
                  provenance=dict(schedule_sha256=digest(directory/"schedule.json"), ledger_sha256=digest(directory/"ledger.json"),
                    context_sha256=digest(directory/"context.json"), raw=raw_hashes, bootstrap=index_files,
                    sources={str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/"src/analysis").glob("*.py"))},
                    requirements_sha256=digest(ROOT/"src/analysis/requirements.txt"),
                    versions={p:importlib.metadata.version(p) for p in ("numpy","scipy","pandas","matplotlib","seaborn","jsonschema")}))
    csv_table(output/"runs.csv",runs)
    csv_table(output/"pairs.csv",pairs)
    csv_table(output/"profiles.csv", [dict(profile=p["profile"], n=p["n"], theta_ms=p["theta_ms"],
        p_raw=p["sign"]["p_raw"], p_Holm=p["sign"]["p_Holm"],
        CI95_low_ms=p["CI95"]["bounds"][0] if p["CI95"] else None,
        CI95_high_ms=p["CI95"]["bounds"][1] if p["CI95"] else None,
        CI9875_low_ms=p["CI9875"]["bounds"][0] if p["CI9875"] else None,
        CI9875_high_ms=p["CI9875"]["bounds"][1] if p["CI9875"] else None,
        mean_delta_S_pp=p["fullness"]["estimate"] if p["fullness"] else None,
        delta_S_low_pp=p["fullness"]["bounds"][0] if p["fullness"] else None,
        delta_S_high_pp=p["fullness"]["bounds"][1] if p["fullness"] else None,
        statistical_decision=p["statistical_decision"], practical_decision=p["practical_decision"],
        completeness_gate=p["completeness_gate"], validity_gate=p["validity_gate"], useful_gain=p["useful_gain"]) for p in profiles])
    csv_table(output/"descriptive.csv",[dict(profile=s["profile"],mode=s["mode"],metric=key,units="ms" if key == "Q" else "percent",
        n=s[key]["n"],n_available=s[key]["n_available"],n_null=s[key]["n_null"],median=s[key]["median"],
        IQR_low=s[key]["iqr"][0] if s[key]["iqr"] else None,IQR_high=s[key]["iqr"][1] if s[key]["iqr"] else None,
        values=json.dumps(s[key]["values"])) for s in summaries for key in ("Q","S","U")])
    csv_table(output/"audit.csv",audit,AUDIT_FIELDS)
    write(output/"analysis.json",json_numbers(report))
    from plots import figures
    figures(output,runs,rtt_records,profiles,thresholds)


def analyze(directory, all_outcomes=False, destination=None):
    directory = directory.resolve()
    admission = read(directory/'admission.json') if not all_outcomes and (directory/'admission.json').exists() else {}
    all_outcomes = all_outcomes or admission.get('execution_policy') == 'exploratory-browser-study-v2'
    require(destination is None or all_outcomes, 'custom output requires all-outcomes mode')
    destination = Path(destination).resolve() if destination is not None else directory/'derived'
    require(destination != directory and not directory.is_relative_to(destination), 'unsafe analysis destination')
    require(not destination.exists() or destination == directory/'derived', 'custom analysis destination exists')
    with measurement_lock(), tempfile.TemporaryDirectory(prefix=".analysis-",dir=destination.parent) as temporary:
        output = Path(temporary)
        if all_outcomes:
            from outcomes import compute_outcomes
            compute_outcomes(directory,output)
        else:
            compute(directory,output)
        (output/"SHA256SUMS").write_text("".join(f"{digest(p)}  {p.relative_to(output)}\n" for p in sorted(output.rglob("*")) if p.is_file()))
        if destination.exists():
            shutil.rmtree(destination)
        output.rename(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("series",type=Path)
    parser.add_argument('--all-outcomes',action='store_true')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    print(analyze(args.series,args.all_outcomes,args.output))
