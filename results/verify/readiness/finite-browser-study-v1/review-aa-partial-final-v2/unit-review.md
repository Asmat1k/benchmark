# Внутренний review контрольной серии

aa: 14/24 published sealed raw; 7/12 process/order/seed pairs. failed-incomplete; empirical equivalence not established.
Run status counts: {'sealed-validated': 14, 'quarantined-invariant-failed': 1, 'not-run': 9}. Quarantined RTT summaries remain descriptive and do not change admission status.
Officially valid sample totals: {'planned_all_runs': 28800, 'known_published_planned': 16800, 'known_published_returned': 16697, 'known_published_missing': 103, 'technical_unknown_planned': 12000}. Quarantine is additional description, never a valid-run substitution.

|Mode|Profile|Status|Q shift ms (side2−side1)|S shift pp|
|---|---|---|---|---|
|WS|r80p0|reviewed|-1.7999999821186066|0.5833333333333286|
|WS|r20p1|reviewed|-9.699999988079071|0.5|
|WT-D|r20p0|reviewed|-0.10000002384185791|0.0833333333333286|
|WT-D|r80p1|reviewed|1.0|0.0|
|WS|r80p1|reviewed|-5.699999958276749|0.6666666666666714|
|WT-D|r20p1|reviewed|-0.4000000059604645|0.5833333333333286|
|WT-S|r20p0|reviewed|-0.5|0.5|
|WT-S|r20p1|unknown|None|None|
|WS|r20p0|unknown|None|None|
|WT-S|r80p0|unknown|None|None|
|WT-D|r80p0|unknown|None|None|
|WT-S|r80p1|unknown|None|None|

Все 24 назначенных исхода:

|Run|Mode|Profile|Status|Slots|Completed|Missing|Error|
|---|---|---|---|---|---|---|---|
|b9-a0-m0|WS|r80p0|sealed-validated|1200|1200|0|None|
|b9-a0-m1|WS|r80p0|sealed-validated|1200|1200|0|None|
|b6-a0-m0|WS|r20p1|sealed-validated|1200|1200|0|None|
|b6-a0-m1|WS|r20p1|sealed-validated|1200|1200|0|None|
|b2-a0-m0|WT-D|r20p0|sealed-validated|1200|1199|1|None|
|b2-a0-m1|WT-D|r20p0|sealed-validated|1200|1200|0|None|
|b5-a0-m0|WT-D|r80p1|sealed-validated|1200|1175|25|None|
|b5-a0-m1|WT-D|r80p1|sealed-validated|1200|1174|26|None|
|b3-a0-m0|WS|r80p1|sealed-validated|1200|1200|0|None|
|b3-a0-m1|WS|r80p1|sealed-validated|1200|1195|5|None|
|b8-a0-m0|WT-D|r20p1|sealed-validated|1200|1175|25|None|
|b8-a0-m1|WT-D|r20p1|sealed-validated|1200|1182|18|None|
|b1-a0-m0|WT-S|r20p0|sealed-validated|1200|1197|3|None|
|b1-a0-m1|WT-S|r20p0|sealed-validated|1200|1200|0|None|
|b7-a0-m0|WT-S|r20p1|quarantined-invariant-failed|1200|1199|1|queues not empty|
|b7-a0-m1|WT-S|r20p1|not-run|None|None|None|None|
|b0-a0-m0|WS|r20p0|not-run|None|None|None|None|
|b0-a0-m1|WS|r20p0|not-run|None|None|None|None|
|b10-a0-m0|WT-S|r80p0|not-run|None|None|None|None|
|b10-a0-m1|WT-S|r80p0|not-run|None|None|None|None|
|b11-a0-m0|WT-D|r80p0|not-run|None|None|None|None|
|b11-a0-m1|WT-D|r80p0|not-run|None|None|None|None|
|b4-a0-m0|WT-S|r80p1|not-run|None|None|None|None|
|b4-a0-m1|WT-S|r80p1|not-run|None|None|None|None|

Отдельный учёт условий (каждое отдельно; ни один исход не исключён):

|Condition|Unit|n planned|n−i (includes unknown)|i violated|Known satisfied|Unknown|
|---|---|---|---|---|---|---|
|technical_completeness|run|24|23|1|14|9|
|cpu_recovery_observed|run|24|18|6|9|9|
|browser_20hz_lag_reference|run|24|9|15|0|9|
|useful_gain_completeness_reference|run|24|20|4|11|9|
|technical_completeness|pair|12|11|1|7|4|
|cpu_recovery_observed|pair|12|7|5|2|5|
|browser_20hz_lag_reference|pair|12|4|8|0|4|
|useful_gain_completeness_reference|pair|12|10|2|5|5|

RTT all/body/tail (дополнительное описание; quarantine не становится официальным raw):

|Run|Published?|Returned / planned|Cutoff p99 ms|Body n|Tail n|Missing|Body median ms|Tail max ms|
|---|---|---|---|---|---|---|---|---|
|b9-a0-m0|True|1200/1200|99.0|1188|12|0|85.69999998807907|136.40000000596046|
|b9-a0-m1|True|1200/1200|94.30000001192093|1188|12|0|84.90000000596046|147.0|
|b6-a0-m0|True|1200/1200|102.0|1189|11|0|25.80000001192093|375.69999998807907|
|b6-a0-m1|True|1200/1200|105.69999998807907|1188|12|0|25.69999998807907|351.0|
|b2-a0-m0|True|1199/1200|39.0|1188|11|1|25.0|71.69999998807907|
|b2-a0-m1|True|1200/1200|35.599999994039536|1188|12|0|25.599999994039536|54.19999998807907|
|b5-a0-m0|True|1175/1200|97.5|1164|11|25|85.5|188.09999999403954|
|b5-a0-m1|True|1174/1200|100.7000000178814|1163|11|26|85.69999998807907|118.69999998807907|
|b3-a0-m0|True|1200/1200|227.2999999821186|1189|11|0|85.80000001192093|310.5|
|b3-a0-m1|True|1195/1200|235.19999998807907|1184|11|5|86.5|420.80000001192093|
|b8-a0-m0|True|1175/1200|30.599999994039536|1165|10|25|24.400000005960464|34.599999994039536|
|b8-a0-m1|True|1182/1200|30.900000005960464|1172|10|18|24.30000001192093|69.89999997615814|
|b1-a0-m0|True|1197/1200|41.0|1186|11|3|25.5|172.7000000178814|
|b1-a0-m1|True|1200/1200|37.900000005960464|1188|12|0|26.299999982118607|80.7000000178814|
|b7-a0-m0|False|1199/1200|101.39999997615814|1188|11|1|25.650000005960464|163.90000000596046|

20Hz p99 lag reference — diagnostic comparison, не новый gate AA; U/disconnect — useful-gain reference, не доказательство эквивалентности. CPU recovery false сохраняется как наблюдение.

All/body/tail описаны внутри каждого run по nearest-rank p99 RTT из run_metrics (body<=p99, tail>p99). Полные статистики, cutoff, ID хвоста и оба знаменателя находятся в unit-review.json. Missing RTT не относится ни к body, ни к tail.

Это source/process/order review внутренних исполнителей; научная эквивалентность при n1 не установлена. Все slots и технически неизвестные исходы сохранены, RTT не корректируется.
