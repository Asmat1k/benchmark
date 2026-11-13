# Короткая диагностика отправителя, 2026-11-13

До измерения: только baseline-before, r80p0-response, baseline-repeat. Каждая проба: 1500 датаграмм, исходный PERIOD_NS=10000000, ~15 с отправки + до 2 с drain. Исходный calibration_probe.send не изменяется: wrapper задаёт COUNT=1500 и измеряет select/receive/send. Маршрут и permanent neighbors — штатные links.sh и calibration-neighbors.sh (2cefcdb). Никаких saturation, полной calibration, A/A, monitoring, pilot/main.

Критерии: каждый t_plan_ms <= t_send_ms < t_plan_ms+10; 1500 уникальных send ID; zero-loss профили должны вернуть все ID без дубликатов. Это только диагностические критерии, не полный gate. Проверить 4 PERMANENT записи до/после, MAC противоположного veth, отсутствие ARP в обоих ingress pcap, отсутствие kernel capture drops, сверку UDP ID и qdisc drops. Raw не редактировать и не удалять, исходный seal 141 файлов перепроверить до/после.

Доказательства: сохранить wall/process CPU/schedstat вокруг каждого select, receive и send; 1 Гц CPU/cgroup throttling/memory/events/pressure, VM /proc/stat/meminfo, UDP socket queues/errors, softnet, router tc backlog. Ожидание select может включать задержку пробуждения и приостановку VM; schedstat runqueue wait показывает лишь Linux runnable wait. Получатель, Python tracing, host scheduler и гипервизор могут влиять; наблюдательная корреляция не доказывает единственную причину. Wrapper добавляет overhead и отдельно сохраняется. Сравнение baseline/r80 отделяет задержанный поток ответов лишь в пределах этих коротких запусков.

Менять код только при воспроизводимом подтверждённом дефекте, с коротким повтором. Ресурсы Docker сначала измерить; не менять по факту одного большого lag и не ослаблять критерии. Для следующего действия сохранить точную команду и основание.
