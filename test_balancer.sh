#!/bin/bash

# Скрипт для демонстрации балансировки нагрузки
# Запускает несколько задач и мониторит их статус

# Конфигурация
API_URL="http://localhost:5001"
PROJECT="demo-1.0-py3.10"
SPIDER="quotes_spa"
VERSION="1_0"
JOB_COUNT=2  # Количество задач для запуска (по умолчанию 2)

# Проверить, установлена ли утилита jq
if ! command -v jq &> /dev/null; then
    echo "Требуется утилита jq. Установите ее с помощью 'apt-get install jq' или 'brew install jq'"
    exit 1
fi

# Проверить, установлена ли утилита watch
if ! command -v watch &> /dev/null; then
    echo "Требуется утилита watch. Установите ее с помощью 'apt-get install procps'"
    exit 1
fi

# Обработка аргументов
while [ $# -gt 0 ]; do
    case "$1" in
        --count=*)
            JOB_COUNT=${1#*=}
            ;;
        --api-url=*)
            API_URL=${1#*=}
            ;;
        --project=*)
            PROJECT=${1#*=}
            ;;
        --spider=*)
            SPIDER=${1#*=}
            ;;
        --version=*)
            VERSION=${1#*=}
            ;;
        --help|-h)
            echo "Использование: $0 [параметры]"
            echo "Параметры:"
            echo "  --count=N       Количество задач для запуска (по умолчанию: 2)"
            echo "  --api-url=URL   URL API Gateway (по умолчанию: $API_URL)"
            echo "  --project=NAME  Имя проекта (по умолчанию: $PROJECT)"
            echo "  --spider=NAME   Имя паука (по умолчанию: $SPIDER)"
            echo "  --version=VER   Версия проекта (по умолчанию: $VERSION)"
            echo "  --help, -h      Показать эту справку"
            exit 0
            ;;
        *)
            echo "Неизвестный параметр: $1. Используйте --help для получения справки."
            exit 1
            ;;
    esac
    shift
done

echo "=== ТЕСТ БАЛАНСИРОВКИ НАГРУЗКИ ==="
echo "API Gateway: $API_URL"
echo "Запуск $JOB_COUNT задач для проекта $PROJECT, паук $SPIDER"
echo ""

# Проверяем доступность API Gateway
status_code=$(curl -s -o /dev/null -w "%{http_code}" ${API_URL})
if [ $status_code -ne 200 ]; then
    echo "❌ API Gateway недоступен (статус: $status_code)"
    echo "Запустите Docker Compose: docker-compose up -d"
    exit 1
fi

# Проверяем статус Scrapyd-инстансов
echo "Проверка статуса Scrapyd-инстансов..."
status=$(curl -s ${API_URL}/status)
online_nodes=$(echo $status | jq '[to_entries[] | select(.value.status == "online")] | length')

if [ "$online_nodes" -eq 0 ]; then
    echo "❌ Нет доступных Scrapyd-инстансов"
    exit 1
fi

echo "✅ Доступно $online_nodes Scrapyd-инстансов"
echo ""

# Запускаем задачи
echo "Запуск $JOB_COUNT задач..."
job_ids=()

for i in $(seq 1 $JOB_COUNT); do
    jobid=$(date +%Y-%m-%dT%H_%M_%S)_$i
    
    echo "Запуск задачи $i (jobid: $jobid)..."
    
    response=$(curl -s -X POST "$API_URL/schedule" \
        -H "Content-Type: application/json" \
        -d '{
          "project": "'"$PROJECT"'",
          "spider": "'"$SPIDER"'",
          "_version": "'"$VERSION"'",
          "jobid": "'"$jobid"'",
          "settings": {
            "CLOSESPIDER_TIMEOUT": "120",
            "LOG_LEVEL": "INFO"
          },
          "auth_enabled": false
        }')
    
    status=$(echo $response | jq -r '.status')
    node=$(echo $response | jq -r '.node')
    
    if [ "$status" == "success" ]; then
        echo "✅ Задача $i запущена на узле $node (jobid: $jobid)"
        job_ids+=($jobid)
    else
        msg=$(echo $response | jq -r '.message')
        echo "❌ Ошибка запуска задачи $i: $msg"
    fi
done

echo ""
echo "Все задачи запущены! Мониторинг статуса..."
echo ""

