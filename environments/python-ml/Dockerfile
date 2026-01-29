# Используем минимальный образ Python
FROM python:3.11-slim

# Установка системных зависимостей (нужны для сборки некоторых ML пакетов)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя
RUN groupadd -r executor && useradd -r -g executor executor

# Установка ML библиотек
# Используем --extra-index-url ВМЕСТО --index-url.
# Это позволяет pip искать torch в репозитории PyTorch, 
# а остальные пакеты (numpy, pandas и т.д.) в стандартном PyPI.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    numpy \
    pandas \
    scikit-learn \
    requests \
    pytest \
    "fastapi[standard]" \
    torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cpu

# Настройка рабочей директории
RUN mkdir -p /workspace && chown executor:executor /workspace
WORKDIR /workspace

USER executor

CMD ["python3"]