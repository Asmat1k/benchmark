import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from admission.admission import admit, controller_session
from measurement.raw import read, require
from execution.series import queue


# Compute dispatch.
def dispatch(directory, request, kind):
    action = request["action"]
    if action == "next":
        admit(directory, kind)
        require(not (directory / "STOP").exists(), "series stopped")
        if (directory / "PENDING_REPLACEMENT").exists() or (
            directory / "replacement.json"
        ).exists():
            return 2, "replacement pending"
        schedule = read(directory / "schedule.json")
        remaining = queue(directory)
        if not remaining:
            return 0, "complete"
        pending = [
            i
            for i, r in enumerate(schedule["runs"])
            if r["attempt_id"] == remaining[0]
            and not (directory / "raw" / r["run_id"]).exists()
        ]
        require(pending, "no pending member")
        return 0, str(pending[0])
    from execution.record import run_spec, complete, bind_run_context

    partial = Path(request["partial"])
    require(
        partial.resolve().is_relative_to(directory.resolve()),
        "foreign partial directory",
    )
    with contextlib.redirect_stdout(io.StringIO()) as output:
        if action == "prepare":
            run_spec(directory, request["index"], partial)
        elif action == "context":
            bind_run_context(directory, request["index"], partial)
        elif action == "complete":
            complete(directory, request["index"], partial)
        else:
            raise ValueError("unknown controller action")
    return 0, output.getvalue().strip()


# Serve requests using the configured listener.
def serve(directory, kind="real"):
    with controller_session(directory, kind):
        print(
            json.dumps(
                dict(
                    code=0,
                    value="ready",
                    commit=read(directory / "admission.json")["release_commit"],
                )
            ),
            flush=True,
        )
        for line in sys.stdin:
            try:
                code, value = dispatch(directory, json.loads(line), kind)
            except SystemExit as error:
                code, value = error.code, str(error)
            except Exception as error:
                code, value = 2, str(error)
            print(json.dumps(dict(code=code, value=value)), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        serve(args.directory)
    except Exception as error:
        print(json.dumps(dict(code=2, value=str(error))), flush=True)
        raise SystemExit(2)
