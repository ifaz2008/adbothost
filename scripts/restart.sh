#!/usr/bin/env bash
set -Eeuo pipefail

cd /opt/adbothost
docker compose restart
docker compose ps
