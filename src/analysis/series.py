import contextlib
import fcntl
import subprocess
import sys
from pathlib import Path

from raw import digest, read, require, write


def queue(directory):
    ledger = read(directory / "ledger.json")
    planned = [a["attempt_id"] for a in ledger["attempts"] if a["status"] == "planned"]
    path = directory / "queue.json"
    return [a for a in (read(path) if path.exists() else planned) if a in planned]


def advance(directory, schedule, run):
    ledger = read(directory / "ledger.json")
    members = [r for r in schedule["runs"] if r["attempt_id"] == run["attempt_id"]]
    if all((directory / "raw" / r["run_id"]).exists() for r in members):
        next(a for a in ledger["attempts"] if a["attempt_id"] == run["attempt_id"])["status"] = "complete"
        write(directory / "ledger.tmp", ledger)
        (directory / "ledger.tmp").replace(directory / "ledger.json")
        write(directory / "queue.json", queue(directory))


@contextlib.contextmanager
def measurement_lock():
    if sys.platform == "darwin":
        process = subprocess.Popen(["docker", "run", "--rm", "-i", "--network", "none",
            "-v", f"{Path.cwd()}:/bench", "-w", "/bench", "wswt-bench-analyzer:dev",
            "python", "-B", "src/analysis/series.py", "hold"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            if process.stdout.readline().strip() != "locked":
                raise BlockingIOError("Measurement lock held")
            yield
        finally:
            process.stdin.close()
            process.wait()
    else:
        path = Path("build/measurement.flock")
        path.parent.mkdir(exist_ok=True)
        with path.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def context_snapshot(partial):
    names = ("plan", "thresholds", "profiles")
    context = dict(bindings={p:digest(Path(p)) for p in ("docs/protocol.md", "src/client/package-lock.json", "src/runner/package-lock.json", "src/server/go.sum", "src/analysis/requirements.txt")}, host=(partial / "host.txt").read_text(), vm=read(partial / "vm.json"),
                   leaf=(partial / "leaf.pem").read_text(),
                   config={n: read(Path("configs") / f"{n}.json") for n in names},
                   services=sorted([dict(role=r["role"].rsplit("-", 2)[-2],
                                        **{k: r[k] for k in ("id", "cpu", "memory", "shm")})
                                    for r in read(partial / "limits.json")], key=lambda r: r["role"]))
    return context


def bind_context(directory, partial):
    context = context_snapshot(partial)
    if (directory / "admission.json").exists():
        from admission import admit, checked
        admission = admit(directory)
        require(context == read(checked(admission["environment"])), "admitted environment differs from actual run")
        if "freeze" in admission:
            import hashlib
            import ssl
            frozen = read(checked(admission["freeze"]))
            leaf_hash = hashlib.sha256(ssl.PEM_cert_to_DER_cert(context["leaf"])).hexdigest()
            require(leaf_hash == frozen["bindings"]["leaf_der"]["sha256"], "mounted leaf differs from freeze")
    path = directory / "context.json"
    if path.exists():
        require(context == read(path), "environment changed: series context")
    else:
        write(path, context)
    write(partial / "context.json", context)


if __name__ == "__main__":
    try:
        with measurement_lock():
            print("locked", flush=True)
            sys.stdin.buffer.read()
    except BlockingIOError:
        print("busy", flush=True)
        raise SystemExit(2)
