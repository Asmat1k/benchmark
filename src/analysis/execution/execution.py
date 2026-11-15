import argparse
import datetime
import fcntl
import hashlib
import ipaddress
import shutil
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

VERSION = "exploratory-browser-study-v2"
TERMINAL = {"complete", "rejected", "failed", "interrupted"}


# Read JSON from the supplied path.
def read(path):
    return json.loads(path.read_text())


# Return the current UTC timestamp.
def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# Return whether the series uses the exploratory policy.
def is_exploratory(directory):
    path = directory / "admission.json"
    return path.is_file() and read(path).get("execution_policy") == VERSION


# Load outcomes.
def load_outcomes(directory, create=False):
    schedule = read(directory / "schedule.json")
    sha = hashlib.sha256((directory / "schedule.json").read_bytes()).hexdigest()
    path = directory / "outcomes.json"
    if path.exists():
        value = read(path)
        if value["execution_policy"] != VERSION or value["schedule_sha256"] != sha:
            raise ValueError("execution schedule changed")
        if [(r["index"], r["run_id"]) for r in value["runs"]] != list(
            enumerate(r["run_id"] for r in schedule["runs"])
        ):
            raise ValueError("execution outcomes identity mismatch")
        if any(
            r["status"] not in TERMINAL | {"planned", "running"} for r in value["runs"]
        ):
            raise ValueError("execution outcome status")
        for row in value["runs"]:
            for name in row["artifacts"]:
                path = Path(name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not (directory / path)
                    .resolve()
                    .is_relative_to(directory.resolve())
                ):
                    raise ValueError("foreign execution artifact")
    else:
        value = dict(
            schema_version=1,
            execution_policy=VERSION,
            schedule_sha256=sha,
            runs=[
                dict(
                    index=i,
                    run_id=r["run_id"],
                    status="planned",
                    started_utc=None,
                    ended_utc=None,
                    exit_code=None,
                    reason=None,
                    artifacts=[],
                )
                for i, r in enumerate(schedule["runs"])
            ],
        )
        if create:
            save_outcomes(directory, value)
    return value


# Save outcomes.
def save_outcomes(directory, value):
    path = directory / "reporting.outcomes.tmp"
    with path.open("w") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.replace(directory / "outcomes.json")
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


# Return the next run index from the execution journal.
def next_index(directory):
    return next(
        (
            r["index"]
            for r in load_outcomes(directory)["runs"]
            if r["status"] == "planned"
        ),
        None,
    )


# Locate the artifacts associated with this run.
def artifacts(directory, run_id):
    path = directory / "outcomes.json"
    found = (
        list(
            next(
                (
                    r.get("artifacts", [])
                    for r in read(path)["runs"]
                    if r["run_id"] == run_id
                ),
                [],
            )
        )
        if path.exists()
        else []
    )
    for base in (directory / "raw", directory / "quarantine", directory):
        for folder in base.glob("*"):
            if not folder.is_dir() or not (folder / "run.json").is_file():
                continue
            try:
                identity = read(folder / "run.json").get("run_id")
            except (ValueError, OSError):
                continue
            if identity == run_id:
                found.append(str(folder.relative_to(directory)))
    return sorted(set(found))


# Record the completed run in the execution journal.
def finish_run(directory, index, status, code, reason):
    value = load_outcomes(directory)
    row = value["runs"][index]
    if row["status"] in TERMINAL:
        raise ValueError("immutable terminal outcome")
    row.update(
        status=status,
        exit_code=code,
        reason=reason,
        ended_utc=stamp(),
        artifacts=sorted(
            set(row["artifacts"]) | set(artifacts(directory, row["run_id"]))
        ),
    )
    save_outcomes(directory, value)


# Run a child process with the execution deadline.
def bounded_process(argv, timeout, grace=30, env=None, stdout=None, stderr=None):
    process = subprocess.Popen(
        argv, start_new_session=True, env=env, stdout=stdout, stderr=stderr
    )
    try:
        return process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        if isinstance(error, KeyboardInterrupt):
            raise
        return 124


