FROM python:3.9-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только requirements.txt для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Затем копируем остальные файлы
COPY . .

# Создаем необходимые директории
RUN mkdir -p /tmp/debug_images

# Запускаем приложение
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
