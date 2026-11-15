# Автоматические проверки GitHub

[workflows/](workflows) содержит [checks.yml](workflows/checks.yml): на push и pull request собирается закреплённый analyzer на ARM64, проверяются схемы/fixtures и синтетические статистические эталоны через `make analysis-test`.

Сетевой smoke в CI явно записывается как `not_run`, поскольку требует отдельного хоста; файл состояния публикуется как артефакт `ci-status`. Поэтому успех этого workflow подтверждает только перечисленные офлайн-проверки. Остальные проверки — [docs/verification.md](../docs/verification.md).
