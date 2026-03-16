bind = "0.0.0.0:8000"
workers = 1
threads = 1
timeout = 180
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
capture_output = True
preload_app = True
worker_class = "gthread"

def on_starting(server):
    print("Gunicorn starting")

def when_ready(server):
    print("Gunicorn ready to handle requests")