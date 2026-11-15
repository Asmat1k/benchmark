# Внутренний review контрольной серии

aa: 14/24 sealed raw; 7/12 process/order/seed pairs. technical-unknown-or-invariant-failed.

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

Отдельный учёт условий (каждое отдельно; ни один исход не исключён):

|Condition|Unit|n planned|n−i (includes unknown)|i violated|Known satisfied|Unknown|
|---|---|---|---|---|---|---|
|technical_completeness|run|24|14|10|14|0|
|cpu_recovery_observed|run|24|18|6|8|10|
|browser_20hz_lag_reference|run|24|10|14|0|10|
|useful_gain_completeness_reference|run|24|20|4|10|10|
|technical_completeness|pair|12|7|5|7|0|
|cpu_recovery_observed|pair|12|7|5|2|5|
|browser_20hz_lag_reference|pair|12|5|7|0|5|
|useful_gain_completeness_reference|pair|12|10|2|5|5|

20Hz p99 lag reference — diagnostic comparison, не новый gate AA; U/disconnect — useful-gain reference, не доказательство эквивалентности. CPU recovery false сохраняется как наблюдение.

All/body/tail описаны внутри каждого run по nearest-rank p99 RTT из run_metrics (body<=p99, tail>p99). Полные статистики, cutoff, ID хвоста и оба знаменателя находятся в unit-review.json. Missing RTT не относится ни к body, ни к tail.

Это source/process/order review внутренних исполнителей; научная эквивалентность при n1 не установлена. Все slots и технически неизвестные исходы сохранены, RTT не корректируется.
