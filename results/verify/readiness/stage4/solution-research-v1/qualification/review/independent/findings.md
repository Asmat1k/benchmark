# Independent review of current-source sender qualification

14 November2026. Codex subagent transition_review independently read sender-diagnostic.6uYg6iiy after the user-run collection completed. Source commitd66559066b704fde567b6c9f92f57e2dcde22698. No network, raw/seal modification, bootstrap, production changes or fabricated approval flags. This is a separate computation within the same Codex team, not an external reviewer approval.

## Execution

Working directory `/Users/dobrov/Desktop/Code/ITMO/benchmark`.

Exact command: `python3 -B results/verify/readiness/stage4/solution-research-v1/qualification/review/independent/review.py`

Execution2026-11-14T17:51:52.969675Z–17:51:53.319275Z;0.348239s;exit0;empty stderr;90s hard subprocess limit and Python alarm. Saved review.json,execution.json,stderr.log. Follow-up summary extraction exit0,0.010s.

## Results

Existing sender_quality.evaluate was called unchanged on each complete10000slot series, including ID/grid/finite/monotonic/early-send invariants and unchanged late/maxlag/burst limits. Recomputed objects exactly equal sealed sender-quality.json objects.

|Metric|baseline-q1|baseline-q2|baseline-q3|
|---|---:|---:|---:|
|Sender status|passed|passed|passed|
|Late slots|7/10000(.07%)|0/10000|4/10000(.04%)|
|Maximum lag ms|33.467835|9.163595|27.203662|
|p99lag ms|.007071|.006908|.013494|
|Peak packets/10ms|3|2|4|
|Returned echoes|10000|10000|10000|
|Median RTT ms|.6067085|.609208|.609000|
|Sender CPU,percent of onecore|96.103%|96.106%|96.055%|
|Server CPU,percent of onecore|.2626%|.2632%|.2635%|

All79sealed files match SHA256;13source snapshots are identical before/after and match copied source files. Probe source includes the committed echo-only affinity fix. No scheduler trace or explicit after-mask record is part of this qualification, so CPU placement throughout the run is not independently reconstructed here.

Each of six pcaps contains all10000uniqueIDs with expectedcollectiontag and298byte frame lengths. All replyIDs also complete and unique. Every capture log reports0kernel drops. For each subseries and direction, tc delta is10000packets/2980000bytes,0drops/0requeues/0overlimits; qdisc options unchanged and boundarybacklogs/qlens0. No discrepancy among sentIDs,forwardcapture,reversecapture,replies or counters.

Each browser/server sampler and router sampler contains105samples. Endpoint windows span104.130–104.204s; router104.280–104.340s. Endpoint sampletimestamps strictly increase; maximum gap1.011602s. EndpointUDPInDatagrams andOutDatagrams increment by exactly10000within each resourcewindow, and router first-to-last sampledqdisc packets increase10000in bothdirections, supporting fullcollectioncoverage without joining epoch andmonotonicclocks. UDPInErrors/RcvbufErrors/SndbufErrors/InCsumErrors/MemErrors remain0. EndpointOOM/OOMkill0at allsamples;nr_throttled/throttled_usec unchanged. Minimum sampledVM MemAvailable3098456KiB(~2.955GiB). The CPUpercent includes observer/drain/windowpadding, not exact active-gridCPU; samplers themselves addload. Resourcecoverage does not prove absence of host/vCPU interruption between snapshots.

## Interpretation and limits

The three required10000slot baseline sender checks pass the existing v2contract on this current-source qualification. CPUcost remains about one busyvCPU for poll0; no extra helperbusyspin was added. Some late groups remain, within unchanged allowed budgets; this does not guarantee allfuture packets or rareevents.

This review did not redo root's full ENV/TLS/releaseapplicability/hostresource audit or publish any gate. It supplies no full14+4calibration scientificresult, browserbandwidth/generatorresult,A/A,monitoring or stage4completionclaim. Baselinequalification cannot establish performance of every delayed/lossyprofile or absence of sustained networkRTT transitions. Historicalfailures remain preserved and source-bound.