# Recover retained artifacts for an interrupted run.
def recover_artifacts(directory, run_id):
    value = load_outcomes(directory)
    other = {
        name
        for row in value["runs"]
        if row["run_id"] != run_id
        for name in row["artifacts"]
    }
    recovered = artifacts(directory, run_id)
    for base in (directory, directory / "quarantine"):
        for folder in base.glob("wswt-d3-wswt-measure-*"):
            name = str(folder.relative_to(directory))
            if folder.is_dir() and name not in other:
                recovered.append(name)
    row = next(row for row in value["runs"] if row["run_id"] == run_id)
    row["artifacts"] = sorted(set(recovered))
    save_outcomes(directory, value)


# Retain the page checkpoint before container cleanup.
def harvest_checkpoint(project, folder, deadline):
    if (folder / "SHA256SUMS").exists():
        return
    files = [
        ("browser", "page.partial.json"),
        ("browser", "page.json"),
        ("browser", "security.json"),
    ]
    files.extend((role, "resources.jsonl") for role in ("browser", "server", "router"))
    files.append(("server", "counters.json"))
    for role, name in files:
        remaining = deadline - time.monotonic()
        if remaining <= 0.1:
            break
        target = folder / (
            name
            if name.startswith("page") or name == "security.json"
            else role + "-recovered-" + name
        )
        temporary = folder / (".recovered-" + role + "-" + name)
        try:
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-p",
                    project,
                    "cp",
                    role + ":/tmp/" + name,
                    str(temporary),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=min(4, remaining),
            )
            if result.returncode == 0 and temporary.exists():
                if name.endswith(".json"):
                    read(temporary)
                temporary.replace(target)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        finally:
            temporary.unlink(missing_ok=True)


# Clean up the containers associated with this run.
def cleanup_run(directory, run_id, timeout):
    deadline = time.monotonic() + timeout
    row = next(
        row for row in load_outcomes(directory)["runs"] if row["run_id"] == run_id
    )
    for name in sorted(set(row["artifacts"]) | set(artifacts(directory, run_id))):
        folder = directory / name
        if not folder.resolve().is_relative_to(directory.resolve()):
            raise ValueError("foreign cleanup artifact")
        project = Path(name).name.removesuffix(".partial")
        if not project.startswith("wswt-d3-wswt-measure-"):
            continue
        harvest_checkpoint(project, folder, deadline - 10)
        remaining = max(1, deadline - time.monotonic())
        code = bounded_process(
            ["docker", "compose", "-p", project, "down", "--timeout", "2"], remaining, 2
        )
        if code:
            raise RuntimeError("cleanup failed for " + project)
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + project,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=max(1, deadline - time.monotonic()),
        )
        if result.stdout.strip():
            raise RuntimeError("containers remain for " + project)


# Validate published.
def validate_published(directory, run_id, timeout):
    folder = directory / "raw" / run_id
    if not folder.exists():
        return False
    argv = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-v",
        str(Path.cwd()) + ":/bench",
        "-v",
        str(Path.cwd()) + ":" + str(Path.cwd()),
        "-w",
        "/bench",
        "wswt-bench-analyzer:dev",
        "python",
        "-B",
        "-c",
        'import sys;sys.path.insert(0,"src/analysis");from pathlib import Path;from measurement.raw import validate_raw;validate_raw(Path(sys.argv[1]),Path(sys.argv[2]))',
        str(folder),
        str(directory / "schedule.json"),
    ]
    return bounded_process(argv, timeout, 5) == 0


