import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/analysis"))

from calibration_probe import collection_tag

PROFILES = ("r20p0", "r20p1", "r80p0", "r80p1")
PORT = 29543


# Reject inputs that do not satisfy the condition.
def require(condition, message):
    if not condition:
        raise ValueError(message)


# Compute ingress.
def ingress(path, source, destination, tag):
    packets = []
    with path.open("rb") as capture:
        magic = capture.read(4)
        require(
            magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4"), "expected classic pcap"
        )
        endian = "<" if magic == b"\xd4\xc3\xb2\xa1" else ">"
        header = capture.read(20)
        require(
            struct.unpack_from(endian + "I", header, 16)[0] == 1, "expected Ethernet"
        )
        while record := capture.read(16):
            _, _, captured, length = struct.unpack(endian + "IIII", record)
            frame = capture.read(captured)
            require(len(frame) == captured, "truncated capture")
            if frame[12:14] != b"\x08\x00":
                continue
            ip = frame[14:]
            require(ip[0] >> 4 == 4 and len(ip) >= 20, "invalid IPv4")
            require(
                not (int.from_bytes(ip[6:8], "big") & 0x3FFF), "fragmentation observed"
            )
            if ip[9] != 17:
                continue
            require(ip[12:16] == source and ip[16:20] == destination, "foreign flow")
            udp = ip[(ip[0] & 15) * 4 :]
            sport, dport, udp_length = struct.unpack_from("!HHH", udp)
            require(
                PORT in (sport, dport)
                and udp_length == 264
                and length == 14 + (ip[0] & 15) * 4 + 264,
                "unexpected UDP flow or frame accounting",
            )
            identity, observed_tag = struct.unpack_from("!I8s", udp, 8)
            require(observed_tag == tag, "foreign collection in packet capture")
            packets.append(identity)
    require(len(set(packets)) == len(packets), "duplicate ID on router ingress")
    return set(packets)


# Compute directions.
def directions(directory, probe):
    browser = bytes([172, 28, 10, 10])
    server = bytes([172, 28, 20, 10])
    collection_id = f"{directory.parent.name}/{directory.name}"
    require(probe["collection_id"] == collection_id, "foreign probe collection")
    tag = collection_tag(collection_id)
    forward = ingress(directory / "browser.pcap", browser, server, tag)
    reverse = ingress(directory / "server.pcap", server, browser, tag)
    sent = {r["id"] for r in probe["sent_records"]}
    returned = {r["id"] for r in probe["reply_records"]}
    require(
        sent == forward and returned <= reverse <= forward,
        "UDP ingress/survivor mismatch",
    )
    result = []
    for label, dev, entered, delivered in [
        ("forward", "to_server", forward, reverse),
        ("reverse", "to_browser", reverse, returned),
    ]:
        drops = entered - delivered
        counts = []
        for when in ("before", "after"):
            rows = [
                q
                for q in json.loads((directory / f"qdisc-{when}.json").read_text())
                if q.get("dev") == dev and q["kind"] == "netem"
            ]
            require(
                len(rows) == 1 and rows[0]["qlen"] == 0 and rows[0]["backlog"] == 0,
                "undrained qdisc",
            )
            counts.append(rows[0]["drops"])
        require(
            counts[1] - counts[0] == len(drops), "endpoint loss differs from tc drops"
        )
        result.append(
            dict(
                direction=label, entered_ids=sorted(entered), dropped_ids=sorted(drops)
            )
        )
    return result


# Compute rate.
def rate(directory, direction, loss):
    rows = (directory / "window.txt").read_text().splitlines()
    require(len(rows) == 6, "incomplete saturation window")
    first, last = json.loads(rows[2]), json.loads(rows[5])
    duration = float(rows[3]) - float(rows[0])
    require(
        duration >= 60
        and first["dev"] == last["dev"]
        and first["kind"] == last["kind"] == "netem",
        "saturation sampling window",
    )
    sent = json.loads((directory / "probe.json").read_text())
    require(
        sent["collection_id"] == f"{directory.parent.name}/{directory.name}",
        "foreign saturation collection",
    )
    require(
        (sent["last_ns"] - sent["first_ns"]) / 1e9 >= duration
        and sent["frame_bytes"] == 1200,
        "offered load coverage",
    )
    require(
        sent["first_uptime"] < float(rows[0]) < float(rows[3]) < sent["last_uptime"],
        "rate window outside offered load",
    )
    return dict(
        direction=direction,
        loss=loss,
        duration_s=duration,
        accounting_level="router netem dequeued skb bytes including Ethernet header; offered veth ingress rx_bytes",
        offered_bytes=int(rows[4]) - int(rows[1]),
        forwarded_bytes=last["bytes"] - first["bytes"],
    )


