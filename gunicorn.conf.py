bind = "0.0.0.0:8000"
workers = 1
threads = 1
timeout = 180
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "./logs/gunicorn/access.log"
errorlog = "./logs/gunicorn/error.log"
loglevel = "info"
capture_output = True
preload_app = True
worker_class = "thread"

def on_starting(server):
    print("Gunicorn starting")

def when_ready(server):
    print("Gunicorn ready to handle requests")