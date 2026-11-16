import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from measurement.raw import digest, write
from reporting.comparisons import (
    TITLES, append_report, ecdf, extend, figures, finite, lag_samples, paired_values,
)


class ComparisonTests(unittest.TestCase):
    # Preserve repeated observations and the empirical denominator in the CDF.
    def test_ecdf_sample_values_and_empty_group(self):
        import matplotlib.pyplot as plt

        figure, axis = plt.subplots()
        try:
            ecdf(axis, [20, None, 10, 10], "WS", "blue")
            self.assertEqual(list(axis.lines[0].get_xdata()), [10, 10, 20])
            self.assertEqual(list(axis.lines[0].get_ydata()), [1 / 3, 2 / 3, 1])
            ecdf(axis, [], "WT-D", "green")
            self.assertEqual(len(axis.lines[1].get_xdata()), 0)
            self.assertIn("n=0", axis.lines[1].get_label())
        finally:
            plt.close(figure)

    # Keep unaccepted replies separate and exclude responses beyond the horizon.
    def test_rtt_ecdf_membership(self):
        import matplotlib.pyplot as plt

        items = [self.item("WS")]
        packets = [dict(run_id="b0WS", rtt_ms=value, accepted=accepted,
                        completed_by_horizon=completed)
                   for value, accepted, completed in ((10, True, True),
                                                       (20, False, True),
                                                       (900, True, False))]
        try:
            with tempfile.TemporaryDirectory() as temp, \
                    patch("reporting.comparisons.ecdf") as draw, \
                    patch("reporting.comparisons.save"):
                figures(Path(temp), items, packets, {})
                samples = {call.args[2]: call.args[1] for call in draw.call_args_list
                           if call.args[2].startswith("WS ")}
                self.assertEqual(samples["WS valid"], [10])
                self.assertEqual(samples["WS observations"], [20])
        finally:
            plt.close("all")

    # Build a run with explicit missing values and optional unaccepted observations.
    def item(self, mode, status="complete", attempt="b0", q=30):
        return dict(run_id=attempt + mode, attempt_id=attempt, mode=mode,
                    profile="r20p0", status=status, Q_ms=q if status == "complete" else None,
                    S_pct=90 if status == "complete" else None,
                    U_pct=5 if status == "complete" else None, artifacts=[],
                    observations=dict(Q_observed_ms=42, S_observed_pct=None, U_observed_pct=None))

    # Exclude failed, unmatched, cross-profile, and null pairs without imputing zeros.
    def test_pair_membership_and_nulls(self):
        items = [self.item("WS"), self.item("WT-S", q=35),
                 self.item("WS", attempt="b1"), self.item("WT-S", "failed", "b1"),
                 self.item("WS", attempt="b2"), self.item("WT-S", attempt="b2", q=None)]
        self.assertEqual(paired_values(items, "r20p0", "Q_ms"), ([5.0], 3))
        items[1]["profile"] = "r80p0"
        self.assertEqual(paired_values(items, "r20p0", "Q_ms"), ([], 3))
        self.assertEqual(finite([None, float("nan"), 0, 4]), [0, 4])

    # Read lag from all sent slots, including slots without a returned reply.
    def test_lag_includes_unanswered_and_verifies_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            series = Path(temp)
            folder = series / "raw/run"
            folder.mkdir(parents=True)
            slots = folder / "slots.jsonl"
            slots.write_text('{"send_lag_ms":2}\n{"send_lag_ms":50}\n{"send_lag_ms":null}\n')
            (folder / "SHA256SUMS").write_text(f"{digest(slots)}  slots.jsonl\n")
            item = self.item("WS")
            item["artifacts"] = [dict(path="raw/run", accepted=True)]
            self.assertEqual(lag_samples(series, [item]), {item["run_id"]: [2, 50]})
            slots.write_text('{}\n')
            with self.assertRaises(Exception):
                lag_samples(series, [item])

    # Render every figure format with mixed outcomes, missing modes, and null metrics.
    def test_all_figures_and_report_links(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            items = [self.item("WS"), self.item("WT-S", q=35), self.item("WT-D", "failed")]
            packets = [dict(run_id=items[0]["run_id"], accepted=True,
                            completed_by_horizon=True, rtt_ms=20),
                       dict(run_id=items[2]["run_id"], accepted=False,
                            completed_by_horizon=True, rtt_ms=45)]
            figures(output, items, packets, {items[0]["run_id"]: [0, 30]})
            append_report(output)
            report = (output / "report.md").read_text()
            for name in TITLES:
                self.assertIn(f"figures/{name}.png", report)
                for suffix in ("png", "svg", "pdf"):
                    self.assertGreater((output / "figures" / f"{name}.{suffix}").stat().st_size, 100)
            self.assertIn("descriptive only", report)
            self.assertIn("actual deadline includes send lag", report)

    # Refuse existing destinations and corrupted cached reports without deleting files.
    def test_preserves_existing_results(self):
        with tempfile.TemporaryDirectory() as temp:
            series = Path(temp)
            source = series / "derived"
            source.mkdir()
            marker = source / "report.md"
            marker.write_text("original")
            with self.assertRaises(Exception):
                extend(series, source)
            (source / "SHA256SUMS").write_text("incorrect  report.md\n")
            with self.assertRaises(Exception):
                extend(series, series / "new-report")
            self.assertEqual(marker.read_text(), "original")
            self.assertFalse((series / "new-report").exists())

    # Extend a verified report while leaving every original file byte-for-byte intact.
    def test_extend_preserves_original_and_seals_new_report(self):
        with tempfile.TemporaryDirectory() as temp:
            series = Path(temp)
            source = series / "derived"
            source.mkdir()
            write(series / "schedule.json", dict(runs=[]))
            write(source / "analysis.json", dict(runs=[], schedule_sha256=digest(series / "schedule.json")))
            (source / "report.md").write_text("Original report\n")
            with (source / "rtt.csv").open("w") as handle:
                csv.DictWriter(handle, ["run_id", "accepted", "completed_by_horizon", "rtt_ms"]).writeheader()
            (source / "SHA256SUMS").write_text("".join(
                f"{digest(p)}  {p.name}\n" for p in sorted(source.iterdir())))
            original = {p.name: p.read_bytes() for p in source.iterdir()}
            with patch("reporting.comparisons.figures") as render:
                output = extend(series, series / "comparison-report")
                render.assert_called_once()
            self.assertEqual(original, {p.name: p.read_bytes() for p in source.iterdir()})
            self.assertIn("Transport comparisons", (output / "report.md").read_text())
            from reporting.comparisons import verify_report

            verify_report(output)
            self.assertTrue((output / "comparison-provenance.json").exists())
