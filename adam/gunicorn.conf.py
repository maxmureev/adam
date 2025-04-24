from config import config

bind = f"{config.run.host}:{config.run.port}"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
preload = True

# Disable Gunicorn logs
accesslog = None
errorlog = None
loglevel = "error"
disable_redirect_access_to_syslog = True

# # Debug
# accesslog = "-"        # Output to console
# errorlog = "-"         # Output to console
# loglevel = "debug"
# disable_redirect_access_to_syslog = False
