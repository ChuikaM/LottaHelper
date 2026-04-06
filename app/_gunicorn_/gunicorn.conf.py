import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 1
worker_class = "sync"
timeout = 180
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

log_dir = '/lottahelper/log/gunicorn'
os.makedirs(log_dir, exist_ok=True)
errorlog = os.path.join(log_dir, 'error.log')
accesslog = os.path.join(log_dir, 'access.log')
loglevel = "info"
capture_output = True

def on_starting(server):
    print("Gunicorn starting")

def when_ready(server):
    print("Gunicorn ready to handle requests")