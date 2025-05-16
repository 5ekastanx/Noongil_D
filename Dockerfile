FROM python:3.9-slim

WORKDIR /app

# Устанавливаем системные зависимости для PyAudio и других пакетов
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    portaudio19-dev \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости первыми для кэширования
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы
COPY . .

# Создаем необходимые директории
RUN mkdir -p /tmp/debug_images

# Запускаем приложение
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
