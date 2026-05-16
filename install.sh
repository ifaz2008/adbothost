#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/YOUR_USERNAME/adbothost.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/adbothost}"

need_root() {
  if [ "${EUID}" -ne 0 ]; then
    echo "Please run as root, or pipe to sudo bash."
    exit 1
  fi
}

detect_os() {
  if [ ! -f /etc/os-release ]; then
    echo "Cannot detect OS. Debian or Ubuntu is required."
    exit 1
  fi
  . /etc/os-release
  if [ "${ID}" != "debian" ] && [ "${ID}" != "ubuntu" ]; then
    echo "Unsupported OS: ${PRETTY_NAME:-unknown}. Debian or Ubuntu is required."
    exit 1
  fi
}

install_base_packages() {
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y curl git ca-certificates gnupg openssl
}

setup_docker_repo() {
  . /etc/os-release
  install -m 0755 -d /etc/apt/keyrings
  rm -f /etc/apt/keyrings/docker.gpg
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
}

install_docker() {
  for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
    DEBIAN_FRONTEND=noninteractive apt-get remove -y "$pkg" >/dev/null 2>&1 || true
  done
  setup_docker_repo
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  docker compose version >/dev/null
}

clone_or_update_repo() {
  mkdir -p "$(dirname "$INSTALL_DIR")"
  if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing repo in $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only
  elif [ -d "$INSTALL_DIR" ]; then
    echo "$INSTALL_DIR exists but is not a git repository."
    echo "Move it away or set INSTALL_DIR to another path."
    exit 1
  else
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
}

secret() {
  openssl rand -hex 32
}

escape_env_value() {
  local value="$1"
  value="${value//$'\n'/}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//\$/\\\$}"
  printf '"%s"' "$value"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local file="$INSTALL_DIR/.env"
  local line
  local tmp
  line="${key}=$(escape_env_value "$value")"
  tmp="$(mktemp)"
  awk -v key="$key" -v line="$line" '
    BEGIN { done = 0 }
    $0 ~ "^" key "=" { print line; done = 1; next }
    { print }
    END { if (!done) print line }
  ' "$file" > "$tmp"
  cat "$tmp" > "$file"
  rm -f "$tmp"
}

get_env_value() {
  local key="$1"
  local file="$INSTALL_DIR/.env"
  local value
  value="$(grep -E "^${key}=" "$file" | tail -n1 | cut -d= -f2- || true)"
  value="${value%\"}"
  value="${value#\"}"
  printf '%s' "$value"
}

ensure_secret() {
  local key="$1"
  local current
  current="$(get_env_value "$key")"
  if [ -z "$current" ] || [[ "$current" == change-me* ]] || [[ "$current" == local-* ]]; then
    current="$(secret)"
    set_env_value "$key" "$current"
  fi
  printf '%s' "$current"
}

