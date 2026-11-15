# Проверка стенда

Реализации и тесты фич находятся рядом в [src/analysis/](../src/analysis/README.md); общие проверки и fixtures остаются в src/analysis/tests/. Там же описаны запуск отдельных групп и полный discovery.

- `make build`: сборка четырёх закреплённых native linux/arm64 образов, проверки TypeScript/Go и зависимостей.
- `make smoke`: короткая проверка TLS и сетевого пути; `make measurement-smoke`: короткая проверка измерителя WS/WT-S.
- `make docker-test`: диагностические инструменты без измерительной сети.
- `make analysis-test`, `make acceptance-test`, `make controller-test`: существующие проверки анализа и допуска на fixtures.

Целевые проверки устойчивости находятся в test_execution.py, test_checkpoint_cleanup.py, test_exploratory.py, test_exploratory_stabilization.py и test_outcomes.py. Они проверяют отказ/продолжение, сохранение и восстановление, фиксированное расписание и отчёт по всем назначениям. Принудительное падение Chromium проверяет src/runner/test-checkpoint.mjs.

Успех короткой проверки не доказывает безотказность 15 часов или научную эквивалентность. Исторический расширенный набор содержит устаревшие fixtures; весь legacy-набор не объявляется зелёным. Для новой версии запуска требуется актуальный admission, а не изменение старых результатов.
