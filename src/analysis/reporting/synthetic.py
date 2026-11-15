import argparse
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from measurement.raw import digest, read, rows, write
from execution.schedule import PROFILES, make_schedule

from tests.support import create_template


# Rebuild checksums for the modified fixture.
def rehash(folder):
    manifest = read(folder / "manifest.json")
    for key in (
        "environment",
        "provenance",
        "security",
        "network_before",
        "network_after",
    ):
        manifest[key]["sha256"] = digest(folder / manifest[key]["path"])
    write(folder / "manifest.json", manifest)
    checks = read(folder / "checks.json")
    for check in checks["checks"]:
        for ref in check["evidence"]:
            ref["sha256"] = digest(folder / ref["path"])
    write(folder / "checks.json", checks)
    (folder / "SHA256SUMS").write_text(
        "".join(
            f"{digest(p)}  {p.name}\n"
            for p in sorted(folder.iterdir())
            if p.name != "SHA256SUMS"
        )
    )


# Create fixture.
def make_fixture(
    directory, blocks=1, datagrams=True, schedule=None, execution_order=None
):
    with tempfile.TemporaryDirectory() as temporary:
        source = create_template(Path(temporary) / "template")
        return _make_fixture(
            directory, blocks, datagrams, schedule, execution_order, source
        )


