# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- build stage
# uv and a compiler toolchain live here and are thrown away; only the finished
# virtualenv is copied into the runtime image.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1

WORKDIR /app

# Dependencies resolve from the lockfile alone, so this layer is cached until
# uv.lock actually changes. --locked fails the build if the lockfile is stale
# rather than silently resolving something newer than what was reviewed.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra prod --no-install-project

# --no-editable installs the app as a real wheel into the venv, so the runtime
# image needs no separate source tree to point at.
COPY src ./src
RUN uv sync --locked --no-dev --extra prod --no-editable


# -------------------------------------------------------------- runtime stage
FROM python:3.14-slim-bookworm AS runtime

# Pick up whatever security fixes Debian has published since the base image was
# built, then drop the package lists: no apt metadata, no compilers, nothing an
# attacker landing in the container can build with.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 # Nothing at runtime needs a package manager. Removing them means a process
 # that does win code execution has no pre-installed way to fetch or install
 # a second stage -- it has to bring its own, on a filesystem it cannot write.
 && rm -rf /usr/local/lib/python3.14/site-packages/pip \
           /usr/local/lib/python3.14/ensurepip \
 && rm -f  /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14 \
 && rm -f  /usr/bin/apt /usr/bin/apt-get /usr/bin/apt-cache /usr/bin/apt-key \
           /usr/bin/apt-config /usr/bin/apt-mark /usr/bin/apt-cdrom \
           /usr/bin/dpkg /usr/bin/dpkg-deb /usr/bin/dpkg-split \
           /usr/bin/dpkg-query /usr/bin/dpkg-trigger /usr/bin/dpkg-divert \
           /usr/bin/dpkg-statoverride /usr/bin/dpkg-maintscript-helper

# Fixed high uid/gid so the numbers are stable across rebuilds and match the
# `user:` pin in compose.yaml and the ownership of the data volume.
RUN groupadd --gid 10001 lister \
 && useradd --uid 10001 --gid 10001 --no-create-home \
            --home-dir /app --shell /usr/sbin/nologin lister

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    LISTER_DB_PATH=/data/shopping.db

WORKDIR /app

# Application files stay owned by root and are only readable by the app user,
# so a compromised process cannot rewrite the code it is about to run -- this
# holds even if the read-only root filesystem is ever turned off.
COPY --from=builder --chown=root:root /app/.venv /app/.venv
COPY --chown=root:root gunicorn.conf.py /app/gunicorn.conf.py

# The single writable location. Creating it here with the right ownership means
# a named volume mounted at /data inherits that ownership on first use.
RUN install -d -o 10001 -g 10001 -m 0700 /data

USER 10001:10001

EXPOSE 8000

# Exercises a route that actually touches SQLite, so a container with a broken
# or unwritable database reports unhealthy instead of merely accepting sockets.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["gunicorn"]
CMD ["-c", "/app/gunicorn.conf.py", "src.app:app"]
