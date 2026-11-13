# План короткой трассы sender, 13 ноября 2026

Статус: подготовлено, UDP-измерение не запускалось. Последний control T6NngDpB: одна пауза потока, четыре поздних слота, max 40.942417 мс. Отсутствие потерь, ARP, throttling и низкая средняя CPU не объясняют эту паузу. Предыдущий wrapper локализует основные задержки вокруг select, но не разделяет Linux/host/VM.

## Возможности и границы

Проверка без сетевой нагрузки: Linux6.12.76-linuxkit/aarch64 имеет tracefs, `sched_switch`, `sched_waking`, `sched_wakeup`, `sys_enter/exit_pselect6`, `sendto`, `recvfrom`. Отдельного syscall select на этой архитектуре нет. Установленные образы не содержат perf/trace-cmd/bpftrace/strace; perf_event_paranoid=2. Обычный cap-drop контейнер видит пустой `/sys/kernel/tracing`. Рабочий проверенный вариант: временный `--privileged --pid host --network none` контейнер, mount tracefs и собственный instance. Sender остаётся cap-drop ALL, в прежнем unrestricted cgroup. Глобальные trace filters/clock/buffer не меняются. Контейнер с такими правами имеет широкий доступ к Linux VM; он используется только на время диагностики, без изменения CPU/RAM Docker.

macOS: uid501, SIP enabled. DTrace отказывает без дополнительных прав; `sudo -n true` требует пароль; `ktrace info` возвращает `Too many levels of remote in path`; xctrace требует полного Xcode, установлен CommandLineTools. Наличие бинарника не означает возможность записи. Процессы VM: com.docker.virtualization и Virtualization.VirtualMachine.xpc (PID в снимке проверки, перед будущей host-трассой определить заново). sample/spindump не заменяют непрерывные события wakeup/context switch.

Поэтому команда ниже явно собирает **только Linux scheduling**. Времена mono из tracefs сопоставляются с Python monotonic_ns по маркеру с bracket before/after; сохранены start_ns, namespace PID/TID и NSpid→host TID. Realtime сохранён как справочная привязка, часы host/VM и pcap напрямую не вычитаются. Поздний wakeup в guest сам по себе не отделяет поздний таймер Linux от остановки исполнения VM. Даже runnable-wait может включать отсутствие исполнения vCPU на host.

Если Linux-данных окажется недостаточно, следующий вариант — отдельно проверить на host с интерактивным администраторским доступом `sudo ktrace info`, затем короткий захват scheduler-событий macOS с проверкой потерь и отображением потоков vCPU. Либо установить Xcode и проверить System Trace. До проверки записи, потерь и синхронизации это не готовая host-команда. SIP не отключать; успешность root DTrace здесь не установлена.

## Единственный запуск пользователем

Из корня репозитория, после остановки фоновой разработки:

```sh
SERIES_TLS_DIR="$PWD/build/series-tls.PMYktiWa" sh docker/sender-scheduling.sh
```

Одна baseline-проба: исходный `calibration_probe.send`, COUNT=1500, период 10000000 нс, прежние payload/receive/select/catch-up/drain≤2с. 15с — окно отправки; подготовка/очистка занимают дополнительное время. Маршрут browser→router→server, baseline netem, штатные permanent neighbors и ingress pcap. Без r80/control/полной calibration/A/A/monitoring/pilot/main. Measurement lock тот же. Старые raw не изменяются.

До первого send: полный flush первого CPU/memory/network snapshot обоих endpoint подтверждается readiness-файлами; router — строкой snapshot-end после чтения всех полей. Затем sender ждёт gate; tracer определяет host TID, устанавливает фильтры, включает запись, пишет маркер и trace-ready; только после этого открывается gate. Samplers работают до явного stop после завершения sender и дают конечный снимок. Проверяется покрытие endpoint до start_ns и после usage_after, router проверяется по uptime/snapshot-end. Частота ресурсов 1Гц не разрешает краткие пики.

## Критерии и разбор

