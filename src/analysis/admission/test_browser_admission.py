import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from admission.browser_admission import create, validate
from measurement.raw import digest, read, write


class BrowserAdmissionTests(unittest.TestCase):
    def test_failed_history_is_preserved_and_scope_cannot_expand(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            context = dict(host="host", vm=dict(cpus=2, mem=4109484032), leaf="leaf", services=[dict(role=role) for role in ("browser", "server", "router")],
                           bindings={"configs/contracts/protocol.json": digest(Path("configs/contracts/protocol.json"))}, config={name:read(Path("configs")/f"{name}.json")
                                                for name in ("plan", "thresholds", "profiles")})
            env, historical, policy, decision = [root/name for name in ("env.json", "failed.json", "policy.md", "decision.json")]
            write(env, context)
            from admission.admission import ref
            report = dict(source_hashes={"source":"exact"}, kind="real", gate="calibration", status="failed", result=dict(status="failed"),
                          environment=ref(env), evidence=[], integrity=dict(files={str(env):ref(env)["sha256"]},trees={}))
            write(historical, report)
            policy.write_text("User-authorized diagnostic study with fixed sample and known limitations")
            before = historical.read_bytes()
            with patch("admission.browser_admission.sources", return_value={"source":"exact"}):
                create(decision, env, historical, policy)
                self.assertEqual(validate(decision, env)["scope"], "diagnostic-generator")
                self.assertEqual(historical.read_bytes(), before)
                with self.assertRaisesRegex(ValueError, "immutable"):
                    create(decision, env, historical, policy)
                with patch("admission.browser_admission.sources", return_value={"source":"unexpected"}):
                    with self.assertRaisesRegex(ValueError, "unexpected source change"):
                        create(root/"unexpected.json", env, historical, policy)
                accepted = read(decision)
                write(decision, dict(accepted, scope="main"))
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    validate(decision, env)
                write(decision, accepted)
                with patch("admission.browser_admission.sources", return_value={"source":"changed"}):
                    with self.assertRaisesRegex(ValueError, "source/environment"):
                        validate(decision, env)
                policy.write_text("changed")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    validate(decision, env)

    def test_historical_integrity_is_required(self):
        from admission.admission import ref, sources
        from admission.browser_admission import historical_calibration
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env, report = root/"env.json", root/"report.json"
            context = dict(host="host",vm={},leaf="leaf",services=[])
            write(env,context)
            data = dict(source_hashes=sources(), kind="real",gate="calibration",status="failed",result=dict(status="failed"),
                        environment=ref(env),evidence=[],integrity=dict(files={str(env):"bad"},trees={}))
            write(report,data)
            with self.assertRaisesRegex(ValueError,"immutable evidence changed"):
                historical_calibration(ref(report),context)
            write(report,dict(data,status="passed"))
            with self.assertRaisesRegex(ValueError,"preserved failed"):
                historical_calibration(ref(report),context)


if __name__ == "__main__":
    unittest.main()
