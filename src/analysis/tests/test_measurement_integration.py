import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import ValidationError

from measurement.raw import digest, read, rows, validate_raw, write
from execution.record import run_spec
from execution.replace import replace
from measurement.resources import validate_resources
from execution.schedule import make_schedule
from execution.series import (
    advance,
    bind_context,
    context_snapshot,
    measurement_lock,
    queue,
)
from execution.violation import diagnose

from tests.support import create_template


# Rebuild checksums for the modified fixture.
def rehash(folder):
    manifest = read(folder / "manifest.json")
    for key in (
        "environment",
        "provenance",
        "security",
        "network_before",
        "network_after",
    ):
        manifest[key]["sha256"] = digest(folder / manifest[key]["path"])
    write(folder / "manifest.json", manifest)
    checks = read(folder / "checks.json")
    for check in checks["checks"]:
        for ref in check["evidence"]:
            ref["sha256"] = digest(folder / ref["path"])
    write(folder / "checks.json", checks)
    (folder / "SHA256SUMS").write_text(
        "".join(
            f"{digest(p)}  {p.name}\n"
            for p in sorted(folder.iterdir())
            if p.name != "SHA256SUMS"
        )
    )


# Create the test fixture.
def fixture(directory):
    schedule = make_schedule("smoke", directory.name, 1, 1)
    create_template(directory, schedule)
    for run in schedule["runs"][2:]:
        shutil.rmtree(directory / "raw" / run["run_id"])
    ledger = read(directory / "ledger.json")
    for block in ledger["attempts"][1:]:
        block["status"] = "planned"
    write(directory / "ledger.json", ledger)
    (directory / "queue.json").unlink()
    settings = "mtu 1500\n" + "\n".join(
        f"{feature}: off"
        for feature in (
            "tcp-segmentation-offload",
            "generic-segmentation-offload",
            "generic-receive-offload",
            "large-receive-offload",
        )
    )
    for folder in (directory / "raw").iterdir():
        write(
            folder / "config.json",
            {
                name: read(Path("configs") / f"{name}.json")
                for name in ("plan", "thresholds", "profiles")
            },
        )
        manifest = read(folder / "manifest.json")
        manifest["config_sha256"] = digest(folder / "config.json")
        manifest["protocol_sha256"] = digest(Path("configs/contracts/protocol.json"))
        write(folder / "manifest.json", manifest)
        for name in ("network_before", "network_after"):
            snapshot = read(folder / f"{name}.json")
            snapshot["endpoints"] = dict(browser=settings, server=settings)
            write(folder / f"{name}.json", snapshot)
        resources = rows(folder / "resources.jsonl")
        end = {}
        for role in ("browser", "server", "router"):
            current = 0
            for index, sample in enumerate(r for r in resources if r["role"] == role):
                current += sample["interval_usec"]
                sample.update(sample_index=index, end_usec=current)
            end[role] = current
        (folder / "resources.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in resources)
        )
        write(
            folder / "resource-window.json",
            dict(start_usec=2000000, end_usec=min(end.values()) - 1000000),
        )
        write(folder / "context.json", context_snapshot(folder))
        write(directory / "context.json", context_snapshot(folder))
        rehash(folder)
    return read(directory / "schedule.json")


# Stage an incomplete publication for the recovery test.
def pending_publication(directory, partial):
    schedule = read(directory / "schedule.json")
    schedule["series_id"] = directory.name
    write(directory / "schedule.json", schedule)
    write(partial / "schedule.json", schedule)
    ledger = read(directory / "ledger.json")
    ledger["series_id"] = directory.name
    ledger["attempts"][0]["status"] = "planned"
    write(directory / "ledger.json", ledger)


