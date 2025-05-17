# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы
COPY . .

# Устанавливаем переменные среды
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=5000

# Открываем порт
EXPOSE $PORT

# Запускаем приложение
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT}", "app:app"]