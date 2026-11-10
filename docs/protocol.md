# Протокол версии 1

Единица эксперимента — один свежий браузер, один сервер, одно соединение и один режим. Make запускает локальный Compose. Страница измеряет время, TypeScript runner управляет ею через Playwright pipe. Python готовит расписание заранее и обрабатывает raw после опыта. Сервисы используют только две внутренние IPv4 сети с явными прямым и обратным маршрутами через router. IP и поток данных указаны на [диаграмме](architecture.mmd). NAT, опубликованные порты и обходной management path исключены. NET_ADMIN получают router и кратковременный route-init.

По адресу https://bench.test:8443 один Go binary обслуживает HTTPS и /ws по TCP HTTP/1.1 (Upgrade 101), /wt по UDP HTTP/3 CONNECT поверх QUIC v1. Origin проверяется точно. WS использует TCP_NODELAY без compression. HTTP/2, Alt-Svc, fallback, 0-RTT и возобновление сессий отключены. WT-S открывает один прикладной bidi stream, отдельно от служебных H3 streams. CC, buffers, negotiated options и размер пакета записывают по факту.

Для TCP и QUIC используется один leaf ECDSA P-256 с SAN bench.test на 13 суток. TLS 1.3. CA доверена в system/NSS. WT получает ровно 32 двоичных байта SHA256 полного DER leaf. Ключ CA вне сервисов, ключ leaf доступен только серверу. Проверки wrong SAN, unknown CA и expired обязательны для HTTPS/WSS, wrong pin и expired для pinned WT. Endpoint-пробы выполняют с уже загруженной доверенной страницы отдельного разрешённого origin только внутри изолированного negative-профиля. Положительный pin удостоверяет leaf независимо от CA и SAN. Смена сертификата требует новой серии.

## Состояния

1. Fresh server/Chromium/qdisc → новое соединение → клиент передаёт ASCII READY, сервер возвращает ASCII ACK по выбранному каналу (WS binary message, WT-S точное чтение 5/3 байт на том же stream, WT-D одна datagram). Служебный обмен завершается до измерений. Ошибка подготовки прерывает прогон.
2. Прогрев 200 слотов за 10 с, measurement 1200 за 60 с, затем drain до последнего t_plan + 5000 мс. Разрыв в ходе фаз фиксируется, оставшиеся слоты учитываются, переподключения нет.
3. Пауза ≥5 с, нулевые очереди обоих egress непрерывно 1 с, server idle и CPU baseline. Предельное ожидание стабилизации 30 с, затем stop. Следующий run получает новые процессы, соединение и qdisc.

## Бинарная рамка

Все многобайтовые поля big-endian. Рамка всегда содержит 256 байт.

| Смещения включительно | Значение |
|---|---|
| 0–3 | magic 0x42575431 |
| 4 | version 1 |
| 5 | phase 0 warmup или 1 measurement |
| 6–7 | reserved 0 |
| 8–15 | runNonce uint64 |
| 16–23 | sequence uint64 |
| 24–255 | для абсолютного смещения i байт равен (sequence + i) mod 256 |

ID образуют nonce, phase и seq, sequence начинается с 0 в каждой фазе. В JS используется BigInt, в JSON nonce и seq — канонические десятичные строки в пределах uint64. Время хранится только в журнале. WS переносит один binary message на рамку. WT-S выделяет рамки из любых chunks, сохраняет хвост длиной 0–255, EOF с хвостом даёт framing_error. На сервере полное чтение и запись, эхо побайтно тождественно запросу. WT-D переносит одну рамку на datagram без прикладной фрагментации, повтора и сортировки. Поддержку проверяют по maxDatagramSize ≥256 и точному echo. Статус unsupported фиксируют до freeze.

## Профили и среда

Четыре профиля в configs/profiles.json задают для каждого egress delay 10/40 мс, loss 0/1%, rate 10 Мбит/с, limit 1000 пакетов. RTT содержит baseline и суммарную добавку двух egress. MTU 1500, jitter и correlation 0. Направления имеют разные seeds. Сверяют readback qdisc, routes, MTU и выключенных GRO/GSO/TSO/LRO, forwarding-off обязан нарушать оба пути. При отсутствии kernel seed run останавливается.

Целевой бюджет VM 8 vCPU, 12 GiB RAM, 30 GiB свободного диска. Browser 2 CPU/3 GiB/shm 1 GiB/init, server 2 CPU/1 GiB, router 1 CPU/512 MiB, analyzer отдельно 2 CPU/2 GiB. Используется одна native linux/amd64 или arm64. Фактическое железо, питание, состояние фона, OS/VMM/kernel, cgroups и диск заносят при обследовании. Базовые версии и условия их замены заданы в §2.1 утверждённого плана.
