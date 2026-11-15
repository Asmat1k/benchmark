# Подготовка диагностики паузы UDP sender

Изучены sender-diagnostic, sender-control-yB7Jzpyh, sender-idle-T6NngDpB и последний raw. Причина 40.942417-мс опоздания остаётся неустановленной: четыре поздних слота соответствуют одной паузе с догоняющими отправками. Полные ответы, отсутствие ARP/потерь/throttling исключают эти наблюдаемые сбои в данной пробе, но не задержку пробуждения или краткую остановку исполнения VM. Прежние select wall/CPU/schedstat недостаточны для разделения Linux и host.

Подготовлен один 15-секундный baseline с новым измеряемым фактором — kernel trace sender: pselect6 entry/exit, sendto/recvfrom, sched_waking/wakeup/switch. Первые полные снимки endpoint/router и готовность трассы подтверждаются до разрешения отправки. Алгоритм 100Гц, router, Docker CPU/RAM и критерий каждого 10-мс слота сохранены. Сбор использует отдельный каталог; прежние raw не изменены (T6NngDpB: 41/41 SHA256).

Рабочая Linux-трассировка проверена в network-none контейнерах; ей необходим временный privileged helper с host PID namespace. Трасса macOS недоступна с текущими правами: DTrace требует дополнительных прав, sudo требует пароль, ktrace info завершился ошибкой; xctrace требует Xcode вместо установленного CommandLineTools. Поэтому будущий вывод ограничен Linux VM. Для разделения timer/host/VM затем потребуется отдельно проверенный привилегированный host System Trace/ktrace с vCPU threads и синхронизацией часов. Увеличение ресурсов Docker данными не обосновано.

Проверено без UDP: синтаксис shell/Python, compose config, четыре автономных теста, реальный selftest (20 pselect и UNIX socketpair send/receive), PID-фильтры, совпадение временных интервалов, барьер snapshot, нулевые потери на двух CPU. Первоначальная ошибка теста распознавания текстового имени syscall исправлена; финальный selftest успешен. Полный сетевой путь нового сборщика пока не исполнялся — измерение оставлено пользователю.

Влияние наблюдения не нулевое: wrapper добавил около 29.9мкс CPU/вызов в проверке пустого select; дополнительно работают ftrace, sampler и pcap. Полный эффект под UDP не измерен; к lag не применяется поправка, причинное сравнение числа опозданий с control не заявляется. Счётчики overrun/commit overrun/dropped events и соответствие syscall wrapper проверяются автоматически; late-details сохраняет участок каждой поздней группы. При непригодной трассе сбор завершается с ошибкой, а raw сохраняется.

Команда из корня репозитория после остановки фоновой разработки:

```sh
SERIES_TLS_DIR="$PWD/build/series-tls.PMYktiWa" sh docker/sender-scheduling.sh
```

[План, критерии, ограничения и ожидаемые файлы](sender-scheduling-plan.md). [Проверки и команды](../../results/verify/readiness/sender-scheduling-preflight/). Сам UDP-запуск, обычный control, полная calibration, A/A, monitoring, pilot и основная серия не выполнялись.
