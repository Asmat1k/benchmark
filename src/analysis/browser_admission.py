import argparse
from pathlib import Path

from admission import check_integrity, checked, ref, sources
from collection import environment
from raw import binding_digest, digest, now, read, require, write

POLICY = dict(sample="fixed-planned-sample-all-outcomes", violations="report-n-minus-i-and-i-without-exclusion",
              missing="unknown-no-rtt-imputation", lag="observed-no-subtraction",
              scope="diagnostic-generator-only-no-main-admission")
ADMISSION_SOURCE_CHANGES = {"src/analysis/browser_admission.py", "src/analysis/test_browser_admission.py",
                            "docker/commands/collect-diagnostic.sh", "configs/contracts/protocol.json", "configs/plan.json",
                            "configs/schemas/plan.schema.json", "docker/commands/measure.sh", "docker/commands/experiment.sh",
                            "src/analysis/raw.py", "src/analysis/record.py", "src/analysis/test_stabilization_cpu.py",
                            "src/analysis/test_diagnostic_input.py"}
LIMITATIONS = ["historical-udp-calibration-failed", "vm-2vcpu-4109484032-bytes",
               "scheduler-backlog-unresolved", "100hz-reserve-separate-from-20hz-main"]


def current_environment(path):
    context = environment(path)
    require(all(binding_digest(name) == sha for name, sha in context["bindings"].items()),
            "browser admission stale environment bindings")
    require(context["config"] == {name: read(Path("configs") / f"{name}.json")
                                  for name in ("plan", "thresholds", "profiles")},
            "browser admission stale environment config")
    require(context["vm"]["cpus"] == 2 and context["vm"]["mem"] == 4109484032,
            "browser admission applies to measured VM only")
    return context


def historical_calibration(binding, context):
    report = read(checked(binding))
    require(report["kind"] == "real" and report["gate"] == "calibration" and
            report["status"] == report["result"]["status"] == "failed",
            "browser admission requires preserved failed calibration")
    current = sources()
    historical_sources = report["source_hashes"]
    changed = {name for name in current.keys() | historical_sources.keys()
               if current.get(name) != historical_sources.get(name)}
    require(changed <= ADMISSION_SOURCE_CHANGES, "browser admission unexpected source change: "+str(sorted(changed-ADMISSION_SOURCE_CHANGES)))
    historical = read(checked(report["environment"]))
    require(all(context[key] == historical[key] for key in ("host", "vm", "leaf", "services")),
            "browser admission historical hardware/images/TLS mismatch")
    for item in report["evidence"]:
        checked(item)
    check_integrity(report["integrity"])
    return report


def validate(path, environment_path):
    decision = read(path)
    require(decision["schema_version"] == 1 and decision["decision"] == "admitted-with-known-limitations" and
            decision["scope"] == "diagnostic-generator" and decision["policy"] == POLICY and
            decision["limitations"] == LIMITATIONS, "unsupported browser admission decision")
    require(decision["source_hashes"] == sources() and decision["environment"] == ref(environment_path),
            "browser admission source/environment mismatch")
    checked(decision["policy_document"])
    historical_calibration(decision["historical_calibration"], current_environment(environment_path))
    return decision


def create(path, environment_path, calibration_path, policy_path):
    require(not path.exists(), "browser admission is immutable")
    context = current_environment(environment_path)
    historical_calibration(ref(calibration_path), context)
    decision = dict(schema_version=1, decision="admitted-with-known-limitations", scope="diagnostic-generator",
                    utc=now(), source_hashes=sources(), environment=ref(environment_path),
                    policy_document=ref(policy_path), historical_calibration=ref(calibration_path),
                    policy=POLICY, limitations=LIMITATIONS)
    write(path, decision)
    return decision


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "check"))
    parser.add_argument("decision", type=Path)
    parser.add_argument("environment", type=Path)
    parser.add_argument("calibration", type=Path, nargs="?")
    parser.add_argument("policy", type=Path, nargs="?")
    args = parser.parse_args()
    if args.action == "create":
        require(args.calibration is not None and args.policy is not None, "calibration and policy required")
        create(args.decision, args.environment, args.calibration, args.policy)
    else:
        validate(args.decision, args.environment)
    print(args.decision)
