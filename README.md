# AdBotHost

AdBotHost is an MVP SaaS for hosting small Telegram bots only. It is not a VPS platform and explicitly blocks AI model hosting, crypto mining, proxies/VPNs, browser automation, scraping, spam/mass DM bots, phishing, malware, shell access, custom Dockerfiles, privileged containers, and Docker socket exposure to users.

## What is included

- FastAPI backend with SQLAlchemy models, JWT-style placeholder auth, Telegram login placeholder, REST APIs, upload scanning, credit accounting, node scheduling, and admin moderation endpoints.
- Worker agent FastAPI service that receives signed controller requests and manages Docker containers with strict limits.
- aiogram 3 Telegram control bot with `/start`, `/mybots`, `/addbot`, `/credits`, and `/help`.
- React + Tailwind dashboard with login, bots, upload, settings, environment variables, logs, credits, and admin screens.
- Local `docker-compose.yml`, `.env.example`, seed script, and example Python/Node Telegram bot projects.

## Local setup

Start the local stack with Docker only:

```bash
docker compose up -d --build
```

Then seed plans and a local worker node:

```bash
docker compose exec backend python scripts/seed_plans.py
```

Open the dashboard at [http://localhost:5173](http://localhost:5173), or through the reverse proxy at [http://localhost](http://localhost). Log in as `admin` with `change-me-admin-password`, or use the dev-user login mode with any email.

The backend is available at [http://localhost/api/docs](http://localhost/api/docs) through Caddy and at [http://localhost:8000](http://localhost:8000) directly. The worker is available at `http://localhost:9000`, but it requires `NODE_AGENT_TOKEN` and signed requests for container actions.

## One-command Debian/Ubuntu RDP install

After publishing this repo, replace `YOUR_USERNAME` in the URL with the GitHub owner:

```bash
curl -fsSL https://raw.githubusercontent.com/ifaz2008/adbothost/main/install.sh | bash
```

You can also override the repo URL while testing a fork:

```bash
curl -fsSL https://raw.githubusercontent.com/ifaz2008/adbothost/main/install.sh | REPO_URL=https://github.com/ifaz2008/adbothost.git bash
```

The installer detects Debian/Ubuntu, installs Docker and the Compose plugin, clones or updates `/opt/adbothost`, writes `.env`, asks for server IP/domain, admin username, admin password, and Telegram control bot token, starts the full stack, runs initialization, seeds plans, and prints final URLs.

Default production-style routes:

- `http://SERVER_IP/` -> dashboard
- `http://SERVER_IP/api` -> backend API
- `http://SERVER_IP/worker-health` -> worker health

Operations scripts installed under `/opt/adbothost/scripts`:

```bash
/opt/adbothost/scripts/status.sh
/opt/adbothost/scripts/restart.sh
/opt/adbothost/scripts/update.sh
/opt/adbothost/scripts/stop.sh
/opt/adbothost/scripts/backup.sh
```

## Health Checklist

After install, run:

```bash
cd /opt/adbothost
docker compose ps
docker compose logs -f
curl http://SERVER_IP/api/health
```

Replace `SERVER_IP` with the IP or domain you entered during install.

## Runtime model

1. A user creates a bot and uploads a ZIP.
2. The backend validates size, extension, archive paths, runtime type, file types, suspicious keywords, and disallowed Docker/custom runtime files.
3. Clean uploads become immutable bot versions.
4. Deployment chooses the healthiest worker node with enough capacity.
5. The backend sends the ZIP plus signed metadata to the worker.
6. The worker generates a safe runtime Dockerfile, builds an image, and starts a non-root container with:
   - CPU limit
   - RAM limit
   - PID limit
   - `cap_drop=ALL`
   - `no-new-privileges:true`
   - no privileged mode
   - no host path mounts
   - no Docker socket mount

## Default plans

| Plan | Bots | CPU | Memory | Storage | Upload | Multiplier | 24h runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1x Basic | 1 | 0.10 | 128 MB | 250 MB | 50 MB | 1x | 4 credits |
| 2x Plus | 3 | 0.20 | 256 MB | 500 MB | 100 MB | 2x | 8 credits |
| 4x Boost | 6 | 0.40 | 512 MB | 1 GB | 150 MB | 4x | 16 credits |
| 8x Max | 10 | 0.80 | 1 GB | 2 GB | 200 MB | 8x | 32 credits |

## Credits

The MVP stores user wallet credit balances and transactions. Credits stay in the wallet until a user manually redeems them for a bot. Runtime is calculated as `credits_redeemed * 6 / credit_multiplier` hours, and the bot stores the resulting `active_until` time. The scheduler runs every minute, stops running deployments after `active_until` expires, restarts crashed deployments only while runtime is active, and marks stale worker nodes unhealthy.

Fake rewarded-ad callback:

```bash
curl -X POST http://localhost:8000/ad-rewards/callback \
  -H "Content-Type: application/json" \
  -d '{"reward_id":"demo-1","email":"user@example.com","credits":1}'
```

The callback is idempotent by `reward_id`, so the same reward cannot be credited twice.

Credits can also be added through admin-approved manual payment requests and coupon redemptions. Admins can add or deduct credits manually for refunds, bonuses, corrections, abuse penalties, or payment review outcomes. Normal users never see private admin notes.

More details:

- [Credits, Ads, Payments, and Coupons](docs/credits-and-ads.md)
- [User Guide](docs/user-guide.md)
- [Acceptable Use Policy](docs/acceptable-use-policy.md)

## Example bot ZIPs

Example source projects live in:

- `examples/python-bot`
- `examples/node-bot`

The generated ZIP archives are:

- `examples/python-bot.zip`
- `examples/node-bot.zip`

Regenerate them with PowerShell:

```powershell
Compress-Archive -Path examples/python-bot/* -DestinationPath examples/python-bot.zip -Force
Compress-Archive -Path examples/node-bot/* -DestinationPath examples/node-bot.zip -Force
```

## Production hardening TODOs

- Replace placeholder auth with real session/JWT lifecycle, CSRF protection where applicable, and real Telegram login verification.
- Encrypt environment variables with a KMS-backed envelope key.
- Use object storage for uploads and build artifacts.
- Add a real rewarded-ad or payment provider.
- Add outbound egress policy/proxying per bot.
- Add per-node secret rotation and mTLS between controller and workers.
- Add AI-assisted code review via OpenRouter/OpenClaw after the deterministic scanner.
- Enforce storage quotas at the Docker volume or filesystem driver level.
- Add robust queueing for long-running build/deploy jobs.


