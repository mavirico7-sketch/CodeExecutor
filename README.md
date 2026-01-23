# Code Executor

Backend-сервис для исполнения пользовательского кода в изолированных Docker-контейнерах. Предназначен для использования в симуляторах технических собеседований (live coding).

## Особенности

- **Простой API** — один endpoint для выполнения кода
- **Полная изоляция** — каждый запрос выполняется в новом контейнере
- **Автоматическая очистка** — контейнер удаляется сразу после выполнения
- **Безопасность** — контейнеры без сети, с ограничением ресурсов

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         Клиент                                   │
│              POST /api/v1/execute (environment, code)           │
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
│                    (Celery Broker/Backend)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Celery Worker  │  │  Celery Worker  │  │  Celery Beat    │
│                 │  │                 │  │  (Cleanup)      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
              │               │
              ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Daemon                             │
│         Создаёт контейнер → Выполняет код → Удаляет контейнер   │
└─────────────────────────────────────────────────────────────────┘
```

## Требования

- Docker 20.10+
- Docker Compose 2.0+

## Быстрый старт

### 1. Сборка execution образов

```bash
./scripts/build-environments.sh
```

Или отдельных образов:

```bash
docker build -t code-executor-python environments/python/
docker build -t code-executor-python-ml environments/python-ml/
docker build -t code-executor-node environments/node/
docker build -t code-executor-rust environments/rust/
```

### 2. Запуск сервиса

```bash
docker compose up -d
```

### 3. Проверка работоспособности

```bash
curl http://localhost:8000/api/v1/health
```

### 4. Выполнение кода

```bash
curl -X POST http://localhost:8000/api/v1/execute \
    -H "Content-Type: application/json" \
    -d '{"environment": "python", "code": "print(\"Hello, World!\")"}'
```

## API Endpoints

### Health Check

```bash
GET /api/v1/health
```

### Список окружений

```bash
GET /api/v1/environments
```

**Ответ:**
```json
[
  {"name": "python", "description": "Python 3.11 with basic packages", "file_extension": ".py"},
  {"name": "python-ml", "description": "Python 3.11 with ML packages", "file_extension": ".py"},
  {"name": "node", "description": "Node.js 20 LTS", "file_extension": ".js"},
  {"name": "rust", "description": "Rust 1.75", "file_extension": ".rs"}
]
```

### Выполнение кода

```bash
POST /api/v1/execute
Content-Type: application/json

{
    "environment": "python",
    "code": "print('Hello, World!')",
    "stdin": "optional input",
    "filename": "main.py"
}
```

**Параметры:**
- `environment` (обязательный) — среда выполнения
- `code` (обязательный) — код для выполнения
- `stdin` (опционально) — входные данные
- `filename` (опционально) — имя файла

**Ответ:**
```json
{
    "environment": "python",
    "stdout": "Hello, World!\n",
    "stderr": "",
    "exit_code": 0,
    "execution_time": 0.045,
    "status": "completed"
}
```

## Примеры

### Python

```bash
curl -X POST http://localhost:8000/api/v1/execute \
    -H "Content-Type: application/json" \
    -d '{
        "environment": "python",
        "code": "for i in range(5):\n    print(f\"Number: {i}\")"
    }'
```

### Python с stdin

```bash
curl -X POST http://localhost:8000/api/v1/execute \
    -H "Content-Type: application/json" \
    -d '{
        "environment": "python",
        "code": "name = input()\nprint(f\"Hello, {name}!\")",
        "stdin": "World"
    }'
```

### Node.js

```bash
curl -X POST http://localhost:8000/api/v1/execute \
    -H "Content-Type: application/json" \
    -d '{
        "environment": "node",
        "code": "console.log(\"Hello from Node.js!\");"
    }'
```

### Python ML

```bash
curl -X POST http://localhost:8000/api/v1/execute \
    -H "Content-Type: application/json" \
    -d '{
        "environment": "python-ml",
        "code": "import numpy as np\nprint(np.array([1,2,3]).mean())"
    }'
```

## Конфигурация

### code-executor.conf

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
CONTAINER_MEMORY_LIMIT=256m
CONTAINER_CPU_LIMIT=0.5
CONTAINER_PIDS_LIMIT=50
EXECUTION_TIMEOUT=30

# Безопасность
NETWORK_DISABLED=true
NO_NEW_PRIVILEGES=true
```

### config/environments.yaml

```yaml
environments:
  python:
    image: python
    default_filename: main.py
    file_extension: .py
    run_command: python {file_path}
    description: Python 3.11 with basic packages
    enabled: true

  node:
    image: node
    default_filename: main.js
    file_extension: .js
    run_command: node {file_path}
    description: Node.js 20 LTS
    enabled: true
```

## Добавление нового окружения

### 1. Создайте Dockerfile

```bash
mkdir environments/go
```

```dockerfile
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
go:
  image: go
  default_filename: main.go
  file_extension: .go
  run_command: sh -c "go build -o {output_path} {file_path} && {output_path}"
  description: Go 1.21
  enabled: true
```

### 4. Перезапустите

```bash
docker compose restart api worker
```

## Безопасность

Каждый контейнер запускается с ограничениями:

- **Изоляция сети**: `network_mode: none`
- **Пользователь**: непривилегированный `executor`
- **Память**: ограничена (по умолчанию 256MB)
- **CPU**: ограничен (по умолчанию 0.5 ядра)
- **Процессы**: лимит `pids_limit`
- **Таймаут**: автоматическое завершение
- **Очистка**: контейнер удаляется сразу после выполнения

## Мониторинг

```bash
# Логи
docker compose logs -f

# Активные контейнеры
docker ps --filter "label=code-executor=true"

# Ручная очистка
docker rm -f $(docker ps -aq --filter "label=code-executor=true")
```

## Структура проекта

```
code-executor/
├── app/
│   ├── api/
│   │   ├── routes.py       # API endpoints
│   │   └── schemas.py      # Pydantic модели
│   ├── core/
│   │   └── redis_client.py # Redis клиент
│   ├── worker/
│   │   ├── celery_app.py   # Celery конфигурация
│   │   ├── docker_executor.py  # Выполнение в Docker
│   │   └── tasks.py        # Celery задачи
│   ├── config.py           # Конфигурация
│   └── main.py             # FastAPI приложение
├── config/
│   └── environments.yaml
├── environments/
│   ├── python/
│   ├── python-ml/
│   ├── node/
│   └── rust/
├── code-executor.conf
├── docker-compose.yml
└── Dockerfile
```

## Лицензия

MIT
