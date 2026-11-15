# Матрица исполнения

Для реализации допустимы «не начата», «выполняется», «завершена». Для экспериментальной проверки допустимы not_run, passed, failed, inconclusive. Статус реализации отражает наличие артефакта. Решение рецензента и SHA фиксируются отдельно в материалах передачи и Git.

| Волна | Артефакт | Реализация | Экспериментальная проверка | Причина |
|---|---|---|---|---|
| D0 | Контракты, схемы, конфигурации и примеры | завершена | not_run | deferred_by_user |
| D1 | WS/WT-S, TLS, echo | завершена | not_run | deferred_by_user |
| D2 | Контейнеры, locks, маршруты и ресурсы | завершена | not_run | deferred_by_user |
| D3 | Измеритель и raw | завершена | not_run | deferred_by_user |
| D4 | Анализ, статистика и графики | завершена | not_run | deferred_by_user |
| D5 | Команды calibration, A/A, monitoring, pilot, power, freeze, main | завершена | not_run | deferred_by_user |
| D6 | Независимая интеграция и передача | завершена | not_run | deferred_by_user |

| Отложенная проверка | Экспериментальная проверка | Причина |
|---|---|---|
| Калибровка таймера и сети, потерь и readback под нагрузкой | not_run | deferred_by_user |
| Saturation полосы | not_run | deferred_by_user |
| Генератор 20/100 Гц | not_run | deferred_by_user |
| A/A | not_run | deferred_by_user |
| Monitoring on/off | not_run | deferred_by_user |
| Официальный pilot и оценка мощности | not_run | deferred_by_user |
| Final verify, freeze и воспроизведение экспериментального пакета | not_run | deferred_by_user |
| Основная серия | not_run | deferred_by_user |

Интеграция D6 выполнена в разрешённом объёме разработки; независимая приёмка и SHA фиксируются отдельно в [передаче](handoffs/dev-wave-6.md). Экспериментальная волна 6 плана остаётся отложенной.
