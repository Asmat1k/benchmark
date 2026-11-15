import argparse
from pathlib import Path

from series import advance, bind_context, validate_context, queue
from raw import diagnostic_interval, binding, digest, json, now, publish, read, require, rows, write


def runnable_run(directory, index, partial):
    schedule = read(directory/"schedule.json")
    from admission import phase_path
    phase_path(directory,schedule)
    require(0 <= index < len(schedule["runs"]), "invalid run index")
    run = schedule["runs"][index]
    require(partial.absolute().parent == directory.absolute() and partial.suffix == ".partial" and
            partial.is_dir() and not partial.is_symlink() and partial.resolve().parent == directory.resolve(),
            "invalid staging directory")
    if (directory/"admission.json").exists() or schedule["series"] in ("pilot","main") or any(b["design"] != "comparison" for b in schedule["blocks"]):
        from admission import admit
        admit(directory)
    require(directory.name == schedule["series_id"], "directory mismatch")
    from execution import is_exploratory, load_outcomes
    if is_exploratory(directory):
        outcomes = load_outcomes(directory)
        pending = next((r['index'] for r in outcomes['runs'] if r['status'] in ('planned','running')),None)
        require(index == pending, "run outside exploratory schedule order")
        return schedule, run
    require(not (directory/"STOP").exists(), "series stopped")
    attempt = next(a for a in read(directory/"ledger.json")["attempts"] if a["attempt_id"] == run["attempt_id"])
    require(attempt["status"] == "planned", "attempt not runnable")
    require(not (directory/"replacement.json").exists() and not (directory/"PENDING_REPLACEMENT").exists(), "replacement pending")
    remaining = queue(directory)
    require(remaining and run["attempt_id"] == remaining[0], "run outside scheduled block order")
    members = [r for r in schedule["runs"] if r["attempt_id"] == run["attempt_id"]]
    pending = [r for r in members if not (directory/"raw"/r["run_id"]).exists()]
    require(pending and run == pending[0], "run outside scheduled mode order")
    return schedule, run


def prepared_run(directory, index, partial):
    schedule, run = runnable_run(directory, index, partial)
    spec = read(partial/"run.json")
    require(all(spec.get(k) == run[k] for k in ("run_id","nonce","mode")), "partial run mismatch")
    require(read(partial/"schedule.json") == schedule, "partial schedule mismatch")
    return schedule, run


def bind_run_context(directory, index, partial):
    prepared_run(directory, index, partial)
    bind_context(directory, partial)


def run_spec(directory, index, partial):
    schedule, run = runnable_run(directory, index, partial)
    plan, thresholds = read(Path("configs/plan.json")), read(Path("configs/thresholds.json"))
    smoke = schedule["series"] == "smoke"
    require(not (directory/"raw"/run["run_id"]).exists(), "immutable run already exists")
    (partial/"schedule.json").write_bytes((directory/"schedule.json").read_bytes())
    write(partial/"run.json", {k:run[k] for k in ("run_id","nonce","mode")} |
          dict(warmup_slots=1 if smoke else plan["warmup_slots"],
               measurement_slots=3 if smoke else plan["measurement_slots"],interval_ms=diagnostic_interval(schedule, plan["interval_ms"]),
               queue_limit_bytes=plan["queue_limit_bytes"],deadline_ms=thresholds["deadline_ms"],horizon_ms=thresholds["horizon_ms"]))
    from execution import is_exploratory
    if is_exploratory(directory):
        (partial/'exploratory-execution').touch()
        write(partial/'execution-policy.json',dict(execution_policy='exploratory-browser-study-v2',
              policy=read(directory/'admission.json')['policy']))
    if smoke and schedule.get("collect_timer") and index == 0:
        (partial/"collect-timer").touch()
    if schedule.get("generator_hz"):
        (partial/"collect-backlog").touch()
    if plan.get("execution_policy") == "finite-browser-study-v1":
        (partial/"observe-cpu-recovery").touch()
    if (partial/"collect-timer").exists() or (partial/"collect-backlog").exists():
        from admission import sources
        write(partial/"collection-sources.json", sources())
    (partial/"monitoring-mode").write_text(run.get("monitoring","on"))
    print(run["profile"],run["forward_seed"],run["reverse_seed"],run["run_id"],30 if smoke else 90)


