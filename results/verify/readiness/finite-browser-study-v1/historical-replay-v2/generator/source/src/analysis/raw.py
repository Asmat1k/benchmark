import hashlib
import json
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path.cwd()


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path):
    return dict(path=path.name, sha256=digest(path))


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_hashes(folder):
    checksums = {}
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        sha, name = line.split("  ", 1)
        require(Path(name).name == name and name not in checksums, "invalid checksum entry")
        checksums[name] = sha
    require(checksums == {f.name: digest(f) for f in folder.iterdir() if f.name != "SHA256SUMS"}, "hash mismatch")
    return checksums


def validate_stabilization(folder, plan):
    stabilization = read(folder/"stabilization.json")
    require(stabilization["empty_queue_window_ms"] >= 1000 and stabilization["wait_limit_s"] <= 30,
            "stabilization bounds")
    queues = [q for q in read(folder/"qdisc-stable.json") if q["kind"] == "netem"]
    require(len(queues) == 2 and all(q["backlog"] == 0 and q["qlen"] == 0 for q in queues), "queues not empty")
    if plan.get("execution_policy") != "finite-browser-study-v1":
        require(stabilization["stable"], "stabilization")
        return
    from stabilization_cpu import compare, quiet_summary
    attempt = stabilization["attempts"]
    require(isinstance(attempt, int) and attempt >= 1, "stabilization attempt")
    summaries = []
    for prefix in ("baseline", f"stabilization-{attempt}"):
        records = [r for role in ("browser", "server", "router") for r in rows(folder/f"{prefix}-{role}.jsonl")]
        summary = quiet_summary(records, int((folder/f"{prefix}-marker").read_text()))
        require(summary == read(folder/f"{prefix}-cpu.json"), "stabilization CPU primary correspondence")
        summaries.append(summary)
    comparison = compare(*summaries)
    require(comparison == read(folder/f"stabilization-{attempt}-comparison.json"), "stabilization comparison correspondence")
    recovered = comparison["status"] == "passed"
    require(stabilization["stable"] is recovered and stabilization["cpu_recovered"] is recovered,
            "stabilization CPU observation mismatch")
    snapshots = rows(folder/f"stabilization-{attempt}-queues.jsonl")
    require(len(snapshots) == 11 and all(len([q for q in snapshot if q["kind"] == "netem"]) == 2 and
            all(q["backlog"] == q["qlen"] == 0 for q in snapshot if q["kind"] == "netem")
            for snapshot in snapshots), "stabilization empty queue window")


def diagnostic_interval(schedule, default):
    frequency = schedule.get("generator_hz")
    if frequency is None:
        return default
    require(schedule["series"] == "diagnostic" and frequency in (20, 100) and
            all(block["profile"] == "baseline" and block["design"] == "comparison" for block in schedule["blocks"]),
            "generator frequency requires a baseline diagnostic schedule")
    return 1000 // frequency


