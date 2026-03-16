FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /lottahelper

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 appuser && \
    mkdir -p data log/gunicorn log/celery .cache && \
    chown -R appuser:appuser /lottahelper

USER appuser

WORKDIR /lottahelper

EXPOSE 8000

CMD ["gunicorn", "-c", "app/gunicorn/gunicorn.conf.py", "main:app"]