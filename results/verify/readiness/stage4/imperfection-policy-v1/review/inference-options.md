# Inference options when imperfections are retained

14November2026. Independent Codex trace_review research. No measurement, bootstrap, code/gate change, method adoption, data removal or retrospective pass decision. Reviewed calibration_blocks.py, inference.py, schedule.py, analyze.py, configs/plan.json, configs/thresholds.json and the existing imperfection-policy methodology review.

## Recommendation and scope

The lowest-cost honest next deliverable is a **versioned finite-observation calibration report**, using the complete existing collection, plus a separately labelled sensitivity analysis. Its claim is what this fixed acquisition observed, including rare pauses and the residual step. It does not assert a confidence interval for future VM states or silently pass the old stationary-bootstrap gate. A short protocol amendment should settle whether this narrower calibration claim is sufficient for the intended experiment before commissioning another network run.

If a repeatable population calibration claim is essential, choose a justified nuisance model or a prospective run-level design first. Merely increasing the permissible ACF, classifying a small step as harmless, or expanding the existing bootstrap interval by the observed .134ms does not establish valid coverage. Main practical Q=5ms and S=1percentage-point scales remain unchanged; these are scientific relevance scales, not already allocated nuisance budgets. Calibration itself still has its separate existing ±2ms target.

## Why small nonstationarity still matters to inference

The current circular-block-medians-v1 explicitly assumes a stationary short-memory joint RTT/survival process and provides approximate percentile intervals, not finite-sample coverage. Its100/200/500-slot envelope explores three specified resampling scales; taking their envelope is not a theorem covering arbitrary drift, jumps or shared pauses. The method globally resamples blocks, including wraparound from collection end to beginning, and therefore changes the relative placement of a regime step.

