import os

bind         = f"0.0.0.0:{os.getenv('PORT', '10000')}"
workers      = 1
threads      = 2
worker_class = "gthread"
timeout      = 120
keepalive    = 2
max_requests = 100
max_requests_jitter = 20
preload_app  = False
accesslog    = "-"
errorlog     = "-"
loglevel     = "warning"
worker_tmp_dir = "/dev/shm"
