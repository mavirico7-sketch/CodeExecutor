# Code Executor

Backend-сервис для исполнения пользовательского кода в изолированных Docker-контейнерах. Предназначен для использования в симуляторах технических собеседований (live coding).

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         Клиент                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│             Nginx Proxy Manager (Reverse Proxy)                  │
│           Ports: 80 (HTTP), 443 (HTTPS), 81 (Admin)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI (API Gateway)                       │
│                         Port: 8000                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                           Redis                                  │
│              (Broker + State Storage + Results)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Celery Worker  │  │  Celery Worker  │  │  Celery Beat    │
│                 │  │                 │  │  (Scheduler)    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
              │               │
              ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Daemon                             │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Execution Containers                           │
│     (python, python-ml, node, rust, ...)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Требования

- Docker 20.10+
- Docker Compose 2.0+

## Быстрый старт

### 1. Клонирование репозитория

```bash
cd code-executor
```

### 2. Сборка execution образов

Перед запуском сервиса необходимо собрать Docker-образы для выполнения кода.

**Сборка всех образов:**

```bash
./scripts/build-environments.sh
```

**Или отдельных образов:**

```bash
docker build -t code-executor-python environments/python/
docker build -t code-executor-python-ml environments/python-ml/
docker build -t code-executor-node environments/node/
docker build -t code-executor-rust environments/rust/
```

### 3. Запуск сервиса

```bash
docker compose up -d
```

**Доступные адреса:**
- API напрямую: http://localhost:8000
- Nginx Proxy Manager (Admin UI): http://localhost:81
- HTTP через прокси: http://localhost:80
- HTTPS через прокси: https://localhost:443

### 4. Настройка Nginx Proxy Manager

При первом запуске войдите в админ-панель NPM:
1. Откройте http://localhost:81
2. Войдите с учётными данными по умолчанию:
   - Email: `admin@example.com`
   - Password: `changeme`
3. **Обязательно смените пароль** при первом входе

**Настройка Proxy Host для API:**
1. В админ-панели перейдите в **Hosts → Proxy Hosts**
2. Нажмите **Add Proxy Host**
3. Заполните:
   - **Domain Names**: `your-domain.com` (или `localhost` для локальной разработки)
   - **Scheme**: `http`
   - **Forward Hostname / IP**: `api` (имя сервиса из docker-compose)
   - **Forward Port**: `8000`
4. При необходимости включите SSL через вкладку **SSL**

### 5. Проверка работоспособности

```bash
# Напрямую через API
curl http://localhost:8000/api/v1/health

# Через Nginx Proxy Manager (после настройки)
curl http://localhost/api/v1/health
```

## Конфигурация

Конфигурация сервиса разделена на несколько файлов:

```
code-executor/
├── code-executor.conf      # Основные настройки (env переменные)
├── config/
│   └── environments.yaml   # Конфигурация сред выполнения
└── docker-compose.yml      # Конфигурация контейнеров
```

### code-executor.conf

Основной файл конфигурации в формате переменных окружения:

```bash
# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_WORKER_CONCURRENCY=4

# Docker
DOCKER_SOCKET=/var/run/docker.sock
DOCKER_IMAGE_PREFIX=code-executor

# Лимиты выполнения
CONTAINER_MEMORY_LIMIT=256m   # Лимит памяти контейнера
CONTAINER_CPU_LIMIT=0.5       # Лимит CPU (доля ядра)
CONTAINER_PIDS_LIMIT=50       # Лимит процессов
EXECUTION_TIMEOUT=30          # Таймаут выполнения (сек)
SESSION_TTL=3600              # Время жизни сессии (сек)

# Безопасность
NETWORK_DISABLED=true         # Отключить сеть в контейнерах
NO_NEW_PRIVILEGES=true        # Запрет эскалации привилегий
TMPFS_SIZE=64m

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false
```

### config/environments.yaml

Конфигурация сред выполнения кода:

