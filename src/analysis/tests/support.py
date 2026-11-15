import hashlib
import json
import ssl
from pathlib import Path

from execution.schedule import make_schedule
from execution.series import context_snapshot
from measurement.raw import digest, read, write
from measurement.stabilization_cpu import compare, quiet_summary

START = "2026-11-12T12:00:00Z"


# Write newline-delimited records without changing their order.
def json_lines(path, records):
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


# Build a complete offline smoke series from explicit synthetic observations.
def create_template(directory, schedule=None):
    directory.mkdir(parents=True, exist_ok=True)
    write(
        directory / "SYNTHETIC.json",
        dict(purpose="isolated offline raw fixture; not measurement evidence"),
    )
    schedule = schedule or make_schedule("smoke", directory.name, 1, 1, baseline=True)
    write(directory / "schedule.json", schedule)
    write(
        directory / "ledger.json",
        dict(
            schema_version=1,
            series_id=schedule["series_id"],
            attempts=[dict(block, status="complete") for block in schedule["blocks"]],
        ),
    )
    write(directory / "queue.json", [])
    config = {
        name: read(Path("configs") / f"{name}.json")
        for name in ("plan", "thresholds", "profiles")
    }
    for run in schedule["runs"]:
        folder = directory / "raw" / run["run_id"]
        folder.mkdir(parents=True)
        (folder / "leaf.pem").write_bytes(
            (Path(__file__).parent / "fixtures/leaf.pem").read_bytes()
        )
        (folder / "host.txt").write_text("offline synthetic host\n")
        (folder / "server-build.txt").write_text("offline synthetic build\n")
        write(folder / "vm.json", dict(platform="aarch64", engine="synthetic"))
        limits = [
            dict(
                role=f"fixture-{role}-1",
                id="sha256:" + "1" * 64,
                cpu=1000000000,
                memory=1073741824,
                shm=1073741824,
            )
            for role in ("browser", "server", "router")
        ]
        write(folder / "limits.json", limits)
        write(folder / "images.json", limits)
        write(folder / "config.json", config)
        write(folder / "schedule.json", schedule)
        spec = {key: run[key] for key in ("run_id", "nonce", "mode")}
        spec.update(
            warmup_slots=1,
            measurement_slots=3,
            interval_ms=50,
            queue_limit_bytes=config["plan"]["queue_limit_bytes"],
            deadline_ms=config["thresholds"]["deadline_ms"],
            horizon_ms=config["thresholds"]["horizon_ms"],
        )
        write(folder / "run.json", spec)
        records, events = [], []
        for index in range(4):
            phase = int(index > 0)
            seq = str(index - phase)
            plan = 1000 + index * 50
            slot = dict(
                schema_version=1,
                run_id=run["run_id"],
                phase=phase,
                nonce=run["nonce"],
                seq=seq,
                t_plan_ms=plan,
                t_send_ms=plan,
                send_lag_ms=0,
                api_return_ms=plan,
                write_fulfilled_ms=None,
                send_state="sent",
                bytes=256,
                queue_before_bytes=0,
                desired_size=None,
                first_correct_echo_ms=plan + 20,
                echo_bytes=256,
                completed_by_horizon=True,
                ontime=True,
                terminal_reason="ontime",
            )
            records.append(slot)
            identity = {key: slot[key] for key in ("nonce", "seq", "phase")}
            for kind, moment in ([("phase_transition", plan)] if seq == "0" else []) + [
                ("first_correct_echo", plan + 20)
            ]:
                events.append(
                    dict(
                        schema_version=1,
                        run_id=run["run_id"],
                        event_index=len(events),
                        t_ms=moment,
                        type=kind,
                        id=identity,
                        details={},
                    )
                )
        json_lines(folder / "warmup.jsonl", records[:1])
        json_lines(folder / "slots.jsonl", records[1:])
        json_lines(folder / "events.jsonl", events)
        counts = {
            name: dict(
                received=size, invalid=0, write_attempted=size, echoed=size, errors=0
            )
            for name, size in (("warmup", 1), ("measurement", 3))
        }
        write(
            folder / "server.json",
            dict(schema_version=1, run_id=run["run_id"], **counts),
        )
        write(folder / "counters.json", dict(active=0, **counts))
        write(
            folder / "completion.json",
            dict(
                schema_version=1,
                run_id=run["run_id"],
                status="complete",
                warmup_rows=1,
                measurement_rows=3,
                reason=None,
            ),
        )
        resources = [
            dict(
                schema_version=1,
                run_id=run["run_id"],
                role=role,
                interval_usec=1000000,
                cpu_usage_usec=10000,
                throttled_usec=0,
                memory_current=1000000,
                oom=0,
                sample_index=i,
                end_usec=(i + 1) * 1000000,
            )
            for role in ("browser", "server", "router")
            for i in range(80)
        ]
        json_lines(folder / "resources.jsonl", resources)
        for role in ("browser", "server", "router"):
            json_lines(
                folder / f"{role}-baseline.jsonl",
                [next(row for row in resources if row["role"] == role)],
            )

        write(
            folder / "resource-window.json", dict(start_usec=1000000, end_usec=80000000)
        )
        settings = "mtu 1500\n" + "\n".join(
            f"{feature}: off"
            for feature in (
                "tcp-segmentation-offload",
                "generic-segmentation-offload",
                "generic-receive-offload",
                "large-receive-offload",
            )
        )
        profile = next(
            (p for p in config["profiles"]["profiles"] if p["id"] == run["profile"]),
            dict(egress_delay_ms=0, egress_loss_pct=0),
        )
        queues = [
            dict(
                kind="netem",
                dev=dev,
                backlog=0,
                qlen=0,
                options=dict(
                    seed=run[key],
                    delay=dict(
                        delay=profile["egress_delay_ms"] / 1000, jitter=0, correlation=0
                    ),
                    **{"loss-random": dict(loss=profile["egress_loss_pct"] / 100)},
                    limit=config["profiles"]["limit_packets"],
                    rate=dict(rate=config["profiles"]["rate_mbit_s"] * 125000),
                ),
            )
            for dev, key in (
                ("to_server", "forward_seed"),
                ("to_browser", "reverse_seed"),
            )
        ]
        for when in ("before", "after"):
            write(
                folder / f"network_{when}.json",
                dict(
                    forwarding=1,
                    browser="172.28.20.10 via 172.28.10.2 dev bench0",
                    server="172.28.10.10 via 172.28.20.2 dev bench0",
                    endpoints=dict(browser=settings, server=settings),
                    links=settings + "\n" + settings,
                    qdisc=queues,
                ),
            )
        for when in ("before", "after"):
            (folder / f"forward-{when}").write_text("1\n")
            write(folder / f"qdisc-{when}.json", queues)
            for role, route in (
                ("browser", "172.28.20.10 via 172.28.10.2 dev bench0"),
                ("server", "172.28.10.10 via 172.28.20.2 dev bench0"),
            ):
                (folder / f"{role}-route-{when}.txt").write_text(route)
                (folder / f"{role}-settings-{when}.txt").write_text(settings)
            (folder / f"router-links-{when}.txt").write_text(settings + "\n" + settings)
        (folder / "started").write_text(START + "\n")
        (folder / "commit").write_text("1" * 40 + "\n")
        (folder / "dirty").write_text("")
        (folder / "server-log.txt").write_text("offline synthetic server\n")
        write(folder / "qdisc-stable.json", queues)
        summaries = []
        for prefix in ("baseline", "stabilization-1"):
            quiet = [
                dict(
                    r,
                    cpu_start_lower_usec=max(
                        0, r["end_usec"] - r["interval_usec"] - 10000
                    ),
                    cpu_end_upper_usec=r["end_usec"] + 10000,
                )
                for r in resources
                if r["sample_index"] < 6
            ]
            for role in ("browser", "server", "router"):
                json_lines(
                    folder / f"{prefix}-{role}.jsonl",
                    [r for r in quiet if r["role"] == role],
                )
            (folder / f"{prefix}-marker").write_text("1000000\n")
            summary = quiet_summary(quiet, 1000000)
            write(folder / f"{prefix}-cpu.json", summary)
            summaries.append(summary)
        write(folder / "stabilization-1-comparison.json", compare(*summaries))
        json_lines(folder / "stabilization-1-queues.jsonl", [queues] * 11)
        write(
            folder / "stabilization.json",
            dict(
                stable=True,
                cpu_recovered=True,
                attempts=1,
                empty_queue_window_ms=1000,
                wait_limit_s=30,
            ),
        )
        context = context_snapshot(folder)
        write(folder / "context.json", context)
        write(directory / "context.json", context)
        write(
            folder / "environment.json",
            dict(
                host=(folder / "host.txt").read_text(),
                vm=read(folder / "vm.json"),
                limits=limits,
            ),
        )
        locks = {
            p: digest(Path(p))
            for p in (
                "src/client/package-lock.json",
                "src/runner/package-lock.json",
                "src/server/go.sum",
                "src/analysis/requirements.txt",
                "docker/config/images.lock.json",
            )
        }
        write(
            folder / "provenance.json",
            dict(
                images=limits,
                build=(folder / "server-build.txt").read_text(),
                lock_hashes=locks,
            ),
        )
        leaf_hash = hashlib.sha256(
            ssl.PEM_cert_to_DER_cert(context["leaf"])
        ).hexdigest()
        write(
            folder / "security.json",
            dict(
                secure_context=True,
                endpoint="https://bench.test:8443/",
                args=[],
                leaf_der_sha256=leaf_hash,
            ),
        )
        write(
            folder / "checks.json",
            dict(
                schema_version=1,
                checks=[
                    dict(
                        id="slot-count",
                        mandatory=True,
                        expected=3,
                        actual=3,
                        units="slots",
                        tolerance=0,
                        status="passed",
                        reason=None,
                        utc=START,
                        evidence=[
                            dict(
                                path="slots.jsonl",
                                sha256=digest(folder / "slots.jsonl"),
                            )
                        ],
                    )
                ],
            ),
        )
        manifest = dict(
            schema_version=1,
            protocol_version=1,
            **run,
            series=schedule["series"],
            series_id=schedule["series_id"],
            started_utc=START,
            ended_utc="2026-11-12T12:01:20Z",
            commit="1" * 40,
            dirty=False,
            protocol_sha256=digest(Path("configs/contracts/protocol.json")),
            config_sha256=digest(folder / "config.json"),
            schedule_sha256=digest(folder / "schedule.json"),
            technical_valid=True,
            reason=None,
        )
        for name in (
            "environment",
            "provenance",
            "security",
            "network_before",
            "network_after",
        ):
            manifest[name] = dict(
                path=name + ".json", sha256=digest(folder / (name + ".json"))
            )
        write(folder / "manifest.json", manifest)
        (folder / "SHA256SUMS").write_text(
            "".join(f"{digest(p)}  {p.name}\n" for p in sorted(folder.iterdir()))
        )
    return directory
