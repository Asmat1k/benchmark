# Причина частичного завершения A/A

24 назначенных исхода:14 опубликованы и проверены;1 WT-S/r20p1 b7-a0-m0 сохранён в quarantine;9 не запускались. Научная эквивалентность не установлена; серия failed/incomplete.

Одиннадцать последовательных snapshots показали нулевые backlog/qlen обеих netem очередей. После них исходный код делает quiet CPU observation (маркер159905970000us,ожидание6s,comparisonpassed), затем отдельный qdisc-stable snapshot. В последнем to_server содержит182bytes/2packets; to_browser пуст. raw validator отклонил publication именно с queues not empty. Это два разных момента наблюдения, а не противоречие одновременных измерений. Тип пакетов и транспортная причина по этим журналам не установлены.

В quarantine сохранены SHA256SUMS,manifest/completion,1200slots,server counters,resource-window и sampler records. Их хэши, ресурсное покрытие и quiet CPU primary correspondence проверены отдельно.1199 returned/1200planned,missing1 — только дополнительное описание quarantine; оно не дополняет официальную выборку.

Официально достоверная опубликованная часть:16800planned,16697returned,103missing;12000плановыхслотов относятся к10техническинеполным/невыполненнымисходам. RTTbody16540/tail157поrun-specificnearest-rankp99неисключаютсяизанализа. Остальныеquarantine1199returned(body1188/tail11)показаныотдельно. Никаких новых сборов,исправленийисточников,перезаписиfailedилиrestamprawнепроизводилось.