# Collect the supplied data.
def collect(directory, executor=None, published=None, cleanup=None):
    limits = read(directory / "admission.json")["limits"]
    run_timeout = limits["run_timeout_seconds"]
    cleanup_timeout = limits["cleanup_timeout_seconds"]
    budget = limits["series_budget_seconds"]
    # Supply the inline callback for this operation.
    executor = executor or (
        lambda i, out, err: bounded_process(
            ["sh", "docker/commands/measure.sh", str(directory), str(i)],
            run_timeout,
            cleanup_timeout,
            dict(os.environ, BENCH_RESILIENT_RUN="1"),
            out,
            err,
        )
    )
    # Supply the inline callback for this operation.
    published = published or (
        lambda run_id: validate_published(directory, run_id, cleanup_timeout)
    )
    # Supply the inline callback for this operation.
    cleanup = cleanup or (
        lambda run_id: cleanup_run(directory, run_id, cleanup_timeout)
    )
    value = load_outcomes(directory, create=True)
    for row in value["runs"]:
        if row["status"] != "running":
            continue
        recover_artifacts(directory, row["run_id"])
        cleanup(row["run_id"])
        complete = published(row["run_id"])
        finish_run(
            directory,
            row["index"],
            "complete" if complete else "interrupted",
            0 if complete else 130,
            "recovered published run"
            if complete
            else "previous executor interrupted; no retry",
        )
    value = load_outcomes(directory)
    if "deadline_utc" not in value:
        value["started_utc"] = stamp()
        maximum = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=budget
        )
        absolute = read(directory / "admission.json").get("series_end_utc")
        if absolute:
            maximum = min(maximum, datetime.datetime.fromisoformat(absolute))
        value["deadline_utc"] = maximum.isoformat()
        save_outcomes(directory, value)
    deadline = datetime.datetime.fromisoformat(value["deadline_utc"]).timestamp()
    (directory / "execution-logs").mkdir(exist_ok=True)
    while True:
        index = next_index(directory)
        if index is None:
            return 0
        if time.time() + run_timeout + 2 * cleanup_timeout > deadline:
            return 124
        value = load_outcomes(directory)
        row = value["runs"][index]
        row.update(status="running", started_utc=stamp())
        save_outcomes(directory, value)
        run_id = row["run_id"]
        try:
            with (
                (directory / "execution-logs" / f"{run_id}.stdout.log").open(
                    "x"
                ) as out,
                (directory / "execution-logs" / f"{run_id}.stderr.log").open(
                    "x"
                ) as err,
            ):
                code = executor(index, out, err)
            recover_artifacts(directory, run_id)
            cleanup(run_id)
            valid = published(run_id)
            if valid:
                status, reason = "complete", "raw validation passed"
            elif (directory / "raw" / run_id).exists() or any(
                (directory / name / "SHA256SUMS").exists()
                for name in artifacts(directory, run_id)
            ):
                status, reason = "rejected", "published raw failed validation"
            else:
                status, reason = (
                    "failed",
                    "measurement timeout"
                    if code == 124
                    else "measurement or publication failure; see retained logs",
                )
            finish_run(directory, index, status, code, reason)
        except KeyboardInterrupt:
            recover_artifacts(directory, run_id)
            cleanup(run_id)
            finish_run(
                directory, index, "interrupted", 130, "executor interrupted; no retry"
            )
            return 130
        except Exception as error:
            value = load_outcomes(directory)
            value["runs"][index]["reason"] = "executor blocked: " + str(error)
            save_outcomes(directory, value)
            raise


