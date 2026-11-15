# Независимая внутренняя проверка браузерного генератора

Официальный результат: failed; exit сбора: 1.
Предусмотрено 6 запусков; расписано 6; проверено sealed raw 6; технически неизвестно 0.

| Hz | Mode | Status | Slots | Sent | Completed | Late | Missing | Lag p99 ms | RTT p99 ms |
|---|---|---|---|---|---|---|---|---|---|
| 20 | WT-D | sealed-validated | 1200 | 1200 | 1200 | 0 | 0 | 9.5 | 2.699999988079071 |
| 20 | WS | sealed-validated | 1200 | 1200 | 1200 | 0 | 0 | 8.5 | 3.7999999821186066 |
| 20 | WT-S | sealed-validated | 1200 | 1200 | 1200 | 0 | 0 | 9.900000005960464 | 5.0 |
| 100 | WS | sealed-validated | 1200 | 1200 | 1200 | 0 | 0 | 6 | 3.199999988079071 |
| 100 | WT-S | sealed-validated | 1200 | 1200 | 1200 | 0 | 0 | 6.0 | 3.4000000059604645 |
| 100 | WT-D | sealed-validated | 1200 | 1199 | 1199 | 0 | 1 | 6 | 3.0 |

All scheduled outcomes retained. 100 Hz is reserve only; failed performance does not imply invalid data. No RTT imputation or lag subtraction.

Полные состояния slots, ресурсы по фактическому CPU limit, backlog/drops, seals и provenance приведены в review.json. Оценки RTT условны на возвращённые ответы; все missing сохранены в знаменателе.
