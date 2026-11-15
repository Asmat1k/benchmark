import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median

import numpy as np
from jsonschema import Draft202012Validator

from reporting.inference import (
    bootstrap,
    decisions,
    holm4,
    nearest_rank,
    rank_interval,
    sign_test,
)
from measurement.metrics import descriptive, run_metrics
from measurement.raw import (
    ROOT,
    digest,
    read,
    require,
    rows,
    validate_hashes,
    validate_raw,
    write,
)
from execution.schedule import PROFILES, block_runs, seeds


# Compute paired statistics.
def paired_statistics(schedule, items, config, output, bookkeeping_error=False):
    unavailable = dict(
        status="unavailable",
        scope="exploratory-full-planned-pairs",
        reason="Requires every planned comparison run, non-null Q/S/U, and intact assignment accounting; no selected-pair inference.",
    )
    if (
        bookkeeping_error
        or not items
        or any(
            item["status"] != "complete"
            or any(item[key] is None for key in ("Q_ms", "S_pct", "U_pct"))
            for item in items
        )
    ):
        return unavailable
    if not schedule["blocks"] or any(
        block["design"] != "comparison" for block in schedule["blocks"]
    ):
        return unavailable
    modes = set(schedule["blocks"][0]["modes"])
    if (
        any(set(block["modes"]) != modes for block in schedule["blocks"])
        or schedule["series"] == "main"
        and modes != {"WS", "WT-S", "WT-D"}
    ):
        return unavailable
    if set(block["profile"] for block in schedule["blocks"]) != set(PROFILES):
        return unavailable
    if schedule["series"] == "main" and any(
        sum(block["profile"] == profile for block in schedule["blocks"]) != 20
        for profile in PROFILES
    ):
        return unavailable
    if schedule["runs"] != [
        run
        for index, block in enumerate(schedule["blocks"])
        for run in block_runs(schedule, block, index)
    ]:
        return unavailable
    by_id = {item["run_id"]: item for item in items}
    pairs = []
    for block in schedule["blocks"]:
        assigned = [
            run for run in schedule["runs"] if run["attempt_id"] == block["attempt_id"]
        ]
        sides = {run["mode"]: by_id[run["run_id"]] for run in assigned}
        if len(sides) != len(assigned) or not {"WS", "WT-S"} <= sides.keys():
            return unavailable
        ws, wt = sides["WS"], sides["WT-S"]
        pairs.append(
            dict(
                profile=block["profile"],
                attempt_id=block["attempt_id"],
                WS_run=ws["run_id"],
                WT_S_run=wt["run_id"],
                Q_WS_ms=ws["Q_ms"],
                Q_WT_S_ms=wt["Q_ms"],
                D_ms=wt["Q_ms"] - ws["Q_ms"],
                S_WS_pct=ws["S_pct"],
                S_WT_S_pct=wt["S_pct"],
                delta_S_pp=wt["S_pct"] - ws["S_pct"],
            )
        )
    profiles, provenance, summaries = [], {}, []
    for index, profile in enumerate(PROFILES):
        members = [pair for pair in pairs if pair["profile"] == profile]
        effects = [pair["D_ms"] for pair in members]
        n = len(members)
        rng = seeds(schedule["series"], schedule["series_id"], 6, index)
        state = rng.bit_generator.state
        indices = rng.integers(0, n, size=(config["plan"]["bootstrap_replicates"], n))
        filename = f"bootstrap-{profile}.npz"
        np.savez_compressed(output / filename, indices=indices)
        provenance[profile] = dict(
            path=filename,
            sha256=digest(output / filename),
            generator="PCG64",
            state_before=state,
            seed_branch=6,
            profile_index=index,
            blocks=[pair["attempt_id"] for pair in members],
        )
        result = dict(
            profile=profile,
            n=n,
            latency_available=True,
            n_null=0,
            theta_ms=float(np.median(effects)),
            sign=sign_test(effects),
            CI95=rank_interval(effects),
            CI9875=rank_interval(effects, 0.0125),
            fullness=bootstrap([pair["delta_S_pp"] for pair in members], indices),
        )
        datagrams = [
            item
            for item in items
            if item["profile"] == profile and item["mode"] == "WT-D"
        ]
        if datagrams:
            by_attempt = {item["attempt_id"]: item for item in datagrams}
            if set(by_attempt) != {pair["attempt_id"] for pair in members}:
                return unavailable
            ordered = [by_attempt[pair["attempt_id"]] for pair in members]
            result["WT_D"] = dict(
                descriptive_only=True,
                n=n,
                n_null_Q=0,
                S=bootstrap([item["S_pct"] for item in ordered], indices, 0.95),
                Q=bootstrap(
                    [item["Q_ms"] for item in ordered], indices, 0.95, "median"
                ),
                Q_reason=None,
            )
        profiles.append(result)
        for mode in ("WS", "WT-S", "WT-D"):
            sample = [
                item
                for item in items
                if item["profile"] == profile and item["mode"] == mode
            ]
            if sample:
                summaries.append(
                    dict(
                        profile=profile,
                        mode=mode,
                        **{
                            key: descriptive(
                                [
                                    item[key + "_ms" if key == "Q" else key + "_pct"]
                                    for item in sample
                                ]
                            )
                            for key in ("Q", "S", "U")
                        },
                    )
                )
    for result, adjusted in zip(
        profiles, holm4([profile["sign"]["p_raw"] for profile in profiles])
    ):
        result["sign"]["p_Holm"] = adjusted
        sample = [
            item
            for item in items
            if item["profile"] == result["profile"] and item["mode"] in ("WS", "WT-S")
        ]
        complete = all(
            item["U_pct"] <= config["thresholds"]["max_uncompleted_pct"]
            and item["metrics"]["disconnects"] == 0
            for item in sample
        )
        result.update(
            decisions(
                result["CI9875"]["bounds"],
                result["fullness"]["bounds"],
                adjusted,
                True,
                complete,
                config["thresholds"],
            )
        )
    for name, records in (
        ("pairs", pairs),
        ("profiles", profiles),
        ("descriptive", summaries),
    ):
        fields = list(records[0])
        with (output / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fields)
            writer.writeheader()
            from reporting.analyze import json_numbers

            writer.writerows(
                {
                    key: json.dumps(json_numbers(value), allow_nan=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in record.items()
                }
                for record in records
            )
    return dict(
        status="available",
        scope="exploratory-full-planned-pairs",
        profiles=profiles,
        pairs=pairs,
        descriptive=summaries,
        bootstrap=provenance,
        thresholds=config["thresholds"],
        limitations=[
            "Same full-n sign/Holm4/rank intervals/block bootstrap as strict analysis.",
            "Independent blocks remain an assumption; no confirmatory readiness or power claim.",
            "No overall transport winner; WT-D descriptive only.",
        ],
    )


# Write the report figures.
def figures(output, items):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    statuses = list(dict.fromkeys(item["status"] for item in items))
    colors = {
        status: plt.get_cmap("tab10")(index % 10)
        for index, status in enumerate(statuses)
    }
    counts = Counter(item["status"] for item in items)
    figure, axis = plt.subplots(figsize=(8, 4), layout="constrained")
    axis.bar(
        statuses,
        [counts[status] for status in statuses],
        color=[colors[status] for status in statuses],
    )
    axis.set(ylabel="Assigned runs", title=f"All {len(items)} planned assignments")
    figure_dir = output / "figures"
    figure_dir.mkdir()
    for suffix in ("png", "svg", "pdf"):
        figure.savefig(figure_dir / f"outcomes.{suffix}", dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(
        4,
        1,
        figsize=(13, 10),
        sharex=True,
        layout="constrained",
        gridspec_kw=dict(height_ratios=[3, 3, 3, 1]),
    )
    for axis, key, label, observed_key in zip(
        axes[:3],
        ("Q_ms", "S_pct", "U_pct"),
        ("Q: p95 RTT (ms)", "S: on time (%)", "U: uncompleted (%)"),
        ("Q_observed_ms", "S_observed_pct", "U_observed_pct"),
    ):
        for index, item in enumerate(items):
            if item[key] is not None:
                axis.scatter(index, item[key], color=colors[item["status"]], s=18)
            elif (
                item["observations"] is not None
                and item["observations"][observed_key] is not None
            ):
                axis.scatter(
                    index,
                    item["observations"][observed_key],
                    facecolors="none",
                    edgecolors=colors[item["status"]],
                    s=24,
                )
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    for index, item in enumerate(items):
        axes[3].scatter(index, 0, marker="s", color=colors[item["status"]], s=30)
    axes[3].set_yticks([])
    axes[3].set_ylabel("Outcome")
    step = max(1, math.ceil(len(items) / 30))
    ticks = list(range(0, len(items), step))
    axes[3].set_xticks(
        ticks, [items[index]["run_id"] for index in ticks], rotation=90, fontsize=7
    )
    axes[3].set_xlabel("Assignment order; absent Q/S/U is unknown, never zero")
    for status in statuses:
        axes[0].scatter([], [], color=colors[status], label=status, s=18)
    axes[0].scatter(
        [],
        [],
        facecolors="none",
        edgecolors="black",
        label="unaccepted observations",
        s=24,
    )
    axes[0].legend(fontsize=8, ncol=3)
    figure.suptitle(
        "All assignments retained; filled: validated raw; hollow: descriptive observations"
    )
    for suffix in ("png", "svg", "pdf"):
        figure.savefig(figure_dir / f"runs.{suffix}", dpi=160)
    plt.close(figure)


# Compute partition.
def partition(records, planned):
    values = [r["rtt_ms"] for r in records]
    cutoff = nearest_rank(values, 0.99)
    parts = (
        dict(
            all=values,
            body=[v for v in values if v <= cutoff],
            tail=[v for v in values if v > cutoff],
        )
        if values
        else dict(all=[], body=[], tail=[])
    )
    return dict(
        cutoff_ms=cutoff,
        method="Within-run nearest-rank p99; body <= cutoff, tail > cutoff; no exclusion.",
        statistics={
            name: dict(
                n=len(sample),
                denominator_returned=len(values),
                denominator_planned=planned,
                median_ms=median(sample) if sample else None,
                mean_ms=sum(sample) / len(sample) if sample else None,
                p95_ms=nearest_rank(sample, 0.95),
                p99_ms=nearest_rank(sample, 0.99),
                max_ms=max(sample, default=None),
            )
            for name, sample in parts.items()
        },
    )


# Compute observations.
def observations(folder, run, planned):
    errors = []
    for filename in ("slots.jsonl", "page.json", "page.partial.json"):
        source = folder / filename
        if not source.is_file():
            continue
        try:
            summary, packets = observations_source(folder, run, planned, source)
            summary.update(source=filename, source_errors=errors)
            return summary, packets
        except Exception as error:
            errors.append(dict(source=filename, reason=str(error)))
    raise ValueError("No readable measurement snapshot: " + str(errors))


# Compute observations source.
def observations_source(folder, run, planned, source):
    spec = read(folder / "run.json")
    require(
        all(spec[k] == run[k] for k in ("run_id", "nonce", "mode")),
        "observation identity mismatch",
    )
    complete = source.name != "page.partial.json"
    captured = None
    if source.name == "slots.jsonl":
        slots = rows(source)
    else:
        data = read(source)
        if not complete:
            require(
                data["status"] == "partial" and data["run_id"] == run["run_id"],
                "checkpoint identity/status mismatch",
            )
            captured = data["captured_page_ms"]
            require(
                isinstance(captured, (int, float)) and math.isfinite(captured),
                "checkpoint clock invalid",
            )
        slots = [s for s in data["slots"] if s["phase"] == 1]
    validator = Draft202012Validator(read(ROOT / "configs/schemas/slot.schema.json"))
    seen = set()
    rtts = []
    timely = 0
    mature_missing = 0
    for slot in slots:
        validator.validate(slot)
        require(
            slot["run_id"] == run["run_id"]
            and slot["nonce"] == run["nonce"]
            and slot["phase"] == 1,
            "slot identity mismatch",
        )
        seq = int(slot["seq"])
        require(seq not in seen and 0 <= seq < planned, "duplicate/out-of-range slot")
        seen.add(seq)
        for value in slot.values():
            require(
                not isinstance(value, float) or math.isfinite(value),
                "nonfinite observation",
            )
        sent, echo = slot["t_send_ms"], slot["first_correct_echo_ms"]
        require(
            echo is None or sent is not None and echo >= sent, "invalid echo ordering"
        )
        recorded_times = [v for v in (sent, echo) if v is not None]
        require(
            captured is None or all(v <= captured for v in recorded_times),
            "observation beyond checkpoint",
        )
        completed = echo is not None and echo <= slot["t_plan_ms"] + spec["horizon_ms"]
        if echo is not None:
            rtts.append(
                dict(
                    run_id=run["run_id"],
                    nonce=slot["nonce"],
                    seq=slot["seq"],
                    rtt_ms=echo - sent,
                    send_lag_ms=slot["send_lag_ms"],
                    completed_by_horizon=completed,
                    ontime=echo <= slot["t_plan_ms"] + spec["deadline_ms"],
                )
            )
        if completed:
            timely += echo <= slot["t_plan_ms"] + spec["deadline_ms"]
        elif complete or slot["t_plan_ms"] + spec["horizon_ms"] <= captured:
            mature_missing += 1
    require(len(slots) <= planned, "too many slots")
    require(not complete or len(slots) == planned, "incomplete final slot inventory")
    within_horizon = [record for record in rtts if record["completed_by_horizon"]]
    unknown = planned - len(within_horizon) - mature_missing
    lags = [s["send_lag_ms"] for s in slots if s["send_lag_ms"] is not None]
    summary = dict(
        scope="unaccepted-observations-only",
        measurement_finished=complete,
        planned_slots=planned,
        recorded_slot_rows=len(slots),
        captured_page_ms=captured,
        observed_completed=len(within_horizon),
        observed_returned=len(rtts),
        observed_late_after_horizon=len(rtts) - len(within_horizon),
        observed_timely=timely,
        observed_uncompleted_after_horizon=mature_missing,
        unknown_slots=unknown,
        Q_observed_ms=nearest_rank([r["rtt_ms"] for r in within_horizon], 0.95),
        S_observed_pct=100 * timely / planned if complete else None,
        U_observed_pct=100 * mature_missing / planned if complete else None,
        p99_lag_observed_ms=nearest_rank(lags, 0.99),
        all_body_tail=partition(within_horizon, planned),
        all_returned_body_tail=partition(rtts, planned),
    )
    for record in rtts:
        record["partition"] = (
            "late_after_horizon"
            if not record["completed_by_horizon"]
            else "tail"
            if record["rtt_ms"] > summary["all_body_tail"]["cutoff_ms"]
            else "body"
        )
    return summary, rtts


# Compute artifact index.
def artifact_index(directory):
    result = {}
    errors = []
    candidates = (
        list((directory / "raw").glob("*"))
        + list((directory / "quarantine").glob("*"))
        + list(directory.glob("*.partial"))
        + list((directory / "audit").glob("*/*"))
    )
    for folder in candidates:
        if not folder.is_dir():
            continue
        try:
            run_id = read(folder / "run.json")["run_id"]
            result.setdefault(run_id, []).append(folder)
        except Exception as error:
            errors.append(
                dict(path=str(folder.relative_to(directory)), reason=str(error))
            )
            if folder.parent == directory / "raw":
                result.setdefault(folder.name, []).append(folder)
    return result, errors


# Run outcome.
def run_outcome(directory, run, planned, candidates, journal):
    status = journal.get("status", "planned")
    item = dict(
        run_id=run["run_id"],
        attempt_id=run["attempt_id"],
        mode=run["mode"],
        profile=run["profile"],
        status="not_run" if status == "planned" else status,
        reason=journal.get("reason"),
        planned_slots=planned,
        Q_ms=None,
        S_pct=None,
        U_pct=None,
        metrics=None,
        observations=None,
        artifacts=[],
        artifact_errors=[],
    )
    packet_rows = []
    for folder in candidates:
        artifact = dict(
            path=str(folder.relative_to(directory)),
            accepted=False,
            integrity="unsealed",
            validation_error=None,
        )
        try:
            if (folder / "SHA256SUMS").exists():
                validate_hashes(folder)
                artifact["integrity"] = "sealed"
            try:
                validate_raw(folder, directory / "schedule.json")
                artifact["accepted"] = (
                    folder.parent == directory / "raw" and folder.name == run["run_id"]
                )
            except Exception as error:
                artifact["validation_error"] = str(error)
            summary, packets = observations(folder, run, planned)
            artifact["observations"] = summary
            if artifact["accepted"]:
                spec = read(folder / "run.json")
                metrics, _ = run_metrics(
                    rows(folder / "slots.jsonl"),
                    rows(folder / "events.jsonl"),
                    rows(folder / "resources.jsonl"),
                    spec["deadline_ms"],
                    spec["horizon_ms"],
                )
                item.update(
                    status="complete",
                    reason=None,
                    metrics={
                        k: v for k, v in metrics.items() if k != "penalized_p95_ms"
                    },
                    Q_ms=metrics["Q_ms"],
                    S_pct=metrics["S_pct"],
                    U_pct=metrics["U_pct"],
                )
            elif item["status"] in ("not_run", "complete"):
                item["status"] = (
                    "rejected" if summary["measurement_finished"] else "interrupted"
                )
            if item["observations"] is None or artifact["accepted"]:
                item["observations"] = summary
                packet_rows = [
                    dict(
                        packet, artifact=artifact["path"], accepted=artifact["accepted"]
                    )
                    for packet in packets
                ]
        except Exception as error:
            artifact["error"] = str(error)
            item["artifact_errors"].append(artifact["path"] + ": " + str(error))
            if item["status"] == "not_run":
                item["status"] = "rejected"
        item["artifacts"].append(artifact)
    if item["status"] == "complete" and item["metrics"] is None:
        item.update(
            status="rejected", reason="journal complete without validated published raw"
        )
    if item["reason"] is None and item["status"] != "complete":
        item["reason"] = next(
            (
                a.get("error") or a.get("validation_error")
                for a in item["artifacts"]
                if a.get("error") or a.get("validation_error")
            ),
            None,
        )
    return item, packet_rows


# Compute outcomes.
def compute_outcomes(directory, output):
    schedule = read(directory / "schedule.json")
    runs = schedule["runs"]
    require(len({r["run_id"] for r in runs}) == len(runs), "duplicate planned run ID")
    context = (
        read(directory / "context.json")
        if (directory / "context.json").exists()
        else dict(
            config={
                name: read(ROOT / f"configs/{name}.json")
                for name in ("plan", "thresholds", "profiles")
            }
        )
    )
    planned = (
        3
        if schedule["series"] == "smoke"
        else context["config"]["plan"]["measurement_slots"]
    )
    journal = {}
    journal_error = None
    if (directory / "outcomes.json").exists():
        try:
            from execution.execution import load_outcomes

            journal = {
                r["run_id"]: r for r in load_outcomes(directory, create=False)["runs"]
            }
        except Exception as error:
            journal_error = str(error)
    artifacts, artifact_errors = artifact_index(directory)
    items, packets = [], []
    for run in runs:
        item, packet_rows = run_outcome(
            directory,
            run,
            planned,
            artifacts.get(run["run_id"], []),
            journal.get(run["run_id"], {}),
        )
        items.append(item)
        packets.extend(packet_rows)
    valid = [r for r in items if r["status"] == "complete"]
    profiles = []
    for profile in dict.fromkeys(r["profile"] for r in runs):
        members = [r for r in items if r["profile"] == profile]
        profiles.append(
            dict(
                profile=profile,
                planned_runs=len(members),
                status_counts=dict(Counter(r["status"] for r in members)),
                inference="unavailable",
                reason="Descriptive all-outcomes report; no inference on selected complete pairs.",
            )
        )
    result = dict(
        schema_version=1,
        scope="descriptive-all-planned-outcomes",
        series_id=schedule["series_id"],
        schedule_sha256=digest(directory / "schedule.json"),
        source_sha256=digest(Path(__file__)),
        planned_runs=len(items),
        planned_slots=planned * len(items),
        status_counts=dict(Counter(r["status"] for r in items)),
        collection_status="complete"
        if len(valid) == len(items) and journal_error is None
        else "partial",
        accepted_totals=dict(
            planned_slots=sum(r["metrics"]["count_planned"] for r in valid),
            completed=sum(r["metrics"]["completed"] for r in valid),
            timely=sum(r["metrics"]["timely"] for r in valid),
            uncompleted=sum(r["metrics"]["uncompleted"] for r in valid),
        ),
        unknown_planned_slots=planned * (len(items) - len(valid)),
        journal_error=journal_error,
        artifact_index_errors=artifact_errors,
        unassigned_artifacts={
            key: [str(p.relative_to(directory)) for p in value]
            for key, value in artifacts.items()
            if key not in {r["run_id"] for r in runs}
        },
        limitations=[
            "All assignments retained, including rejected, interrupted and not_run.",
            "Unknown data are not measured loss; partial observations never replace validated Q/S/U.",
            "Lag, RTT tails, disconnects and late replies do not filter membership.",
            "No inferential claims or useful-gain decision from selected complete pairs.",
        ],
        profiles=profiles,
        runs=items,
    )
    result["paired_statistics"] = paired_statistics(
        schedule,
        items,
        context["config"],
        output,
        journal_error is not None
        or bool(artifact_errors)
        or bool(result["unassigned_artifacts"]),
    )
    if result["paired_statistics"]["status"] == "available":
        for profile in result["profiles"]:
            profile.update(
                inference="available",
                reason="Exploratory full-planned-pair statistics in paired_statistics.",
            )
    from reporting.analyze import json_numbers

    write(output / "analysis.json", json_numbers(result))
    fields = [
        "run_id",
        "attempt_id",
        "mode",
        "profile",
        "status",
        "reason",
        "planned_slots",
        "Q_ms",
        "S_pct",
        "U_pct",
    ]
    with (output / "runs.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(
            {k: "NA" if r[k] is None else r[k] for k in fields} for r in items
        )
    packet_fields = [
        "run_id",
        "nonce",
        "seq",
        "rtt_ms",
        "send_lag_ms",
        "completed_by_horizon",
        "ontime",
        "partition",
        "artifact",
        "accepted",
    ]
    with (output / "rtt.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, packet_fields)
        writer.writeheader()
        writer.writerows(packets)
    lines = [
        "# All planned outcomes",
        "",
        f"{len(items)} planned runs; {len(valid)} accepted complete; collection {result['collection_status']}.",
        "",
        "Unknown values are unavailable, not measured loss. Rejected and partial observations remain descriptive. No inference on selected complete pairs.",
        "",
        "|Run|Mode|Profile|Status|Q ms|S %|U %|Observed replies|Unknown observation slots|Reason|",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in items:
        observed = item["observations"] or {}
        values = [
            item[k]
            for k in ("run_id", "mode", "profile", "status", "Q_ms", "S_pct", "U_pct")
        ] + [
            observed.get("observed_completed"),
            observed.get("unknown_slots"),
            item["reason"],
        ]
        lines.append(
            "|"
            + "|".join(
                "NA"
                if value is None
                else str(value).replace("|", "/").replace("\n", " ")
                for value in values
            )
            + "|"
        )
    statistics = result["paired_statistics"]
    lines.extend(
        [
            "",
            "## Paired statistics",
            "",
            f"Status: {statistics['status']}; scope: exploratory full planned pairs.",
        ]
    )
    if statistics["status"] == "available":
        lines.extend(
            [
                "",
                "|Profile|Planned pairs|Median ΔQ ms|Holm p|98.75% ΔQ interval ms|Mean ΔS pp|98.75% ΔS interval pp|",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for profile in statistics["profiles"]:
            values = (
                profile["profile"],
                profile["n"],
                profile["theta_ms"],
                profile["sign"]["p_Holm"],
                json_numbers(profile["CI9875"]["bounds"]),
                profile["fullness"]["estimate"],
                profile["fullness"]["bounds"],
            )
            lines.append("|" + "|".join(str(value) for value in values) + "|")
        lines.append(
            "\nIntervals and decisions retain exploratory scope; no confirmatory readiness or power claim."
        )
    else:
        lines.append(statistics["reason"])
    (output / "report.md").write_text("\n".join(lines) + "\n")
    figures(output, items)
    return result
