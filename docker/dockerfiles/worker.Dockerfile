FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker ./worker
COPY ai ./ai
COPY core ./core
COPY db ./db
COPY enums ./enums

CMD ["taskiq", "worker", "worker.broker:broker", "worker.tasks", "--workers", "1", "--max-async-tasks", "10", "--log-level", "INFO"]