```yaml
environments:
  python:
    image: python                 # Станет code-executor-python
    default_filename: main.py
    file_extension: .py
    run_command: python {file_path}
    description: Python 3.11 with basic packages
    enabled: true

  python-ml:
    image: python-ml
    default_filename: main.py
    file_extension: .py
    run_command: python {file_path}
    description: Python 3.11 with ML packages
    enabled: true

  node:
    image: node
    default_filename: main.js
    file_extension: .js
    run_command: node {file_path}
    description: Node.js 20 LTS
    enabled: true

  rust:
    image: rust
    default_filename: main.rs
    file_extension: .rs
    run_command: sh -c "rustc {file_path} -o {output_path} && {output_path}"
    description: Rust 1.75
    enabled: true

defaults:
  default_environment: python
  workspace_dir: /workspace
  executor_user: executor
```

**Плейсхолдеры в run_command:**
- `{file_path}` — полный путь к файлу (`/workspace/main.py`)
- `{filename}` — только имя файла (`main.py`)
- `{output_path}` — путь без расширения (`/workspace/main`)

### Изменение конфигурации

Отредактируйте файл `code-executor.conf` и перезапустите сервисы:

```bash
# Редактируем конфигурацию
nano code-executor.conf

# Перезапускаем сервисы
docker compose down
docker compose up -d
```

**Пример изменений:**
```bash
# Увеличить память для контейнеров
CONTAINER_MEMORY_LIMIT=512m

# Увеличить таймаут выполнения
EXECUTION_TIMEOUT=60
```

## Добавление нового окружения

### 1. Создайте Dockerfile

```bash
mkdir environments/go
```

```dockerfile
# environments/go/Dockerfile
FROM golang:1.21-alpine

RUN addgroup -S executor && adduser -S executor -G executor
RUN mkdir -p /workspace && chown executor:executor /workspace
WORKDIR /workspace
USER executor
CMD ["sleep", "infinity"]
```

### 2. Соберите образ

```bash
docker build -t code-executor-go environments/go/
```

### 3. Добавьте в config/environments.yaml

```yaml
environments:
  # ... существующие окружения ...
  
  go:
    image: go
    default_filename: main.go
    file_extension: .go
    run_command: sh -c "go build -o {output_path} {file_path} && {output_path}"
    description: Go 1.21
    enabled: true
```

### 4. Перезапустите сервисы

```bash
docker compose down
docker compose up -d --build
```

## API Документация

После запуска доступна интерактивная документация:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Получение списка окружений

```bash
GET /api/v1/environments
```

**Ответ:**
```json
["python", "python-ml", "node", "rust"]
```

### Создание сессии

```bash
POST /api/v1/sessions
Content-Type: application/json

{
    "environment": "python"
}
```

**Ответ:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending",
    "environment": "python",
    "message": "Session created. Container is starting..."
}
```

### Получение статуса сессии

```bash
GET /api/v1/sessions/{session_id}
```

**Ответ:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "ready",
    "environment": "python",
    "container_id": "abc123...",
    "created_at": "2024-01-15T10:30:00",
    "last_execution": null
}
```

**Возможные статусы:**
- `pending` - сессия создана, контейнер запускается
- `creating` - контейнер создается
- `ready` - готов к выполнению кода
- `executing` - код выполняется
- `stopping` - сессия останавливается
- `stopped` - сессия остановлена
- `error` - ошибка

### Выполнение кода

```bash
POST /api/v1/sessions/{session_id}/execute
Content-Type: application/json

{
    "code": "print('Hello, World!')",
    "filename": "main.py"  # опционально
}
```

**Ответ:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "stdout": "Hello, World!\n",
    "stderr": "",
    "exit_code": 0,
    "execution_time": 0.045,
    "status": "completed"
}
```

### Завершение сессии

```bash
DELETE /api/v1/sessions/{session_id}
```

**Ответ:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "stopping",
    "message": "Session is being stopped..."
}
```

## Примеры использования

### Python

```bash
# Создаем сессию
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
    -H "Content-Type: application/json" \
    -d '{"environment": "python"}' | jq -r '.session_id')

echo "Session ID: $SESSION"

# Ждем готовности (в production используйте polling)
sleep 3

# Выполняем код
curl -X POST "http://localhost:8000/api/v1/sessions/$SESSION/execute" \
    -H "Content-Type: application/json" \
    -d '{"code": "for i in range(5):\n    print(f\"Number: {i}\")"}'

# Завершаем сессию
curl -X DELETE "http://localhost:8000/api/v1/sessions/$SESSION"
```

