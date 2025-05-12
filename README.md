# PoC сервиса управления парсерами

Это proof-of-concept для сервиса управления парсерами на базе Scrapyd, ScrapydWeb и Selenium. Проект демонстрирует возможности распределенного запуска и управления Scrapy пауками с поддержкой работы с SPA-сайтами, сохранением данных в PostgreSQL и S3-совместимое хранилище.

## Стек технологий

- **Scrapy** - фреймворк для парсинга сайтов
- **Scrapyd** - сервис для управления Scrapy пауками
- **ScrapydWeb** - веб-интерфейс для Scrapyd
- **Selenium** - инструмент для автоматизации браузера и работы с SPA
- **PostgreSQL** - реляционная база данных для хранения результатов
- **MinIO** - S3-совместимое хранилище
- **NGINX** - балансировщик нагрузки
- **TinyProxy** - прокси-сервер для маскировки запросов

## Развертывание

### Требования

- Docker и Docker Compose
- Python 3.10+

### Запуск

1. Клонируйте репозиторий
2. Соберите egg-файл для демо-паука и запустите контейнеры:

```bash
docker compose down -v; rm shared-eggs/demo-1.0-py3.10.egg; cd demo_spider/; python3 setup.py bdist_egg; cd ..; cp demo_spider/dist/demo-1.0-py3.10.egg shared-eggs/; docker compose up --build -d
```

## Примеры использования

### Запуск паука с авторизацией и прокси на Scrapyd2

```bash
curl -u group2:scrapyd2 \
http://localhost:6801/schedule.json \
-d project=demo-1.0-py3.10 \
-d _version=1_0 \
-d spider=quotes_spa \
-d jobid=2025-05-09T13_15_00 \
-d setting=CLOSESPIDER_PAGECOUNT=0 \
-d setting=CLOSESPIDER_TIMEOUT=60 \
-d arg1=val1 \
-d auth_enabled=true \
-d username=admin \
-d password=admin \
-d proxy=http://tinyproxy:8888
```

### Запуск паука без прокси на Scrapyd1

```bash
curl -u group1:scrapyd1 \
http://localhost:6800/schedule.json \
-d project=demo-1.0-py3.10 \
-d _version=1_0 \
-d spider=quotes_spa \
-d jobid=custom_job_id \
-d setting=CLOSESPIDER_TIMEOUT=60
```

### Остановка запущенного паука

```bash
curl http://localhost:6800/cancel.json -d project=demo-1.0-py3.10 -d job=custom_job_id
```

## Доступные сервисы

