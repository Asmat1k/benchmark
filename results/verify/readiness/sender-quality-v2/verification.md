# Проверка внедрения v2

- 8 адресных тестов прошли в штатном analyzer image, --network none, timeout30: шесть новых тестов sender_quality, текущий raw и отказ исторической конфигурации, diagnostic context/run identity. Время unittest1.412с.
- 9 тестов docker/*test.py прошли: pcap collection tag, фактические directional losses, saturation accounting, neighbors и scheduler trace integrity/coverage/losses.
- Проверены14 схем, configs, положительные/отрицательные синтетические примеры; sh -n обоих collectors, Python syntax, git diff --check.
- CLI на LGEmSpOH: exit0; на T6NngDpB: exit1, burst6 >4.
- Пересчитаны22 подсерии; 9 timing passed, 13 failed; seals и неизменность raw проверены. Формальная calibration не перепубликовывалась.
- Расширенный сквозной R7 остановлен после уточнения пользователя: его synthetic A/A report passed, monitoring не завершён. Общий прогон без R7 ограничен timeout180 и завершился exit124:37 тестов passed,1 skipped, следующий тест прерван. Это не полный зелёный suite. Новых долгих прогонов не назначено.
- Первоначальные проверки выявили устаревшие конфигурации временных synthetic fixtures. Исправлено создание текущей config/context и их hashes; исторические raw остаются неизменны и не принимаются за текущую конфигурацию. Ошибка ожидания исторического smoke в test_valid_raw исправлена и адресно перепроверена.

Воспроизведение адресной проверки:

```sh
docker run --rm --network none -v "$PWD:/bench" -w /bench -e PYTHONPATH=src/analysis wswt-bench-analyzer:dev timeout 30 python -B -m unittest -v test_sender_quality test_measurement.MeasurementTests.test_valid_raw test_diagnostic_input.DiagnosticInputTests.test_published_context_and_run_identity
PYTHONPATH=docker /opt/anaconda3/bin/python3 -B -m unittest discover -s docker -p '*test.py'
/opt/anaconda3/bin/python3 -B docs/fixtures/synthetic/validate.py
sh -n docker/sender-diagnostic.sh docker/sender-scheduling.sh
python3 -B results/verify/readiness/sender-quality-v2/recompute.py
```

Новые сетевые измерения, полная calibration, реальные A/A/monitoring/pilot/main не выполнялись. Права, ресурсы Docker, алгоритм calibration_probe, частота и payload не изменены.
