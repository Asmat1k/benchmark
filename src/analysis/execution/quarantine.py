import sys
from pathlib import Path

from measurement.raw import read, write


# Move invalid raw artifacts into quarantine.
def quarantine(directory, index, project):
    from execution.execution import is_exploratory

    if is_exploratory(directory):
        return
    (directory / "STOP").write_text(f"incomplete_log/OOM/orchestration: {project}\n")
    schedule = read(directory / "schedule.json")
    failed = schedule["runs"][index]
    audit = directory / "audit" / failed["attempt_id"]
    audit.mkdir(parents=True, exist_ok=True)
    for run in schedule["runs"]:
        if run["attempt_id"] == failed["attempt_id"]:
            path = directory / "raw" / run["run_id"]
            if path.exists():
                path.rename(audit / path.name)
    ledger = read(directory / "ledger.json")
    attempt = next(
        a for a in ledger["attempts"] if a["attempt_id"] == failed["attempt_id"]
    )
    attempt.update(status="stopped", reason=f"incomplete_log: quarantine/{project}")
    write(directory / "ledger.tmp", ledger)
    (directory / "ledger.tmp").replace(directory / "ledger.json")


if __name__ == "__main__":
    quarantine(Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
