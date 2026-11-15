# Independent integration review: observed-profile-check-v1

2026-11-14. Internal subagent review of HEAD d66559066b704fde567b6c9f92f57e2dcde22698, before implementation. This is code/dependency inspection, not external peer review or acceptance of any measurement. No network measurements or historical report changes were performed.

## Minimal implementation boundary

- Dispatch `acceptance.calibration` by explicit method. Keep common ID, RTT, loss-denominator, saturation and trace invariants. Put observed-window and sender shadow calculations in one small new analysis module. Keep main metrics, Q/S/U, paired inference and browser generator unchanged.
- Change `configs/plan.json` and its schema to the fixed observed contract. Leave `thresholds.udp_sender` v2 intact for historical calls and sender qualification; observed calibration may call the existing sender evaluator with an explicit option suppressing only its max-lag failure, then add an explicit observed criteria version and proxy checks. Do not silently change the default evaluator.
- Keep all six latency probes and eight before/after loss probes in sender assessment. Evaluate all 20 contiguous 500 planned-ID windows, not 500 returned RTTs. Empty windows must fail. Name outputs observed ranges rather than confidence intervals; ACF/drift remain diagnostics.
- Existing collection/payload schemas use generic `values`, so they need no new calibration-specific schema branches. Admission source inventory automatically includes new files under src/analysis and docs/schemas.

## Critical integration details

1. `calibration_blocks.intervals` currently requires the current plan to equal legacy constants. Changing the current plan breaks the old method and its tests. Extract the fixed legacy contract and allow explicitly historical legacy computation without claiming it is a current real release. A current real package must still match its prospectively saved plan and source inventory. Keep the existing rejection of unknown method names.
2. `docker/calibration_report.package` currently hardcodes `calibration_blocks.METHOD` and requires stationarity/short-memory/Bernoulli rationale for every package. Select the method from the verified collection plan, and make method-specific review requirements explicit. Do not infer reviewed=true from absence of a field. Keep collection-specific reviewer and rationale, seals, source equality, environment equality, pcap/counters and all existing trace invariants.
3. `probe_records(..., enforce_timing=False)` still invokes the default sender evaluator for integrity; it does not reject timing failures in that mode. A practical wrapper must retain ID ordering, complete 10000 IDs, finite times, 100 Hz grid, nonnegative lag and clock ordering. Retain actual RTT without sender-lag subtraction.
4. Collector minimum echo spacing is 2.5 ms (`MIN_ECHO_GAP_NS`); the existing evaluator only checks monotonic timestamps and burst count. An observed minimum-spacing check can directly enforce the collector contract, accounting for float conversion from ns to ms. This is an invariant, not a new budget fitted to observed results. Test 2.5 ms and just-below boundary.
5. Shadow windows must retain all five phases and all 801 starts per phase, count equality at lag >=50 ms, and distinguish known late reply (`t_send+rtt > t_plan+100`) from unknown missing reply. Loss0 needs zero missing for a complete joint check. Loss1 keeps unknown explicitly and uses lag-only acceptance; known joint lower bounds are descriptive, not full timing rates.
6. The acceptance return structure currently calls all median bounds `intervals`, supplies `CI99`/`confidence` for loss and a survivor-bias string about intervals. Practical output should explicitly identify observed range/fraction and avoid fabricated confidence claims, even if a compatibility field is retained.

## Source and evidence applicability

`admission.aggregate` and `verify` require every report's complete source inventory to equal current sources and recalculate measured gates. Historical reports cannot simply enter a new REPORT_MAP. Dependency reuse needs a newly generated capsule/report with actual evidence of unchanged relevant dependencies, while old reports and hashes remain untouched.

`sources()` includes docs/protocol.md, configs, every src/docker/schema file (including tests), Makefile and compose.yaml. Complete protocol and test edits before the release/source snapshot and prospective verification plan. New analyzer modules are host-mounted by calibration.sh; no image rebuild is implied by their addition.

`collection.measured` checks calibration primary-payload correspondence but does not itself reconstruct calibration from raw as it does timer/generator. The packager checks seals and reconstructs pcap/qdisc-derived directions. Independent raw review remains necessary, including capture logs and all expected file membership; exit0 alone is insufficient.

`browser_bandwidth.package` binds calibration and bytecount artifacts to exact source/environment values. Reuse of unchanged bytecounts must be separately justified, not implemented by rewriting historical hashes. The old stage4-primary-v4 helper hardcodes a bounded source delta and is no longer directly applicable after the new implementation.

## Meaningful regression coverage

- Legacy sender boundaries and legacy calibration tests still run after changing current plan.
- Practical isolated >50 ms lag can pass with disclosed lag and complete records; 500 ms/catchup synthetic case fails shadow budget; frequent shorter pauses also fail where their count exceeds 12.
- All phase/window counts and >=50 / >100 boundaries are checked; an invalid ID, impossible survivor, malformed log or empty window cannot pass.
- 3 ms median regime fails, small median shift remains visible, ACF flag alone does not produce an observed-period stationarity claim.
- Loss0 missing/drop fails; loss1 observed .005/.015 boundaries and actual reverse denominator checked, unknown timing retained. No deleted RTTs or excluded tails.
- Packager selects saved method, rejects plan/source/environment mismatch and missing explicit review. Observed output has no confidence-interval claim.

Update the method paragraphs in docs/protocol.md, docs/verification.md, docs/experiments.md and docker/calibration.md before source fixation. Do not rerun full calibration until implementation, tests and diff review finish.
