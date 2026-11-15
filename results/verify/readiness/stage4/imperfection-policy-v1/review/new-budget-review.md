# Independent review of design-based interruption sensitivity

14 November 2026. Codex transition_review. Read-only methodological review of the parent's proposed synthetic analysis of browser-bandwidth-v4.9r51339s. No measurements, raw changes, bootstrap, admission-code edits or approval flags. The three modes provide concrete baseline examples; the transformed records are synthetic assumptions, not replays of WS/WT-S/WT-D or newly valid raw runs.

## What the design can establish

Using the main design's 50 ms period, 100 ms planned-slot deadline and 5000 ms planned-slot horizon is appropriate. Durations 50/100/200/500 ms arise from 1/2/4/10 design periods rather than the latest observed UDP pause. Event counts 1/3/6 over the 60 s measurement interval are explicit scenario assumptions, not measured future event rates. Retain all 1200 planned slots and compute official Q/S/U from complete transformed copies, alongside the unchanged baseline.

Treat the mechanisms separately:

- Receive-service pause: an existing first echo in [T,T+d) is deferred to T+d; actual send remains unchanged. It approximates buffered callback/receive delivery, with no new loss, no backpressure propagation and ideal drain at the end. It is not a full guest/kernel or network outage model.
- Planned-slot miss: planned slots in [T,T+d) become unsent scheduler misses with no echo. It approximates complete missed invocations without later catch-up. It does not simulate transport disruption of already outstanding messages or actual browser resume logic in every phase.

Keeping the mechanisms separate avoids attributing a missed-send outcome to a receive-only stall. Neither is a universal upper envelope of a real interruption; simultaneous effects, disconnects, stream head-of-line blocking, socket overflow, delayed writes and dependent congestion are outside these assumptions.

## Define the event placement and boundaries precisely

For counts 3 and 6, state the exact event-placement rule: for example, equally spaced starts with a swept common phase. Sweeping 1200 common phases is not all possible configurations of three or six arbitrary interruptions. If the actual rule differs, document that rule and the resulting start times. Store both theoretical event count and actual within-window starts/affected IDs, including boundary cases.

The maximum is over this predetermined discrete family, not over all real-valued interruption start times, all operating states or all realizations. In particular, starting only at planned times has a consequential optimistic boundary: an exactly 100 ms receive pause starting at a slot's plan time may deliver that slot's echo exactly at its inclusive deadline and leave S unchanged; shifting the pause slightly later can make the same response late. Show this limitation explicitly. Conservative affected-slot bounds below remain relevant, or a separately stated prospective off-grid phase variant can be studied. Do not claim the grid sweep is a continuous-phase worst case.

Intervals are half open [T,T+d): an echo exactly at T is deferred, one at T+d is unchanged; a planned slot at T is missed, one at T+d is not. Deadlines and horizons remain inclusive. Pauses extending past the final planned slot must retain their full duration when delivering outstanding echoes; do not clip the end to 60 s. Do not circularly wrap late echoes into the beginning of this finite run. Starts before measurement/warmup and pauses beginning after the last planned slot while echoes are pending are outside the stated sweep, not proved harmless.

For receive events, determine all eligibility from a consistent causal timeline. If deferred delivery lands inside another pause, it must be deferred again. Merge overlapping/adjacent receive blackout intervals or perform chronological cascading; applying every interval independently to original echoes can produce an impossible delivery inside another blackout. Track affected IDs as a union so overlapping events do not multiply-count messages. The largest per-metric effect may occur at different phases/modes; do not present their separate maxima as one jointly realized event pattern.

## Correct metric accounting

For receive-only scenarios, retain t_send and all planned times. Reevaluate whether delayed first echoes are by the per-slot horizon, whether they are by the planned-slot deadline, and their actual-send RTT. A response beyond the horizon leaves primary Q's completed population and increases U; it is not retained as a finite completed RTT. Preserve separately known after-horizon delivery in descriptive accounting. Never silently place missing responses in a finite tail subgroup.

For missed-slot scenarios, set send/echo fields consistently in the derived copy and preserve every planned slot in S/U denominators. Treat original unsent/errors as their existing outcomes; do not create a second loss by missing a slot already uncompleted. If reporting broader synthetic counters, update them consistently or explicitly restrict output to recomputed Q/S/U rather than producing contradictory synthetic event/server counters.

Use the exact official nearest-rank Q and the original completed-by-horizon definition, not an interpolated p95. Keep infinity/null for undefined or penalized metrics as the existing metric contract specifies. For a null Q, report undefined and the reason; an absolute difference is not a finite zero. Publish baseline value, transformed value, signed difference, absolute difference and witness event positions/IDs. Do not infer empirical confidence intervals or changed gate statuses from a deterministic sensitivity grid.