Small amplitude can imply small practical distortion **under an appropriate model**, but it does not make the sampling assumptions true. Conversely, rejecting exact stationarity need not imply the experiment is unusable: it means the estimand and uncertainty procedure need an explicit alternative. Paparoditis and Politis propose local resampling for slowly changing stochastic structure; their result is not a general license to replace the method for arbitrary jumps, medians with loss-dependent missingness, or this particular fixed collection. [Local block bootstrap, primary paper abstract](https://www.numdam.org/articles/10.1016/S1631-073X(02)02578-5/).

## Option1: exact description of the acquired time window

Define the target as the empirical distribution of all planned slots in the identified collection, with the original actual-send RTT definition, completed/returned population, loss accounting, IDs and denominators. Report full-sample median/p95, all specified time windows, directional loss, pauses and diagnostics. A p99 body/tail partition may supplement those outputs but never replaces the full sample. Finite empirical summaries have no sampling uncertainty about those already observed records; clock/instrument accuracy and missing-outcome interpretation remain separate uncertainties.

For calibration, report full-window profile-minus-before and profile-minus-after empirical contrasts and whether each lies within the **unchanged** target±2ms. Label these as observed engineering checks, not a simultaneous confidence statement about future acquisitions. An envelope of observed window contrasts is an observed range; it is not a confidence interval or guaranteed drift bound. Do not call20consecutive chunks20independent replications.

This option needs no additional network experiment and does not require solving the cause of every permissible pause. Its cost is a narrower claim. It cannot, without an explicit revised methodology and applicable source-bound gates, unlock the existing calibration→generator→main workflow. Historical failed/inconclusive statuses remain historical facts.

## Option2: bounded nuisance with an uncertainty budget

First decide what is nuisance and what belongs to the measured system. Real scheduler/VM delays are part of observed end-to-end performance unless the scientific target explicitly defines a different reference system. A UDP helper result does not automatically bound distortion of browser p95 or deadline success.

A useful conditional model is Y_i=X_i+b_i with a justified uniform bound |b_i|≤B, the same observation identities and completion membership, and valid reference inference for X. For any empirical quantile, including median and p95, the pointwise coupling implies |q_p(Y)−q_p(X)|≤B, regardless of serial dependence. A two-mode contrast can require B_A+B_B; a shared error cancels only if the coupling really is shared. This is a deterministic sensitivity argument, not a claim that B has been established here.

If a valid reference interval is [L,U] and the relevant parameter distortion is bounded byD, [L−D,U+D] protects against that distortion. With a reference error probability α and a bound failure probability β, a union-bound guarantee is at best1−α−β, with approximation error from the reference procedure still disclosed. One must specify why that reference interval is valid and how the nuisance bound is obtained. Expanding an otherwise unjustified stationary-bootstrap interval does not solve either requirement.

There is a potentially economical proof route when the reference series differs pointwise by at mostB and the finite/missing mask is identical: each block-resampled median, and hence each empirical percentile endpoint using the same resampling indices, differs by at mostB. Thus expanding the observed bootstrap interval byB contains the corresponding reference bootstrap interval pathwise. Coverage still inherits the reference stationary/joint-survival assumptions, its approximation error, and the independently justified bound. It cannot cover arbitrary changes of which packets return or arbitrary contamination of many queued neighbors.

If at mostm same-population observations may change arbitrarily, an order-statistic/rank envelope is possible instead of a millisecond bound. At p95 this concerns ranks near.95±m/n, with endpoint clipping and the actual quantile convention specified. It is not proof of a5ms bound. The sender's late-call fraction, upper-p99 fraction and number of causally affected messages are different quantities. Changing completion membership needs additional bounds.

For S, a proved limit ofm affected planned-slot indicators bounds an absolute single-mode S change by100m/N percentage points. Under a different, explicit uniform deadline-offset boundB, counts at deadline−B and deadline+B bound the true timely count, provided outcomes/identities are coupled. These are conditional scenarios; neither bound has been established by the present sender statistics. Account for both modes and all allocated error sources rather than spending1pp twice.

A TypeB uncertainty component may use prior data, external specifications or scientific judgment, but its distribution and limits must be justified; NIST does not turn an observed range into a universal bound. [NIST TypeB evaluation](https://physics.nist.gov/cuu/Uncertainty/typeb.html). Here the .134ms observed step cannot be promoted to a maximum possible nuisance, and a submillisecondB cannot also explain away the retained~70ms pause.

## Option3: run-level or randomized temporal design

If future-window inference is required and no defensible nuisance envelope exists, the unit of replication must match the claim: separately randomized run blocks or genuinely independent acquisition sessions, rather than the10000packets within one time-dependent series. Separate sessions are not automatically independent if the same host state persists; state the sampling frame and assumptions. A fixed-order A/B pair is not randomized merely because it has two runs. Historical collections with different sender/source states are not interchangeable replications.

Prospective temporal randomization can support inference over the actual scheduled period even when baseline outcomes vary with calendar time, under explicit assignment, nonanticipation and carryover assumptions. Switchback theory supplies exact sharp-null randomization tests and, under further conditions, conservative intervals for its specified treatment-effect estimand. It does **not** give a universal CI for any nonlinear median/p95 contrast. An exact no-effect test alone does not establish equivalence within5ms or1pp. [Bojinov, Simchi-Levi and Zhao, primary paper](https://arxiv.org/abs/2009.00148).

The repository already randomizes profile/mode order and uses paired block outcomes. Audit whether those existing units, reset/queue-empty rules and inference support the desired finite-period Q/S claims before proposing more acquisition. Main bootstrap resamples complete block contrasts; its dependence/exchangeability assumptions differ from packet-level calibration and cannot be dismissed solely because calibration has a small step. A redesign must preserve the stated Q/S estimands or explicitly disclose any change; mean treatment-effect theory is not automatically a proof for median paired p95 differences.

This route may need new data, but neither a fixed large experiment nor a blanket repeat of full calibration is justified before resolving the design question. Repetition count follows precision/coverage needs under the selected design, not an attempt to observe a clean run.

## Prospective validation before adoption

1. Write the claim: this acquired period, a specified future acquisition distribution, or a reference system under a bounded distortion. State the Q/S populations, missingness and carryover treatment. Preserve all original records and full-sample primary outputs.
2. Fix the alternative method, assumptions, numerical uncertainty allocation, multiplicity and unchanged scientific thresholds before evaluating a new validation dataset. Existing failures are development evidence, not an untouched validation set. No retrospective green gate is implied.
3. Begin with bounded offline verification, not another network campaign: deterministic quantile/rank/denominator examples; mathematical bound checks; and a prespecified small simulation matrix containing stationary dependence, small steps at several times, slow drift, clustered pauses and loss-dependent missingness. Validate the **chosen** estimator/coverage claim, not only median bias. Any larger simulation or collection exceeding5minutes remains user-run under the standing rule.
4. If Option1 suffices, publish its limitation and revise the contract explicitly; no predictive CI needs to be fabricated. If Option2 is chosen, obtain or justify the bound and reference assumptions first. If those cannot be supported and a predictive claim is required, specify one prospective run/block validation design and its finite budget; do not keep repeating the present protocol.

No option is automatically adopted in this review. The present task supports preparing the methodological choice and its reviewable consequences, while retaining the existing thresholds, historical raw and all reported imperfections.