- [ScrapydWeb интерфейс](http://localhost:5000) - управление пауками, просмотр логов и статистики
- [S3 хранилище (MinIO)](http://localhost:9001) - для доступа к сохраненным файлам результатов
  - Логин: minio_user
  - Пароль: minio_password
  - Бакет: scraper-results
- [pgAdmin](http://localhost:5050) - управление базой данных
  - Логин: admin@example.com
  - Пароль: admin
  - Данные для подключения к PostgreSQL:
    - Хост: postgres
    - Порт: 5432
    - Пользователь: scraper_user
    - Пароль: scraper_password
    - База данных: scraper_data
- [Scrapyd1](http://localhost:6800) - первый экземпляр Scrapyd
- [Scrapyd2](http://localhost:6801) - второй экземпляр Scrapyd
- [NGINX балансировщик](http://localhost:8800) - балансировщик нагрузки (в разработке)
- [API Gateway](http://localhost:5001) - API-шлюз для интеллектуальной балансировки нагрузки и управления заданиями

## Архитектура

Проект состоит из нескольких взаимосвязанных контейнеров:

1. **scrapyd1, scrapyd2** - экземпляры Scrapyd для запуска и управления пауками
2. **scrapydweb** - веб-интерфейс для мониторинга и управления пауками
3. **selenium-hub** - сервис для автоматизации браузера Chrome (необходим для работы с SPA)
4. **postgres** - база данных для хранения результатов парсинга
5. **pgadmin** - веб-интерфейс для управления базой данных
6. **load-balancer** - NGINX для балансировки нагрузки между экземплярами Scrapyd
7. **tinyproxy** - прокси-сервер для маскировки запросов
8. **minio** - S3-совместимое хранилище для файлов
9. **minio-mc** - утилита для настройки MinIO
10. **api-gateway** - API-шлюз для управления заданиями и балансировки нагрузки
11. **redis** - хранилище для сессий и состояния системы

## Улучшенные возможности балансировки нагрузки

### API Gateway для управления заданиями

API Gateway предоставляет унифицированный интерфейс для запуска и мониторинга заданий на всех Scrapyd-инстансах с автоматическим выбором наименее загруженного узла.

#### Проверка статуса API Gateway:

```bash
./check_api_gateway.sh
```

#### Пример ответа:

```
Checking API Gateway at http://localhost:5001...
✅ API Gateway is running

Scrapyd Instances Status:
✅ scrapyd1: online (running: 0, pending: 0)
✅ scrapyd2: online (running: 0, pending: 0)

Example usage:
  Schedule a spider:  ./api-gateway/client_example.py schedule --project demo --spider example --kwargs='{"url":"https://example.com"}'
  List jobs:          ./api-gateway/client_example.py list --project demo
  Cancel a job:       ./api-gateway/client_example.py cancel --project demo --job-id JOB_ID
```

### Запуск задач через API Gateway

Используйте скрипт `schedule_api.sh` для запуска задач через API Gateway с тем же синтаксисом, что и для прямого обращения к Scrapyd:

```bash
./schedule_api.sh \
-d project=demo-1.0-py3.10 \
-d _version=1_0 \
-d spider=quotes_spa \
-d jobid=custom_job_id \
-d setting=CLOSESPIDER_PAGECOUNT=0 \
-d setting=CLOSESPIDER_TIMEOUT=60 \
-d auth_enabled=true \
-d username=admin \
-d password=admin \
-d proxy=http://tinyproxy:8888
```

### Использование Python-клиента для API Gateway

```bash
# Проверка статуса всех Scrapyd-инстансов
python3 api-gateway/client_example.py status

# Запуск паука на наименее загруженном узле
python3 api-gateway/client_example.py schedule \
  --project demo-1.0-py3.10 \
  --spider quotes_spa \
  --version 1_0 \
  --setting CLOSESPIDER_TIMEOUT=60 \
  --auth-enabled \
  --username admin \
  --password admin \
  --proxy http://tinyproxy:8888

# Список всех заданий
python3 api-gateway/client_example.py list --project demo-1.0-py3.10

# Отмена задания
python3 api-gateway/client_example.py cancel --project demo-1.0-py3.10 --job-id JOB_ID
```

### Мониторинг балансировки нагрузки

Для демонстрации и тестирования работы балансировщика используйте скрипт `test_balancer.sh`:

```bash
# Запуск 3 заданий и мониторинг их выполнения
./test_balancer.sh --count=3
```

#### Пример вывода:

```
=== ТЕСТ БАЛАНСИРОВКИ НАГРУЗКИ ===
API Gateway: http://localhost:5001
Проект: demo-1.0-py3.10, Паук: quotes_spa
Запущено задач: 3

=== СТАТУС SCRAPYD-ИНСТАНСОВ ===
✓ scrapyd1: 0 задач выполняется, 0 в очереди
✓ scrapyd2: 0 задач выполняется, 0 в очереди

=== СТАТУС ЗАДАЧ ===
Узел: scrapyd1
  Завершено: 2 (последние 3)
    - 2025-05-12T15_12_12_3 (quotes_spa) - завершена 2025-05-12 13:13:12.291379
    - 2025-05-12T15_12_08_1 (quotes_spa) - завершена 2025-05-12 13:12:44.918356

Узел: scrapyd2
  Завершено: 1 (последние 3)
    - 2025-05-12T15_12_10_2 (quotes_spa) - завершена 2025-05-12 13:13:39.125474
```

Этот мониторинг обновляется каждые 2 секунды и показывает:
1. Статус каждого Scrapyd-инстанса (количество выполняемых и ожидающих задач)
2. Задания в очереди, выполняющиеся задания и недавно завершенные задания для каждого узла

## Текущее состояние PoC

Сейчас реализовано:
- Запуск пауков на нескольких экземплярах Scrapyd
- Использование Selenium для работы с SPA-сайтами
- Поддержка работы через прокси
- Сохранение данных в PostgreSQL и S3-хранилище
- Мониторинг работы пауков через ScrapydWeb

Подробнее о текущем состоянии и планах развития смотрите в файле TODO.md.
