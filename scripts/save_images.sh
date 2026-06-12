#!/usr/bin/env bash
set -euo pipefail
mkdir -p docker-images
IMAGES=(
  "postgres:16"
  "mysql:8.4"
  "mcr.microsoft.com/mssql/server:2022-latest"
  "gvenzl/oracle-free:23-slim"
)
for img in "${IMAGES[@]}"; do
  docker pull "$img"
done
docker save "${IMAGES[@]}" | gzip > docker-images/sgbd-benchmark-images.tar.gz
echo "Arquivo criado: docker-images/sgbd-benchmark-images.tar.gz"