1. Сбор пригоден: sources before/after совпадают; captured SHA256 верны; каждый wrapper select/send/receive имеет syscall entry/exit внутри своего wall-интервала (допуск 2мкс на текстовую точность trace), PID/TID верны. Readiness-маркер предшествует первой отправке, stop следует после последнего вызова. Нет потерянных trace events: overrun, commit overrun, dropped events =0 на каждом CPU. Отказ проверки означает непригодность соответствующего вывода, а не отсутствие паузы.
2. Критерий частоты прежний: для **каждого** ID `0 <= t_send_ms - t_plan_ms < 10`. 1500 уникальных send/reply ID, план i×10мс. RTT от фактической отправки анализируется отдельно. Shell exit0 не означает прохождение слотов.
3. Сеть: оба ingress имеют 1500 корректных tag/ID, ARP=0, capture kernel drops=0, UDP/netem delta drops=0; qdisc до/после пусты; все четыре neighbor до/после PERMANENT, IP/MAC/interface сверены с veth и pcap. Эту сетевую сверку выполняют offline по raw, она не заменяется trace-check.json.
4. Ресурсы: CPU и runnable-wait sender, cgroup cpu.stat/cpu.max (delta nr_throttled/throttled_usec), memory.current/events/stat/pressure, VM CPU/meminfo/pressure/softnet/snmp, socket queues, router qdisc и cgroup. Сохранить пики и deltas, не выводить отсутствие краткой перегрузки из среднего CPU.
5. Для позднего ID: deadline→select entry, переданный timeout и ready из wrapper, syscall exit/ret, sched_waking→sched_wakeup→sched_switch(next=sender), вытеснения prev_state=R, receive wall/CPU/schedstat и интервалы между вызовами. late-details включает весь участок от последней своевременной отправки перед группой опозданий. CPU-wait реконструировать по всем runnable участкам и миграциям, не только последнему wakeup. Отдельно отмечать догоняющие send. При wakeup до deadline и позднем switch наблюдается ожидание CPU в guest; при позднем wakeup причина Linux timer/host/VM остаётся открытой. Отсутствие wakeup возможно для неблокирующего возврата и не является потерей само по себе.

## Влияние наблюдения и проверка

Сохраняется прежний wrapper с monotonic/process CPU, schedstat/rusage на границах вызовов; добавлены сохранение start_ns и kernel events. В отдельной несетевой микропроверке 1000 пустых select(timeout=0): ~0.753мкс CPU без wrapper, ~30.670мкс с wrapper, разность ~29.917мкс/вызов. Это локальная оценка стоимости обёртки, не поправка к lag и не оценка стоимости ftrace под UDP. Буфер 8192KiB на CPU (16MiB при двух vCPU), только события target TID, без потокового чтения во время send; helper опрашивает stop раз в 50мс. Samplers, tcpdump, Python instrumentation и kernel hooks также влияют на исполнение. Полная величина observer effect без парного эксперимента не установлена; число опозданий не сравнивать причинно с прежним control. A/A здесь не запускается.

Проверки без UDP: `sh -n`; компиляция Python; четыре теста проверки целостности/потерь/покрытия/критерия слота; реальный selftest в network-none контейнере на 20 pselect(timeout=5мс) и UNIX socketpair send/receive. Проверены фильтры TID, пары syscall, scheduling, mono-привязка, первый snapshot и нулевые потери. Первый selftest выявил иной текстовый формат syscall (`sys_pselect6(...)`/`sys_pselect6 ->`), исправлено и повторено. Сквозной сетевой collector сознательно не запускался; его первая UDP-проверка — команда пользователя выше.

Семантика loss counters: [документация Linux ftrace](https://www.kernel.org/doc/html/latest/trace/ftrace.html). Фактические форматы событий, права и результат selftest сохранены в `results/verify/readiness/sender-scheduling-preflight/`.

## Ожидаемые файлы

Новый `results/verify/diagnostic/sender-scheduling.XXXXXXXX/`:

- `collector.sh`, `plan.md`, `commands.log`, `commit`, `sources/`, `sources-before.json`, `sources-after.json`, `captured.json`, `started`, `ended`, `exit`.
- `docker-info.json`, `inspect.json`, `containers-before.txt`, `stats-{before,after}.jsonl`, `host.txt`, `host-resources.txt`, `host-memory-{before,after}.txt`, `idle-resources.jsonl`.
- `router-links.txt`, `{browser,server}-route.txt`, `{browser,server}-neighbors{,-after}.json`, `router-{browser,server}-neighbors{,-after}.json`.
- В `baseline-scheduling/`: `probe.json` (plan/send/RTT, start_ns, per-call wall/CPU/schedstat), `sender-ready.json`, `target.json`, `trace-config.json`, `trace-ready.json`, `trace-stop`, `trace.txt`, `trace-loss.json`, `stats-{before,after}.json`, `*.format`, `tracer.log`, `trace-check.json`, `late-details.json`.
- Там же `{browser,server}-resources.jsonl`, `router-resources.txt`, `{browser,server}-route.txt`, `profile.txt`, `qdisc-{before,after}.json`, `{browser,server}.pcap`, `{browser,server}.log`. При аварии — `*.interrupted.*`; смотреть exit и commands.log, не принимать неполный сбор.
