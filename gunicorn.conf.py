"""Gunicorn settings for the container image.

Read by ``gunicorn -c /app/gunicorn.conf.py src.app:app`` (see the Dockerfile).
Flask's built-in server is never used here: it is single-threaded, and with
``debug=True`` it exposes the Werkzeug debugger, which is a remote code
execution interface for anyone who can reach the port.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# One worker process, several threads.
#
# The store is a single SQLite file. Multiple *processes* writing to it in
# rollback-journal mode contend for a whole-file lock and start returning
# "database is locked"; threads inside one process queue up far more politely.
# For a household shopping list this is ample. If this ever needs to scale out,
# the move is a real database, not more workers.
workers = 1
worker_class = "gthread"
threads = int(os.environ.get("LISTER_THREADS", "4"))

# /dev/shm is a tmpfs Docker always provides, so the heartbeat file never
# touches the read-only root filesystem.
worker_tmp_dir = "/dev/shm"

# Recycle workers periodically: bounds the damage of a slow leak, and the
# jitter stops every worker restarting in lockstep.
max_requests = 1000
max_requests_jitter = 100

timeout = 30
graceful_timeout = 30
keepalive = 5

# Caps on what a single request may send us, so a hostile client cannot make
# the process allocate unbounded memory while parsing headers.
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190

# Trust no proxy headers by default. If you put this behind a reverse proxy,
# set LISTER_FORWARDED_ALLOW_IPS to that proxy's address -- never to "*", which
# would let any client forge X-Forwarded-For and poison your logs.
forwarded_allow_ips = os.environ.get("LISTER_FORWARDED_ALLOW_IPS", "")

# Log to stdout/stderr so the container runtime owns log rotation.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LISTER_LOG_LEVEL", "info")
