# gosu (the privilege-drop helper the postgres entrypoint runs) is rebuilt here with a patched Go toolchain: the copy in
# the official image is built with Go 1.24.6 and carries CVE-2025-68121 (crypto/tls). Pinned to gosu 1.19's commit.
# Drop this stage once the official postgres image ships a gosu built with Go >= 1.24.13.
FROM golang:1.27-bookworm@sha256:5cf287a799e6b94384bad13d16b14904c531f51ba65792237e122ce42b392f61 AS gosu
RUN CGO_ENABLED=0 GOBIN=/out go install -trimpath -ldflags '-d -w' \
      github.com/tianon/gosu@40506998e34a7a679e6dae41374c1b7aa37eb73f \
 && /out/gosu --version

# PostgreSQL 17 + PostGIS 3 + pgvector, from the official image and the PGDG repository it already configures.
FROM postgres:18-bookworm@sha256:afc7e2d441324c0388fa80c3d24f733b4194a4eb7f47dd8ee2b08eb1a24a647c

COPY --from=gosu /out/gosu /usr/local/bin/gosu
RUN gosu nobody true

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-17-postgis-3 postgresql-17-pgvector \
 && rm -rf /var/lib/apt/lists/*

COPY ehimaya-roles.sh /usr/local/bin/ehimaya-roles.sh
COPY initdb/ /docker-entrypoint-initdb.d/
