import argparse
import os
from pathlib import Path

from measurement.raw import digest, read, require, write
from execution.schedule import replace_block
from execution.series import measurement_lock, queue
from execution.violation import detect


def atomic(path, value):
    temporary = path.with_suffix(".tmp")
    write(temporary, value)
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def replace(directory, attempt_id, reason, evidence, checkpoint=lambda stage: None):
    directory, evidence = directory.resolve(), evidence.resolve()
    with measurement_lock():
        return replace_locked(directory, attempt_id, reason, evidence, checkpoint)


def replace_locked(directory, attempt_id, reason, evidence, checkpoint):
    require(not (directory / "STOP").exists(), "stopped series requires a new version")
    completed = directory / "audit" / attempt_id / "transaction.json"
    if completed.exists():
        transaction = read(completed)
        require(transaction["evidence_sha256"] == digest(evidence), "different completed replacement")
        return transaction["replacement"]
    journal = directory / "replacement.json"
    if journal.exists():
        transaction = read(journal)
        require(transaction["attempt_id"] == attempt_id and transaction["evidence_sha256"] == digest(evidence), "different replacement pending")
    else:
        proof = read(evidence)
        require(proof["attempt_id"] == attempt_id and proof["reason"] == reason, "foreign evidence")
        source = (directory / proof["folder"]).resolve()
        require(source.is_relative_to(directory.resolve()), "foreign evidence path")
        require(proof["files"] == {p.name: digest(p) for p in source.iterdir()}, "evidence changed")
        require(proof["schedule_sha256"] == digest(directory / "schedule.json"), "foreign evidence schedule")
        require(detect(source, directory / "schedule.json") == (reason, proof["error"]), "violation not reproducible")
        schedule = read(directory / "schedule.json")
        run = next(r for r in schedule["runs"] if r["run_id"] == proof["run_id"])
        manifest = read(source / "manifest.json")
        archived = read(source / "schedule.json")
        require(run["attempt_id"] == attempt_id and
                all(manifest.get(k) == run[k] for k in run) and run in archived["runs"] and
                manifest["run_id"] == proof["run_id"] and manifest["attempt_id"] == proof["attempt_id"] and
                proof["identity"] == {k:manifest[k] for k in ("run_id", "attempt_id", "block_id", "session_id", "series_id", "series")} and
                proof["context_sha256"] == digest(source / "context.json") == digest(directory / "context.json"), "foreign evidence run/context")
        ledger = read(directory / "ledger.json")
        old = next(a for a in ledger["attempts"] if a["attempt_id"] == attempt_id)
        require(old["status"] in ("complete", "planned"), "attempt cannot be replaced")
        remaining = [a for a in queue(directory) if a != attempt_id]
        new = replace_block(schedule, attempt_id, reason, remaining)
        old.update(status="quarantined", reason=reason)
        ledger["attempts"].append(new)
        audit = directory / "audit" / attempt_id
        audit.mkdir(parents=True, exist_ok=True)
        moves = []
        for member in schedule["runs"]:
            if member["attempt_id"] == attempt_id:
                path = source if member["run_id"] == run["run_id"] else directory / "raw" / member["run_id"]
                if path.exists():
                    moves.append([str(path.relative_to(directory)), str((audit / member["run_id"]).relative_to(directory))])
        transaction = dict(attempt_id=attempt_id, evidence_sha256=digest(evidence), schedule=schedule,
                           ledger=ledger, queue=remaining, moves=moves, replacement=new)
        (audit / "schedule.json").write_bytes((directory / "schedule.json").read_bytes())
        (audit / "evidence.json").write_bytes(evidence.read_bytes())
        atomic(journal, transaction)
    for index, (before, after) in enumerate(transaction["moves"]):
        source, destination = directory / before, directory / after
        if source.exists():
            require(not destination.exists(), "audit destination already exists")
            source.rename(destination)
            for parent in (source.parent, destination.parent):
                fd = os.open(parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        else:
            require(destination.exists(), "replacement raw lost")
        checkpoint(f"move-{index}")
    atomic(directory / "queue.json", transaction["queue"])
    atomic(directory / "schedule.json", transaction["schedule"])
    checkpoint("before-ledger")
    atomic(directory / "ledger.json", transaction["ledger"])
    (directory / "PENDING_REPLACEMENT").unlink(missing_ok=True)
    journal.rename(directory / "audit" / attempt_id / "transaction.json")
    return transaction["replacement"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("attempt_id")
    parser.add_argument("reason", choices=("hash", "config", "schema", "clock", "path"))
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    replace(args.directory, args.attempt_id, args.reason, args.evidence)