# Populate the requested schedule from an isolated synthetic template.
def _make_fixture(directory, blocks, datagrams, schedule, execution_order, source):
    directory.mkdir(parents=True, exist_ok=False)
    schedule = schedule or make_schedule(
        "diagnostic", "synthetic-analysis-v1", blocks, 1, datagrams
    )
    write(directory / "schedule.json", schedule)
    write(
        directory / "ledger.json",
        dict(
            schema_version=1,
            series_id=schedule["series_id"],
            attempts=[
                dict(
                    a,
                    status="quarantined"
                    if a["status"] == "quarantined"
                    else "complete",
                )
                for a in schedule["blocks"]
            ],
        ),
    )
    write(directory / "queue.json", [])
    write(
        directory / "SYNTHETIC.json",
        dict(
            purpose="D4 known-answer analysis only; no network experiment",
            environment_template="explicit offline fixture",
            generated_slots=True,
            n_per_profile=blocks,
        ),
    )
    template = source / "raw/b0-a0-m0"
    config = {
        name: read(Path("configs") / f"{name}.json")
        for name in ("plan", "thresholds", "profiles")
    }
    context = read(source / "context.json")
    context["config"] = config
    write(directory / "context.json", context)
    active = [
        r["run_id"]
        for r in schedule["runs"]
        if next(
            b["status"]
            for b in schedule["blocks"]
            if b["attempt_id"] == r["attempt_id"]
        )
        != "quarantined"
    ]
    execution_order = execution_order or active
    if sorted(execution_order) != sorted(active):
        raise ValueError("synthetic execution order must cover all active runs")
    start = datetime.fromisoformat(
        read(template / "manifest.json")["started_utc"].replace("Z", "+00:00")
    )
    warmup, measurement = (1, 3) if schedule["series"] == "smoke" else (200, 1200)
    for run in schedule["runs"]:
        if (
            next(
                b["status"]
                for b in schedule["blocks"]
                if b["attempt_id"] == run["attempt_id"]
            )
            == "quarantined"
        ):
            continue
        folder = directory / "raw" / run["run_id"]
        shutil.copytree(template, folder)
        write(folder / "context.json", context)
        write(folder / "config.json", config)
        write(folder / "schedule.json", schedule)
        manifest = read(folder / "manifest.json")
        manifest["config_sha256"] = digest(folder / "config.json")
        manifest.update(
            run,
            series=schedule["series"],
            series_id=schedule["series_id"],
            schedule_sha256=digest(folder / "schedule.json"),
        )
        moment = start + timedelta(seconds=90 * execution_order.index(run["run_id"]))
        manifest.update(
            started_utc=moment.isoformat().replace("+00:00", "Z"),
            ended_utc=(moment + timedelta(seconds=80))
            .isoformat()
            .replace("+00:00", "Z"),
        )
        write(folder / "manifest.json", manifest)
        spec = read(folder / "run.json")
        spec.update(
            run_id=run["run_id"],
            nonce=run["nonce"],
            mode=run["mode"],
            warmup_slots=warmup,
            measurement_slots=measurement,
        )
        write(folder / "run.json", spec)
        profile_index = PROFILES.index(run["profile"])
        latency = (
            20
            + profile_index * 20
            + (-10 if run["mode"] == "WT-S" else 5 if run["mode"] == "WT-D" else 0)
        )
        slots, events = [], []
        base = rows(template / "slots.jsonl")[0]
        for index in range(warmup + measurement):
            phase = int(index >= warmup)
            seq = index - warmup * phase
            plan = 1000 + index * 50
            lost = (
                phase == 1
                and run["mode"] == "WT-S"
                and seq < 6
                and schedule["series"] != "smoke"
            )
            slot = dict(
                base,
                run_id=run["run_id"],
                phase=phase,
                nonce=run["nonce"],
                seq=str(seq),
                t_plan_ms=plan,
                t_send_ms=plan,
                send_lag_ms=0,
                api_return_ms=plan,
                write_fulfilled_ms=None,
                first_correct_echo_ms=None if lost else plan + latency,
                echo_bytes=None if lost else 256,
                completed_by_horizon=not lost,
                ontime=not lost,
                terminal_reason="horizon" if lost else "ontime",
            )
            slots.append(slot)
            identity = {k: slot[k] for k in ("nonce", "seq", "phase")}

            # Append the synthetic event record.
            def event(kind, time):
                events.append(
                    dict(
                        schema_version=1,
                        run_id=run["run_id"],
                        event_index=0,
                        t_ms=time,
                        type=kind,
                        id=identity,
                        details={},
                    )
                )

            if seq == 0:
                event("phase_transition", plan)
            if not lost:
                event("first_correct_echo", plan + latency)
        for name, records in (("warmup", slots[:warmup]), ("slots", slots[warmup:])):
            (folder / f"{name}.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in records)
            )
        # Supply the inline callback for this operation.
        events.sort(key=lambda e: e["t_ms"])
        for i, e in enumerate(events):
            e["event_index"] = i
        (folder / "events.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in events)
        )
        server = read(folder / "server.json")
        server["run_id"] = run["run_id"]
        for phase, size in (("warmup", warmup), ("measurement", measurement)):
            server[phase] = dict(
                received=size, invalid=0, write_attempted=size, echoed=size, errors=0
            )
        write(folder / "server.json", server)
        write(
            folder / "counters.json",
            dict(active=0, **{k: server[k] for k in ("warmup", "measurement")}),
        )
        write(
            folder / "completion.json",
            dict(
                schema_version=1,
                run_id=run["run_id"],
                status="complete",
                warmup_rows=warmup,
                measurement_rows=measurement,
                reason=None,
            ),
        )
        samples = []
        for role in ("browser", "server", "router"):
            base_resource = next(
                r for r in rows(template / "resources.jsonl") if r["role"] == role
            )
            samples.extend(
                dict(
                    base_resource,
                    run_id=run["run_id"],
                    sample_index=i,
                    end_usec=(i + 1) * 1000000,
                    interval_usec=1000000,
                )
                for i in range(80)
            )
        (folder / "resources.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in samples)
        )
        write(
            folder / "resource-window.json", dict(start_usec=1000000, end_usec=80000000)
        )
        check = read(folder / "checks.json")
        check["checks"][0].update(expected=measurement, actual=measurement)
        write(folder / "checks.json", check)
        profile = config["profiles"]["profiles"][profile_index]
        for when in ("before", "after"):
            network = read(folder / f"network_{when}.json")
            for q in network["qdisc"]:
                if q["kind"] == "netem":
                    option = q["options"]
                    option["seed"] = run[
                        "forward_seed" if q["dev"] == "to_server" else "reverse_seed"
                    ]
                    option["delay"] = dict(
                        delay=profile["egress_delay_ms"] / 1000, jitter=0, correlation=0
                    )
                    option["loss-random"] = dict(loss=profile["egress_loss_pct"] / 100)
            write(folder / f"network_{when}.json", network)
            write(folder / f"qdisc-{when}.json", network["qdisc"])
        from measurement.stabilization_cpu import quiet_summary, compare

        for role in ("browser", "server", "router"):
            path = folder / f"{role}-baseline.jsonl"
            records = [dict(row, run_id=run["run_id"]) for row in rows(path)]
            path.write_text("".join(json.dumps(row) + "\n" for row in records))
        summaries = []
        for prefix in ("baseline", "stabilization-1"):
            quiet = []
            for role in ("browser", "server", "router"):
                path = folder / f"{prefix}-{role}.jsonl"
                records = [dict(row, run_id=run["run_id"]) for row in rows(path)]
                path.write_text("".join(json.dumps(row) + "\n" for row in records))
                quiet.extend(records)
            summary = quiet_summary(
                quiet, int((folder / f"{prefix}-marker").read_text())
            )
            write(folder / f"{prefix}-cpu.json", summary)
            summaries.append(summary)
        write(folder / "stabilization-1-comparison.json", compare(*summaries))
        rehash(folder)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--blocks", type=int, default=1)
    args = parser.parse_args()
    print(make_fixture(args.directory, args.blocks))
