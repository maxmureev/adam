bind = "0.0.0.0:8000"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
preload = True

# Disable Gunicorn logs
accesslog = None
errorlog = None
loglevel = "critical"
disable_redirect_access_to_syslog = True

# Debug
# accesslog = "-"
# errorlog = "-"
# loglevel = "debug"
# disable_redirect_access_to_syslog = False
