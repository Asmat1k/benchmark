import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"src/analysis"))
from admission import ref, sources
from raw import now, read, rows, validate_raw
from resources import validate_resources


def quantile(values, fraction):
    return sorted(values)[math.ceil(len(values)*fraction)-1] if values else None


def inspect_run(directory, run, hz, expected_context):
    folder = directory/"raw"/run["run_id"]
    result = dict(mode=run["mode"], frequency_hz=hz, run_id=run["run_id"], raw=str(folder),
                  status="raw-missing", unknown=True)
    if not folder.exists():
        return result
    try:
        validate_raw(folder, directory/"schedule.json")
        slots = rows(folder/"slots.jsonl")
        events = rows(folder/"events.jsonl")
        samples = rows(folder/"resources.jsonl")
        window = read(folder/"resource-window.json")
        context = read(folder/"context.json")
        if context != expected_context or context != read(directory/"context.json"):
            raise ValueError("published raw environment differs from admitted environment")
        validate_resources(samples, window)
        backlog = rows(folder/"backlog.jsonl")
        queues = [q for record in backlog for q in record["queues"]]
        sent = [s for s in slots if s["t_send_ms"] is not None]
        completed = [s for s in slots if s["first_correct_echo_ms"] is not None and
                     s["first_correct_echo_ms"] <= s["t_plan_ms"]+5000]
        rtts = [s["first_correct_echo_ms"]-s["t_send_ms"] for s in completed]
        lags = [s["t_send_ms"]-s["t_plan_ms"] for s in sent]
        timely = sum(s["first_correct_echo_ms"] <= s["t_plan_ms"]+100 for s in completed)
        result.update(status="sealed-validated", unknown=False, seal=ref(folder/"SHA256SUMS"),
                      source_exact=read(folder/"collection-sources.json")==sources(),
                      environment=ref(folder/"context.json"), started=read(folder/"manifest.json")["started_utc"],
                      ended=read(folder/"manifest.json")["ended_utc"], slots=len(slots), sent=len(sent),
                      states=dict(Counter(s["send_state"] for s in slots)), completed=len(completed),
                      timely_100ms=timely, late_within_5000ms=len(completed)-timely,
                      missing_within_5000ms=len(slots)-len(completed),
                      events=dict(Counter(e["type"] for e in events)),
                      rtt_ms=dict(n=len(rtts), p50=quantile(rtts,.5), p95=quantile(rtts,.95),
                                  p99=quantile(rtts,.99), max=max(rtts,default=None)),
                      lag_ms=dict(p99=quantile(lags,.99), max=max(lags,default=None)),
                      grid_exact=all(s["t_plan_ms"]==slots[0]["t_plan_ms"]+i*1000/hz for i,s in enumerate(slots)),
                      observed_hz=(len(sent)-1)*1000/(sent[-1]["t_send_ms"]-sent[0]["t_send_ms"]) if len(sent)>1 else None,
                      resource_window=window, resource_samples=len(samples),
                      router=dict(coverage=bool(backlog) and backlog[0]["usec"]<=window["start_usec"] and
                                  backlog[-1]["usec"]>=window["end_usec"] and
                                  all(0<b["usec"]-a["usec"]<=1500000 for a,b in zip(backlog,backlog[1:])),
                                  peak_backlog_bytes=max(q["backlog"] for q in queues),
                                  max_drops=max(q["drops"] for q in queues),
                                  queues_with_full_limit=sum(q["qlen"]>=q["limit"] for q in queues)), resources={})
        for role in ("browser", "server", "router"):
            resource = [s for s in samples if s["role"]==role]
            limit = next(s["cpu"]/1e9 for s in context["services"] if s["role"]==role)
            result["resources"][role] = dict(cpu_limit_cores=limit,
                peak_cpu_pct_limit=max(100*s["cpu_usage_usec"]/s["interval_usec"]/limit for s in resource),
                throttling_pct=100*sum(s["throttled_usec"] for s in resource)/sum(s["interval_usec"] for s in resource),
                oom=sum(s["oom"] for s in resource),
                peak_memory_bytes=max(s["memory_current"] for s in resource))
    except Exception as error:
        result.update(status="technical-unknown", error=str(error), unknown=True)
    return result


parser = argparse.ArgumentParser()
parser.add_argument("execution", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
record = read(args.execution/"execution.json")
directories = []
reports = []
for line in (args.execution/"stdout.log").read_text().splitlines():
    path = Path(line.strip())
    if str(path).startswith("results/verify/diagnostic/generator-"):
        if (path/"schedule.json").is_file() and path not in directories:
            directories.append(path)
        if path.name=="report.json" and path.is_file():
            reports.append(path)
results = []
for directory in directories:
    schedule = read(directory/"schedule.json")
    for run in schedule["runs"]:
        results.append(inspect_run(directory,run,schedule["generator_hz"],read(Path(record["environment"]))))
report = read(reports[-1]) if reports else None
summary = dict(utc=now(), reviewer="internal-independent-subagent", execution=ref(args.execution/"execution.json"),
               execution_exit=record["exit"], schedules=[ref(d/"schedule.json") for d in directories],
               expected_runs=6, scheduled_runs=len(results), retained_runs=len(results),
               sealed_validated=sum(r["status"]=="sealed-validated" for r in results),
               technical_unknown=sum(r["unknown"] for r in results), runs=results,
               official_report=ref(reports[-1]) if reports else None,
               official_status=report["status"] if report else "not-published",
               interpretation="All scheduled outcomes retained. 100 Hz is reserve only; failed performance does not imply invalid data. No RTT imputation or lag subtraction.")
args.output.mkdir(parents=True,exist_ok=False)
(args.output/"review.json").write_text(json.dumps(summary,indent=2,allow_nan=False)+"\n")
lines = ["# Независимая внутренняя проверка браузерного генератора", "",
         f"Официальный результат: {summary['official_status']}; exit сбора: {record['exit']}.",
         f"Предусмотрено 6 запусков; расписано {len(results)}; проверено sealed raw {summary['sealed_validated']}; технически неизвестно {summary['technical_unknown']}.", "",
         "| Hz | Mode | Status | Slots | Sent | Completed | Late | Missing | Lag p99 ms | RTT p99 ms |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in results:
    lines.append("| "+" | ".join(str(v) for v in (r['frequency_hz'],r['mode'],r['status'],r.get('slots'),r.get('sent'),r.get('completed'),r.get('late_within_5000ms'),r.get('missing_within_5000ms'),r.get('lag_ms',{}).get('p99'),r.get('rtt_ms',{}).get('p99')))+" |")
lines += ["", summary["interpretation"], "", "Полные состояния slots, ресурсы по фактическому CPU limit, backlog/drops, seals и provenance приведены в review.json. Оценки RTT условны на возвращённые ответы; все missing сохранены в знаменателе."]
(args.output/"review.md").write_text("\n".join(lines)+"\n")
print(args.output)
