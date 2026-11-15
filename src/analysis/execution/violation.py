import argparse
import ssl
from datetime import datetime
from pathlib import Path

from jsonschema import ValidationError

from measurement.raw import digest, read, rows, validate_raw, write
from measurement.resources import validate_resources


def stop_reason(folder, schedule_file):
    folder, schedule_file = folder.resolve(), schedule_file.resolve()
    try:
        declared = {line.split("  ", 1)[1] for line in (folder / "SHA256SUMS").read_text().splitlines()}
        if not declared.issubset({p.name for p in folder.iterdir() if p.name != "SHA256SUMS"}):
            return "incomplete_log"
        manifest = read(folder / "manifest.json")
        certificate = ssl._ssl._test_decode_cert(str(folder / "leaf.pem"))
        start = datetime.fromisoformat(manifest["started_utc"].replace("Z", "+00:00")).timestamp()
        end = datetime.fromisoformat(manifest["ended_utc"].replace("Z", "+00:00")).timestamp()
        if not (ssl.cert_time_to_seconds(certificate["notBefore"]) <= start <= end <= ssl.cert_time_to_seconds(certificate["notAfter"])):
            return "certificate_expiry_or_clock_range"
        from execution.series import context_snapshot
        if context_snapshot(folder) != read(schedule_file.parent / "context.json"):
            return "environment_changed"
        completion = read(folder / "completion.json")
        spec = read(folder / "run.json")
        if completion["status"] != "complete" or (completion["warmup_rows"], completion["measurement_rows"]) != (spec["warmup_slots"], spec["measurement_slots"]):
            return "incomplete_completion_log"
        slots = rows(folder / "warmup.jsonl") + rows(folder / "slots.jsonl")
        events = rows(folder / "events.jsonl")
        if len(slots) != spec["warmup_slots"] + spec["measurement_slots"]:
            return "incomplete_slot_log"
        if sum(s["first_correct_echo_ms"] is not None for s in slots) != sum(e["type"] == "first_correct_echo" for e in events):
            return "incomplete_event_log"
        for phase, count in enumerate((spec["warmup_slots"], spec["measurement_slots"])):
            if count and not any(e["type"] == "phase_transition" and e["id"] and e["id"]["phase"] == phase and e["id"]["seq"] == "0" for e in events):
                return "incomplete_event_log"
        validate_resources(rows(folder / "resources.jsonl"), read(folder / "resource-window.json"))
        for name in ("checks.json", "context.json", "schedule.json", "stabilization.json", "qdisc-stable.json", "manifest.json", "completion.json", "server.json", "counters.json", "config.json", "security.json", "network_before.json", "network_after.json", "provenance.json", "environment.json", "SHA256SUMS"):
            if name != "SHA256SUMS" and name not in declared:
                return "incomplete_checksum_log"
            if not (folder / name).is_file():
                return "incomplete_log"
    except Exception:
        return "incomplete_log_or_resources"
    return None


def detect(folder, schedule_file):
    folder, schedule_file = folder.resolve(), schedule_file.resolve()
    if stop_reason(folder, schedule_file):
        return None

    try:
        validate_raw(folder, schedule_file)
    except ValidationError as error:
        return "schema", error.message
    except ValueError as error:
        message = str(error)
        categories = {
            "hash mismatch": "hash", "schedule hash": "hash", "check evidence hash": "hash",
            "protocol/config hash": "config", "config mismatch": "config", "run parameters": "config",
            "clock/grid": "clock", "clock/send": "clock", "clock/echo": "clock", "clock/write": "clock",
            "clock/event order": "clock", "clock/write event": "clock", "clock/duplicate event": "clock",
            "path/forwarding": "path", "path/route": "path", "path/offload": "path", "path/qdisc": "path",
            "path/endpoints": "path", "path/endpoint settings": "path",
            "schema/terminal outcome": "schema", "schema/terminal send state": "schema", "schema/terminal write": "schema",
            "schema/server snapshot": "schema", "schema/mandatory check failed": "schema", "schema/slot-count check": "schema",
            "schema/event identity": "schema", "schema/late event": "schema", "schema/phase event": "schema", "schema/API event": "schema",
        }
        if message in categories:
            return categories[message], message
    return None


def diagnose(folder, schedule_file, evidence, future_folder=None):
    folder, schedule_file = folder.resolve(), schedule_file.resolve()
    folder.relative_to(schedule_file.parent)
    fatal = stop_reason(folder, schedule_file)
    if fatal:
        (schedule_file.parent / "STOP").write_text(fatal + "\n")
        return False
    result = detect(folder, schedule_file)
    if result is None:
        return False
    manifest = read(folder / "manifest.json")
    run = next(r for r in read(schedule_file)["runs"] if r["run_id"] == manifest["run_id"])
    evidence.parent.mkdir(parents=True, exist_ok=True)
    write(evidence, dict(run_id=run["run_id"], attempt_id=run["attempt_id"], reason=result[0], error=result[1],
          folder=str((future_folder or folder).resolve().relative_to(schedule_file.parent)),
          identity={k:manifest[k] for k in ("run_id", "attempt_id", "block_id", "session_id", "series_id", "series")},
          context_sha256=digest(folder / "context.json"),
          files={p.name: digest(p) for p in folder.iterdir()}, schedule_sha256=digest(schedule_file)))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("schedule", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    if not diagnose(args.folder, args.schedule, args.evidence):
        raise SystemExit("no reproducible replaceable violation; log loss/OOM requires STOP")
