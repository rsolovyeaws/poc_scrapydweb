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

## Текущее состояние PoC

Сейчас реализовано:
- Запуск пауков на нескольких экземплярах Scrapyd
- Использование Selenium для работы с SPA-сайтами
- Поддержка работы через прокси
- Сохранение данных в PostgreSQL и S3-хранилище
- Мониторинг работы пауков через ScrapydWeb

Подробнее о текущем состоянии и планах развития смотрите в файле TODO.md.
