import tempfile
import unittest
from pathlib import Path

from admission.acceptance import paired_schedule
from admission.collection import environment
from measurement.raw import rows, validate_raw, write
from reporting.synthetic import make_fixture, rehash
from tests.support import create_template


class FixtureSupportTests(unittest.TestCase):
    # Validate generated raw using the unchanged production validator.
    def test_generated_raw_is_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = create_template(Path(temporary) / "template")
            for folder in (directory / "raw").iterdir():
                validate_raw(folder, directory / "schedule.json")

    # Monitoring runs retain baseline observations and reject their absence.
    def test_monitoring_baseline_is_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            schedule = paired_schedule(
                "monitoring", "fixture-monitoring", blocks=1, smoke=True
            )
            schedule["blocks"] = schedule["blocks"][:1]
            attempt = schedule["blocks"][0]["attempt_id"]
            schedule["runs"] = [
                run for run in schedule["runs"] if run["attempt_id"] == attempt
            ]
            directory = make_fixture(Path(temporary) / "monitoring", schedule=schedule)
            for run in schedule["runs"]:
                folder = directory / "raw" / run["run_id"]
                for role in ("browser", "server", "router"):
                    baseline = rows(folder / f"{role}-baseline.jsonl")
                    self.assertEqual(len(baseline), 1)
                    self.assertEqual(baseline[0]["run_id"], run["run_id"])
                    self.assertEqual(baseline[0]["oom"], 0)
                if run["monitoring"] == "off":
                    write(
                        folder / "monitoring-window.json",
                        dict(
                            monitoring="off",
                            unobserved_start_usec=1000000,
                            unobserved_end_usec=2000000,
                            resource_metrics_available=False,
                        ),
                    )
                    write(
                        folder / "resource-window.json",
                        dict(start_usec=3000000, end_usec=80000000),
                    )
                    for role in ("browser", "server", "router"):
                        (folder / f"{role}-oom-before.txt").write_text("oom 0\n")
                        (folder / f"{role}-oom-after.txt").write_text("oom 0\n")
                rehash(folder)
                validate_raw(folder, directory / "schedule.json")
                if run["monitoring"] == "off":
                    (folder / "browser-baseline.jsonl").unlink()
                    rehash(folder)
                    with self.assertRaises(FileNotFoundError):
                        validate_raw(folder, directory / "schedule.json")

    # Repeated construction produces identical bytes outside the temporary path.
    def test_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = create_template(root / "first" / "template")
            second = create_template(root / "second" / "template")
            first_files = {
                str(path.relative_to(first)): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_files = {
                str(path.relative_to(second)): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)

    # Synthetic context cannot be admitted as a real measurement environment.
    def test_context_is_rejected_as_real_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = create_template(Path(temporary) / "template")
            for path in (
                directory / "context.json",
                directory / "raw" / "b0-a0-m0" / "context.json",
            ):
                with self.assertRaisesRegex(ValueError, "synthetic environment"):
                    environment(path, kind="real")
