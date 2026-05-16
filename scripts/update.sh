#!/usr/bin/env bash
set -Eeuo pipefail

cd /opt/adbothost
git pull --ff-only
docker compose up -d --build
docker compose exec -T backend python scripts/seed_plans.py
docker compose ps
