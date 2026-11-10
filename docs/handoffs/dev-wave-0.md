# Передача D0

Вход — main, 5896b72965dae7e277d482e4c708c276b4712810. В рабочей копии до D0 находился пользовательский .agents/plan/. Редакция 2 плана SHA256 0a19ce603d7e4519f000176b957b855b11466d5910649ac02db65a0f1aab7c7d, AGENTS.md 9ab52434a7a82d98096f68814aeb34ec94bf78fd33c5041fdde39f5272022f08, README.md a4d4769d8f4727dd8e091f71242d836e6e67a99477c9bf21600fc9d275070bf2. В .github/workflows/ не было workflow. Основания — §§2–3 плана, краткий отчёт §§4–6 и В2/01–03,05. R1–R3 предыдущей независимой рецензии закрыты в плане.

## Что передано

- docs/protocol.md, metrics.md, analysis.md, verification.md и architecture.mmd определяют рамку, контрольный обмен, время, исходы, статистику и последовательность допуска.
- configs/{plan,profiles,thresholds}.json — предварительные параметры v1. Изменение фиксируется версией и повторной проверкой. Freeze отсутствует.
- docs/schemas/*.schema.json — JSON Schema Draft 2020-12, v1 для трёх configs и slot/event/resource/server/completion/manifest/checks/ledger/freeze. Ограничения между записями, проверка содержимого evidence и хешей, допустимость main и точное сложение времён проверяются потребителями в D3–D5.
- docs/fixtures/synthetic/ содержит пример граничного echo при 100 мс с максимальным nonce, пример not_run и неприемлемый числовой nonce. Это только иллюстрации контракта.
- docs/development-scope.md и execution-matrix.md отделяют приёмку разработки от научных gates.

## Воспроизведение

Из корня репозитория выполнить `python3 docs/fixtures/synthetic/validate.py` с установленным jsonschema 4.x. Проверка offline на /opt/anaconda3/bin/python3 подтвердила 12 метасхем, 3 конфигурации и позитивные примеры. Негативный slot отвергнут на $.nonce с причиной «is not of type 'string'». Сетевые процессы и контейнеры D0 не создавались. Состав и точные хеши переданных файлов после commit доступны через `git ls-tree -r <SHA> docs configs`.

D1 использует [byte map и handshake](../protocol.md), три конфигурации и isolated smoke. В D3 потребуются полные семантические проверки slot IDs, границ, counts и хешей, в D4 — эталоны статистики. Все отложенные gates перечислены в [матрице](../execution-matrix.md) со статусом not_run/deferred_by_user. Замечания независимого ревью и их закрытие сохраняет рецензент в docs/reviews/ws-wt-bench/dev-wave-0/. Итоговый commit SHA передаёт координатор отдельно.

После независимой рецензии исправлены D0-R1 и D0-R2. Контракт ledger различает сравнение, A/A и monitoring on/off, задаёт обязательные стороны пары и порядок мониторинга. Синтетический ledger проверяет оба порядка WS/WT-S, A/A и on/off; подмена WT-S режимом WT-D отклонена. Для baseline есть отдельное значение в manifest вне pilot/main. Позитивный пример verify принят, тот же baseline для main отклонён. Повторная команда validate.py также перепроверяет первоначальные примеры. Решение о закрытии замечаний принимает независимый рецензент.