The authoritative implementation is src/analysis/metrics.py; the metric contract is docs/metrics.md. These transformed copies must remain clearly labeled derived synthetic scenarios, with parent raw hashes, stress specification and analysis source/version. They cannot acquire fabricated protocol counters, raw seals or source-bound admission reports.

## Deterministic bounds and the practical targets

Let N=1200, P=50 ms, and let m be the number of distinct planned outcomes that can change under the specific model. For planned-slot misses, an interval of duration d contains at most ceil(d/P) grid points, so m <= sum ceil(d_j/P), capped at N; overlap and end-of-run clipping can reduce it. With the proposed integer-period durations and c events, m <= c*d/P. For receive pauses, m must be counted from affected delivered echoes: pre-pause outstanding replies and baseline arrival clustering mean the same planned-slot duration formula does not generally bound it. Compute actual affected-ID unions in each scenario.

For a baseline-to-transformed comparison with changes restricted to these m outcomes, |delta S| and |delta U| are each bounded by 100*m/N percentage points. This is a within-run bound, not a statement that both metrics necessarily attain it or that a comparison of two separately perturbed modes is bounded by the same one-sided number. With unrelated affected sets on both modes, compare or sum the appropriate bounds; do not assume identical exposure, timing or cancellation.

The 1 percentage point practical fullness tolerance corresponds arithmetically to 12 of 1200 planned outcomes. That motivates reporting the modeled affected counts and which scenarios can exceed that scale. It does not justify adopting 12 as an operational sender budget, a rate guarantee, or an estimate of the footprint of a UDP pause. In the largest miss scenario the simple bound allows 60 affected slots, or 5 percentage points; exact synthetic results may be smaller.

For Q, counts alone give rank bounds rather than a millisecond bound. Let X_(i) be the original ordered finite completed RTTs, n their number, and k=ceil(.95*n).

- If m completed values only increase and completion membership remains fixed, Q_new >= X_(k) and Q_new <= X_(k+m) when k+m<=n; beyond that there is no finite bound from original order statistics alone.
- If exactly a completed values are removed with no replacements, put k'=ceil(.95*(n-a)). The new conditional Q lies between original X_(k') and X_(k'+a), provided n-a>0.
- If a horizon crossing changes membership while other RTTs also change, combine the membership and value-change reasoning or compute exact official metrics on the transformed full slot list. Do not apply the fixed-n contamination envelope as if completion membership were unchanged.

For n=1200 and deletion of 60 completed values, k'=1083 and the upper original rank is 1143; the original Q rank was 1140. Conditional Q can improve when slow messages disappear even while U worsens. For the existing penalized p95, exactly 1140 finite completions still gives a finite highest-ranked observation; 1139 gives infinity. These boundary facts require explicit presentation, not a favorable missingness treatment.

The existing 5 ms practical Q effect motivates checking actual Q displacement and rank-envelope widths against a scientific decision scale. A baseline with tightly clustered RTTs can show little Q movement despite substantial modeled failures; that demonstrates limited sensitivity of conditional p95 in this baseline, not negligible harm to all workloads or tail behavior. Conversely, an extreme shifted p95 in a deliberately strong scenario is a sensitivity result, not a failure of the original validated baseline.

## Can UDP evidence alone justify a new policy budget?

No. UDP establishes useful timing, route and service facts, but does not establish the browser generator's deadline/miss semantics, WS/WT transport queues, application event-loop behavior, conditional completion membership or comparative-mode exposure. In particular, late sender calls are not an identified bound on all affected browser planned slots or on Q/S/U displacement.

This synthetic analysis is a useful intermediate step: it makes the current estimands' sensitivities and blind spots concrete without another measurement. It cannot by itself certify how a physical 50/100/200/500 ms interruption changes real browser runs. A prospective numerical admission policy needs a defensible mapping from observed infrastructure defects to affected outcomes, an inference method valid under the admitted process variation, and evidence applicable to the intended profiles/modes. The existing baseline source/version and its limited scenarios must be disclosed; current-source full scientific acceptance does not follow from historical browser baseline sensitivity alone.

Use the results to choose what scientific risks to control and which targeted validation would distinguish them, then fix any new numerical policy before collecting its validation evidence. Do not select a maximum duration, ACF budget or allowed incident count because it happens to accept the latest 69 ms sender event or .13 ms process shift. User authorization of justified imperfections supports this analysis; concrete replacement numerical gates remain undecided. Historical failures and all full-sample primary estimates stay intact.
