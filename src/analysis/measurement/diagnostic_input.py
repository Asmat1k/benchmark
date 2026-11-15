import argparse
from pathlib import Path

import numpy as np

from admission.admission import checked, ref, sources
from reporting.inference import nearest_rank
from measurement.raw import read, require, rows, validate_raw, write
from measurement.resources import validate_resources
from execution.schedule import make_schedule


# Compute generator run.
def generator_run(folder, frequency):
    slots = rows(folder / "slots.jsonl")
    samples = rows(folder / "resources.jsonl")
    window = read(folder / "resource-window.json")
    validate_resources(samples, window)
    observations = rows(folder / "backlog.jsonl")
    stamps = [r["usec"] for r in observations]
    require(
        stamps
        and stamps[0] <= window["start_usec"]
        and stamps[-1] >= window["end_usec"]
        and all(0 < b - a <= 1500000 for a, b in zip(stamps, stamps[1:])),
        "router sampling coverage",
    )
    for record in observations:
        require(
            {q["dev"] for q in record["queues"]} == {"to_browser", "to_server"},
            "router queue coverage",
        )
    queues = [q for r in observations for q in r["queues"]]
    sent = [s for s in slots if s["t_send_ms"] is not None]
    require(len(sent) >= 2, "insufficient send times for observed frequency")
    result = dict(
        frequency_hz=frequency,
        profile="baseline",
        measurement_slots=len(slots),
        slots=slots,
        resources_complete=True,
        resource_samples=samples,
        resource_window=window,
        oom=sum(r["oom"] for r in samples),
        miss=sum(s["send_state"] == "scheduler_miss" for s in slots),
        lag_p99_ms=nearest_rank([s["send_lag_ms"] for s in sent], 0.99),
        observed_hz=1000
        * (len(sent) - 1)
        / (sent[-1]["t_send_ms"] - sent[0]["t_send_ms"]),
        router_backlog_reviewed=all(
            q["drops"] == 0 and 0 <= q["qlen"] < q["limit"] for q in queues
        ),
        router_peak_backlog_bytes=max(q["backlog"] for q in queues),
    )
    limits = {
        service["role"]: service["cpu"] / 1e9
        for service in read(folder / "context.json")["services"]
    }
    for r in samples:
        r["cpu_limit"] = limits[r["role"]]
    for role in ("browser", "server"):
        role_samples = [r for r in samples if r["role"] == role]
        result[f"{role}_cpu_pct_limit"] = max(
            100 * r["cpu_usage_usec"] / r["interval_usec"] / r["cpu_limit"]
            for r in role_samples
        )
        result[f"{role}_throttling_pct"] = (
            100
            * sum(r["throttled_usec"] for r in role_samples)
            / sum(r["interval_usec"] for r in role_samples)
        )
    return result


# Compute diagnostic raw.
def diagnostic_raw(directory, run, schedule, environment, hashes):
    folder = directory / "raw" / run["run_id"]
    require(
        folder.resolve() == directory.resolve() / "raw" / run["run_id"]
        and not any(p.is_symlink() for p in folder.iterdir()),
        "foreign raw path",
    )
    validate_raw(folder, directory / "schedule.json")
    manifest = read(folder / "manifest.json")
    require(
        all(manifest[k] == v for k, v in run.items()),
        "published diagnostic run mismatch",
    )
    require(
        read(folder / "schedule.json") == schedule,
        "published diagnostic schedule mismatch",
    )
    require(
        read(folder / "context.json") == environment,
        "published diagnostic context mismatch",
    )
    require(
        run["profile"] == "baseline"
        and not (folder / "SYNTHETIC.json").exists()
        and read(folder / "collection-sources.json") == hashes,
        "foreign diagnostic sources",
    )
    return folder


# Compute observations.
def observations(gate, evidence, environment, hashes):
    runs, extra = [], {}
    require(
        len(evidence) == (1 if gate == "timer" else 2),
        "wrong number of diagnostic schedules",
    )
    frequencies = set()
    for binding in evidence:
        schedule_path = checked(binding)
        directory = schedule_path.parent
        require(
            schedule_path.name == "schedule.json"
            and directory.resolve().parent
            == Path("results/verify/diagnostic").resolve()
            and read(directory / "context.json") == environment
            and not (directory / "STOP").exists()
            and not (directory / "SYNTHETIC.json").exists(),
            "diagnostic environment",
        )
        schedule = read(schedule_path)
        phase = "smoke" if gate == "timer" else "diagnostic"
        expected = make_schedule(
            phase,
            directory.name,
            blocks=1,
            sessions=1,
            datagrams=gate == "generator",
            baseline=True,
        )
        if gate == "timer":
            expected["collect_timer"] = True
        else:
            frequency = schedule["generator_hz"]
            require(
                frequency in (20, 100) and frequency not in frequencies,
                "both generator frequencies required",
            )
            frequencies.add(frequency)
            expected["generator_hz"] = frequency
        require(schedule == expected, "unexpected diagnostic schedule")
        ledger = read(directory / "ledger.json")
        require(
            ledger
            == dict(
                schema_version=1,
                series_id=directory.name,
                attempts=[dict(b, status="complete") for b in schedule["blocks"]],
            ),
            "incomplete diagnostics",
        )
        selected = schedule["runs"][:1] if gate == "timer" else schedule["runs"]
        for run in selected:
            folder = diagnostic_raw(directory, run, schedule, environment, hashes)
            if gate == "timer":
                samples = read(folder / "clock-samples.json")
                require(
                    len(samples) == 100001 and np.isfinite(samples).all(),
                    "invalid page samples",
                )
                delta = np.diff(samples)
                positive = delta[delta > 0]
                values = dict(
                    count=len(delta),
                    monotonic=bool(np.all(delta >= 0)),
                    step_ms=float(min(positive)) if len(positive) else None,
                    p99_overhead_ms=float(np.sort(delta)[98999]),
                )
                extra["clock_samples_ms"] = samples
            else:
                runs.append(dict(mode=run["mode"], **generator_run(folder, frequency)))
    if gate == "generator":
        values = dict(runs=runs)
    return values, extra


# Collect the supplied data.
def collect(gate, directories, environment, output):
    evidence = [ref(directory / "schedule.json") for directory in directories]
    hashes = sources()
    values, extra = observations(gate, evidence, read(environment), hashes)
    output.mkdir(parents=True, exist_ok=False)
    identity = output.name
    meta = dict(
        kind="real",
        gate=gate,
        collection_id=identity,
        source_hashes=hashes,
        environment=ref(environment),
    )
    payload = output / "payload.json"
    write(payload, dict(gate=gate, collection_id=identity, values=values, **extra))
    collection = output / "collection.json"
    write(collection, dict(**meta, payload=ref(payload)))
    write(
        output / "input.json",
        dict(**meta, collection=ref(collection), evidence=evidence, **values),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("gate", choices=("timer", "generator"))
    p.add_argument("environment", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("directories", type=Path, nargs="+")
    args = p.parse_args()
    collect(args.gate, args.directories, args.environment, args.output)
