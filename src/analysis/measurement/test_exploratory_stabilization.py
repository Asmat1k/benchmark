import json
from pathlib import Path
import tempfile
import unittest

from measurement.raw import validate_stabilization, write
from measurement.stabilization_cpu import compare, quiet_summary
from measurement import test_stabilization_cpu


class ExploratoryQueueTests(unittest.TestCase):
    # Check nonempty final queue is observation only in exploratory policy.
    def test_nonempty_final_queue_is_observation_only_in_exploratory_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            records = test_stabilization_cpu.QuietCpuTests().records()
            summary = quiet_summary(records, 1000000)
            for prefix in ("baseline", "stabilization-1"):
                (folder / f"{prefix}-marker").write_text("1000000")
                for role in ("browser", "server", "router"):
                    (folder / f"{prefix}-{role}.jsonl").write_text(
                        "".join(
                            json.dumps(r) + "\n" for r in records if r["role"] == role
                        )
                    )
                write(folder / f"{prefix}-cpu.json", summary)
            write(folder / "stabilization-1-comparison.json", compare(summary, summary))
            empty = [dict(kind="netem", backlog=0, qlen=0) for _ in range(2)]
            nonempty = [dict(kind="netem", backlog=182, qlen=2), empty[1]]
            write(folder / "qdisc-stable.json", nonempty)
            (folder / "stabilization-1-queues.jsonl").write_text(
                (json.dumps(empty) + "\n") * 11
            )
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
            plan = dict(execution_policy="finite-browser-study-v1")
            with self.assertRaisesRegex(ValueError, "queues not empty"):
                validate_stabilization(folder, plan)
            validate_stabilization(folder, plan, exploratory=True)
            (folder / "stabilization-1-queues.jsonl").write_text(
                (json.dumps(nonempty) + "\n") * 11
            )
            write(
                folder / "stabilization.json",
                dict(
                    stable=False,
                    cpu_recovered=True,
                    attempts=1,
                    empty_queue_window_ms=1000,
                    wait_limit_s=30,
                ),
            )
            validate_stabilization(folder, plan, exploratory=True)
            (folder / "baseline-browser.jsonl").write_text("")
            with self.assertRaises(ValueError):
                validate_stabilization(folder, plan, exploratory=True)
