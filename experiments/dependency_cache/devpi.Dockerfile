ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE}

ARG DEVPI_SERVER_VERSION=6.20.3
RUN python -m pip install --no-cache-dir \
    "devpi-server==${DEVPI_SERVER_VERSION}"

LABEL org.envsolve.dependency-cache.role=pypi-service \
      org.envsolve.dependency-cache.component-version=${DEVPI_SERVER_VERSION}

COPY devpi-entrypoint.sh /usr/local/bin/envsolve-devpi-entrypoint
RUN chmod 0755 /usr/local/bin/envsolve-devpi-entrypoint

EXPOSE 3141
ENTRYPOINT ["/usr/local/bin/envsolve-devpi-entrypoint"]
CMD ["--host", "0.0.0.0", "--port", "3141", "--serverdir", "/data", "--mirror-cache-expiry", "1800"]