# Compute collection plan.
def collection_plan():
    from measurement.raw import read

    names = (
        ["baseline-before"]
        + [f"{p}-before" for p in PROFILES]
        + [f"{p}-latency" for p in PROFILES]
        + [f"{p}-after" for p in PROFILES]
        + ["baseline-after"]
    )
    names += [
        f"saturation-{loss}-{direction}"
        for loss in (0, 1)
        for direction in ("forward", "reverse")
    ]
    return dict(
        method=read(Path("configs/plan.json"))["calibration"],
        collections=[
            dict(
                name=name, forward_seed=20261110 + 2 * i, reverse_seed=20261111 + 2 * i
            )
            for i, name in enumerate(names)
        ],
    )


# Package the calibration report and its evidence.
def package(directory, review_path, env_path):
    from admission.admission import ref, sources
    from measurement.raw import read, write

    require(
        (directory / "exit").read_text().strip() == "0", "collection did not finish"
    )
    for entry in read(directory / "captured.json"):
        from admission.admission import checked

        checked(entry)
    require(
        read(directory / "collection-plan.json") == collection_plan(),
        "calibration preregistered plan mismatch",
    )
    review = read(review_path)
    method = read(directory / "collection-plan.json")["method"]["method"]
    from calibration.calibration_observed import METHOD as OBSERVED_METHOD

    if method == OBSERVED_METHOD:
        require(
            review.get("trace_review", {}).get("observed_period_reviewed") is True,
            "explicit observed-period review required",
        )
    else:
        require(
            all(
                isinstance(review.get("assumptions", {}).get(k), str)
                and review["assumptions"][k].strip()
                for k in ("stationarity", "short_memory", "bernoulli_loss")
            ),
            "process assumptions rationale required",
        )
    require(
        review["collection_id"] == directory.name
        and review["reviewer"]
        and review["rationale"].strip(),
        "collection-specific independent trace review required",
    )
    require(
        read(directory / "context-before.json")
        == read(directory / "context-after.json")
        == read(env_path),
        "environment mismatch",
    )
    original = read(directory / "sources-before.json")
    require(
        original == read(directory / "sources-after.json") == sources(),
        "source inventory changed",
    )
    echo, egress, saturation = {}, [], []
    for label in ("before", *PROFILES, "after"):
        name = f"{label}-latency" if label in PROFILES else f"baseline-{label}"
        path = directory / name
        probe = read(path / "probe.json")
        directions(path, probe)
        echo[label] = probe
    for profile in PROFILES:
        for when in ("before", "after"):
            path = directory / f"{profile}-{when}"
            probe = read(path / "probe.json")
            for row in directions(path, probe):
                row.update(
                    profile=profile, when=when, collection_id=probe["collection_id"]
                )
                if row["direction"] == "forward":
                    row["probe"] = probe
                egress.append(row)
    for loss in (0, 1):
        for direction in ("forward", "reverse"):
            path = directory / f"saturation-{loss}-{direction}"
            saturation.append(rate(path, direction, loss / 100))
    values = dict(
        method=method,
        echo=echo,
        egress=egress,
        saturation=saturation,
        trace_review=review["trace_review"],
    )
    common = dict(
        kind="real",
        gate="calibration",
        collection_id=directory.name,
        environment=ref(env_path),
        source_hashes=original,
    )
    evidence = [ref(p) for p in sorted(directory.rglob("*")) if p.is_file()] + [
        ref(review_path)
    ]
    output = directory / "publication"
    output.mkdir()
    payload = output / "primary.json"
    write(
        payload, dict(gate="calibration", collection_id=directory.name, values=values)
    )
    collection = output / "collection.json"
    write(collection, dict(**common, payload=ref(payload)))
    write(
        output / "input.json",
        dict(**common, collection=ref(collection), evidence=evidence, **values),
    )


if __name__ == "__main__":
    if sys.argv[1] == "plan":
        from measurement.raw import write

        write(Path(sys.argv[2]) / "collection-plan.json", collection_plan())
    elif sys.argv[1] == "context":
        from admission.admission import sources
        from execution.series import context_snapshot
        from measurement.raw import write

        directory = Path(sys.argv[2])
        write(directory / f"context-{sys.argv[3]}.json", context_snapshot(directory))
        write(directory / f"sources-{sys.argv[3]}.json", sources())
    elif sys.argv[1] == "seal":
        from admission.admission import ref
        from measurement.raw import write

        directory = Path(sys.argv[2])
        write(
            directory / "captured.json",
            [ref(p) for p in sorted(directory.rglob("*")) if p.is_file()],
        )
    elif sys.argv[1] == "package":
        package(*(Path(arg) for arg in sys.argv[2:]))
    else:
        raise SystemExit(2)