configure_env() {
  cd "$INSTALL_DIR"
  if [ ! -f .env ]; then
    cp .env.example .env
  fi

  local default_ip
  default_ip="$(curl --max-time 5 -fsSL https://api.ipify.org || hostname -I | awk '{print $1}')"

  read -rp "Public server IP or domain [${default_ip}]: " public_host
  public_host="${public_host:-$default_ip}"
  public_host="${public_host#http://}"
  public_host="${public_host#https://}"

  read -rp "Admin username [admin]: " admin_username
  admin_username="${admin_username:-admin}"

  read -rsp "Admin password: " admin_password
  echo
  if [ -z "$admin_password" ]; then
    echo "Admin password cannot be empty."
    exit 1
  fi

  read -rsp "Telegram control bot token (leave blank to disable for now): " telegram_token
  echo

  local node_token
  local postgres_db
  local postgres_user
  postgres_db="$(get_env_value POSTGRES_DB)"
  postgres_user="$(get_env_value POSTGRES_USER)"
  postgres_db="${postgres_db:-adbothost}"
  postgres_user="${postgres_user:-adbothost}"

  set_env_value APP_ENV "production"
  set_env_value POSTGRES_DB "$postgres_db"
  set_env_value POSTGRES_USER "$postgres_user"
  ensure_secret POSTGRES_PASSWORD >/dev/null
  ensure_secret APP_SECRET >/dev/null
  ensure_secret JWT_SECRET >/dev/null
  node_token="$(ensure_secret NODE_AGENT_TOKEN)"
  set_env_value DEFAULT_NODE_AGENT_TOKEN "$node_token"
  ensure_secret ADMIN_SECRET >/dev/null
  set_env_value ADMIN_USERNAME "$admin_username"
  set_env_value ADMIN_PASSWORD "$admin_password"
  set_env_value ADMIN_EMAIL "${admin_username}@adbothost.local"
  set_env_value TELEGRAM_CONTROL_BOT_TOKEN "$telegram_token"
  set_env_value PUBLIC_BASE_URL "http://${public_host}"
  set_env_value API_ROOT_PATH "/api"
  set_env_value FRONTEND_BASE_URL "http://${public_host}"
  set_env_value BACKEND_BASE_URL "http://${public_host}/api"
  set_env_value WORKER_PUBLIC_BASE_URL "http://worker:9000"
  set_env_value UPLOAD_DIR "/app/uploads"
  set_env_value WORKER_DATA_DIR "/var/lib/adbothost-worker"
  set_env_value DATABASE_URL "postgresql+psycopg2://$(get_env_value POSTGRES_USER):$(get_env_value POSTGRES_PASSWORD)@db:5432/$(get_env_value POSTGRES_DB)"
  set_env_value CORS_ORIGINS "http://${public_host},http://${public_host}:5173"
  set_env_value WORKER_ENFORCE_STORAGE_OPT "false"
  set_env_value ALLOW_NEGATIVE_CREDITS "false"
  set_env_value MANUAL_PAYMENT_ENABLED "true"
  if [ -z "$(get_env_value MANUAL_PAYMENT_PROVIDER_NAME)" ]; then
    set_env_value MANUAL_PAYMENT_PROVIDER_NAME "Binance Pay"
  fi
  if [ -z "$(get_env_value MANUAL_PAYMENT_INSTRUCTIONS)" ]; then
    set_env_value MANUAL_PAYMENT_INSTRUCTIONS "Send payment, then submit your Binance ID and TxID."
  fi
  if [ -z "$(get_env_value MANUAL_PAYMENT_CURRENCY)" ]; then
    set_env_value MANUAL_PAYMENT_CURRENCY "USDT"
  fi
}

start_stack() {
  cd "$INSTALL_DIR"
  chmod +x scripts/*.sh || true
  docker compose up -d --build
  echo "Waiting for backend to become healthy..."
  for attempt in $(seq 1 60); do
    if docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" >/dev/null 2>&1; then
      break
    fi
    if [ "$attempt" -eq 60 ]; then
      echo "Backend did not become healthy in time. Recent backend logs:"
      docker compose logs --tail=80 backend
      exit 1
    fi
    sleep 2
  done
  docker compose exec -T backend python scripts/seed_plans.py
}

print_summary() {
  local public_base
  public_base="$(grep '^PUBLIC_BASE_URL=' "$INSTALL_DIR/.env" | cut -d= -f2- | sed 's/^"//; s/"$//')"
  cat <<EOF

AdBotHost is running.

Dashboard URL:     ${public_base}/
Backend API URL:   ${public_base}/api
Worker health URL: ${public_base}/worker-health

Useful commands:
  View logs:  cd ${INSTALL_DIR} && docker compose logs -f
  Restart:    ${INSTALL_DIR}/scripts/restart.sh
  Update:     ${INSTALL_DIR}/scripts/update.sh
  Stop:       ${INSTALL_DIR}/scripts/stop.sh
  Status:     ${INSTALL_DIR}/scripts/status.sh
  Backup:     ${INSTALL_DIR}/scripts/backup.sh

EOF
}

main() {
  need_root
  detect_os
  install_base_packages
  install_docker
  clone_or_update_repo
  configure_env
  start_stack
  print_summary
}

main "$@"
