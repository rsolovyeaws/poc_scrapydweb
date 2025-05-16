#!/bin/bash

# Скрипт для демонстрации балансировки нагрузки
# Запускает несколько задач и мониторит их статус

# Конфигурация
API_URL="http://localhost:5001"
PROJECT="demo-1.0-py3.10"
SPIDER="quotes_spa"
VERSION="1_0"
JOB_COUNT=3  # Количество задач для запуска (по умолчанию 3)
USER_AGENT_TYPE="desktop"  # Тип User-Agent (по умолчанию desktop)
USER_AGENT=""  # Пользовательский User-Agent
DEFAULT_PROXY="http://tinyproxy1:8888"  # Default proxy to use
USE_PROXY_ROTATION=true  # Use proxy rotation instead of a fixed proxy
DEBUG_MODE=false  # Режим отладки (сохраняет ответы API в файлы)

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
        --user-agent-type=*)
            USER_AGENT_TYPE=${1#*=}
            ;;
        --user-agent=*)
            USER_AGENT=${1#*=}
            ;;
        --proxy=*)
            DEFAULT_PROXY=${1#*=}
            USE_PROXY_ROTATION=false
            ;;
        --use-proxy-rotation)
            USE_PROXY_ROTATION=true
            ;;
        --no-proxy-rotation)
            USE_PROXY_ROTATION=false
            ;;
        --debug)
            DEBUG_MODE=true
            ;;
        --help|-h)
            echo "Использование: $0 [параметры]"
            echo "Параметры:"
            echo "  --count=N       Количество задач для запуска (по умолчанию: 3)"
            echo "  --api-url=URL   URL API Gateway (по умолчанию: $API_URL)"
            echo "  --project=NAME  Имя проекта (по умолчанию: $PROJECT)"
            echo "  --spider=NAME   Имя паука (по умолчанию: $SPIDER)"
            echo "  --version=VER   Версия проекта (по умолчанию: $VERSION)"
            echo "  --user-agent-type=TYPE Тип User-Agent (desktop, mobile, tablet) (по умолчанию: $USER_AGENT_TYPE)"
            echo "  --user-agent=STRING    Пользовательский User-Agent (переопределяет user-agent-type)"
            echo "  --proxy=URL     Прокси-сервер (отключает ротацию, по умолчанию: $DEFAULT_PROXY)"
            echo "  --use-proxy-rotation  Использовать ротацию прокси (по умолчанию)"
            echo "  --no-proxy-rotation   Не использовать ротацию прокси"
            echo "  --debug         Включить режим отладки (сохраняет ответы API в файлы)"
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
if [ -n "$USER_AGENT" ]; then
    echo "Пользовательский User-Agent: $USER_AGENT"
else
    echo "Тип User-Agent: $USER_AGENT_TYPE"
fi
if [ "$USE_PROXY_ROTATION" = true ]; then
    echo "Прокси-сервер: Автоматическая ротация"
else
    echo "Прокси-сервер: $DEFAULT_PROXY (фиксированный)"
fi
echo ""

# Проверяем доступность API Gateway
status_code=$(curl -s -o /dev/null -w "%{http_code}" ${API_URL})
if [ $status_code -ne 200 ]; then
    echo "❌ API Gateway недоступен (статус: $status_code)"
    echo "Запустите Docker Compose: docker-compose up -d"
    exit 1
fi

# Reset Selenium counter to ensure we start fresh
echo "Сбрасываем счетчик сессий Selenium..."
reset_response=$(curl -s ${API_URL}/selenium/reset)
reset_status=$(echo $reset_response | jq -r '.status')
if [ "$reset_status" == "success" ]; then
    echo "✅ Счетчик сессий Selenium сброшен"