### Python ML

```bash
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
    -H "Content-Type: application/json" \
    -d '{"environment": "python-ml"}' | jq -r '.session_id')

sleep 5

curl -X POST "http://localhost:8000/api/v1/sessions/$SESSION/execute" \
    -H "Content-Type: application/json" \
    -d '{"code": "import numpy as np\narr = np.array([1, 2, 3, 4, 5])\nprint(f\"Mean: {arr.mean()}\")"}'
```

### Node.js

```bash
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
    -H "Content-Type: application/json" \
    -d '{"environment": "node"}' | jq -r '.session_id')

sleep 3

curl -X POST "http://localhost:8000/api/v1/sessions/$SESSION/execute" \
    -H "Content-Type: application/json" \
    -d '{"code": "const arr = [1, 2, 3, 4, 5];\nconsole.log(`Sum: ${arr.reduce((a, b) => a + b, 0)}`);", "filename": "main.js"}'
```

## Безопасность

Каждый execution контейнер запускается с следующими ограничениями:

- **Изоляция сети**: `network_mode: none`
- **Непривилегированный пользователь**: `user: executor`
- **Ограничение памяти**: настраивается в config.yaml
- **Ограничение CPU**: настраивается в config.yaml
- **Ограничение процессов**: `pids_limit`
- **Запрет эскалации привилегий**: `no-new-privileges:true`
- **Таймаут выполнения**: настраивается в config.yaml

## Мониторинг

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Только worker
docker compose logs -f worker

# Только API
docker compose logs -f api
```

### Просмотр активных execution контейнеров

```bash
docker ps --filter "label=code-executor=true"
```

### Ручная очистка контейнеров

```bash
docker rm -f $(docker ps -aq --filter "label=code-executor=true")
```

## Остановка сервиса

```bash
docker compose down
```

С удалением данных (включая настройки NPM и сертификаты SSL):

```bash
docker compose down -v
```

**Volumes:**
- `redis_data` — данные Redis (сессии)
- `npm_data` — настройки Nginx Proxy Manager
- `npm_letsencrypt` — SSL сертификаты Let's Encrypt

## Разработка

### Локальный запуск без Docker

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск Redis (требуется)
docker run -d -p 6379:6379 redis:7-alpine

# Запуск API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Запуск Worker (в отдельном терминале)
celery -A app.worker.celery_app worker --loglevel=info

# Запуск Beat (в отдельном терминале)
celery -A app.worker.celery_app beat --loglevel=info
```

## Troubleshooting

### Сессия не переходит в статус ready

1. Проверьте, что execution образ собран:
   ```bash
   docker images | grep code-executor
   ```

2. Проверьте логи worker:
   ```bash
   docker compose logs worker
   ```

### Ошибка "Container not found"

Сессия могла истечь по таймауту. Создайте новую сессию.

### Код выполняется слишком долго

Увеличьте `limits.timeout` в `config/config.yaml`.

## Структура проекта

```
code-executor/
├── app/
│   ├── api/
│   │   ├── routes.py       # API endpoints
│   │   └── schemas.py      # Pydantic модели
│   ├── core/
│   │   ├── redis_client.py # Redis клиент
│   │   └── session.py      # Управление сессиями
│   ├── worker/
│   │   ├── celery_app.py   # Celery конфигурация
│   │   ├── docker_executor.py  # Выполнение в Docker
│   │   └── tasks.py        # Celery задачи
│   ├── config.py           # Загрузка конфигурации
│   └── main.py             # FastAPI приложение
├── config/
│   └── environments.yaml   # Настройки сред выполнения
├── environments/
│   ├── python/
│   ├── python-ml/
│   ├── node/
│   └── rust/
├── scripts/
│   └── build-environments.sh
├── code-executor.conf      # Основные настройки сервиса
├── docker-compose.yml      # Docker Compose конфигурация
├── Dockerfile
├── requirements.txt
└── README.md
```

## Лицензия

MIT
