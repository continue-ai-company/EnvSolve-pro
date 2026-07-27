ARG BASE_IMAGE=ghcr.io/jetbrains-research/envbench-python:latest
FROM ${BASE_IMAGE}

ARG BASE_IMAGE
ARG PYPI_INDEX_URL=http://host.docker.internal:3141/root/pypi/+simple/
ARG APT_PROXY_URL=http://host.docker.internal:3142
ARG CACHE_SNAPSHOT_ID=development-unfrozen
ARG CACHE_MODE=mutable-shared
ARG UPSTREAM_MISS_POLICY=allow
ARG PIP_DEFAULT_TIMEOUT_SECONDS=180

ENV PIP_INDEX_URL=${PYPI_INDEX_URL}
ENV PIP_TRUSTED_HOST=host.docker.internal
ENV PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT_SECONDS}

RUN printf '%s\n' \
    'Acquire::http::Proxy "DIRECT";' \
    "Acquire::http::Proxy::ports.ubuntu.com \"${APT_PROXY_URL}\";" \
    "Acquire::http::Proxy::archive.ubuntu.com \"${APT_PROXY_URL}\";" \
    "Acquire::http::Proxy::security.ubuntu.com \"${APT_PROXY_URL}\";" \
    'Acquire::Queue-Mode "access";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::http::Timeout "120";' \
    'Acquire::Retries "5";' \
    > /etc/apt/apt.conf.d/01envsolve-dependency-cache

LABEL org.envsolve.dependency-cache.role=client \
      org.envsolve.dependency-cache.base-image=${BASE_IMAGE} \
      org.envsolve.dependency-cache.snapshot=${CACHE_SNAPSHOT_ID} \
      org.envsolve.dependency-cache.mode=${CACHE_MODE} \
      org.envsolve.dependency-cache.upstream-miss-policy=${UPSTREAM_MISS_POLICY} \
      org.envsolve.dependency-cache.pypi=${PYPI_INDEX_URL} \
      org.envsolve.dependency-cache.apt=${APT_PROXY_URL}
