# Independent prerequisite and reuse review

2026-11-14. Internal subagent inspection of stage4-primary-v4.py, release-v4 evidence, current diff, sender qualification6uYg6iiy and browser-bandwidth-v4.9r51339s. No network, image build or long command was launched; executable sources were not edited. Recommendations below require actual checks after final source fixation and are not passed gates.

## Minimal order

1. Finish implementation, regression tests and independent diff review; update protocol before recording release. Commit only intended sources/docs, preserve untracked historical artifacts. Generate current release-state and inventory, record exact old-to-new delta and host-mounted analyzer applicability.
2. Run one short bounded preflight/smoke/timer sequence with original ENV and TLS under caffeinate. Historical release-v4 smoke took15.527s, timer73.235s. Its240s total hard limit is a reasonable bounded short check; timeout must preserve interrupted artifacts and cleanup. Preflight must occur before raw/network and include AC/lid/disk/images/TLS reserve/source/subnets/lock/own projects. Existing run-early.py lacks those full checks and hardcodes old output paths, so do not execute it unchanged.
3. Run current short offline known-answer/raw/client/null checks and publish fresh early gate traces referencing their actual logs plus fresh smoke/timer. Keep explicit scope distinctions: fixture edge cases/recovery are not actual real replacement experiments. Do not change old report provenance.
4. Independently establish qualification applicability, then execute the one prospectively planned practical calibration through the user. Review raw and metrics before deciding it passed.
5. Execute the required real generator20/100Hz collection for WS/WT-S/WT-D through the user. Its three20Hz raw runs can also supply browser bandwidth bytecounts paired with the new calibration saturation. This removes the need for an extra separate bandwidth run or a permissive old-source compatibility path.
6. Publish calibration/generator and aggregate current REPORT_MAP: eight passed gates, aa/monitoring not_run, final=false, expected exit2. Only then admit A/A; monitoring follows A/A, pilot follows all10gates. Preserve all failed/inconclusive states.

## Build, TLS, path, timer, raw and analysis

Existing admitted image IDs and Dockerfiles/locks remain unchanged in the inspected diff. No rebuild is needed solely for host-mounted calibration/report/analysis changes. Dockerfile.analyzer copies analysis into /analysis, but collectors explicitly mount repository at /bench and invoke its files; record that the image is the unchanged interpreter/dependency provider while the current mounted sources implement the new policy.

Reuse build install/version/package logs and image archive only with a fresh bounded dependency capsule: Dockerfiles, lockfiles, package lists, requirements, source files used by browser/server runtime, actual image IDs and platform checked. Existing source-archive-preflight concerns image archive bytes, not a new current-source archive. Do not claim the image contains newly edited analyzer files.

Fresh smoke supplies real TLS positive/negative/path/profile observations. Fresh timer diagnostic supplies current raw/config/protocol/source binding, actual timer samples and resource traces. Old timer report cannot become current by changing source_hashes. `diagnostic_input.observations` enforces exact current collection sources; use a newly collected timer report. Require original ENV byte equality or explicitly reassess every affected dependency.

stage4-primary-v4.py is a useful trace construction pattern, but its accepted delta and source paths are hardcoded to stage3/release-v4 and cannot be reused unchanged. It also cites historical offline/client/null logs using an old unchanged-config claim that is false after this policy change. Adapt to fresh release/evidence paths and current test logs. Each predicate must still have actual observations; imported report machinery does not by itself validate that a preparer used a scientifically valid predicate.

Known-answer/raw suite documented in stage3-evidence-plan: StatisticalTests five tests plus six MeasurementTests and two RecoveryTests (13 total) historically1.960s. Client framing tests historically0.152s. Null-family current-context helper is explicitly synthetic and refreshes protocol hashes only on newly created temporary fixtures. Current targeted tests are preferable to claiming unchanged config dependencies. Analyze imports and test prerequisites before setting a short execution cap; commands without a reliable <=5min bound belong to the user.

## Qualification6uYg6iiy

Historical accepted qualification: d665590,3x10000 baseline,79seals,13recorded source dependencies; collection elapsed341.003856s. Raw summary documents complete captures/counters,105samples perrole/series, zero overflow/throttle/OOM, default sender-v2 passed on all3.

At inspection, only `src/analysis/sender_quality.py` differs among its13captured source paths. Its diff adds `enforce_max_lag=True` and conditions the existing max-lag rejection on that flag. Qualification calls use the unchanged default, so collection runtime and default numeric rule are unchanged. That is a strong basis to reuse qualification with an explicit semantic dependency capsule, rather than rerun six minutes of unchanged network load.

Before marking applicability passed: verify all79original seals and unchanged file inventory, before/after original sources and saved source copies; bind original primary-review and execution identity; compare changed evaluator default behavior with original implementation/stored sender-quality results on all3full probes and retain legacy boundary regressions. Confirm unchanged13dependencies except the disclosed evaluator change, actual images/resources/ENV/TLS and absence of intervening collector changes. Record current release/hash, historical release/hash and exact rationale. Do not rewrite old raw/report or claim all13files byte-identical. The original primary.py asserts equality to its134file inventory and will now fail by design; create a new applicability artifact rather than altering it. This qualification does not qualify observed ranges or replace browser generator.

## Bandwidth9r51339s

Historical v4 collection elapsed321s. Browser/client/server/network and measure.sh are unchanged relative to that collection in the inspected delta. Sender poll0/affinity changes affect UDP calibration, not the real browser load. The new plan changes calibration policy, not frame bytes/warmup/measurement/frequency; reuse of raw bytecounts is scientifically plausible with an explicit dependency review.

However, existing `browser_bandwidth.package` and `diagnostic_raw` intentionally require exact current sources/config/protocol; historical validation through current defaults fails. Do not weaken those guards just to reuse this artifact. An honest old-config validation would require a separate immutable historical config root and actual historical protocol/source checks, followed by an explicit dependency bridge to current browser/runtime and new capacity evidence.

The simpler solution is to calculate loads from the20Hz half of the already mandatory fresh generator6run collection. It uses the same3modes,256byteframes,200warmup/1200measurement, baseline and byte counters as bandwidth load_rates. Revalidate every run and retain all resource/timing results; combine load_rates with the four new saturation samples through existing fractions(). The resulting fraction is conservative setup/warmup/measurement/drain bytes divided by60s and remains baseline-only. Existing9r51339s artifacts remain unchanged supplementary evidence.

Generator20Hz/100Hz sixrun collection can exceed5min: collect-diagnostic.sh generator invokes three full20Hz runs and three100Hz runs sequentially. Use the user long-command protocol with unique start/end/stdout/stderr/exit/identity and a predeclared conservative total deadline. No heavy parallel tests during any network measurement.
