# Независимый review запуска browser generator

15 ноября 2026. Внутренний reviewer `/root/design`. Проверены browser-generator-run.py, browser-generator-policy-v1.md, browser_admission.py, collect-diagnostic.sh и связанные preflight/release/measurement cleanup/diagnostic input. Сеть и Docker не запускались. Обзор относится к рабочим файлам до нового commit, а не удостоверяет будущий запуск или полученные результаты.

## Блокирующее замечание: применимость historical source

`historical_calibration()` сверяет historical hardware/images/TLS, evidence hashes и integrity receipt, однако не сопоставляет historical `source_hashes` с текущими sources. `validate()` проверяет лишь совпадение decision с текущими sources. В результате после произвольного нового committed изменения client/runner/server/measure/network можно создать новый decision и пройти admission, хотя policy обосновывает reuse именно неизменностью этих зависимостей. SHA текущего source доказывает его идентичность решению, но не применимость прежних свидетельств.

До сети требуется предметная проверка границы изменений: старые source hashes равны текущим для всех незатронутых зависимостей, изменения только по точному списку добавленного admission и изменённого collector (и явных тестовых файлов). Не использовать общее разрешение `src/analysis/*` или `docker/*`. Новые неожиданные executable paths также закрывают допуск. Для измерительных/client/server/runner/network изменений нужны отдельные применимые свидетельства. Meaningful regression: изменение прежнего client/measure hash либо новый неожиданный executable source отклоняется; текущий узкий набор изменений принимается.

## Release и preflight

На момент чтения HEAD acce594, collect-diagnostic.sh изменён, browser_admission.py ещё не tracked. Такой запуск должен остановиться в check-release/preflight. Нужен новый commit, включающий весь фактический executable delta и tests. Wrapper правильно берёт актуальный HEAD, создаёт release-state и адаптирует прежний hardcoded preflight HEAD; executable inventory затем сравнивается с committed snapshot. Отдельный новый docs commit во время работы недопустим: HEAD фиксируется и проверяется после сбора. Не считать успешный тест до commit реальным preflight будущего релиза.

Preflight проверяет AC/open lid, диск, exact images/VM/TLS, отсутствие чужой wswt серии, свободные подсети и measurement lock. Caffeinate отсутствует внутри wrapper, поэтому запуск должен явно идти под `caffeinate -ims`. Новый ENV не нужен только из-за добавленного source: config и bindings должны остаться фактически одинаковыми; при изменении protocol/config текущий ENV обоснованно отвергается `current_environment`.

## Абсолютные пути receipts

Двойной bind mount одного workspace в `/bench` и по точному host absolute path решает проверку исторических absolute receipt references. Исторические hashes не переписываются. Оба analyzer-вызова collector и wrapper используют этот mount. Measurement analyzer оставляет `/bench` mount; historical admission там не вызывается. Это соответствует видимым зависимостям. Если historical refs ведут вне этого workspace, их доступность надо отдельно проверить до сети; широкое монтирование host filesystem не требуется.

## Timeout и cleanup

Wrapper задаёт network deadline1500с, отдельную process group и TERM с ожиданием30с, затем KILL. Measure устанавливает TERM/INT→exit и EXIT cleanup; cleanup собирает остаточные resource logs, делает compose down, переносит partial в quarantine и освобождает lock. Нормальный путь согласован. После сети wrapper проверяет отсутствие wswt containers и неизменность HEAD/source/ENV/policy/leaf.

Ограничение: после KILL при зависшем cleanup контейнеры могут остаться; wrapper только отмечает отказ по leftovers. Это не разрешение удалять чужие проекты. При таком исходе остановиться, сохранить STOP/partial и завершить адресный cleanup только проекта, созданного данным execution; новый сетевой запуск до этого запрещён. Общий stderr traceback/exit/ended сохраняется и при ошибке preflight. Cигнал, завершающий сам wrapper вне KeyboardInterrupt, не гарантирует эти журналы; текущий review не удостоверяет устойчивость к аварийному завершению хоста.

## Семантика результата

Новый decision ограничен diagnostic-generator и не превращает calibration failed в passed, не выдаёт main readiness. Шесть slots запускаются штатно: 20/100Гц × WS/WT-S/WT-D. Diagnostic parser проверяет schedules/contexts/raw/resources/router coverage и применяет существующие generator criteria. Генерация report выполняется после сети. Техническая ошибка может прервать сетку: сохранить planned/partial и назвать её неполной, а не шестью выполненными runs. Exit0 оболочки сам по себе не scientific passed.

Policy не снижает численные generator thresholds и правильно отделяет 100Гц reserve от 20Гц main. Допуск следующего сравнительного дизайна и main этим review не выдаётся.

## Вердикт

Запуск сети условно допустим после узкой проверки historical source applicability, нового clean commit/release и фактического успешного preflight под caffeinate. До устранения applicability gap reviewer не подтверждает заявленное обоснование повторного использования неизменённых зависимостей. Независимого сетевого результата пока нет.
