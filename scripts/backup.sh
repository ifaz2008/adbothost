#!/usr/bin/env bash
set -Eeuo pipefail

cd /opt/adbothost
mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "backups/adbothost-${stamp}.sql"
docker compose exec -T backend tar -czf - -C /app uploads > "backups/uploads-${stamp}.tar.gz" 2>/dev/null || true
echo "Backup written under /opt/adbothost/backups"
