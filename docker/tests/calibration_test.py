import json
import struct
import tempfile
import unittest
from pathlib import Path

from calibration_probe import collection_tag
from calibration_report import directions, rate


# Capture the requested calibration evidence.
def capture(path, source, destination, ids):
    data = bytearray(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 96, 1))
    tag = collection_tag(f"{path.parent.parent.name}/{path.parent.name}")
    for i in ids:
        ip = struct.pack(
            "!BBHHHBBH4s4s", 0x45, 0, 284, 0, 0, 64, 17, 0, source, destination
        )
        udp = struct.pack("!HHHHI8s", 29543, 30000, 264, 0, i, tag)
        frame = bytes(12) + b"\x08\x00" + ip + udp
        data.extend(struct.pack("<IIII", 0, 0, len(frame), 298) + frame)
    path.write_bytes(data)


class Calibration(unittest.TestCase):
    # Check observed package requires saved plan and explicit review.
    def test_observed_package_requires_saved_plan_and_explicit_review(self):
        from unittest.mock import patch
        import calibration_report
        from calibration.calibration_observed import METHOD

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "collection"
            directory.mkdir()
            (directory / "exit").write_text("0")
            review = dict(
                collection_id="collection",
                reviewer="independent unit fixture",
                rationale="synthetic packaging test",
                trace_review=dict(observed_period_reviewed=True),
            )
            plan = calibration_report.collection_plan()

            # Read JSON from the supplied path.
            def read(path):
                path = Path(path)
                if path.name == "captured.json":
                    return []
                if path.name == "collection-plan.json":
                    return plan
                if path.name == "review.json":
                    return review
                if path.name == "probe.json":
                    return dict(collection_id=path.parent.name)
                if path.name.startswith("context-") or path.name in (
                    "ENV.json",
                    "sources-before.json",
                    "sources-after.json",
                ):
                    return {}
                raise AssertionError(path)

            # Supply the inline callback for this operation.
            with (
                patch("measurement.raw.read", side_effect=read),
                patch("calibration_report.collection_plan", return_value=plan),
                patch("admission.admission.sources", return_value={}),
                patch(
                    "admission.admission.ref",
                    side_effect=lambda p: dict(path=str(p), sha256="a" * 64),
                ),
                patch(
                    "calibration_report.directions",
                    return_value=[dict(direction="forward"), dict(direction="reverse")],
                ),
                patch("calibration_report.rate", return_value={}),
            ):
                review["trace_review"]["observed_period_reviewed"] = False
                with self.assertRaisesRegex(
                    ValueError, "explicit observed-period review"
                ):
                    calibration_report.package(
                        directory, Path("review.json"), Path("ENV.json")
                    )
                review["trace_review"]["observed_period_reviewed"] = True
                calibration_report.package(
                    directory, Path("review.json"), Path("ENV.json")
                )
            payload = json.loads((directory / "publication/primary.json").read_text())
            self.assertEqual(payload["values"]["method"], METHOD)
            self.assertTrue(
                payload["values"]["trace_review"]["observed_period_reviewed"]
            )
            self.assertEqual(len(payload["values"]["echo"]), 6)
            self.assertEqual(len(payload["values"]["egress"]), 16)
            self.assertEqual(len(payload["values"]["saturation"]), 4)

    # Check actual directional losses.
    def test_actual_directional_losses(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            browser, server = bytes([172, 28, 10, 10]), bytes([172, 28, 20, 10])
            capture(directory / "browser.pcap", browser, server, [0, 1, 2, 3])
            capture(directory / "server.pcap", server, browser, [0, 2, 3])
            for phase, drops in [("before", 0), ("after", 1)]:
                rows = [
                    dict(dev=dev, kind="netem", drops=drops, qlen=0, backlog=0)
                    for dev in ("to_server", "to_browser")
                ]
                (directory / f"qdisc-{phase}.json").write_text(json.dumps(rows))
            probe = dict(
                collection_id=f"{directory.parent.name}/{directory.name}",
                sent_records=[dict(id=i) for i in range(4)],
                reply_records=[dict(id=i) for i in (0, 3)],
            )
            forward, reverse = directions(directory, probe)
            self.assertEqual(
                ([1], [0, 2, 3], [2]),
                (
                    forward["dropped_ids"],
                    reverse["entered_ids"],
                    reverse["dropped_ids"],
                ),
            )
            capture(directory / "server.pcap", server, browser, [0, 3])
            with self.assertRaisesRegex(ValueError, "tc drops"):
                directions(directory, probe)
            capture(directory / "server.pcap", server, browser, [0, 0, 3])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                directions(directory, probe)

    # Check latency collection cannot supply loss.
    def test_latency_collection_cannot_supply_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            latency = root / "r20p0-latency"
            loss = root / "r20p0-before"
            latency.mkdir()
            loss.mkdir()
            capture(
                latency / "browser.pcap",
                bytes([172, 28, 10, 10]),
                bytes([172, 28, 20, 10]),
                [0],
            )
            (loss / "browser.pcap").write_bytes((latency / "browser.pcap").read_bytes())
            with self.assertRaisesRegex(ValueError, "foreign probe collection"):
                directions(loss, dict(collection_id=f"{root.name}/{latency.name}"))
            with self.assertRaisesRegex(
                ValueError, "foreign collection in packet capture"
            ):
                directions(loss, dict(collection_id=f"{root.name}/{loss.name}"))

    # Check saturation window.
    def test_saturation_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            # Supply the inline callback for this operation.
            q = lambda size: json.dumps(dict(dev="to_server", kind="netem", bytes=size))
            (directory / "window.txt").write_text(
                "\n".join(["10", "4", q(10), "71", "82", q(75)])
            )
            probe = dict(
                collection_id=f"{directory.parent.name}/{directory.name}",
                frame_bytes=1200,
                last_ns=72000000000,
                first_ns=0,
                first_uptime=5,
                last_uptime=77,
            )
            (directory / "probe.json").write_text(json.dumps(probe))
            result = rate(directory, "forward", 0)
            self.assertEqual(
                (61, 78, 65),
                (
                    result["duration_s"],
                    result["offered_bytes"],
                    result["forwarded_bytes"],
                ),
            )
            probe["first_uptime"] = 11
            (directory / "probe.json").write_text(json.dumps(probe))
            with self.assertRaisesRegex(ValueError, "outside"):
                rate(directory, "forward", 0)


if __name__ == "__main__":
    unittest.main()
