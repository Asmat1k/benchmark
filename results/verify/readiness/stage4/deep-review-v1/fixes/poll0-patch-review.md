# Read-only review of the applied poll0 change

Reviewed commit `12ba5e5e5740c2f0acf61e6bd4849026ef136c26` against `494e1a9`. Reviewer: Codex subagent `fix_research`. No production edits or timing workload were run by this reviewer while the parent executed the fixed two-profile validation.

## Patch correctness

The production change is one constant: `MAX_ECHO_WAIT_NS` changes from 1,000,000 to 0. The ordinary echo loop therefore calls `select` with timeout zero while preserving the absolute 100 Hz schedule, 10,000 IDs, 256-byte payload/tag, 2.5 ms minimum actual-send spacing, timestamp immediately before send, complete replies, and actual RTT calculation. No samples are corrected or excluded.

Saturation explicitly selects `remaining`, so its 800 µs pacing, 90,000 packets and 1,200-byte frames remain unchanged. The final echo drain retains its original two-second blocking timeout. Actual socket `recv` and `send` remain blocking: “no blocking anywhere” would be an incorrect description. Only deliberate waits in the scheduled ordinary send loop are removed.

The fake clock now advances when a mocked zero-timeout select is called. Otherwise the mock could never reach its deadline. This is a test model, not a production delay or evidence of OS timing. The test still injects 55 ms pauses and retains strict boundary assertions. The parent reported 11 tests passed.

## Supported effect and CPU cost

The fixed baseline ABBA used 5,000 IDs per phase. Waiting A phases had p99 send lag 0.858547/0.885714 ms; poll0 B phases had 0.017517/0.017229 ms. RTT p99 changed from 1.784583/1.566922 ms to 0.802545/0.785895 ms. Improvement also appears in router-span timestamps, not merely in client reply logging. Returning to A restored the phase structure. Packet review checked all 70 sealed files and all four ID/tag/drop correspondences.

Sender CPU changed from 2.242/2.199% of one core to 95.529/95.460%: approximately +93.3 percentage points and 43 times the CPU time per phase-second. This is economical in implementation effort, **not energy consumption**. On a 2-vCPU VM it occupies almost one core, approximately 47.8% of total VM CPU capacity. The extra probe runs in its own cgroup; sharing a browser network namespace does not give it the browser CPU quota. Its CPU must not be reported as browser-generator CPU or treated as passing that formal gate.

Removing sleep changes runnable state and CPU residency together. Short ABBA does not distinguish guest timer handling, vCPU idling, or host scheduling as the exclusive cause, nor prove that arbitrary host preemption is impossible. Historical 129 ms pauses remain unexplained at that precision.

## Which prior admissions no longer apply automatically

- **Qualification Mbdvg8v6:** `docker/calibration_probe.py` is one of its 13 captured dependencies and now differs. The previous collector-only applicability argument no longer holds. A new full fixed qualification is required; do not replace historical hashes.
- **Six early reports:** their `source_hashes` bind the old inventory. Update release-state/inventory and create newly validated source-bound publications. Unchanged build/runtime observations may be reused only with explicit provenance where the standard contract permits it.
- **Timer raw:** the standard `diagnostic_raw` guard requires current `collection-sources`; the old raw cannot simply receive a new source hash. A fresh timer collection is required for the current standard report path.
- **Browser-bandwidth raw:** the standard adapter likewise requires the same current inventory as calibration. A new three-mode BW collection is required for a new standard pair.
- **Calibration lShojabe:** remains failed and sealed. Poll0 changes the calibrator's CPU load and observed RTT conditions. Its capacity/RTT data cannot be represented as measured under poll0. A new full 14-echo/4-saturation collection, unchanged block inference and substantive assumption review remain necessary.
- **Generator:** WS/WT-S/WT-D × 20/100 Hz remains not run. UDP polling evidence cannot establish this formal browser gate.

Exact images, resource limits and TLS can remain identical because the modified sender/test are host-mounted, not image build inputs. This does not preserve source-bound report freshness. An existing image archive can remain valid for identical image IDs after verification; rebuilding or archiving identical images is not inherently required.

## Required limits on the conclusion

ABBA and two similar-profile 10,000-ID probes are diagnostics, not full qualification, calibration or stage-4 completion. Absence of rare pauses in a short test does not establish 30-minute reliability. Two profiles do not cover all 14 series and four saturation windows. No diagnostic flag is not automatic proof of stationarity, short memory or independent Bernoulli loss. Thresholds, blocks and volume must remain unchanged.

The defensible conclusion is: **a minimal runtime change was implemented and supported by short diagnostics, with substantial disclosed CPU cost; full acceptance remains outstanding.** No A/A, monitoring, pilot/power, freeze or main admission follows from this work. Preserve every historical failure and negative candidate experiment.

Inputs: `git show 12ba5e5`; `wake-abba/analysis.json`; `dependence/wake-abba-analysis/{README.md,correctness.json,analysis.json}`; `configs/{thresholds,plan}.json`; `docs/readiness/stage4-polling-validation-plan.md`.
