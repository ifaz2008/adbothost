#!/usr/bin/env bash
set -Eeuo pipefail

cd /opt/adbothost
docker compose ps
echo
docker compose logs --tail=60 backend worker proxy
