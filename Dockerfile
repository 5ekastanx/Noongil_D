FROM python:3.9.10-slim-buster

WORKDIR /app

# Сначала копируем только requirements.txt для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Затем копируем остальные файлы
COPY . .

# Создаем необходимые директории
RUN mkdir -p /tmp/debug_images

# Запускаем приложение
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
