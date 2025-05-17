FROM python:3.9-slim

WORKDIR /app

# Установка только необходимых зависимостей
RUN apt-get update && apt-get install -y \
    libgl1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Используем переменную окружения для отключения звука
ENV SDL_AUDIODRIVER=dummy

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]