else
    echo "⚠️ Не удалось сбросить счетчик Selenium, но продолжаем..."
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
    
    # Build the appropriate JSON payload based on proxy rotation setting
    if [ "$USE_PROXY_ROTATION" = true ]; then
        # With proxy rotation
        if [ -n "$USER_AGENT" ]; then
            # With custom user agent
            json_payload='{
              "project": "'"$PROJECT"'",
              "spider": "'"$SPIDER"'",
              "_version": "'"$VERSION"'",
              "jobid": "'"$jobid"'",
              "settings": {
                "CLOSESPIDER_TIMEOUT": "360",
                "LOG_LEVEL": "INFO"
              },
              "user_agent": "'"$USER_AGENT"'",
              "auth_enabled": "true",
              "username": "admin",
              "password": "admin"
            }'
        else
            # With user agent type
            json_payload='{
              "project": "'"$PROJECT"'",
              "spider": "'"$SPIDER"'",
              "_version": "'"$VERSION"'",
              "jobid": "'"$jobid"'",
              "settings": {
                "CLOSESPIDER_TIMEOUT": "360",
                "LOG_LEVEL": "INFO"
              },
              "user_agent_type": "'"$USER_AGENT_TYPE"'",
              "auth_enabled": "true",
              "username": "admin",
              "password": "admin"
            }'
        fi
    else
        # With fixed proxy
        if [ -n "$USER_AGENT" ]; then
            # With custom user agent
            json_payload='{
              "project": "'"$PROJECT"'",
              "spider": "'"$SPIDER"'",
              "_version": "'"$VERSION"'",
              "jobid": "'"$jobid"'",
              "settings": {
                "CLOSESPIDER_TIMEOUT": "360",
                "LOG_LEVEL": "INFO"
              },
              "user_agent": "'"$USER_AGENT"'",
              "auth_enabled": "false",
              "username": "admin",
              "password": "admin",
              "proxy": "'"$DEFAULT_PROXY"'"
            }'
        else
            # With user agent type
            json_payload='{
              "project": "'"$PROJECT"'",
              "spider": "'"$SPIDER"'",
              "_version": "'"$VERSION"'",
              "jobid": "'"$jobid"'",
              "settings": {
                "CLOSESPIDER_TIMEOUT": "360",
                "LOG_LEVEL": "INFO"
              },
              "user_agent_type": "'"$USER_AGENT_TYPE"'",
              "auth_enabled": "false",
              "username": "admin",
              "password": "admin",
              "proxy": "'"$DEFAULT_PROXY"'"
            }'
        fi
    fi
    
    response=$(curl -s -X POST "$API_URL/schedule" \
        -H "Content-Type: application/json" \
        -d "$json_payload")
    
    status=$(echo $response | jq -r '.status')
    node=$(echo $response | jq -r '.node')
    
    if [ "$status" == "success" ]; then
        echo "✅ Задача $i запущена на узле $node (jobid: $jobid)"
        job_ids+=($jobid)
    else
        msg=$(echo $response | jq -r '.message')
        echo "❌ Ошибка запуска задачи $i: $msg"
    fi
    
    # No delays between job launches
    if [ $i -lt $JOB_COUNT ]; then
        echo "⏱️ Запуск следующей задачи..."
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
    echo "Тип User-Agent: $USER_AGENT_TYPE"
    if [ "$USE_PROXY_ROTATION" = true ]; then
        echo "Прокси-сервер: Автоматическая ротация"
    else
        echo "Прокси-сервер: $DEFAULT_PROXY (фиксированный)"
    fi
    echo ""
    
    # Получаем полный статус API Gateway
    status_response=$(curl -s ${API_URL}/status)
    
    echo "=== СТАТУС SCRAPYD-ИНСТАНСОВ ==="
    echo "$status_response" | jq -r '
        .scrapyd | to_entries[] | 
        if .value.status == "online" then
            "✓ \(.key): \(.value.running) задач выполняется, \(.value.pending) в очереди"
        else 
            "✗ \(.key): \(.value.status)"
        end
    '
    
    # Вывод информации о статусе Selenium
    echo ""
    echo "=== СТАТУС SELENIUM ==="
    echo "$status_response" | jq -r '
        .selenium | 
        if .status == "online" then
            "✓ Sessions: \(.active_sessions)/\(.max_sessions) active, \(.queued_jobs) в очереди"
        else
            "✗ \(.message // "offline")"
        end
    '
    
    echo ""
    echo "=== СТАТУС ЗАДАЧ ==="
    
    # Добавим вывод текущей даты/времени для отслеживания активности
    echo "Время запроса: $(date '+%Y-%m-%d %H:%M:%S')"
    
    # Получаем и сохраняем ответ API в переменную
    jobs_response=$(curl -s "${API_URL}/list-jobs/${PROJECT}")
    
    # В режиме отладки сохраняем ответ в файл
    if [ "$DEBUG_MODE" = true ]; then
        debug_file="debug_jobs_$(date +%Y%m%d_%H%M%S).json"
        echo "$jobs_response" > "$debug_file"
        echo "📋 Ответ API сохранен в файл: $debug_file"
    fi
    
    # Вывод размера ответа для диагностики
    response_size=${#jobs_response}
    echo "Размер ответа: $response_size байт"
    
    # Проверка на пустой ответ
    if [ -z "$jobs_response" ]; then
        echo "❌ Получен пустой ответ от API"
        return
    fi
    
    # Проверка на ошибки в JSON
    if ! echo "$jobs_response" | jq empty 2>/dev/null; then
        echo "❌ Получен невалидный JSON:"
        echo "$jobs_response"
        return
    fi
    
    # Отладка: выводим структуру ответа
    echo "Структура ответа:"
    echo "$jobs_response" | jq 'keys'
    
    # Обрабатываем очередь Selenium, если она есть
    if echo "$jobs_response" | jq -e 'has("queued")' > /dev/null 2>&1; then
        queued_count=$(echo "$jobs_response" | jq '.queued | length')
        if [ "$queued_count" -gt 0 ]; then
            echo "Узел: API Gateway Queue"
            echo "  В очереди Selenium: $queued_count"
            echo "$jobs_response" | jq -r '.queued[] | "    - \(.id) (\(.spider)) - узел: \(.node)"'
            echo ""
        fi
    fi
    
    # Получаем список всех узлов, исключая "queued"
    nodes=$(echo "$jobs_response" | jq -r 'keys[] | select(. != "queued")')
    
    # Проверяем, есть ли узлы
    if [ -z "$nodes" ]; then
        echo "ℹ️ Нет активных Scrapyd-узлов или задач"
        return
    fi
    
    # Выводим список найденных узлов
    echo "Найдено узлов: $(echo "$nodes" | wc -l)"
    
    # Обрабатываем информацию по каждому узлу
    for node in $nodes; do
        echo "Узел: $node"
        
        # Получаем данные узла для упрощения работы
        node_data=$(echo "$jobs_response" | jq --arg node "$node" '.[$node]')
        
        # Отладка: показываем структуру данных узла
        echo "  Доступные ключи для узла:"
        echo "$node_data" | jq 'keys'
        
        # Проверка на пустые/null данные
        if [ "$(echo "$node_data" | jq 'length')" -eq 0 ] || [ "$(echo "$node_data" | jq 'length')" = "null" ]; then
            echo "  ℹ️ Нет данных"
            continue
        fi
        
        # Проверяем задачи в очереди
        pending_count=$(echo "$node_data" | jq '.pending | length // 0')
        if [ "$pending_count" != "null" ] && [ "$pending_count" -gt 0 ]; then
            echo "  В очереди: $pending_count"
            echo "$node_data" | jq -r '.pending[] | "    - \(.id) (\(.spider))"' 2>/dev/null || echo "    (ошибка отображения)"
        fi
        
        # Проверяем выполняющиеся задачи
        running_count=$(echo "$node_data" | jq '.running | length // 0')
        if [ "$running_count" != "null" ] && [ "$running_count" -gt 0 ]; then
            echo "  Выполняется: $running_count"
            echo "$node_data" | jq -r '.running[] | "    - \(.id) (\(.spider)) - запущена \(.start_time)"' 2>/dev/null || echo "    (ошибка отображения)"
        fi
        
        # Проверяем завершенные задачи
        finished_count=$(echo "$node_data" | jq '.finished | length // 0')
        if [ "$finished_count" != "null" ] && [ "$finished_count" -gt 0 ]; then
            echo "  Завершено: $finished_count (последние 3)"
            echo "$node_data" | jq -r '.finished | sort_by(.end_time) | reverse | .[0:3] | .[] | "    - \(.id) (\(.spider)) - завершена \(.end_time)"' 2>/dev/null || echo "    (ошибка отображения)"
        fi
        
        # Если ни одной задачи не найдено, выводим информацию
        if [ "$pending_count" = "0" ] && [ "$running_count" = "0" ] && [ "$finished_count" = "0" ]; then
            echo "  ℹ️ Нет активных или завершенных задач"
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
USER_AGENT_TYPE="$USER_AGENT_TYPE"
USER_AGENT="$USER_AGENT"
DEFAULT_PROXY="$DEFAULT_PROXY"
USE_PROXY_ROTATION="$USE_PROXY_ROTATION"
DEBUG_MODE="$DEBUG_MODE"

# Функция для проверки статуса задач
check_status() {
    echo "=== ТЕСТ БАЛАНСИРОВКИ НАГРУЗКИ ==="
    echo "API Gateway: \$API_URL"
    echo "Проект: \$PROJECT, Паук: \$SPIDER"
    echo "Запущено задач: \$JOB_COUNT"
    echo "Тип User-Agent: \$USER_AGENT_TYPE"
    if [ "\$USE_PROXY_ROTATION" = true ]; then
        echo "Прокси-сервер: Автоматическая ротация"
    else
        echo "Прокси-сервер: \$DEFAULT_PROXY (фиксированный)"
    fi
    echo ""
    
    # Получаем полный статус API Gateway
    status_response=\$(curl -s \${API_URL}/status)
    
    echo "=== СТАТУС SCRAPYD-ИНСТАНСОВ ==="
    echo \$status_response | jq -r '
        .scrapyd | to_entries[] | 
        if .value.status == "online" then
            "✓ \(.key): \(.value.running) задач выполняется, \(.value.pending) в очереди"
        else 
            "✗ \(.key): \(.value.status)"
        end
    '
    
    # Вывод информации о статусе Selenium
    echo ""
    echo "=== СТАТУС SELENIUM ==="
    echo \$status_response | jq -r '
        .selenium | 
        if .status == "online" then
            "✓ Sessions: \(.active_sessions)/\(.max_sessions) active, \(.queued_jobs) в очереди"
        else
            "✗ \(.message // "offline")"
        end
    '
    
    echo ""
    echo "=== СТАТУС ЗАДАЧ ==="
    jobs_response=\$(curl -s "\${API_URL}/list-jobs/\${PROJECT}")
    
    # В режиме отладки сохраняем ответ в файл
    if [ "\$DEBUG_MODE" = true ]; then
        debug_file="debug_jobs_\$(date +%Y%m%d_%H%M%S).json"
        echo "\$jobs_response" > "\$debug_file"
        echo "📋 Ответ API сохранен в файл: \$debug_file"
    fi
    
    # Проверка на пустой ответ
    if [ -z "\$jobs_response" ]; then
        echo "❌ Получен пустой ответ от API"
        return
    fi
    
    # Проверка на ошибки в JSON
    if ! echo "\$jobs_response" | jq empty 2>/dev/null; then
        echo "❌ Получен невалидный JSON:"
        echo "\$jobs_response"
        return
    fi
    
    # Обрабатываем очередь Selenium, если она есть
    if echo "\$jobs_response" | jq -e 'has("queued")' > /dev/null 2>&1; then
        queued_count=\$(echo "\$jobs_response" | jq '.queued | length')
        if [ \$queued_count -gt 0 ]; then
            echo "Узел: API Gateway Queue"
            echo "  В очереди Selenium: \$queued_count"
            echo "\$jobs_response" | jq -r '.queued[] | "    - \(.id) (\(.spider)) - узел: \(.node)"'
            echo ""
        fi
    fi
    
    # Получаем список всех узлов, исключая "queued"
    nodes=\$(echo "\$jobs_response" | jq -r 'keys[] | select(. != "queued")')
    
    # Проверяем, есть ли узлы
    if [ -z "\$nodes" ]; then
        echo "ℹ️ Нет активных Scrapyd-узлов или задач"
        return
    fi
    
    # Выводим список найденных узлов
    echo "Найдено узлов: \$(echo \$nodes | wc -l)"
    
    # Обрабатываем информацию по каждому узлу
    for node in \$nodes; do
        echo "Узел: \$node"
        
        # Получаем данные узла для упрощения работы
        node_data=\$(echo "\$jobs_response" | jq --arg node "\$node" '.[\$node]')
        
        # Проверка на пустые/null данные
        if [ "\$(echo "\$node_data" | jq 'length')" -eq 0 ] || [ "\$(echo "\$node_data" | jq 'length')" = "null" ]; then
            echo "  ℹ️ Нет данных"
            continue
        fi
        
        # Проверяем задачи в очереди
        pending_count=\$(echo "\$node_data" | jq '.pending | length // 0')
        if [ \$pending_count != "null" ] && [ \$pending_count -gt 0 ]; then
            echo "  В очереди: \$pending_count"
            echo "\$node_data" | jq -r '.pending[] | "    - \(.id) (\(.spider))"' 2>/dev/null || echo "    (ошибка отображения)"
        fi
        
        # Проверяем выполняющиеся задачи
        running_count=\$(echo "\$node_data" | jq '.running | length // 0')
        if [ \$running_count != "null" ] && [ \$running_count -gt 0 ]; then
            echo "  Выполняется: \$running_count"
            echo "\$node_data" | jq -r '.running[] | "    - \(.id) (\(.spider)) - запущена \(.start_time)"' 2>/dev/null || echo "    (ошибка отображения)"
        fi
        
        # Проверяем завершенные задачи
        finished_count=\$(echo "\$node_data" | jq '.finished | length // 0')
        if [ \$finished_count != "null" ] && [ \$finished_count -gt 0 ]; then
            echo "  Завершено: \$finished_count (последние 3)"
            echo "\$node_data" | jq -r '.finished | sort_by(.end_time) | reverse | .[0:3] | .[] | "    - \(.id) (\(.spider)) - завершена \(.end_time)"' 2>/dev/null || echo "    (ошибка отображения)"
        fi
        
        # Если ни одной задачи не найдено, выводим информацию
        if [ \$pending_count = "0" ] && [ \$running_count = "0" ] && [ \$finished_count = "0" ]; then
            echo "  ℹ️ Нет активных или завершенных задач"
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