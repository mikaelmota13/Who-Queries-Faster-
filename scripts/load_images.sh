#!/usr/bin/env bash
set -euo pipefail
gunzip -c docker-images/sgbd-benchmark-images.tar.gz | docker load
