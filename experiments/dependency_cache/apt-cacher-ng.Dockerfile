ARG UBUNTU_IMAGE=ubuntu:22.04
FROM ${UBUNTU_IMAGE}

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        apt-cacher-ng ca-certificates \
    && rm -rf /var/lib/apt/lists/*

LABEL org.envsolve.dependency-cache.role=apt-service

COPY apt-cacher-ng.conf /etc/apt-cacher-ng/acng.conf
COPY apt-cacher-ng-entrypoint.sh /usr/local/bin/envsolve-apt-cache-entrypoint
RUN chmod 0755 /usr/local/bin/envsolve-apt-cache-entrypoint \
    && mkdir -p /var/cache/apt-cacher-ng /var/log/apt-cacher-ng \
    && chown -R apt-cacher-ng:apt-cacher-ng \
        /var/cache/apt-cacher-ng /var/log/apt-cacher-ng

EXPOSE 3142
ENTRYPOINT ["/usr/local/bin/envsolve-apt-cache-entrypoint"]
