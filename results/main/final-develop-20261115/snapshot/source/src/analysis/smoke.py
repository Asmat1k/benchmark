import sys
from pathlib import Path

from raw import read, require, rows, validate_raw


def check_smoke(directory):
    runs = read(directory / "schedule.json")["runs"]
    require(len(runs) == 2 and {r["mode"] for r in runs} == {"WS", "WT-S"} and
            all(r["profile"] == "baseline" for r in runs), "smoke requires baseline pair")
    for run in runs:
        folder = directory / "raw" / run["run_id"]
        validate_raw(folder, directory / "schedule.json")
        check_echoes(folder)


def check_echoes(folder):
    for name, count in (("warmup", 1), ("slots", 3)):
        slots = rows(folder / f"{name}.jsonl")
        require(len(slots) == count and all(s["completed_by_horizon"] and s["echo_bytes"] == 256 for s in slots), "smoke exact echoes missing")


if __name__ == "__main__":
    check_smoke(Path(sys.argv[1]))