# Функция для проверки статуса задач
check_status() {
    echo "=== ТЕСТ БАЛАНСИРОВКИ НАГРУЗКИ ==="
    echo "API Gateway: $API_URL"
    echo "Проект: $PROJECT, Паук: $SPIDER"
    echo "Запущено задач: $JOB_COUNT"
    echo ""
    
    echo "=== СТАТУС SCRAPYD-ИНСТАНСОВ ==="
    curl -s ${API_URL}/status | jq -r '
        to_entries[] | 
        if .value.status == "online" then
            "✓ \(.key): \(.value.running) задач выполняется, \(.value.pending) в очереди"
        else 
            "✗ \(.key): \(.value.status)"
        end
    '
    
    echo ""
    echo "=== СТАТУС ЗАДАЧ ==="
    jobs_json=$(curl -s "${API_URL}/list-jobs/${PROJECT}")
    
    for node in $(echo $jobs_json | jq -r 'keys[]'); do
        echo "Узел: $node"
        
        # Проверяем задачи в очереди
        pending=$(echo $jobs_json | jq -r --arg node "$node" '.[$node].pending // [] | length')
        if [ $pending -gt 0 ]; then
            echo "  В очереди: $pending"
            echo $jobs_json | jq -r --arg node "$node" '.[$node].pending // [] | .[] | "    - \(.id) (\(.spider))"'
        fi
        
        # Проверяем выполняющиеся задачи
        running=$(echo $jobs_json | jq -r --arg node "$node" '.[$node].running // [] | length')
        if [ $running -gt 0 ]; then
            echo "  Выполняется: $running"
            echo $jobs_json | jq -r --arg node "$node" '.[$node].running // [] | .[] | "    - \(.id) (\(.spider)) - запущена \(.start_time)"'
        fi
        
        # Проверяем завершенные задачи
        finished=$(echo $jobs_json | jq -r --arg node "$node" '.[$node].finished // [] | length')
        if [ $finished -gt 0 ]; then
            echo "  Завершено: $finished (последние 3)"
            echo $jobs_json | jq -r --arg node "$node" '.[$node].finished // [] | sort_by(.end_time) | reverse | .[0:3] | .[] | "    - \(.id) (\(.spider)) - завершена \(.end_time)"'
        fi
        
        echo ""
    done
}

# Запускаем мониторинг однократно
check_status

echo ""
echo "Запуск непрерывного мониторинга (нажмите Ctrl+C для выхода)..."
echo ""

# Создаем временный скрипт для watch, чтобы избежать проблем с 'source'
TEMP_SCRIPT=$(mktemp)
cat > "$TEMP_SCRIPT" << EOF
#!/bin/bash
API_URL="$API_URL"
PROJECT="$PROJECT"
JOB_COUNT="$JOB_COUNT"
SPIDER="$SPIDER"

# Функция для проверки статуса задач
check_status() {
    echo "=== ТЕСТ БАЛАНСИРОВКИ НАГРУЗКИ ==="
    echo "API Gateway: \$API_URL"
    echo "Проект: \$PROJECT, Паук: \$SPIDER"
    echo "Запущено задач: \$JOB_COUNT"
    echo ""
    
    echo "=== СТАТУС SCRAPYD-ИНСТАНСОВ ==="
    curl -s \${API_URL}/status | jq -r '
        to_entries[] | 
        if .value.status == "online" then
            "✓ \(.key): \(.value.running) задач выполняется, \(.value.pending) в очереди"
        else 
            "✗ \(.key): \(.value.status)"
        end
    '
    
    echo ""
    echo "=== СТАТУС ЗАДАЧ ==="
    jobs_json=\$(curl -s "\${API_URL}/list-jobs/\${PROJECT}")
    
    for node in \$(echo \$jobs_json | jq -r 'keys[]'); do
        echo "Узел: \$node"
        
        # Проверяем задачи в очереди
        pending=\$(echo \$jobs_json | jq -r --arg node "\$node" '.[\$node].pending // [] | length')
        if [ \$pending -gt 0 ]; then
            echo "  В очереди: \$pending"
            echo \$jobs_json | jq -r --arg node "\$node" '.[\$node].pending // [] | .[] | "    - \(.id) (\(.spider))"'
        fi
        
        # Проверяем выполняющиеся задачи
        running=\$(echo \$jobs_json | jq -r --arg node "\$node" '.[\$node].running // [] | length')
        if [ \$running -gt 0 ]; then
            echo "  Выполняется: \$running"
            echo \$jobs_json | jq -r --arg node "\$node" '.[\$node].running // [] | .[] | "    - \(.id) (\(.spider)) - запущена \(.start_time)"'
        fi
        
        # Проверяем завершенные задачи
        finished=\$(echo \$jobs_json | jq -r --arg node "\$node" '.[\$node].finished // [] | length')
        if [ \$finished -gt 0 ]; then
            echo "  Завершено: \$finished (последние 3)"
            echo \$jobs_json | jq -r --arg node "\$node" '.[\$node].finished // [] | sort_by(.end_time) | reverse | .[0:3] | .[] | "    - \(.id) (\(.spider)) - завершена \(.end_time)"'
        fi
        
        echo ""
    done
}

check_status
EOF

chmod +x "$TEMP_SCRIPT"

# Запуск watch с временным скриптом
watch -n 2 -c "$TEMP_SCRIPT"

# Удаляем временный скрипт
rm "$TEMP_SCRIPT"

# Выходим из скрипта - это важно, чтобы скрипт не продолжался после watch
exit 0 