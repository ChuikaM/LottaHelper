FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    redis-server && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p ./logs/gunicorn ./logs/celery .cache

EXPOSE 8000

CMD ["gunicorn", "-c", "app/gunicorn/conf.py", "app.main:app"]