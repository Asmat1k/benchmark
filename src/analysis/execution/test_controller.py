import contextlib
import io
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from admission import test_acceptance as fixtures
from admission.admission import GATES, controller_session, ref, sources, validate_gate
from execution.controller import dispatch
from measurement.raw import read, write
from admission.acceptance import paired_schedule
from execution.schedule import make_schedule, block_runs
from reporting.synthetic import make_fixture, rehash
from tests.support import create_template


class ControllerTests(unittest.TestCase):
    setUp = fixtures.AcceptanceTests.setUp
    tearDown = fixtures.AcceptanceTests.tearDown
    collection = fixtures.AcceptanceTests.collection
    primary = fixtures.AcceptanceTests.primary
    timer = fixtures.AcceptanceTests.timer
    probe = fixtures.AcceptanceTests.probe
    calibration_fixture = fixtures.AcceptanceTests.calibration_fixture
    generator_fixture = fixtures.AcceptanceTests.generator_fixture
    pairs = fixtures.AcceptanceTests.pairs
    produce = fixtures.AcceptanceTests.produce
    verification_fixture = fixtures.AcceptanceTests.verification_fixture
    environment_template = fixtures.AcceptanceTests.environment_template

    # Check initial copied admission commit mismatch refuses ready.
    def test_initial_copied_admission_commit_mismatch_refuses_ready(self):
        from execution.controller import serve

        directory = self.root / "copied-admission"
        directory.mkdir()
        write(directory / "schedule.json", {})
        original = self.root / "accepted-admission.json"
        write(
            original,
            dict(kind="real", source_hashes=sources(), release_commit="a" * 40),
        )
        shutil.copyfile(original, directory / "admission.json")
        copied = read(directory / "admission.json")
        copied["release_commit"] = "b" * 40
        write(directory / "admission.json", copied)
        output = io.StringIO()
        with (
            patch("admission.admission.release", return_value="a" * 40),
            contextlib.redirect_stdout(output),
        ):
            with self.assertRaisesRegex(
                ValueError, "initial admission release commit mismatch"
            ):
                serve(directory)
        self.assertNotIn("ready", output.getvalue())

    # Check real cli forged integrity refuses next record and boot.
    def test_real_cli_forged_integrity_refuses_next_record_and_boot(self):
        directory = self.root / "forged"
        directory.mkdir()
        schedule = paired_schedule("aa", directory.name)
        for name, value in (
            ("schedule.json", schedule),
            ("schedule-original.json", schedule),
            (
                "ledger.json",
                dict(
                    schema_version=1,
                    series_id=directory.name,
                    attempts=schedule["blocks"],
                ),
            ),
            ("SYNTHETIC.json", dict(kind="synthetic")),
        ):
            write(directory / name, value)
        evidence = self.root / "evidence.json"
        write(evidence, dict(purpose="isolated controller integrity evidence"))
        environment = self.environment_template() / "context.json"
        checks = []
        for gate in GATES:
            path = directory / (gate + ".json")
            write(
                path,
                dict(
                    kind="real",
                    gate=gate,
                    status="passed",
                    source_hashes=sources(),
                    environment=ref(environment),
                    result=dict(status="passed"),
                    evidence=[ref(evidence)],
                    integrity=dict(
                        files={str(evidence.resolve()): ref(evidence)["sha256"]},
                        trees={},
                    ),
                ),
            )
            checks.append(
                dict(
                    id=gate,
                    mandatory=True,
                    expected="passed",
                    actual="passed",
                    units="gate",
                    tolerance=None,
                    status="passed",
                    reason=None,
                    utc="2026-11-12T00:00:00Z",
                    evidence=[ref(path)],
                )
            )
        verification = directory / "verify.json"
        write(
            verification,
            dict(
                kind="real",
                final=False,
                source_hashes=sources(),
                environment=ref(environment),
                document=dict(schema_version=1, checks=checks),
            ),
        )
        write(
            directory / "admission.json",
            dict(
                kind="real",
                phase="aa",
                source_hashes=sources(),
                schedule=ref(directory / "schedule-original.json"),
                verify=ref(verification),
                environment=ref(environment),
            ),
        )
        partial = directory / "partial"
        partial.mkdir()
        commands = (
            [
                sys.executable,
                "-B",
                "-m",
                "execution.experiments",
                "next",
                "--output",
                str(directory),
                "--kind",
                "real",
                "--execute-real-experiments",
            ],
            [
                sys.executable,
                "-B",
                "-m",
                "execution.record",
                "prepare",
                str(directory),
                "0",
                str(partial),
            ],
        )
        for command in commands:
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(process.returncode, 0, process.stdout)
        self.assertFalse((partial / "run.json").exists())
        (directory / "SYNTHETIC.json").unlink()
        process = subprocess.run(
            [sys.executable, "-B", "-m", "execution.controller", str(directory)],
            input="",
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertNotIn('"value": "ready"', process.stdout)

    # Check memory controller deep once then actual fast record context.
    def test_memory_controller_deep_once_then_actual_fast_record_context(self):
        verification = self.verification_fixture()
        directory = self.root / "controlled"
        schedule = make_schedule("verify", directory.name, 1, 1)
        for block in schedule["blocks"]:
            block.update(design="aa", modes=["WS", "WS"])
        schedule["runs"] = [
            r
            for i, b in enumerate(schedule["blocks"])
            for r in block_runs(schedule, b, i)
        ]
        make_fixture(directory, schedule=schedule)
        write(directory / "schedule-original.json", schedule)
        ledger = read(directory / "ledger.json")
        for attempt in ledger["attempts"]:
            attempt["status"] = "planned"
        write(directory / "ledger.json", ledger)
        (directory / "queue.json").unlink()
        first = schedule["runs"][0]
        for folder in (directory / "raw").iterdir():
            if folder.name != first["run_id"]:
                shutil.rmtree(folder)
        manifest = read(directory / "raw" / first["run_id"] / "manifest.json")
        write(
            directory / "admission.json",
            dict(
                kind="synthetic",
                phase="aa",
                source_hashes=sources(),
                release_commit=manifest["commit"],
                schedule=ref(directory / "schedule-original.json"),
                verify=ref(verification),
                environment=ref(self.env),
            ),
        )
        partial = directory / "next.partial"
        partial.mkdir()
        context = directory / "context.partial"
        shutil.copytree(directory / "raw" / first["run_id"], context)
        context_run = read(context / "run.json")
        context_run.update(
            {k: schedule["runs"][1][k] for k in ("run_id", "nonce", "mode")}
        )
        write(context / "run.json", context_run)
        fifo = self.root / "controller-input"
        os.mkfifo(fifo)
        response = self.root / "controller-output"
        script = """set -eu
%s -B -c 'import sys,os;sys.path.insert(0,"src/analysis");from execution.controller import serve;from pathlib import Path;serve(Path(os.environ["CONTROLLER_TEST_DIR"]),"synthetic")' < "$CONTROLLER_TEST_FIFO" > "$BENCH_CONTROLLER_RESPONSE" &
BENCH_CONTROLLER_PID=$!
export BENCH_CONTROLLER_PID
exec 8> "$CONTROLLER_TEST_FIFO"
while [ ! -s "$BENCH_CONTROLLER_RESPONSE" ]; do kill -0 "$BENCH_CONTROLLER_PID"; sleep .1; done
. docker/lib/controller-client.sh
controller_request '{"action":"next"}'
exec 8>&-
wait "$BENCH_CONTROLLER_PID"
""" % shlex.quote(sys.executable)
        process = subprocess.run(
            ["/bin/sh", "-c", script],
            env=dict(
                os.environ,
                CONTROLLER_TEST_DIR=str(directory),
                CONTROLLER_TEST_FIFO=str(fifo),
                BENCH_CONTROLLER_RESPONSE=str(response),
            ),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(process.stdout.strip(), "1")
        from execution.experiments import evaluate as scientific_evaluate

        bootstrap = patch("execution.experiments.evaluate", wraps=scientific_evaluate)
        initial = bootstrap.start()
        self.addCleanup(bootstrap.stop)
        with controller_session(directory, "synthetic"):
            self.assertCountEqual(
                [call.args[0] for call in initial.call_args_list],
                ["timer", "calibrate", "generator"],
            )
            bootstrap.stop()
            with contextlib.ExitStack() as stack:
                for name in (
                    "execution.experiments.evaluate",
                    "measurement.raw.rows",
                    "reporting.inference.bootstrap",
                    "reporting.power.simulate",
                ):
                    stack.enter_context(
                        patch(
                            name,
                            side_effect=AssertionError(
                                "scientific recalculation " + name
                            ),
                        )
                    )
                self.assertEqual(
                    dispatch(directory, dict(action="next"), "synthetic"), (0, "1")
                )
                self.assertEqual(
                    dispatch(
                        directory,
                        dict(action="prepare", index=1, partial=str(partial)),
                        "synthetic",
                    )[0],
                    0,
                )
                for _ in range(2):
                    self.assertEqual(
                        dispatch(
                            directory,
                            dict(action="context", index=1, partial=str(context)),
                            "synthetic",
                        )[0],
                        0,
                    )
                trace = self.root / "build-locked-install.json"
                before = trace.read_bytes()
                trace.write_text("{}")
                with self.assertRaises(ValueError):
                    dispatch(directory, dict(action="next"), "synthetic")
                trace.write_bytes(before)
                report_path = self.root / "build-calculated.json"
                document = read(report_path)
                document["integrity"]["files"].pop(
                    next(iter(document["integrity"]["files"]))
                )
                with self.assertRaises(ValueError):
                    validate_gate(document, recalculate=False)
        with self.assertRaises(ValueError):
            dispatch(directory, dict(action="next"), "synthetic")
        with patch(
            "execution.experiments.evaluate", wraps=scientific_evaluate
        ) as restarted:
            with controller_session(directory, "synthetic"):
                self.assertCountEqual(
                    [call.args[0] for call in restarted.call_args_list],
                    ["timer", "calibrate", "generator"],
                )
                self.assertEqual(
                    dispatch(directory, dict(action="next"), "synthetic"), (0, "1")
                )

    # Create an incomplete publication for the test.
    def publication_partial(self, directory, run):
        from measurement.raw import rows

        partial = directory / (run["run_id"] + ".partial")
        (directory / "raw" / run["run_id"]).rename(partial)
        (partial / "SHA256SUMS").unlink()
        write(
            partial / "page.json",
            dict(
                slots=rows(partial / "warmup.jsonl") + rows(partial / "slots.jsonl"),
                events=rows(partial / "events.jsonl"),
            ),
        )
        for when in ("before", "after"):
            snapshot = read(partial / f"network_{when}.json")
            write(partial / f"qdisc-{when}.json", snapshot["qdisc"])
            for role in ("browser", "server"):
                (partial / f"{role}-route-{when}.txt").write_text(snapshot[role])
                (partial / f"{role}-settings-{when}.txt").write_text(
                    snapshot["endpoints"][role]
                )
            (partial / f"router-links-{when}.txt").write_text(snapshot["links"])
        return partial

    # Check all direct record actions refuse unadmitted and stopped without mutation.
    def test_all_direct_record_actions_refuse_unadmitted_and_stopped_without_mutation(
        self,
    ):
        from measurement.raw import digest

        for phase in ("pilot", "main", "aa"):
            directory = self.root / phase
            schedule = make_schedule(
                "verify" if phase == "aa" else phase, directory.name, 1, 1
            )
            if phase == "aa":
                for b in schedule["blocks"]:
                    b.update(design="aa", modes=["WS", "WS"])
                schedule["runs"] = [
                    r
                    for i, b in enumerate(schedule["blocks"])
                    for r in block_runs(schedule, b, i)
                ]
            make_fixture(directory, schedule=schedule)
            partial = self.publication_partial(directory, schedule["runs"][0])
            ledger = read(directory / "ledger.json")
            ledger["attempts"][0]["status"] = "planned"
            write(directory / "ledger.json", ledger)
            (directory / "STOP").write_text("deliberate stop")

            # Return the retained file inventory.
            def inventory():
                return {str(p): digest(p) for p in directory.rglob("*") if p.is_file()}

            for stopped in (True, False):
                if not stopped:
                    (directory / "STOP").unlink()
                for action in ("prepare", "context", "complete"):
                    before = inventory()
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            "-m",
                            "execution.record",
                            action,
                            str(directory),
                            "0",
                            str(partial),
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(
                        result.returncode, 0, (phase, action, result.stdout)
                    )
                    self.assertEqual(before, inventory(), (phase, action))

    # Check controller context complete guard and authorised publication.
    def test_controller_context_complete_guard_and_authorised_publication(self):
        from measurement.raw import digest

        verification = self.verification_fixture()
        local_temp = tempfile.TemporaryDirectory(prefix="d6-relative-", dir="build")
        self.addCleanup(local_temp.cleanup)
        directory = Path(local_temp.name).resolve() / "publication"
        schedule = make_schedule("verify", directory.name, 1, 1)
        for b in schedule["blocks"]:
            b.update(design="aa", modes=["WS", "WS"])
        schedule["runs"] = [
            r
            for i, b in enumerate(schedule["blocks"])
            for r in block_runs(schedule, b, i)
        ]
        make_fixture(directory, schedule=schedule)
        write(directory / "schedule-original.json", schedule)
        partials = [
            self.publication_partial(directory, r) for r in schedule["runs"][:2]
        ]
        shutil.rmtree(directory / "raw")
        (directory / "raw").mkdir()
        ledger = read(directory / "ledger.json")
        for a in ledger["attempts"]:
            a["status"] = "planned"
        write(directory / "ledger.json", ledger)
        (directory / "queue.json").unlink()
        manifest = read(partials[0] / "manifest.json")
        write(
            directory / "admission.json",
            dict(
                kind="synthetic",
                phase="aa",
                source_hashes=sources(),
                release_commit=manifest["commit"],
                schedule=ref(directory / "schedule-original.json"),
                verify=ref(verification),
                environment=ref(self.env),
            ),
        )

        # Return the retained file inventory.
        def inventory():
            return {str(p): digest(p) for p in directory.rglob("*") if p.is_file()}

        # Assert that the operation is rejected.
        def rejected(action, index=0, partial=None):
            before = inventory()
            with self.assertRaises((ValueError, FileNotFoundError)):
                dispatch(
                    directory,
                    dict(
                        action=action, index=index, partial=str(partial or partials[0])
                    ),
                    "synthetic",
                )
            self.assertEqual(before, inventory())

        with controller_session(directory, "synthetic"):
            for action in ("prepare", "context", "complete"):
                (directory / "STOP").write_text("deliberate stop")
                rejected(action)
                (directory / "STOP").unlink()
                rejected(action, -1)
                rejected(action, len(schedule["runs"]))
                rejected(action, 1, partials[1])
                rejected(action, 0, self.root)
                write(
                    directory / "queue.json",
                    list(reversed([a["attempt_id"] for a in ledger["attempts"]])),
                )
                rejected(action)
                (directory / "queue.json").unlink()
            for action in ("context", "complete"):
                saved = (partials[0] / "run.json").read_bytes()
                spec = read(partials[0] / "run.json")
                spec["nonce"] = "0"
                write(partials[0] / "run.json", spec)
                rejected(action)
                (partials[0] / "run.json").write_bytes(saved)
            from execution.series import context_snapshot

            for action in ("context", "complete"):
                paths = [
                    partials[0] / "host.txt",
                    partials[0] / "context.json",
                    directory / "context.json",
                ]
                saved = [p.read_bytes() for p in paths]
                paths[0].write_text(paths[0].read_text() + " changed host")
                changed = context_snapshot(partials[0])
                write(paths[1], changed)
                write(paths[2], changed)
                rejected(action)
                for path, blob in zip(paths, saved):
                    path.write_bytes(blob)
                for marker in ("PENDING_REPLACEMENT", "replacement.json"):
                    (directory / marker).write_text("{}")
                    rejected(action)
                    (directory / marker).unlink()
            with contextlib.ExitStack() as stack:
                for name in (
                    "execution.experiments.evaluate",
                    "reporting.inference.bootstrap",
                    "reporting.power.simulate",
                ):
                    stack.enter_context(
                        patch(
                            name,
                            side_effect=AssertionError(
                                "scientific recalculation " + name
                            ),
                        )
                    )
                for index, partial in enumerate(partials):
                    relative = str(partial.relative_to(Path.cwd()))
                    for action in ("prepare", "context", "complete"):
                        self.assertEqual(
                            dispatch(
                                directory,
                                dict(action=action, index=index, partial=relative),
                                "synthetic",
                            )[0],
                            0,
                        )
            published = directory / "raw" / schedule["runs"][0]["run_id"]
            nested = directory / "nested"
            nested.mkdir()
            audit = directory / "audit"
            audit.mkdir()
            nested_partial = nested / "member.partial"
            nested_partial.mkdir()
            alias = directory / "published.partial"
            alias.symlink_to(published, target_is_directory=True)
            for address in (
                directory,
                directory / "raw",
                published,
                audit,
                nested_partial,
                alias,
            ):
                for action in ("prepare", "context", "complete"):
                    rejected(action, 2, address)
            self.assertEqual(
                read(directory / "ledger.json")["attempts"][0]["status"], "complete"
            )
            self.assertEqual(
                dispatch(directory, dict(action="next"), "synthetic"), (0, "2")
            )
            self.assertTrue(
                all(
                    (directory / "raw" / r["run_id"] / "SHA256SUMS").is_file()
                    for r in schedule["runs"][:2]
                )
            )

    # Check direct smoke and diagnostic cli publication remain available.
    def test_direct_smoke_and_diagnostic_cli_publication_remain_available(self):
        for phase in ("smoke", "diagnostic"):
            directory = self.root / phase
            schedule = make_schedule(phase, directory.name, 1, 1)
            make_fixture(directory, schedule=schedule)
            partials = [
                self.publication_partial(directory, r) for r in schedule["runs"][:2]
            ]
            shutil.rmtree(directory / "raw")
            (directory / "raw").mkdir()
            ledger = read(directory / "ledger.json")
            for a in ledger["attempts"]:
                a["status"] = "planned"
            write(directory / "ledger.json", ledger)
            (directory / "queue.json").unlink()
            for index, partial in enumerate(partials):
                for action in ("prepare", "context", "complete"):
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            "-m",
                            "execution.record",
                            action,
                            str(directory),
                            str(index),
                            str(partial),
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        result.returncode, 0, (phase, action, result.stderr)
                    )
            self.assertEqual(
                read(directory / "ledger.json")["attempts"][0]["status"], "complete"
            )

    # Check direct record staging cannot modify published raw.
    def test_direct_record_staging_cannot_modify_published_raw(self):
        from measurement.raw import digest, validate_hashes

        directory = create_template(self.root / "staging-series")
        write(
            directory / "SYNTHETIC.json",
            dict(kind="synthetic", purpose="offline staging address regression"),
        )
        schedule = read(directory / "schedule.json")
        first, second = schedule["runs"]
        published = directory / "raw" / first["run_id"]
        staging = directory / "wswt-d3-wswt-measure-fixture.partial"
        (directory / "raw" / second["run_id"]).rename(staging)
        ledger = read(directory / "ledger.json")
        ledger["attempts"][0]["status"] = "planned"
        write(directory / "ledger.json", ledger)
        write(directory / "queue.json", [first["attempt_id"]])
        audit = directory / "audit"
        audit.mkdir()
        nested = directory / "nested"
        nested.mkdir()
        nested_partial = nested / "member.partial"
        nested_partial.mkdir()
        alias = directory / "published.partial"
        alias.symlink_to(published, target_is_directory=True)
        outside = self.root / "outside"
        outside.mkdir()
        escape = directory / "escape.partial"
        escape.symlink_to(outside, target_is_directory=True)

        # Return the retained file inventory.
        def inventory():
            return {str(p): digest(p) for p in directory.rglob("*") if p.is_file()}

        validate_hashes(published)
        for address in (
            directory,
            directory / "raw",
            published,
            audit,
            nested_partial,
            alias,
            escape,
        ):
            for action in ("prepare", "context", "complete"):
                before = inventory()
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "execution.record",
                        action,
                        str(directory),
                        "1",
                        str(address),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0, (action, address))
                self.assertEqual(before, inventory(), (action, address))
                validate_hashes(published)
        for action in ("prepare", "context"):
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "execution.record",
                    action,
                    str(directory),
                    "1",
                    str(staging),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, (action, result.stderr))
        validate_hashes(published)
