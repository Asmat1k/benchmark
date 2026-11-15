# Independent review of applied sender-affinity short validation

14 November2026. Codex subagent transition_review independently inspected raw affinity-validation.83SwishH. No network, bootstrap, raw/seal edits or production modifications. Source commitd66559066b704fde567b6c9f92f57e2dcde22698. Preserved interrupted/battery-invalid affinity-validation.C9bJRLo6(exit130); none of its samples are pooled, selected or used as scientific evidence. This is an independent computation within the same Codex team, not external approval.

## Execution and method

Working directory `/Users/dobrov/Desktop/Code/ITMO/benchmark`; exact command `python3 -B results/verify/readiness/stage4/solution-research-v1/production-validation/independent/review.py`. Saved execution.json:2026-11-14T13:35:08.529334Z–13:35:08.787893Z,0.258168s,exit0,empty stderr.90s subprocess hard deadline plus script alarm. Outputs review.json and stderr.log. Follow-up source comparison exit0 in0.015s.

Existing sender_quality.evaluate used unchanged. Process independently reproduces current stdlib-equivalent finite-survival/median-filled RTT ACF at500/1000/2000,20five-second medians and fitted drift; unchanged thresholds. Prior independent stdlib/primary NumPy cross-check agreed within4.24e-15 ACF error. No missing-RTT imputation used for primary medians or any bootstrap; no scientific intervals computed.

All50sealed files match SHA. Both copied production probe and live docker/calibration_probe.py match SHA25676e51cb92b0a62438f86c8a8cbed2f9884a58a3ea3e65c5e0cdce62886a724c8.134source hashes before/after identical. AllsentIDs/grid/finite/order/minlag checks and existing sender-v2 limits passed. Unique forward IDs all10000; reply⊆reverse⊆forward. Tags and298byte frames checked. Bothpcaps report0kernel drops. Directional pcaps/IDlosses match tc packets/bytes/drops; qdisc options unchanged, boundaryqueues empty.

## Both prespecified profiles pass these short checks

|Metric|r80p0-check|r80p1-check|
|---|---:|---:|
|Sender status|passed|passed|
|Late slots|15/10000(.15%)|2/10000(.02%)|
|Maximum lag ms|35.367858|12.990372|
|p99lag ms|.018912|.009788|
|Peak packets/10ms|4|3|
|Median RTT ms|80.511125|80.496167|
|Fitted drift ms|−.001232|.000228|
|RTTrho500|.001475|−.002056|
|RTTrho1000|−.002720|−.001869|
|RTTrho2000|−.002477|−.000264|
|Process suspect|false|false|
|Returned echoes|10000|9810|
|Forward loss|0/10000|75/10000(.75%)|
|Reverse loss|0/10000|115/9925(1.15869%)|
|Post-run sender allowed CPUs|[0]|[0]|
|SenderCPU,percent of onecore|97.598%|97.694%|
|Sender usage delta|99.901102s|99.980531s|
|Router usage delta|36.737ms|25.518ms|
|Sender/router throttling delta|0/0|0/0|

Both survival ACFs also clear. Exact20window medians and sender burst/late groups are in review.json. Five-second router-span medians40.251–40.260ms and40.249ms respectively; no prior sustained+1.84/+2.84ms state appears. CPUcost remains essentially one busyvCPU for the sender, not an extra busy thread. CPUpercent uses resource snapshots' uptime span~102s, so it includes drain/setup boundaries and is not exact active-grid utilization. The source pins before echo timeline, and the wrapper observes actual[0]after; no new scheduler trace was introduced to certify every intermediate scheduling event.

## Interpretation and limits

This is positive noninstrumented evidence for the applied minimal echo sender affinity change under two fixed10000sample profiles. Existing numeric policies were not relaxed. Previous full unpinned post-poll0 collection had formal3/6processsuspect and broad9/14flags; these two newly defined checks are not a replacement for that failed report or permission to relabel historical data. The intervening causal research and source change mean this is a new validation, not an unchanged failed experience repeated until passing.

This review reports directional losses/counter agreement, not new formal binomial-family or block-bootstrap approval. The parent primary reviewer checks the remaining ENV/TLS/release applicability and admission details. Absence of flags is not proof of stationarity, short memory or elimination of every rare pause. No fresh full14+4calibration, formal3xqualification, generator, A/A or monitoring gate is supplied by this short validation. Stage4 remains unfinished pending its current source-bound prerequisites and required later results.