def validate_raw(folder, schedule_file, config_root=ROOT / "configs"):
    checksums=validate_hashes(folder)
    manifest = read(folder / "manifest.json")
    snapshot = folder / "schedule.json"
    require(manifest["schedule_sha256"] == digest(snapshot if snapshot.exists() else schedule_file), "schedule hash")
    schedule = read(schedule_file)
    run = next(r for r in schedule["runs"] if r["run_id"] == manifest["run_id"])
    require(all(manifest[k] == v for k, v in run.items()), "schedule mismatch")
    if snapshot.exists():
        archived = read(snapshot)
        require(run in archived["runs"] and archived["series"] == schedule["series"] and
                archived["series_id"] == schedule["series_id"], "schedule snapshot mismatch")
    require(0 <= int(run["nonce"]) < 2**64, "nonce range")
    require(manifest["series"] == schedule["series"] and manifest["series_id"] == schedule["series_id"], "series mismatch")
    require(manifest["technical_valid"], "technical violation")
    for key in ("provenance", "environment", "network_before", "network_after", "security"):
        ref = manifest[key]
        require(checksums.get(ref["path"]) == ref["sha256"], key)
    require(manifest["config_sha256"] == digest(folder / "config.json") and
            manifest["protocol_sha256"] == digest(ROOT / "docs/protocol.md"), "protocol/config hash")
    config = read(folder / "config.json")
    require(config == {p:read(config_root / f"{p}.json") for p in ("plan","thresholds","profiles")}, "config mismatch")
    for name, value in config.items():
        Draft202012Validator(read(ROOT / "docs/schemas" / f"{name}.schema.json")).validate(value)
    security = read(folder / manifest["security"]["path"])
    require(security["secure_context"] and security["endpoint"] == "https://bench.test:8443/", "security/origin")
    require(not any("ignore-certificate-errors" in arg or "disable-web-security" in arg
                    for arg in security["args"]), "security/flags")
    certificate = ssl._ssl._test_decode_cert(str(folder / "leaf.pem"))
    start = datetime.fromisoformat(manifest["started_utc"].replace("Z", "+00:00")).timestamp()
    end = datetime.fromisoformat(manifest["ended_utc"].replace("Z", "+00:00")).timestamp()
    require(ssl.cert_time_to_seconds(certificate["notBefore"]) <= start <= end <=
            ssl.cert_time_to_seconds(certificate["notAfter"]), "certificate expiry/clock")
    require(hashlib.sha256(ssl.PEM_cert_to_DER_cert((folder / "leaf.pem").read_text())).hexdigest() ==
            security["leaf_der_sha256"], "certificate pin")
    spec = read(folder / "run.json")
    smoke = manifest["series"] == "smoke"
    sizes = (1,3) if smoke else (config["plan"]["warmup_slots"],config["plan"]["measurement_slots"])
    require((spec["warmup_slots"],spec["measurement_slots"]) == sizes and
            spec["nonce"] == manifest["nonce"] and spec["mode"] == manifest["mode"] and
            spec["deadline_ms"] == config["thresholds"]["deadline_ms"] and
            spec["horizon_ms"] == config["thresholds"]["horizon_ms"] and
            spec["interval_ms"] == diagnostic_interval(schedule, config["plan"]["interval_ms"]) and
            spec["queue_limit_bytes"] == config["plan"]["queue_limit_bytes"], "run parameters")
    groups = {name: [read(folder / (name + ".json"))] for name in ("manifest","server","checks","completion")}
    groups.update(slot=rows(folder/"warmup.jsonl")+rows(folder/"slots.jsonl"),
                  event=rows(folder/"events.jsonl"),resource=rows(folder/"resources.jsonl"))
    for name, records in groups.items():
        validator = Draft202012Validator(read(ROOT/"docs/schemas"/f"{name}.schema.json"), format_checker=FormatChecker())
        for record in records:
            validator.validate(record)
            require(record.get("run_id", run["run_id"]) == run["run_id"], "run ID mismatch")
    completion = groups["completion"][0]
    require(completion["status"] == "complete" and
            (completion["warmup_rows"], completion["measurement_rows"]) == sizes, "incomplete log")
    require(len(groups["slot"]) == sum(sizes) and len(rows(folder/"warmup.jsonl")) == sizes[0], "slot count")
    start = groups["slot"][0]["t_plan_ms"]
    for index, s in enumerate(groups["slot"]):
        phase = int(index >= sizes[0])
        require((s["phase"], s["nonce"], s["seq"]) == (phase,run["nonce"],str(index-phase*sizes[0])), "slot ID")
        require(s["t_plan_ms"] == start + index * spec["interval_ms"], "clock/grid")
        sent, echo, plan = s["t_send_ms"], s["first_correct_echo_ms"], s["t_plan_ms"]
        require((sent is not None) == (s["send_state"] in ("sent","local_api_error")), "send invocation")
        require(sent is not None or (s["api_return_ms"] is None and s["send_lag_ms"] is None and
                s["write_fulfilled_ms"] is None and echo is None), "unsent timestamps")
        require(sent is None or (sent >= plan and s["api_return_ms"] >= sent and s["send_lag_ms"] == sent-plan), "clock/send")
        require(echo is None or (sent is not None and echo >= sent and s["echo_bytes"] == 256), "clock/echo")
        require(s["write_fulfilled_ms"] is None or (sent is not None and s["write_fulfilled_ms"] >= sent), "clock/write")
        require(s["ontime"] == (echo is not None and echo <= plan + spec["deadline_ms"]) and
                s["completed_by_horizon"] == (echo is not None and echo <= plan + spec["horizon_ms"]), "outcome")
    previous = 0
    for i, event in enumerate(groups["event"]):
        require(event["event_index"] == i and event["t_ms"] >= previous, "clock/event order")
        previous = event["t_ms"]
        if event["id"] is not None:
            identity = event["id"]
            if event["type"] not in ("unknown_ID", "invalid_frame"):
                require(identity["nonce"] == run["nonce"] and
                        0 <= int(identity["seq"]) < sizes[identity["phase"]], "event ID")
    def matching(kind, slot):
        identity = {k: slot[k] for k in ("phase", "nonce", "seq")}
        return [e for e in groups["event"] if e["type"] == kind and e["id"] == identity]

    for slot in groups["slot"]:
        echo = slot["first_correct_echo_ms"]
        echoes = matching("first_correct_echo", slot)
        require(len(echoes) == int(echo is not None) and
                (echo is None or echoes[0]["t_ms"] == echo), "incomplete echo events")
        if slot["seq"] == "0":
            require(len(matching("phase_transition", slot)) == 1, "incomplete phase events")
        if echo is not None:
            terminal = "ontime" if slot["ontime"] else "late_before_horizon" if slot["completed_by_horizon"] else "late_after_horizon"
            require(slot["terminal_reason"] == terminal, "schema/terminal outcome")
            if not slot["ontime"]:
                require(any(e["t_ms"] == echo for e in matching(terminal, slot)), "incomplete late events")
        elif slot["send_state"] != "sent":
            require(slot["terminal_reason"] == slot["send_state"], "schema/terminal send state")
        else:
            rejected = matching("write_rejection", slot)
            require(slot["terminal_reason"] == ("write_rejection" if rejected else "horizon"), "schema/terminal write")
        if slot["send_state"] == "local_api_error":
            require(len(matching("api_error", slot)) == 1, "incomplete API event")
        if slot["send_state"] == "local_backpressure_error":
            require(any(e["details"].get("bytes") == slot["queue_before_bytes"] for e in matching("buffer_sample", slot)), "incomplete buffer event")
        if slot["send_state"] == "not_sent_after_disconnect":
            require(any(e["type"] == "disconnect" and e["t_ms"] < slot["t_plan_ms"] + spec["interval_ms"] for e in groups["event"]), "incomplete disconnect event")
    for event in groups["event"]:
        if event["type"] in ("api_error", "write_rejection", "buffer_sample", "duplicate", "late_before_horizon", "late_after_horizon", "phase_transition"):
            identity = event["id"]
            require(identity is not None, "schema/event identity")
            slot = next(s for s in groups["slot"] if all(s[k] == identity[k] for k in ("phase", "nonce", "seq")))
            if event["type"] in ("late_before_horizon", "late_after_horizon"):
                require(slot["terminal_reason"] == event["type"] and slot["first_correct_echo_ms"] == event["t_ms"], "schema/late event")
            if event["type"] == "phase_transition":
                require(slot["seq"] == "0", "schema/phase event")
            if event["type"] == "api_error":
                require(slot["send_state"] == "local_api_error" and event["t_ms"] >= slot["api_return_ms"], "schema/API event")
            if event["type"] == "write_rejection":
                require(slot["t_send_ms"] is not None and event["t_ms"] >= slot["t_send_ms"], "clock/write event")
            if event["type"] == "duplicate":
                require(slot["first_correct_echo_ms"] is not None and event["t_ms"] >= slot["first_correct_echo_ms"], "clock/duplicate event")
    counters = read(folder / "counters.json")
    require(counters["active"] == 0, "server not idle")
    require(all(groups["server"][0][p] == counters[p] for p in ("warmup", "measurement")), "schema/server snapshot")
    if (folder / "schedule.json").exists():
        validate_stabilization(folder, config["plan"])
    from resources import validate_resources
    validate_resources(groups["resource"], read(folder / "resource-window.json"))
    if run.get("monitoring") == "off":
        block = next(b for b in schedule["blocks"] if b["attempt_id"] == run["attempt_id"])
        require(block["design"] == "monitoring", "monitoring off outside on/off design")
        window = read(folder/"monitoring-window.json")
        require(window["monitoring"] == "off" and window["resource_metrics_available"] is False and
                window["unobserved_start_usec"] < window["unobserved_end_usec"] <=
                read(folder/"resource-window.json")["start_usec"], "off observation window")
        for role in ("browser","server","router"):
            require((folder/f"{role}-oom-before.txt").read_bytes() == (folder/f"{role}-oom-after.txt").read_bytes(), "resources OOM during off window")
            baseline = rows(folder/f"{role}-baseline.jsonl")
            require(baseline and all(r["oom"] == 0 for r in baseline), "missing off baseline/OOM")
    resource = groups["resource"]
    require({r["role"] for r in resource} == {"server","browser","router"} and not any(r["oom"] for r in resource), "resources/OOM")
    for phase, name in enumerate(("warmup", "measurement")):
        counts = groups["server"][0][name]
        require(counts["received"] == counts["invalid"] + counts["write_attempted"] and
                counts["write_attempted"] == counts["echoed"] + counts["errors"], "server counts")
    for check in groups["checks"][0]["checks"]:
        require(not check["mandatory"] or check["status"] == "passed", "schema/mandatory check failed")
        if check["id"] == "slot-count":
            require(check["actual"] == check["expected"] == sizes[1], "schema/slot-count check")
        for ref in check["evidence"]:
            require(checksums.get(ref["path"]) == ref["sha256"], "check evidence hash")
    from series import context_snapshot
    require(context_snapshot(folder) == read(folder / "context.json") == read(schedule_file.parent / "context.json"), "environment changed: context")
    environment = read(folder / manifest["environment"]["path"])
    provenance = read(folder / manifest["provenance"]["path"])
    require(environment == dict(host=(folder/"host.txt").read_text(), vm=read(folder/"vm.json"), limits=read(folder/"limits.json")), "environment publication mismatch")
    require(provenance["images"] == read(folder/"images.json") == read(folder/"limits.json") and
            provenance["build"] == (folder/"server-build.txt").read_text() and
            provenance["lock_hashes"] == {p:digest(Path(p)) for p in ("docker/images.lock.json", "src/client/package-lock.json", "src/runner/package-lock.json", "src/server/go.sum", "src/analysis/requirements.txt")}, "provenance publication mismatch")
    for when in ("network_before", "network_after"):
        snapshot = read(folder / manifest[when]["path"])
        require(snapshot["forwarding"] == 1, "path/forwarding")
        for name, peer, gateway in [("browser",20,10),("server",10,20)]:
            require(f"172.28.{peer}.10 via 172.28.{gateway}.2 dev bench0" in snapshot[name], "path/route")
        require(set(snapshot["endpoints"]) == {"browser", "server"}, "path/endpoints")
        for settings in snapshot["endpoints"].values():
            require("mtu 1500" in settings and all(f"{f}: off" in settings for f in ("tcp-segmentation-offload", "generic-segmentation-offload", "generic-receive-offload", "large-receive-offload")), "path/endpoint settings")
        for feature in ("tcp-segmentation-offload", "generic-segmentation-offload",
                        "generic-receive-offload", "large-receive-offload"):
            require(snapshot["links"].count(f"{feature}: off") == 2, "path/offload")
        profile = dict(egress_delay_ms=0, egress_loss_pct=0) if run["profile"] == "baseline" else next(p for p in config["profiles"]["profiles"] if p["id"] == run["profile"])
        for iface, key in (("to_server","forward_seed"),("to_browser","reverse_seed")):
            q = next(q for q in snapshot["qdisc"] if q.get("dev") == iface and q["kind"] == "netem")
            opt = q["options"]
            require(opt["seed"] == run[key] and opt.get("delay",{}).get("delay",0) == profile["egress_delay_ms"]/1000 and
                    opt.get("delay",{}).get("jitter",0) == 0 and opt.get("delay",{}).get("correlation",0) == 0 and
                    opt.get("loss-random",{}).get("loss",0) == profile["egress_loss_pct"]/100 and
                    opt["limit"] == config["profiles"]["limit_packets"] and
                    opt["rate"]["rate"] == config["profiles"]["rate_mbit_s"]*125000, "path/qdisc")


def publish(folder, destination, schedule_file):
    files = sorted(folder.iterdir())
    (folder / "SHA256SUMS").write_text("".join(f"{digest(p)}  {p.name}\n" for p in files))
    validate_raw(folder, schedule_file)
    for p in folder.iterdir():
        with p.open("rb") as f:
            os.fsync(f.fileno())
    require(not destination.exists(), "immutable raw already exists")
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    folder.rename(destination)
    fd = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