def complete(directory, index, partial):
    schedule_file = directory/"schedule.json"
    schedule, run = prepared_run(directory, index, partial)
    context = validate_context(directory, partial)
    require(read(partial/"context.json") == context == read(directory/"context.json"), "publication context mismatch")
    raw = directory/"raw"
    raw.mkdir(exist_ok=True)
    spec = read(partial/"run.json")
    data = read(partial/"page.json")
    for filename, records in (("slots",[s for s in data["slots"] if s["phase"]==1]),
                              ("warmup",[s for s in data["slots"] if s["phase"]==0]),("events",data["events"])):
        (partial/f"{filename}.jsonl").write_text("".join(json.dumps(r,allow_nan=False)+"\n" for r in records))
    (partial/"page.json").unlink()
    counter = read(partial/"counters.json")
    require(counter.pop("active")==0, "server still active")
    write(partial/"server.json",dict(schema_version=1,run_id=run["run_id"],**counter))
    write(partial/"config.json",{p:read(Path("configs")/f"{p}.json") for p in ("plan","thresholds","profiles")})
    write(partial/"provenance.json",dict(images=read(partial/"images.json"),lock_hashes={
        p:digest(Path(p)) for p in ["docker/config/images.lock.json","src/client/package-lock.json","src/runner/package-lock.json",
                                    "src/server/go.sum","src/analysis/requirements.txt"]}, build=(partial/"server-build.txt").read_text()))
    write(partial/"environment.json",dict(host=(partial/"host.txt").read_text(),vm=read(partial/"vm.json"),limits=read(partial/"limits.json")))
    for when in ("before","after"):
        write(partial/f"network_{when}.json",dict(forwarding=int((partial/f"forward-{when}").read_text()),
              qdisc=read(partial/f"qdisc-{when}.json"),browser=(partial/f"browser-route-{when}.txt").read_text(),
              server=(partial/f"server-route-{when}.txt").read_text(),links=(partial/f"router-links-{when}.txt").read_text(),
              endpoints={role:(partial/f"{role}-settings-{when}.txt").read_text() for role in ("browser","server")}))
    security=read(partial/"security.json")
    security.update(negotiation=(partial/"server-log.txt").read_text(),leaf=(partial/"leaf.pem").read_text())
    write(partial/"security.json",security)
    manifest=dict(schema_version=1,protocol_version=1,series=schedule["series"],series_id=schedule["series_id"],**run,
        started_utc=(partial/"started").read_text().strip(),ended_utc=now(),commit=(partial/"commit").read_text().strip(),
        dirty=bool((partial/"dirty").read_text().strip()),protocol_sha256=digest(Path("docs/protocol.md")),
        config_sha256=digest(partial/"config.json"),schedule_sha256=digest(partial/"schedule.json"),technical_valid=True,reason=None)
    for key in ("environment","provenance","security","network_before","network_after"):
        manifest[key]=binding(partial/f"{key}.json")
    write(partial/"manifest.json",manifest)
    write(partial/"completion.json",dict(schema_version=1,run_id=run["run_id"],status="complete",
        warmup_rows=len(rows(partial/"warmup.jsonl")),measurement_rows=len(rows(partial/"slots.jsonl")),reason=None))
    write(partial/"checks.json",dict(schema_version=1,checks=[dict(id="slot-count",mandatory=True,
        expected=spec["measurement_slots"],actual=len(rows(partial/"slots.jsonl")),units="slots",tolerance=0,
        status="passed" if spec["measurement_slots"]==len(rows(partial/"slots.jsonl")) else "failed",
        reason=None,utc=now(),evidence=[binding(partial/"slots.jsonl")])]))
    try:
        publish(partial,raw/run["run_id"],schedule_file)
    except Exception:
        from execution import is_exploratory
        if is_exploratory(directory):
            raise
        from violation import diagnose
        evidence = directory / "violations" / f"{run['run_id']}.json"
        if diagnose(partial, schedule_file, evidence, directory / "quarantine" / partial.name.removesuffix(".partial")):
            (directory / "PENDING_REPLACEMENT").write_text(run["attempt_id"])
            raise SystemExit(3)
        raise
    from execution import is_exploratory
    if not is_exploratory(directory):
        advance(directory, schedule, run)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action", choices=["prepare","complete","context"])
    p.add_argument("directory",type=Path)
    p.add_argument("index",type=int)
    p.add_argument("partial",type=Path)
    args=p.parse_args()
    if args.action == "context":
        bind_run_context(args.directory, args.index, args.partial)
    else:
        (run_spec if args.action=="prepare" else complete)(args.directory,args.index,args.partial)
