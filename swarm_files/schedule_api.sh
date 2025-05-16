#!/bin/bash

# Скрипт для запуска задач через API Gateway
# Совместим с форматом параметров из schedule_egg.sh

# Определяем URL API Gateway
API_URL="http://localhost:5001"

# Разбираем аргументы
PROJECT=""
SPIDER=""
VERSION=""
JOBID=""
SETTINGS=()
ARGS=()
AUTH_ENABLED=""
USERNAME=""
PASSWORD=""
PROXY=""

# Если нет аргументов, показываем справку
if [ $# -eq 0 ]; then
    echo "Использование: $0 [параметры]"
    echo "Параметры:"
    echo "  -d project=PROJECT         Имя проекта"
    echo "  -d _version=VERSION        Версия проекта"
    echo "  -d spider=SPIDER           Имя паука"
    echo "  -d jobid=JOBID             ID задания"
    echo "  -d setting=KEY=VALUE       Настройка (можно использовать несколько раз)"
    echo "  -d auth_enabled=true       Включить аутентификацию"
    echo "  -d username=USERNAME       Имя пользователя"
    echo "  -d password=PASSWORD       Пароль"
    echo "  -d proxy=PROXY_URL         Прокси"
    echo "  -d KEY=VALUE               Дополнительный параметр (можно использовать несколько раз)"
    echo "  --api-url=URL              URL API Gateway (по умолчанию: $API_URL)"
    exit 1
fi

# Обработка аргументов
while [ $# -gt 0 ]; do
    case "$1" in
        -d)
            shift
            param=$1
            key=${param%%=*}
            value=${param#*=}
            
            case "$key" in
                project)
                    PROJECT=$value
                    ;;
                _version)
                    VERSION=$value
                    ;;
                spider)
                    SPIDER=$value
                    ;;
                jobid)
                    JOBID=$value
                    ;;
                setting)
                    SETTINGS+=("$value")
                    ;;
                auth_enabled)
                    if [ "$value" = "true" ]; then
                        AUTH_ENABLED="--auth-enabled"
                    fi
                    ;;
                username)
                    USERNAME=$value
                    ;;
                password)
                    PASSWORD=$value
                    ;;
                proxy)
                    PROXY=$value
                    ;;
                *)
                    ARGS+=("$key=$value")
                    ;;
            esac
            ;;
        --api-url=*)
            API_URL=${1#*=}
            ;;
        *)
            echo "Неизвестный параметр: $1"
            exit 1
            ;;
    esac
    shift
done

# Проверяем обязательные параметры
if [ -z "$PROJECT" ]; then
    echo "Ошибка: обязательный параметр project не указан"
    exit 1
fi

if [ -z "$SPIDER" ]; then
    echo "Ошибка: обязательный параметр spider не указан"
    exit 1
fi

# Формируем команду
CMD="python3 api-gateway/client_example.py --endpoint $API_URL schedule --project $PROJECT --spider $SPIDER"

if [ -n "$VERSION" ]; then
    CMD="$CMD --version $VERSION"
fi

if [ -n "$JOBID" ]; then
    CMD="$CMD --jobid $JOBID"
fi

if [ -n "$AUTH_ENABLED" ]; then
    CMD="$CMD $AUTH_ENABLED"
fi

if [ -n "$USERNAME" ]; then
    CMD="$CMD --username $USERNAME"
fi

if [ -n "$PASSWORD" ]; then
    CMD="$CMD --password $PASSWORD"
fi

if [ -n "$PROXY" ]; then
    CMD="$CMD --proxy $PROXY"
fi

# Добавляем настройки
for setting in "${SETTINGS[@]}"; do
    CMD="$CMD --setting $setting"
done

# Добавляем дополнительные аргументы
for arg in "${ARGS[@]}"; do
    CMD="$CMD --arg $arg"
done

# Выполняем команду
echo "Выполнение: $CMD"
eval $CMD 