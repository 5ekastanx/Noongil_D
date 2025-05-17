FROM python:3.9-slim

WORKDIR /app

# Установка ALSA и звуковых драйверов
RUN apt-get update && apt-get install -y \
    libgl1 \
    alsa-utils \
    libasound2 \
    libasound2-plugins \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное звуковое устройство
RUN echo "snd-dummy" >> /etc/modules && \
    echo "options snd-dummy index=0 id=CHIP" >> /etc/modprobe.d/alsa-base.conf

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]