# Check the series before execution.
def preflight(directory):
    admission = read(directory / "admission.json")
    timeout = admission["limits"]["cleanup_timeout_seconds"]

    # Compute command.
    def command(argv):
        return subprocess.run(
            argv, check=True, capture_output=True, text=True, timeout=timeout
        ).stdout

    if sys.platform == "darwin":
        if "AC Power" not in command(["pmset", "-g", "batt"]):
            raise ValueError("AC power required")
        if '"AppleClamshellState" = No' not in command(
            ["ioreg", "-r", "-k", "AppleClamshellState", "-d", "4"]
        ):
            raise ValueError("open lid required")
    minimum = 10 * 1024**3
    if shutil.disk_usage(directory).free < minimum:
        raise ValueError("host disk below 10 GiB free")
    environment = read(Path(admission["environment"]["path"]))
    info = json.loads(command(["docker", "info", "--format", "{{json .}}"]))
    expected = environment["vm"]
    if (info["NCPU"], info["MemTotal"], info["Architecture"]) != (
        expected["cpus"],
        expected["mem"],
        expected["platform"],
    ):
        raise ValueError("Docker VM differs from admitted environment")
    services = environment["services"]
    tags = ["wswt-bench-" + r["role"] + ":dev" for r in services]
    images = json.loads(command(["docker", "image", "inspect", *tags]))
    if [image["Id"] for image in images] != [r["id"] for r in services]:
        raise ValueError("runtime images differ from admitted environment")
    tls = Path(os.environ["SERIES_TLS_DIR"]) / "server/good/cert.pem"
    if (
        tls.read_text() != environment["leaf"]
        or tls.read_text() != Path(admission["leaf_pem"]).read_text()
    ):
        raise ValueError("mounted TLS differs from admission")
    disk = command(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "wswt-bench-analyzer:dev",
            "df",
            "-B1",
            "/",
        ]
    )
    if int(disk.splitlines()[-1].split()[3]) < minimum:
        raise ValueError("Docker disk below 10 GiB free")
    ids = command(["docker", "network", "ls", "-q"]).split()
    networks = (
        json.loads(command(["docker", "network", "inspect", *ids])) if ids else []
    )
    subnets = [ipaddress.ip_network(n) for n in ("172.28.10.0/24", "172.28.20.0/24")]
    for network in networks:
        for config in network.get("IPAM", {}).get("Config") or []:
            if not config.get("Subnet"):
                continue
            subnet = ipaddress.ip_network(config["Subnet"])
            if any(
                subnet.version == lab.version and subnet.overlaps(lab)
                for lab in subnets
            ):
                raise ValueError("measurement subnets occupied; retain other projects")
    argv = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-v",
        str(Path.cwd()) + ":/bench",
        "-v",
        str(Path.cwd()) + ":" + str(Path.cwd()),
        "-w",
        "/bench",
        "wswt-bench-analyzer:dev",
        "python",
        "-B",
        "-m",
        "admission.exploratory",
        "check",
        str(directory),
    ]
    command(argv)


# Compute report after cleanup.
def report_after_cleanup(directory):
    timeout = read(directory / "admission.json")["limits"]["cleanup_timeout_seconds"]
    projects = {
        p.name.removesuffix(".partial")
        for base in (directory, directory / "quarantine")
        for p in base.glob("wswt-d3-wswt-measure-*")
        if p.is_dir()
    }
    for project in projects:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + project,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stdout.strip():
            print(
                "Analysis deferred: measurement containers remain for " + project,
                file=sys.stderr,
            )
            return 2
    with (
        (directory / "analysis.stdout.log").open("a") as out,
        (directory / "analysis.stderr.log").open("a") as err,
    ):
        return bounded_process(
            ["sh", "docker/commands/analyze.sh", str(directory), "--all-outcomes"],
            300,
            timeout,
            stdout=out,
            stderr=err,
        )


# Run the supplied data.
def run(directory):
    # Record the interruption request.
    def interrupted(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    if not is_exploratory(directory):
        raise ValueError("explicit exploratory admission required")
    with (directory / "execution.flock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code = 2
        try:
            for row in load_outcomes(directory)["runs"]:
                if row["status"] == "running":
                    recover_artifacts(directory, row["run_id"])
                    cleanup_run(
                        directory,
                        row["run_id"],
                        read(directory / "admission.json")["limits"][
                            "cleanup_timeout_seconds"
                        ],
                    )
            preflight(directory)
            code = collect(directory)
        except Exception as error:
            print(str(error), file=sys.stderr)
        finally:
            try:
                analysis_code = report_after_cleanup(directory)
            except Exception as error:
                print("Analysis failed: " + str(error), file=sys.stderr)
                analysis_code = 2
            (directory / "analysis-exit.json").write_text(
                json.dumps(dict(exit_code=analysis_code, ended_utc=stamp())) + "\n"
            )
        return code or analysis_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run"])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        sys.exit(run(args.directory))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
