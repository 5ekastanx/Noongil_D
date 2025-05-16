FROM python:3.9.10-slim-buster  # Конкретный образ с Python 3.9.10

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование остальных файлов
COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
