# Independent sender/process review of full post-poll0 collection

14 November2026. Codex subagent transition_review performed a separate read-only check of all14echo subseries in `results/verify/diagnostic/calibration.gIdWLx7o` and four named historical comparison subseries in calibration.lShojabe. No network, bootstrap, raw/seal changes or reviewer-approval flags. This is an independent computation within the same Codex team, not an external reviewer approval.

## Reproducible execution

Working directory `/Users/dobrov/Desktop/Code/ITMO/benchmark`.

Command: `python3 -B results/verify/readiness/stage4/calibration-poll0-v1/review/independent.py`

Outputs: `independent.json`, `independent.stderr.log`, execution metadata `independent-execution.json`. Saved deterministic computation ran2026-11-14T09:51:05.051315Z–09:51:05.825102Z, elapsed0.773800s, exit0, empty stderr,90second hard subprocess deadline and Python alarm. Script compute elapsed0.667759s. The initial stdout-only computation completed16.764s/exit0; the saved equivalent removes redundant repeated max calculations and explicitly lists the formal6series subset. No new collection occurred.

Existing `sender_quality.evaluate` was used without modification. Host Python lacks NumPy, so process diagnostics were independently reproduced with stdlib using the same finite-survival series, median-filled RTT, centered dot-product ACF lags500/1000/2000, unchanged3.5/sqrt(n-lag) threshold,20successive500slot medians and OLS fitted drift. Comparing against the primary NumPy-based review afterward gave identical sender metrics/status and all14process flags; maximum ACF numeric difference4.24e-15. No substantial numerical ambiguity near decision thresholds.

## Result and formal scope

Sender14/14passed; worst maxlag35.468481ms(r20p0-after,ID5103),worstlate0.07%,maxburst4/10ms. This supports improved sender behavior on this full run, not guaranteed elimination of rare pauses.

The formal process family consists of baseline-before, four *-latency subseries, and baseline-after. **3/6formal process series suspect**: r20p0-latency,r80p0-latency,r80p1-latency. Thus the necessary formal process prerequisite fails and dependent bootstrap/publication must stop.

The broader diagnostic view evaluates all14 and flags9: r20p0-before,r20p1-before,r80p0-before,r80p1-before,r20p0-latency,r80p0-latency,r80p1-latency,r80p0-after,r80p1-after. These9diagnostic flags must not be described as9failures within the formal6series family. Both baselines clear. All14survival ACF checks clear; flagged ACF concerns RTT. No flag absence is used to assert stationarity or short memory.

|Subseries|maxlag ms|late %|process|
|---|---:|---:|---|
|baseline-before|4.621129|0|clear|
|r20p0-before|29.895251|.07|suspect|
|r20p1-before|7.472376|0|suspect|
|r80p0-before|.046294|0|suspect|
|r80p1-before|.101696|0|suspect|
|r20p0-latency|6.196959|0|suspect|
|r20p1-latency|1.947542|0|clear|
|r80p0-latency|8.723648|0|suspect|
|r80p1-latency|7.697798|0|suspect|
|r20p0-after|35.468481|.04|clear|
|r20p1-after|16.523344|.03|clear|
|r80p0-after|11.678709|.02|suspect|
|r80p1-after|31.415312|.07|suspect|
|baseline-after|14.366293|.02|clear|

r80p1-latency fitted drift3.663525ms,RTTrho500/1000/2000=.473626/.388322/.148673; late five-second medians83.88–84.03ms. r80p1-after drift2.526225ms,rho=.385408/.278979/.214575. r80p0-latency overall median82.133938ms with sustained windows near82.45ms alternating near80.54ms. Exact medians/ACFs for all windows are in independent.json. These are substantial process changes despite timely sender.

## Historical comparison and limits

Recomputed old sender failures: r20p0-after129.224986ms(ID5928)→new35.468481ms(ID5103); r20p1-after53.692504ms(ID891)→16.523344ms(ID2309). Historical baseline-before/r20p0-latency ACF flags also reproduced. This is an across-run comparison, not an otherwise controlled intervention or causal proof for all observed differences. This review does not recompute raw integrity/counters/capacity, which are the primary review's scope.

The parent's extra pointwise loss check finding for r20p1-latency (138forward drops) is outside the formal8before/after-series loss family. This reviewer did not recompute that interval and does not classify it as a formal loss-family failure. Processsuspect in the formal6series family alone already blocks dependent analysis. No thresholds, bootstrap blocks, exclusions, optional stopping or corrected RTT were introduced; stage4 is unfinished and the cause of sustained RTT transitions remains unknown.
