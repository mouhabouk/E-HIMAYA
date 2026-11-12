# gosu (the privilege-drop helper the postgres entrypoint runs) is rebuilt here with a patched Go toolchain: the copy in
# the official image is built with Go 1.24.6 and carries CVE-2025-68121 (crypto/tls). Pinned to gosu 1.19's commit.
# Drop this stage once the official postgres image ships a gosu built with Go >= 1.24.13.
FROM golang:1.27-bookworm@sha256:d9b6a1beb9474adc2a1ce842573639b44b2a0dd49b6669f51d3821baf9ec37c9 AS gosu
RUN CGO_ENABLED=0 GOBIN=/out go install -trimpath -ldflags '-d -w' \
      github.com/tianon/gosu@40506998e34a7a679e6dae41374c1b7aa37eb73f \
 && /out/gosu --version

# PostgreSQL 17 + PostGIS 3 + pgvector, from the official image and the PGDG repository it already configures.
FROM postgres:17-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826

COPY --from=gosu /out/gosu /usr/local/bin/gosu
RUN gosu nobody true

# pgvector is built from its release tag against the server the image carries: the PGDG package (2026-11) now requires
# postgresql-17 > 17.12, which the pinned image and its repository do not have yet. Return to postgresql-17-pgvector
# from apt once the base image moves to 17.12 or later.
ARG PGVECTOR_VERSION=v0.8.1
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-17-postgis-3 \
 && apt-get install -y --no-install-recommends build-essential git ca-certificates postgresql-server-dev-17 \
 && git clone --branch "$PGVECTOR_VERSION" --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
 && make -C /tmp/pgvector OPTFLAGS="" \
 && make -C /tmp/pgvector install \
 && apt-mark manual postgresql-17-postgis-3 \
 && apt-get purge -y --auto-remove build-essential git postgresql-server-dev-17 \
 && rm -rf /tmp/pgvector /var/lib/apt/lists/*

COPY ehimaya-roles.sh /usr/local/bin/ehimaya-roles.sh
# WAL archiving (phase 10 §2.1), switched on by the production compose file.
COPY ehimaya-archive-wal /usr/local/bin/ehimaya-archive-wal
COPY initdb/ /docker-entrypoint-initdb.d/