class MeasurementTests(unittest.TestCase):
    # Prepare the test state.
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.schedule = fixture(self.directory)
        self.folder = self.directory / "raw" / "b0-a0-m0"

    # Release the test resources.
    def tearDown(self):
        self.temp.cleanup()

    # Validate the supplied data.
    def validate(self):
        validate_raw(self.folder, self.directory / "schedule.json")

    # Check valid raw.
    def test_valid_raw(self):
        self.validate()
        original = read(self.folder / "manifest.json")
        for binding in ("protocol_sha256", "config_sha256"):
            with self.subTest(binding=binding):
                write(
                    self.folder / "manifest.json", dict(original, **{binding: "0" * 64})
                )
                rehash(self.folder)
                with self.assertRaisesRegex(
                    ValueError, "protocol/config hash|config mismatch"
                ):
                    self.validate()
        write(self.folder / "manifest.json", original)
        rehash(self.folder)

    # Check r1 contradictions after rehash.
    def test_r1_contradictions_after_rehash(self):
        # Supply the inline callback for this operation.
        cases = [
            ("events.jsonl", lambda x: []),
            (
                "slots.jsonl",
                lambda x: [dict(x[0], terminal_reason="local_api_error"), *x[1:]],
            ),
            (
                "server.json",
                lambda x: dict(x, measurement={k: 0 for k in x["measurement"]}),
            ),
            (
                "checks.json",
                lambda x: dict(x, checks=[dict(x["checks"][0], status="failed")]),
            ),
        ]
        for filename, change in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                other = Path(tmp)
                fixture(other)
                folder = other / "raw" / self.folder.name
                path = folder / filename
                if filename.endswith("jsonl"):
                    path.write_text(
                        "".join(json.dumps(x) + "\n" for x in change(rows(path)))
                    )
                else:
                    write(path, change(read(path)))
                rehash(folder)
                with self.assertRaises((ValueError, ValidationError)):
                    validate_raw(folder, other / "schedule.json")

    # Check r1 valid loss late disconnect.
    def test_r1_valid_loss_late_disconnect(self):
        slots = rows(self.folder / "slots.jsonl")
        events = rows(self.folder / "events.jsonl")
        last = slots[-1]
        identity = {k: last[k] for k in ("nonce", "seq", "phase")}
        events = [e for e in events if e["id"] != identity]
        last.update(
            first_correct_echo_ms=None,
            echo_bytes=None,
            ontime=False,
            completed_by_horizon=False,
            terminal_reason="horizon",
        )
        late = slots[0]
        late.update(
            first_correct_echo_ms=late["t_plan_ms"] + 101,
            ontime=False,
            terminal_reason="late_before_horizon",
        )
        for e in events:
            if (
                e["type"] == "first_correct_echo"
                and e["id"]["seq"] == late["seq"]
                and e["id"]["phase"] == 1
            ):
                e["t_ms"] = late["first_correct_echo_ms"]
        events += [
            dict(
                schema_version=1,
                event_index=0,
                run_id=last["run_id"],
                t_ms=late["first_correct_echo_ms"],
                type="late_before_horizon",
                id={k: late[k] for k in ("nonce", "seq", "phase")},
                details={},
            ),
            dict(
                schema_version=1,
                event_index=0,
                run_id=last["run_id"],
                t_ms=last["t_plan_ms"] + 200,
                type="disconnect",
                id=None,
                details={},
            ),
        ]
        # Supply the inline callback for this operation.
        events.sort(key=lambda e: e["t_ms"])
        for i, e in enumerate(events):
            e["event_index"] = i
        for name, records in (("slots", slots), ("events", events)):
            (self.folder / f"{name}.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in records)
            )
        rehash(self.folder)
        self.validate()
        from measurement.smoke import check_echoes

        with self.assertRaisesRegex(ValueError, "exact echoes missing"):
            check_echoes(self.folder)

    # Check r2 sampler stops and missing interval.
    def test_r2_sampler_stops_and_missing_interval(self):
        records = rows(self.folder / "resources.jsonl")
        window = read(self.folder / "resource-window.json")
        validate_resources(records, window)
        for broken in (
            [r for r in records if r["sample_index"] == 0],
            [
                r
                for r in records
                if not (r["role"] == "browser" and r["sample_index"] == 4)
            ],
            [
                r
                for r in records
                if not (r["role"] == "server" and r["sample_index"] >= 3)
            ],
        ):
            with self.assertRaises(ValueError):
                validate_resources(broken, window)

    # Check r3 series context and after readback.
    def test_r3_series_context_and_after_readback(self):
        baseline = read(self.folder / "limits.json")
        for record in baseline:
            record["role"] = (
                "/fresh-process-" + record["role"].rsplit("-", 2)[-2] + "-1"
            )
        write(self.folder / "limits.json", baseline)
        bind_context(self.directory, self.folder)
        for field in ("id", "cpu", "memory", "shm"):
            changed = copy.deepcopy(baseline)
            changed[0][field] = "other" if field == "id" else changed[0][field] + 1
            write(self.folder / "limits.json", changed)
            with self.assertRaisesRegex(ValueError, "environment changed"):
                bind_context(self.directory, self.folder)
        write(self.folder / "limits.json", baseline)
        original = (self.folder / "leaf.pem").read_text()
        (self.folder / "leaf.pem").write_text(original + "\n")
        with self.assertRaisesRegex(ValueError, "environment changed"):
            bind_context(self.directory, self.folder)
        (self.folder / "leaf.pem").write_text(original)
        environment = read(self.folder / "environment.json")
        environment["limits"] = baseline
        write(self.folder / "environment.json", environment)
        provenance = read(self.folder / "provenance.json")
        provenance["images"] = baseline
        write(self.folder / "provenance.json", provenance)
        write(self.folder / "images.json", baseline)
        snapshot = read(self.folder / "network_after.json")
        snapshot["browser"] = "172.28.20.10 dev bypass"
        write(self.folder / "network_after.json", snapshot)
        rehash(self.folder)
        with self.assertRaisesRegex(ValueError, "path/route"):
            self.validate()

    # Check schedule reproducible balanced and disjoint.
    def test_schedule_reproducible_balanced_and_disjoint(self):
        a = make_schedule("verify", "fixture")
        self.assertEqual(a, make_schedule("verify", "fixture"))
        for session in range(4):
            for profile in ("r20p0", "r20p1", "r80p0", "r80p1"):
                self.assertEqual(
                    sum(
                        b["session_id"] == f"s{session}" and b["profile"] == profile
                        for b in a["blocks"]
                    ),
                    5,
                )
        self.assertNotEqual(
            a["runs"][0]["nonce"],
            make_schedule("diagnostic", "fixture")["runs"][0]["nonce"],
        )

    # Check r4 admission and queue order.
    def test_r4_admission_and_queue_order(self):
        self.schedule["series_id"] = self.directory.name
        partial = self.directory / "member.partial"
        partial.mkdir()
        for series in ("pilot", "main"):
            forbidden = dict(self.schedule, series=series)
            write(self.directory / "schedule.json", forbidden)
            with self.assertRaisesRegex(ValueError, "admission"):
                run_spec(self.directory, 0, partial)
        write(self.directory / "schedule.json", self.schedule)
        with self.assertRaisesRegex(ValueError, "order"):
            run_spec(self.directory, 7, partial)
        run_spec(self.directory, 2, partial)
        with self.assertRaisesRegex(ValueError, "mode order"):
            run_spec(self.directory, 3, partial)
        for r in self.schedule["runs"][2:4]:
            (self.directory / "raw" / r["run_id"]).mkdir()
        advance(self.directory, self.schedule, self.schedule["runs"][3])
        self.assertEqual(queue(self.directory)[0], "b2-a0")
        (self.directory / "STOP").write_text("incomplete log")
        with self.assertRaisesRegex(ValueError, "stopped"):
            run_spec(self.directory, 4, partial)

    # Compute evidence.
    def evidence(self):
        snapshot = read(self.folder / "network_after.json")
        snapshot["forwarding"] = 0
        write(self.folder / "network_after.json", snapshot)
        rehash(self.folder)
        evidence = self.directory / "proof.json"
        self.assertTrue(
            diagnose(self.folder, self.directory / "schedule.json", evidence)
        )
        return evidence

    # Check r5 evidence and normal replacement.
    def test_r5_evidence_and_normal_replacement(self):
        evidence = self.directory / "proof.json"
        self.assertFalse(
            diagnose(self.folder, self.directory / "schedule.json", evidence)
        )
        evidence.write_text("")
        with self.assertRaises((ValueError, KeyError)):
            replace(self.directory, "b0-a0", "path", evidence)
        evidence = self.evidence()
        wrong = read(evidence)
        wrong["attempt_id"] = "b1-a0"
        write(evidence, wrong)
        with self.assertRaises(ValueError):
            replace(self.directory, "b0-a0", "path", evidence)
        evidence = self.evidence()
        new = replace(self.directory, "b0-a0", "path", evidence)
        self.assertEqual(new["replacement_of"], "b0-a0")
        self.assertEqual(len(list((self.directory / "audit/b0-a0").glob("*-m*"))), 2)
        self.assertNotIn("b0-a0", queue(self.directory))
        self.assertEqual(replace(self.directory, "b0-a0", "path", evidence), new)

    # Check r4 two replacements exclude executed blocks.
    def test_r4_two_replacements_exclude_executed_blocks(self):
        for old, new in zip(self.schedule["runs"][:2], self.schedule["runs"][2:4]):
            source = self.directory / "raw" / old["run_id"]
            target = self.directory / "raw" / new["run_id"]
            shutil.copytree(source, target)
            replacements = {
                old[k]: new[k]
                for k in (
                    "run_id",
                    "nonce",
                    "attempt_id",
                    "block_id",
                    "forward_seed",
                    "reverse_seed",
                )
            }

            # Compute rewrite.
            def rewrite(value):
                if isinstance(value, dict):
                    return {k: rewrite(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [rewrite(v) for v in value]
                if isinstance(value, (str, int)):
                    return replacements.get(value, value)
                return value

            for path in target.iterdir():
                if path.suffix == ".json":
                    write(path, rewrite(read(path)))
                if path.suffix == ".jsonl":
                    path.write_text(
                        "".join(json.dumps(rewrite(r)) + "\n" for r in rows(path))
                    )
            manifest = read(target / "manifest.json")
            manifest.update(new)
            write(target / "manifest.json", manifest)
            (target / "schedule.json").write_bytes(
                (self.directory / "schedule.json").read_bytes()
            )
            rehash(target)
        advance(self.directory, self.schedule, self.schedule["runs"][3])
        first = self.evidence()
        one = replace(self.directory, "b0-a0", "path", first)
        other = self.directory / "raw" / "b1-a0-m0"
        snapshot = read(other / "network_after.json")
        snapshot["forwarding"] = 0
        write(other / "network_after.json", snapshot)
        rehash(other)
        proof = self.directory / "second.json"
        self.assertTrue(diagnose(other, self.directory / "schedule.json", proof))
        two = replace(self.directory, "b1-a0", "path", proof)
        remaining = queue(self.directory)
        self.assertEqual(
            set(remaining), {"b2-a0", "b3-a0", one["attempt_id"], two["attempt_id"]}
        )
        self.assertNotIn("b0-a0", remaining)
        self.assertNotIn("b1-a0", remaining)

    # Check r5 publication failure is replaceable but log loss stops.
    def test_r5_publication_failure_is_replaceable_but_log_loss_stops(self):
        from execution.record import complete
        from execution.quarantine import quarantine

        partial = self.directory / "collector.partial"
        self.folder.rename(partial)
        (partial / "SHA256SUMS").unlink()
        pending_publication(self.directory, partial)
        write(
            partial / "page.json",
            dict(
                slots=rows(partial / "warmup.jsonl") + rows(partial / "slots.jsonl"),
                events=rows(partial / "events.jsonl"),
            ),
        )
        for when in ("before", "after"):
            snapshot = read(partial / f"network_{when}.json")
            for role in ("browser", "server"):
                (partial / f"{role}-route-{when}.txt").write_text(snapshot[role])
                (partial / f"{role}-settings-{when}.txt").write_text(
                    snapshot["endpoints"][role]
                )
            (partial / f"router-links-{when}.txt").write_text(snapshot["links"])
        (partial / "forward-after").write_text("0")
        with self.assertRaises(SystemExit) as failure:
            complete(self.directory, 0, partial)
        self.assertEqual(failure.exception.code, 3)
        self.assertTrue((self.directory / "PENDING_REPLACEMENT").exists())
        self.assertFalse((self.directory / "STOP").exists())
        target = self.directory / "quarantine/collector"
        target.parent.mkdir()
        partial.rename(target)
        evidence = self.directory / "violations/b0-a0-m0.json"
        replace(self.directory, "b0-a0", "path", evidence)
        self.assertFalse((self.directory / "PENDING_REPLACEMENT").exists())
        broken = self.directory / "audit/b0-a0/b0-a0-m0"
        (broken / "events.jsonl").write_text("")
        self.assertFalse(
            diagnose(
                broken, self.directory / "schedule.json", self.directory / "lost.json"
            )
        )
        quarantine(self.directory, 2, "synthetic sampler/log loss")
        self.assertTrue((self.directory / "STOP").exists())
        with self.assertRaisesRegex(ValueError, "stopped"):
            replace(self.directory, "b1-a0", "path", evidence)

    # Check r6 recovery and shared lock.
    def test_r6_recovery_and_shared_lock(self):
        evidence = self.evidence()
        with measurement_lock():
            with self.assertRaises(BlockingIOError):
                replace(self.directory, "b0-a0", "path", evidence)
        for stage in ("move-0", "before-ledger"):
            with self.subTest(stage=stage):
                # Simulate a publication failure.
                def crash(point):
                    if point == stage:
                        raise RuntimeError("injected failure")

                with self.assertRaises(RuntimeError):
                    replace(self.directory, "b0-a0", "path", evidence, crash)
        new = replace(self.directory, "b0-a0", "path", evidence)
        ledger = read(self.directory / "ledger.json")
        self.assertEqual(
            sum(a["replacement_of"] == "b0-a0" for a in ledger["attempts"]), 1
        )
        self.assertEqual(len(list((self.directory / "audit/b0-a0").glob("*-m*"))), 2)
        self.assertIn(new["attempt_id"], queue(self.directory))

    # Check r7 baseline and no false smoke success.
    def test_r7_baseline_and_no_false_smoke_success(self):
        from measurement.smoke import check_smoke

        baseline = make_schedule("smoke", "fixture", 1, 1, baseline=True)
        self.assertEqual({r["profile"] for r in baseline["runs"]}, {"baseline"})
        with self.assertRaises(ValueError):
            make_schedule("main", "fixture", baseline=True)
        with self.assertRaises(ValueError):
            check_smoke(self.directory)


if __name__ == "__main__":
    unittest.main()
