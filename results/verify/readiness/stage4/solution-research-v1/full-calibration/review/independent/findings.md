# Independent review of full fixed calibration after affinity fix

14 November2026. Codex subagent transition_review independently computed all14echo sender/process summaries from calibration.ew2u0ceD. Source commitd66559066b704fde567b6c9f92f57e2dcde22698. No network, bootstrap, production changes, raw/seal edits or automatic approval flags. Separate computation within the same Codex team, not an external reviewer approval.

## Execution and method

Working directory `/Users/dobrov/Desktop/Code/ITMO/benchmark`.

Exact command: `python3 -B results/verify/readiness/stage4/solution-research-v1/full-calibration/review/independent/review.py`

Execution2026-11-14T18:34:27.670901Z–18:34:28.934695Z;1.263377s;exit0;empty stderr.90s subprocess deadline and script alarm. Saved review.json,execution.json,stderr.log. Follow-up selectedpacket/windows extraction0.037s/exit0.

Existing sender_quality.evaluate unchanged; process diagnostics independently use the established equivalent stdlib finite-survival and median-filledRTT centeredACF500/1000/2000,20consecutive500slot medians andOLSdrift. New descriptive ACF1/10/50/100/200 and quantile/median-neighborhood summaries do not introduce new acceptance thresholds. All146sealed file hashes match. All14pcap ID/tag/frame checks and directionalID/tc packet/byte/drop agreement pass. Full ENV/TLS,capacity andformalbinomial review remain the parent's scope.

## Mandatory failures remain

Sender **13/14passed**, with **r20p1-before failed**:maximumlag69.794312ms>50ms. ID4525 planned45250ms,sent45319.794312ms;precedingID4524sent45240.000937ms,gap79.793375ms. LateIDs4525–4534 form one catch-upgroup with2.5msminimalspacing preserved. Thisseries late17/10000(.17%),burst4;itsotherlateclustersIDs145–149and2958–2959. The numericalmaxlagfailure cannot be ignored because average/p99timingisgood.

Formalprocess family contains six:baseline-before,four*-latency,baseline-after. **1/6suspect=r80p1-latency**, also the soleflag in broad14diagnosticview. RTTrho500=.056683686andrho1000=.037997508exceedunchanged~.03591/.03689bounds;rho2000=.028235385clear. SurvivalACFall14clear. Fitteddrift−.180586msalonewouldnotfailthe2msrule,butACFalreadydoes.

The formal directional-lossseries family is the eight fourprofile×before/after collections;review.json explicitly marks them. *-latencylosses are descriptive extra checks, not additionalmembers of thatfamily. Inparticular r20p1-latencyforward138/10000mustnotbeintroducedasaformal8serieslossfailure. Thisreviewprovidescounts/agreement,notCPintervalapproval.

|Subseries|maxlag ms|late %|burst|RTTmedian ms|process|
|---|---:|---:|---:|---:|---|
|baseline-before|44.312674|.08|4|.606750|clear|
|r20p0-before|25.450417|.03|3|20.606792|clear|
|r20p1-before|69.794312|.17|4|20.607042|clear|
|r80p0-before|32.265626|.05|4|80.607250|clear|
|r80p1-before|33.148501|.06|4|80.607292|clear|
|r20p0-latency|10.299792|.01|2|20.609542|clear|
|r20p1-latency|19.157459|.03|3|20.675333|clear|
|r80p0-latency|2.827482|0|2|80.686459|clear|
|r80p1-latency|2.810455|0|2|80.571459|suspect|
|r20p0-after|.860955|0|2|20.687209|clear|
|r20p1-after|4.996595|0|2|20.687500|clear|
|r80p0-after|5.413417|0|2|80.685459|clear|
|r80p1-after|.731437|0|2|80.686625|clear|
|baseline-after|24.054725|.07|4|.612917|clear|

## Remaining state differs from previous multi-millisecond forward regimes

Prior unpinned fullpoll0 collection gIdWLx7o had3/6formal and9/14broadflags withmultiple sustained+~1.84/+~2.84msforwardspan states. Thosemultimsstates are absent in the current20window summaries:delayedprofile forwardspanmedian10.293–10.309msor40.293–40.306msacrossall14,withbaseline.291–.323ms. Positiveevidencefortheaffinityfixdoesnotconvertremainingmandatoryfailurestopassed.

Currentr80p1-latency0–35sRTTmedians~80.685–80.700ms,40–100s~80.552–80.559ms. Forwardspanremains40.295–40.304ms;remainingRTTmedianfalls~40.388→40.255msnear35–40s. Thuscurrentformalprocessflagisasmaller~.133msreverse/receive-remainderstatechange,notareappearanceoftheold~3msforwardstate. Componentboundariesremainrouteringress-onlyandcaptureepochversusmonotoniclimitsapply;noexactserver/kernelassignmentisjustified.

## Distribution/quantile evidence without assumption approval

All20windows per14series containreturnedRTTs;fullwindowp5/p25/p49/p50/p51/p75/p95andcomponentmedianssaved. Allserieshavefinite,populatedmedian neighborhoods. Observedexactmedianmassranges~.0102%to.60%,notahugepointmass;1nsneighborhoodfractionranges~.0102%to.76%. Examplesp49/p51:r20p0-latency20.609458/20.609625ms;r80p0-latency80.685833/80.687291ms;r80p1-latency80.570541/80.572583ms. Thisdocumentsmeasurementresolutionandlocalempiricaldensity,butdoesnotproveastablepositivedensityorregularquantileasymptoticsacrosstime.

ShortrangeRTTACFcanbelarge(e.g.baseline-beforelag1=.7515,r20p0-latencylag1=.6706),whilemostseries'lag50–200valuesareclose0. r80p1-latencyremainspersistentlypositiveatlag10/50/100/200=.0693/.0574/.0583/.0564and500=.0567,consistentwithitsobservabletwolevelstate. TheseadditionalACFvaluesareexploratory;theyarenotnewgatesandcannotwaiveexistingflags. Median-tiefractionsorapparentlynarrowwindowscannotestablishstationarity/shortmemory/Bernoullilossorjustifyautotrueflags.

## Conclusion

Theprimaryprerequisitesstillfailfromonesendermaxlagandoneformalprocessseries. Stopdependentbootstrap/successpublication;preserveall146rawsealsandfailedresult. Noadditionaldata,retry,tailremoval,thresholdchangesorhistoricalreportrebindingwasperformed. Stage4remainsunfinished;thecurrentcollectiondoesnotestablishreliabilityagainstrare~70mssenderpausesorstationarityofallformalprocessseries.
