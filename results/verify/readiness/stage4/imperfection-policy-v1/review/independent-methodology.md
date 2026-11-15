# Independent methodology review: transparent imperfection reporting

14 November 2026. Codex transition_review, within the same agent team. This is methodological advice, not an external approval. No network, data correction, bootstrap or executable-threshold changes. Existing raw, seals, reports and historical failures retain their original meaning.

The parent reports user authorization to tolerate justified imperfections and describe ordinary observations alongside outliers. That authorizes an additive descriptive view and development of a prospective policy. It does not itself select new numerical sender/process gates or turn failed historical admission checks into passed ones.

## Exact additive partition

For each collection separately, use the same valid completed/returned RTT population already defined by its primary metric. Keep every record, ID, timestamp, loss and error. Define n as its finite RTT count, k=ceil(.99*n), and threshold as the k-th order statistic with 1-based ranks. This is observed nearest-rank p99, not an estimate of a physical fault boundary.

Publish three descriptive rows:

1. All returned/completed RTTs.
2. RTT <= this collection's observed p99.
3. RTT > this collection's observed p99.

Every tie at the threshold belongs to row 2. Report threshold value, k, counts strictly below/equal/above, both subgroup sizes and the tie policy. Row 3 can contain fewer than 1% or zero observations; do not force exactly 1% by splitting equal RTTs or removing selected IDs. For n=10000 its maximum size is 100; for n=1 the tail is empty. With n=0 threshold and group statistics are null, not zero or infinity fabricated as an observed RTT.

All returned RTTs must belong to exactly one subgroup, without duplication. Invalid/nonfinite values or impossible IDs are data-validity problems requiring explicit handling under the existing integrity contract; they must not be silently discarded as an ordinary outlier step.

Report n, fraction of returned RTTs and fraction of all planned slots for both subgroups. Provide median, p95, p99, mean, min/max where defined, using explicitly named existing quantile conventions. Keep the all-sample primary median/p95, loss/fullness, primary confidence intervals and decisions unchanged. Group p95/p99 are conditional descriptive summaries, not replacements for the original tail quantiles. No subgroup confidence intervals are needed for this additive request; inference after selection would require separately defined treatment of the estimated threshold and dependence.

Use neutral terms such as 'at or below observed p99' and 'above observed p99'. Neither group is declared fault-free, normal in a statistical sense, erroneous, dispensable or independently sampled. A genuinely slow network response remains a real observation. The same absolute RTT can lie in different groups in different collections, so cross-collection subgroup differences are exploratory and conditioned on different thresholds.

## Missingness and denominator

Keep missing/uncompleted observations in a separate accounting row with the full planned denominator. Do not put missing values into either finite RTT subgroup, label them ordinary, assign their RTT the threshold, or treat absence as evidence of an outlier rate below 1%.

For UDP calibration, report planned/sent/returned and directional forward/reverse drops with their actual entering-ID denominators. For browser runs, preserve unsent scheduler misses, local API errors, disconnects, uncompleted and known post-horizon replies as already specified by the raw contract. Existing completed population is responses by the per-slot 5000 ms horizon; RTT is echo minus actual send. Existing S counts echoes by planned-slot+100 ms and divides by all planned slots; U uses all planned slots. Primary Q is nearest-rank p95 among completed echoes, with the existing separate penalized p95 accounting. Additive summaries do not change any of these estimands. Sources: docs/metrics.md, src/analysis/metrics.py.

A tail defined as at most 1% of returned RTTs is not a 1 percentage point bound on lost, late or affected planned messages. Expected bilateral network loss and the practical fullness tolerance are different quantities. Show both finite-RTT and planned denominators to prevent that confusion.

## Why this cannot cure current failures

The observed upper 1% is guaranteed small by construction; it does not demonstrate rarity of a mechanism, independence of interruptions or adequate sample size for future events. A single scheduling pause can affect multiple send slots, queued packets and already outstanding echoes. The tail partition does not identify its causal footprint.

A small sustained state change can affect most observations, yet few appear in the upper 1% of the combined distribution. Consequently, this view cannot excuse the formal process flag in calibration.ew2u0ceD or the max-lag failure in r20p1-before. Existing source-bound statuses remain failed/inconclusive as originally determined. The observed 69 ms event and approximately .13 ms remainder shift may illustrate reports, but must not determine new numerical limits after seeing them.

## Prospectively justify practical error budgets

The existing scientific targets are a 5 ms practical Q effect and 1 percentage point fullness tolerance (configs/thresholds.json; docs/readiness/sender-quality-v2.md). They motivate tolerating imperfections only when their impact on the actual estimands is controlled. They do not directly imply a permissible maximum sender pause or ACF coefficient.

For sender policy, distinguish timing error from estimand error. RTT starts at actual send, so send lag is not automatically an equal additive RTT error. Lag can change offered load, spacing, completion by the planned deadline and responses of outstanding messages. A prospective policy needs a defined bound on all affected planned slots, clustering/burst exposure, and demonstrated effect on Q and S/U. Preserve identity, actual-send timing and load-shape invariants even if a numerical timing budget later changes.

Under an explicitly justified contamination fraction epsilon among the same completed-RTT population, an arbitrary-change model gives a rank envelope around p95 of approximately p(95-100*epsilon) through p(95+100*epsilon). It bounds rank, not milliseconds. The existing epsilon=1% illustration p94–p96 is a sensitivity scenario, not proof that the sender's late-slot count equals that contamination fraction. Missingness or changing completion membership requires additional bounds. A small empirical p94–p96 width from this run cannot establish a universal future millisecond limit.

For fullness, an established bound of m affected planned slots can bound an absolute S/U difference by at most 100*m/N percentage points for that comparison. Establishing m requires the complete causal footprint, not just the number of late send calls or observed p99-tail records. Compare on the same planned-slot basis; do not spend the full tolerance twice across modes or treat relative percent as percentage points.

For process policy, do not replace an ACF rejection with a large enough ACF threshold to admit this run. Separate effect-size stability from validity of the interval construction: a tiny state shift can coexist with invalid stationary-bootstrap assumptions. Before adopting a more permissive rule, define what estimator/inference remains valid under the admitted regime, which independent units support it, and how baseline/condition pairing or nuisance bounds protect the 5 ms decision. If the scientific method changes, its uncertainty and coverage justification must change explicitly; numerical tolerance alone cannot repair dependence.

A prospective error budget should allocate uncertainty/bias across source effects and both compared modes, preserve a margin relative to the 5 ms practical effect, and handle the 1 percentage point fullness decision separately. Choose allocation and numerical limits from scientific relevance, model assumptions and predeclared validation evidence, then fix them before a new validation collection. This review intentionally supplies no new numbers, epsilon choice, ACF cutoff, block length or retrospective pass decision.

## Concrete allowed next implementation

Add a separate derived descriptor with method/version, per-collection observed p99, rank and tie counts, all/body/tail summaries, planned and returned denominators, missing/error accounting, ID references, source hashes and explicit exploratory status. Retain primary outputs unchanged and show both views together. Reconcile count identities and empty/tied groups with a few deterministic examples. Do not inject the derived report into acceptance booleans or assign reviewed=true because a flag was absent.

New numerical admission policy remains a separate undecided deliverable: rationale, predeclared targets/units, impact assumptions, validation plan and source-version applicability. Keep old gates and historical raw reports intact. No new calibration, main run, automatic threshold update or reinterpretation of old success/failure follows solely from this descriptive addition.
