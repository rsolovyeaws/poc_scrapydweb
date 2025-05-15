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
- **Proxy Rotator** - сервис для автоматического переключения между прокси-серверами
- **RabbitMQ** - система обмена сообщениями для асинхронного запуска пауков
- **ELK Stack** - Elasticsearch, Kibana и Filebeat для логирования
- **Prometheus & Grafana** - мониторинг и визуализация метрик
- **Alertmanager** - отправка уведомлений о событиях

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
- [RabbitMQ Management](http://localhost:15672) - интерфейс управления RabbitMQ (логин: guest/guest)
- [Kibana](http://localhost:5601) - визуализация и анализ логов
- [Grafana](http://localhost:3000) - визуализация метрик (логин: admin/admin)
- [Prometheus](http://localhost:9090) - сбор и хранение метрик
- [Elasticsearch](http://localhost:9200) - хранилище логов
- [cAdvisor](http://localhost:8080) - мониторинг контейнеров

## Архитектура

Проект состоит из нескольких взаимосвязанных контейнеров:

1. **scrapyd1, scrapyd2** - экземпляры Scrapyd для запуска и управления пауками
2. **scrapydweb** - веб-интерфейс для мониторинга и управления пауками
3. **selenium-hub** - сервис для автоматизации браузера Chrome (необходим для работы с SPA)
4. **postgres** - база данных для хранения результатов парсинга
5. **pgadmin** - веб-интерфейс для управления базой данных
6. **load-balancer** - NGINX для балансировки нагрузки между экземплярами Scrapyd
7. **tinyproxy1, tinyproxy2** - прокси-серверы для маскировки запросов
8. **proxy-rotator** - сервис для автоматической ротации прокси-серверов
9. **minio** - S3-совместимое хранилище для файлов
10. **minio-mc** - утилита для настройки MinIO
11. **api-gateway** - API-шлюз для управления заданиями и балансировки нагрузки
12. **redis** - хранилище для сессий и состояния системы
13. **rabbitmq** - система обмена сообщениями для асинхронного запуска пауков
14. **task-processor** - сервис для обработки заданий из очереди RabbitMQ
15. **elasticsearch, kibana, filebeat** - стек ELK для сбора и анализа логов
16. **prometheus, grafana, cadvisor, node-exporter** - система мониторинга метрик
17. **alertmanager, telegram-alerts** - система оповещений

## Ротация прокси-серверов

Система поддерживает автоматическую ротацию прокси-серверов для повышения анонимности и снижения риска блокировки. Вы можете использовать как автоматическую ротацию, так и фиксированный прокси.

### Компоненты системы ротации прокси

- **tinyproxy1, tinyproxy2** - контейнеры с независимыми прокси-серверами
- **proxy-rotator** - сервис, обеспечивающий API для получения и ротации прокси
- **ProxyRotationMiddleware** - middleware для Scrapy, которое автоматически использует разные прокси для запросов

### Использование ротации прокси через API Gateway

При запуске задач через API Gateway можно выбрать режим работы с прокси:

#### Автоматическая ротация прокси

При использовании автоматической ротации не указывайте параметр `proxy` в JSON:

```bash
curl -X POST "http://localhost:5001/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "demo-1.0-py3.10",
    "spider": "quotes_spa",
    "_version": "1_0",
    "jobid": "custom_job_id",
    "settings": {
      "CLOSESPIDER_TIMEOUT": "60",
      "LOG_LEVEL": "INFO"
    },
    "user_agent_type": "desktop",
    "auth_enabled": false,
    "username": "admin",
    "password": "admin"
  }'
```

#### Использование фиксированного прокси

Для использования конкретного прокси, добавьте поле `proxy` в JSON:

```bash
curl -X POST "http://localhost:5001/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "demo-1.0-py3.10",
    "spider": "quotes_spa",
    "_version": "1_0",
    "jobid": "custom_job_id",
    "settings": {
      "CLOSESPIDER_TIMEOUT": "60",
      "LOG_LEVEL": "INFO"
    },
    "user_agent_type": "desktop",
    "auth_enabled": false,
    "username": "admin",
    "password": "admin",
    "proxy": "http://tinyproxy1:8888"
  }'
```

#### Использование указанного User-Agent

Для использования конкретного User-Agent вместо ротации, добавьте поле `user_agent` в JSON:

```bash
curl -X POST "http://localhost:5001/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "demo-1.0-py3.10",
    "spider": "quotes_spa",
    "_version": "1_0",
    "jobid": "custom_job_id",
    "settings": {
      "CLOSESPIDER_TIMEOUT": "60",
      "LOG_LEVEL": "INFO"
    },
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "auth_enabled": false,
    "username": "admin",
    "password": "admin"
  }'
```

#### Использование указанного User-Agent и Proxy

```bash
curl -X POST "http://localhost:5001/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "demo-1.0-py3.10",
    "spider": "quotes_spa",
    "_version": "1_0",
    "jobid": "custom_job_id_1",
    "settings": {
      "CLOSESPIDER_TIMEOUT": "60",
      "LOG_LEVEL": "INFO"
    },
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "auth_enabled": false,
    "username": "admin",
    "password": "admin",
    "proxy": "http://tinyproxy2:8888"
  }'
```

### Тестирование ротации прокси с помощью test_balancer.sh

Скрипт `test_balancer.sh` предназначен для тестирования балансировки нагрузки и ротации прокси. Он запускает заданное количество экземпляров паука `quotes_spa` из проекта `demo-1.0-py3.10` через API Gateway и отображает в реальном времени статус их выполнения на разных Scrapyd-узлах. Этот инструмент позволяет наглядно увидеть, как распределяются задачи между узлами и как работает ротация прокси-серверов.

#### С автоматической ротацией прокси:

```bash
./test_balancer.sh --count=3 --use-proxy-rotation
```

#### С фиксированным прокси:

```bash
./test_balancer.sh --count=3 --proxy=http://tinyproxy1:8888 --no-proxy-rotation
```

Также можно указать количество задач и тип User-Agent:
```bash
./test_balancer.sh --count=5 --use-proxy-rotation --user-agent-type=mobile
```

Или задать конкретный User-Agent:
```bash
./test_balancer.sh --count=3 --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
```

User-Agent + Proxy
```bash
./test_balancer.sh --count=3 --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" --proxy=http://tinyproxy1:8888
```

### Использование ротации прокси через RabbitMQ

При запуске задач через RabbitMQ с использованием утилиты `publish_rabbitmq_task.py` также доступны оба режима работы с прокси:

#### С автоматической ротацией прокси:

```bash
# Активация виртуального окружения
source .venv/bin/activate

# Запуск с автоматической ротацией прокси
python publish_rabbitmq_task.py \
  --count=3 \
  --use-proxy-rotation \
  --host localhost \
  --port 5672 \
  --project demo-1.0-py3.10 \
  --spider quotes_spa \
  --setting "CLOSESPIDER_TIMEOUT=120"
```

#### С фиксированным прокси:

```bash
# Запуск с фиксированным прокси
python publish_rabbitmq_task.py \
  --count=3 \
  --proxy=http://tinyproxy1:8888 \
  --no-proxy-rotation \
  --host localhost \
  --port 5672 \
  --project demo-1.0-py3.10 \
  --spider quotes_spa
```

#### С пользовательским User-Agent:

```bash
# Запуск с пользовательским User-Agent
python publish_rabbitmq_task.py \
  --count=3 \
  --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" \
  --host localhost \
  --port 5672 \
  --project demo-1.0-py3.10 \
  --spider quotes_spa
```

### Мониторинг использования прокси

Информация об используемом прокси записывается в логи и сохраняется вместе с данными в PostgreSQL и S3-хранилище. В логах вы увидите сообщения с префиксом emoji:

- 🔄 - Информация о запросах с использованием прокси
- 🌐 - Информация о запросах Selenium с использованием прокси
- 📊 - Информация о сохранении элементов с использованием прокси

Файлы с данными в S3-хранилище также содержат информацию об используемом прокси, что позволяет отслеживать, через какой прокси был получен конкретный результат.

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

## Управление ресурсами Selenium

Система включает улучшенное управление ресурсами Selenium для стабильной работы с SPA-сайтами даже при высокой нагрузке:

### Ключевые особенности

- **Redis-семафоры**: ограничение одновременных подключений к Selenium Hub
- **Система очередей**: справедливое распределение Selenium-сессий между пауками
- **Отслеживание ресурсов**: мониторинг использования Selenium-сессий в реальном времени
- **Отказоустойчивость**: автоматические повторные попытки подключения с экспоненциальной задержкой

### Сброс сессий и счетчиков

API Gateway предоставляет эндпоинт для сброса счетчика сессий в случае необходимости:

```bash
# Сброс счетчика сессий Selenium
curl -X POST http://localhost:5001/api/selenium/reset-sessions
```

### Конфигурация SeleniumMiddleware

Middleware поддерживает расширенную конфигурацию через настройки Scrapy:

```python
# settings.py
SELENIUM_DRIVER_ARGUMENTS = ['--headless', '--no-sandbox', '--disable-dev-shm-usage']
SELENIUM_MAX_RETRY_COUNT = 5  # Количество попыток подключения
SELENIUM_RETRY_BASE_DELAY = 1.0  # Базовая задержка (секунды)
SELENIUM_MAX_JITTER = 0.5  # Максимальный случайный сдвиг (секунды)
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

## Улучшенный мониторинг

### Расширенный мониторинг задач

Скрипт `test_balancer.sh` теперь предоставляет расширенный мониторинг, включая:

- Отображение статуса Selenium-ресурсов
- Подробная информация о статусе заданий
- Подсветка ошибок и таймаутов
- Режим отладки для диагностики проблем

Для запуска мониторинга с расширенной информацией:

```bash
# Базовый мониторинг
./test_balancer.sh --count=3

# С отладочной информацией
./test_balancer.sh --count=3 --debug
```

## Мониторинг и логирование

В проект интегрирована комплексная система мониторинга и логирования на базе популярных инструментов с открытым исходным кодом.

### Система логирования (ELK Stack)

Для централизованного сбора, хранения и анализа логов используется ELK Stack:

1. **Filebeat** - собирает логи из всех Docker-контейнеров
2. **Elasticsearch** - хранит и индексирует собранные логи
3. **Kibana** - предоставляет веб-интерфейс для поиска и визуализации логов

#### Доступ к логам через Kibana:

1. Откройте [Kibana](http://localhost:5601)
2. При первом входе необходимо настроить индекс:
   - Перейдите в Management > Stack Management > Index Patterns
   - Создайте индекс с шаблоном `filebeat-*`
   - Выберите `@timestamp` в качестве поля времени
3. Для просмотра логов перейдите в Analytics > Discover
4. Используйте фильтры для поиска логов конкретного сервиса или паука:
   - `container.name: scrapyd1` - логи первого инстанса Scrapyd
   - `spider_name: example` - логи конкретного паука

### Система мониторинга метрик

Для сбора и визуализации метрик используется связка инструментов:

1. **Prometheus** - сбор и хранение метрик
2. **Grafana** - визуализация метрик в виде интерактивных дашбордов
3. **cAdvisor** - сбор метрик контейнеров (CPU, память, сеть)
4. **Node Exporter** - сбор метрик хоста

#### Доступ к метрикам через Grafana:

1. Откройте [Grafana](http://localhost:3000)
2. Войдите с учетными данными (по умолчанию admin/admin)
3. Перейдите в раздел Dashboards
4. Выберите дашборд "Scrapy Container Metrics" для просмотра метрик использования ресурсов контейнерами

### Система оповещений

Система оповещений на базе Alertmanager и Telegram Bot позволяет получать уведомления о важных событиях:

1. Проблемы с контейнерами (перезапуски, остановки)
2. Высокое использование ресурсов
3. Недоступность сервисов

#### Настройка оповещений:

Настройки оповещений хранятся в файлах:
- `alertmanager.yml` - конфигурация Alertmanager
- `prometheus_rules.yml` - правила генерации оповещений

### Перезапуск сервисов мониторинга

Для перезапуска всех сервисов мониторинга используйте скрипт:

```bash
./restart_monitoring.sh
```

### Интеграция логирования в паукax

В паукax можно использовать расширенное логирование с дополнительными полями для лучшей фильтрации в Kibana:

```python
self.logger.info(f"Parsing {response.url}", 
                 extra={
                     'url': response.url,
                     'status': response.status,
                     'spider_name': self.name,
                     'job_id': self.settings.get('JOB')
                 })
```

## Интеграция с очередями сообщений (RabbitMQ)

Система поддерживает асинхронное планирование задач через RabbitMQ. Это позволяет внешним системам отправлять задачи на парсинг без необходимости прямого обращения к Scrapyd или API Gateway.


### Запуск нескольких пауков через RabbitMQ с балансировкой нагрузки

С утилитой `publish_rabbitmq_task.py` можно запускать несколько пауков одновременно и задавать тип User-Agent:

```bash
# Активация виртуального окружения
source .venv/bin/activate

# Запуск 3 пауков с десктопным User-Agent
python publish_rabbitmq_task.py \
  --count=3 \
  --user-agent-type=desktop \
  --host localhost \
  --port 5672 \
  --project demo-1.0-py3.10 \
  --spider quotes_spa \
  --setting "CLOSESPIDER_TIMEOUT=120" \
  --setting "LOG_LEVEL=INFO"
```

Параметры:
- `--count` - количество пауков для запуска (по умолчанию 1)
- `--user-agent-type` - тип User-Agent (desktop, mobile, tablet) (по умолчанию desktop)

Задания будут автоматически сбалансированы между доступными Scrapyd-инстансами:
1. Сервис task-processor получает задания из RabbitMQ
2. API Gateway распределяет задания между scrapyd1 и scrapyd2, выбирая наименее загруженный инстанс
3. Пауки на разных инстансах выполняются параллельно, а в рамках одного инстанса - последовательно


### Мониторинг заданий

Вы можете мониторить очередь заданий через [RabbitMQ Management Console](http://localhost:15672) (логин: guest/guest), а сами задания отслеживать через стандартный интерфейс [ScrapydWeb](http://localhost:5000).

## Текущее состояние PoC

Сейчас реализовано:
- Запуск пауков на нескольких экземплярах Scrapyd
- Использование Selenium для работы с SPA-сайтами
- Поддержка работы через прокси
- Сохранение данных в PostgreSQL и S3-хранилище
- Мониторинг работы пауков через ScrapydWeb
- Интеллектуальная балансировка нагрузки через API Gateway
- Асинхронное планирование задач через RabbitMQ
- Всесторонний мониторинг и логирование через ELK и Prometheus/Grafana
- Система оповещений через Telegram
- Управление ресурсами Selenium с использованием Redis для предотвращения конфликтов
- Экспоненциальная задержка и повторные попытки для повышения стабильности
- Расширенный мониторинг состояния ресурсов и задач
- Автоматическая ротация прокси-серверов

Подробнее о текущем состоянии и планах развития смотрите в файле TODO.md.

## Тестирование ротации User-Agent

Система поддерживает автоматическую ротацию User-Agent для лучшей имитации поведения реальных пользователей. Для тестирования этой функциональности используйте скрипт `test_user_agent.py`.

### Использование скрипта test_user_agent.py

Скрипт позволяет получать случайные User-Agent от сервиса ротации с возможностью фильтрации по типу устройства и браузеру:

```bash
# Запрос 10 случайных User-Agent
python3 test_user_agent.py --count=10

# Запрос только мобильных User-Agent
python3 test_user_agent.py --type=mobile --count=5

# Запрос только User-Agent для браузера Chrome
python3 test_user_agent.py --browser=chrome --count=5

# Комбинирование фильтров
python3 test_user_agent.py --type=desktop --browser=firefox --count=5
```

### Параметры скрипта

- `--url` - URL сервиса ротации User-Agent (по умолчанию http://localhost:5002)
- `--count` - количество User-Agent для запроса (по умолчанию 10)
- `--delay` - задержка между запросами в секундах (по умолчанию 0.5)
- `--type` - тип устройства (desktop, mobile, tablet)
- `--browser` - семейство браузера (chrome, firefox, safari, edge)

### Пример вывода

```
Testing User-Agent rotation service at http://localhost:5002
Requesting 3 User-Agents
Device type: mobile

Requesting User-Agents:
--------------------------------------------------------------------------------
1. [mobile] [chrome]: Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36
2. [mobile] [firefox]: Mozilla/5.0 (Android 12; Mobile; rv:98.0) Gecko/98.0 Firefox/98.0
3. [mobile] [safari]: Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1

User-Agent Service Statistics:
--------------------------------------------------------------------------------
{
  "total_requests": 128,
  "by_type": {
    "desktop": 76,
    "mobile": 42,
    "tablet": 10
  },
  "by_browser": {
    "chrome": 63,
    "firefox": 32,
    "safari": 21,
    "edge": 12
  }
}
```

Этот скрипт полезен для:
- Проверки работы сервиса ротации User-Agent
- Тестирования поведения сайтов с разными User-Agent
- Просмотра статистики использования различных типов User-Agent
