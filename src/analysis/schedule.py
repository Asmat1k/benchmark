import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SERIES = ("smoke", "verify", "diagnostic", "pilot", "main")
MODES = ("WS", "WT-S", "WT-D")
PROFILES = ("r20p0", "r20p1", "r80p0", "r80p1")


def seeds(series, series_id, branch, *indexes):
    identity = int.from_bytes(hashlib.sha256(series_id.encode()).digest()[:8], "big")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [20261108, identity], spawn_key=(SERIES.index(series), branch, *indexes))))


def make_schedule(series, series_id, blocks=20, sessions=4, datagrams=False, baseline=False):
    if sessions < 1 or blocks < sessions:
        raise ValueError("each session requires at least one block per profile")
    if baseline and series not in ("smoke", "verify", "diagnostic"):
        raise ValueError("baseline is diagnostic only")
    rng = seeds(series, series_id, 0)
    schedule = dict(schema_version=1, series=series, series_id=series_id,
                    master_seed=20261108, blocks=[], runs=[])
    for session in range(sessions):
        profiles = [p for p in (("baseline",) if baseline else PROFILES) for _ in range(session, blocks, sessions)]
        for profile in rng.permutation(profiles):
            i = len(schedule["blocks"])
            modes = list(rng.permutation(MODES if datagrams else MODES[:2]))
            block = dict(block_id=f"b{i}", session_id=f"s{session}", attempt_id=f"b{i}-a0",
                         profile=profile, order_index=i, modes=modes, seed=int(rng.bit_generator.random_raw()),
                         status="planned", reason=None, replacement_of=None, design="comparison")
            schedule["blocks"].append(block)
            schedule["runs"].extend(block_runs(schedule, block, i))
    return schedule


def block_runs(schedule, block, index):
    for j, mode in enumerate(block["modes"]):
        base = (schedule["series"], schedule["series_id"])
        draw = lambda branch: int(seeds(*base, branch, index, 0 if block["design"] == "monitoring" and branch in (1,2) else j).bit_generator.random_raw())
        yield dict(**({"monitoring":block["monitoring_order"][j]} if block["design"] == "monitoring" else {}), run_id=f"{block['attempt_id']}-m{j}", mode=mode,
                   nonce=str(draw(3)), forward_seed=draw(1), reverse_seed=draw(2),
                   **{k: block[k] for k in ("block_id", "session_id", "attempt_id",
                                            "profile", "order_index", "replacement_of")})


def replace_block(schedule, attempt_id, reason, remaining):
    if reason not in {"hash", "config", "schema", "clock", "path"}:
        raise ValueError("block replacement requires a documented technical violation")
    blocks = schedule["blocks"]
    old = next(b for b in blocks if b["attempt_id"] == attempt_id)
    if old["status"] == "quarantined":
        raise ValueError("attempt already replaced")
    index = len(blocks)
    rng = seeds(schedule["series"], schedule["series_id"], 5, index)
    old.update(status="quarantined", reason=reason)
    new = dict(old, attempt_id=f"{old['block_id']}-r{index}", replacement_of=attempt_id,
               status="planned", reason=None, seed=int(rng.bit_generator.random_raw()),
               modes=list(rng.permutation(old["modes"])))
    position = int(rng.integers(len(remaining) + 1))
    remaining.insert(position, new["attempt_id"])
    blocks.append(new)
    schedule["runs"].extend(block_runs(schedule, new, index))
    return new


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("series", choices=SERIES)
    p.add_argument("directory", type=Path)
    p.add_argument("--blocks", type=int, default=20)
    p.add_argument("--sessions", type=int, default=4)
    p.add_argument("--datagrams", action="store_true")
    p.add_argument("--baseline", action="store_true")
    args = p.parse_args()
    schedule = make_schedule(args.series, args.directory.name, args.blocks, args.sessions, args.datagrams, args.baseline)
    args.directory.mkdir(parents=True, exist_ok=True)
    with (args.directory / "schedule.json").open("x") as output:
        json.dump(schedule, output, indent=2)
    with (args.directory / "ledger.json").open("x") as output:
        json.dump(dict(schema_version=1, series_id=args.directory.name, attempts=schedule["blocks"]), output, indent=2)
