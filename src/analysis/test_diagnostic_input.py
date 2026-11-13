import json
import tempfile
import unittest
from pathlib import Path

from acceptance import generator_gate
from diagnostic_input import diagnostic_raw, generator_run
from raw import diagnostic_interval, read, write


class DiagnosticInputTests(unittest.TestCase):
    def test_only_baseline_diagnostic_can_override_interval(self):
        schedule = dict(series="diagnostic", blocks=[dict(design="comparison",profile="baseline")],generator_hz=100)
        self.assertEqual(diagnostic_interval(schedule, 50), 10)
        for series in ("smoke", "verify", "pilot", "main"):
            with self.assertRaises(ValueError):
                diagnostic_interval(dict(schedule, series=series), 50)
        with self.assertRaises(ValueError):
            diagnostic_interval(dict(schedule, blocks=[dict(design="comparison",profile="r20p0")]), 50)

    def test_published_context_and_run_identity(self):
        from shutil import copytree
        from test_measurement import rehash
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            copytree(Path("results/verify/measurement/smoke.yXogitrZ"), directory, dirs_exist_ok=True)
            schedule = read(directory/"schedule.json")
            run = schedule["runs"][0]
            folder = directory/"raw"/run["run_id"]
            context = read(folder/"context.json")
            write(folder/"collection-sources.json", {"collector":"fixed"})
            rehash(folder)
            self.assertEqual(diagnostic_raw(directory,run,schedule,context,{"collector":"fixed"}), folder)
            changed = read(directory/"context.json")
            changed["services"][0]["cpu"] *= 2
            write(directory/"context.json", changed)
            with self.assertRaisesRegex(ValueError, "context"):
                diagnostic_raw(directory,run,schedule,changed,{"collector":"fixed"})
            write(directory/"context.json", context)
            with self.assertRaisesRegex(ValueError, "schedule"):
                diagnostic_raw(directory,run,dict(schedule,extra=True),context,{"collector":"fixed"})
            with self.assertRaisesRegex(ValueError, "run mismatch"):
                diagnostic_raw(directory,dict(run,mode="other"),schedule,context,{"collector":"fixed"})

    def test_generator_observations_and_incomplete_queue_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            def save_rows(name, values):
                (folder/name).write_text("".join(json.dumps(value)+"\n" for value in values))
            roles = ("browser","server","router")
            context = dict(services=[dict(role=role,cpu=2000000000) for role in roles])
            write(folder/"context.json", context)
            write(folder/"resource-window.json", dict(start_usec=0,end_usec=60000000))
            save_rows("resources.jsonl", (dict(sample_index=i, role=role, end_usec=(i+1)*1000000,
                interval_usec=1000000, cpu_usage_usec=1000000, throttled_usec=0, oom=0)
                for role in roles for i in range(60)))
            queues = [dict(dev=dev, drops=0, qlen=1, backlog=256, limit=1000) for dev in ("to_browser","to_server")]
            backlog = [dict(usec=i*1000000, queues=queues) for i in range(61)]
            save_rows("backlog.jsonl", backlog)
            runs = []
            for frequency in (20,100):
                save_rows("slots.jsonl", (dict(t_send_ms=i*1000/frequency+1,t_plan_ms=i*1000/frequency,
                    send_state="sent",send_lag_ms=1) for i in range(1200)))
                run = generator_run(folder, frequency)
                self.assertEqual(run["browser_cpu_pct_limit"], 50)
                self.assertEqual(run["router_peak_backlog_bytes"], 256)
                runs.append(run)
            self.assertEqual(generator_gate(runs)["status"], "passed")
            both_modes = [dict(run, mode=mode) for mode in ("WS","WT-S") for run in runs]
            self.assertEqual(generator_gate(both_modes)["status"], "passed")
            with self.assertRaisesRegex(ValueError, "both modes"):
                generator_gate(both_modes[:2])
            save_rows("backlog.jsonl", backlog[:-1])
            with self.assertRaisesRegex(ValueError, "router sampling coverage"):
                generator_run(folder, 100)
