# Deployment — finance.rahulnainala.com

How WealthPilot goes public, and how it behaves when the 3070 is asleep.

Puts the app on the public internet behind login (Phase 40) + HTTPS. The 3070's
Ollama stays on your home network, reached over Tailscale — the AI never leaves
your hardware.

## Prerequisites
- An EC2 instance (t3.small+; Ubuntu), Docker + Docker Compose installed.
- DNS: an **A record** for `finance.rahulnainala.com` → the EC2 public IP.
- Security group: allow inbound **80** and **443** only (not 8000/3001/5432).
- Tailscale on both the EC2 box and the 3070 PC (so the backend can reach Ollama
  privately).

## One-time setup on the box
```bash
git clone https://github.com/rahulnainala/wealthpilot && cd wealthpilot
cp .env.example .env   # then edit .env (see below)
```

### Required `.env` values (gitignored)
```
APP_PASSWORD=<a strong password>                     # gates the whole app (Phase 40)
FERNET_KEY=<python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())">
OLLAMA_URL=http://<3070-tailscale-ip>:11434
OLLAMA_MODEL=wealthpilot
USE_MOCK_KITE=false
KITE_API_KEY=...   KITE_API_SECRET=...
KITE_REDIRECT_URL=https://finance.rahulnainala.com/auth/kite/callback
MARKET_DATA_PROVIDER=yahoo
VAPID_PUBLIC_KEY=...  VAPID_PRIVATE_KEY=...           # optional (push)
```
Also update `KITE_REDIRECT_URL` in your Zerodha app settings to the https URL.

### Edit the domain/email
- `deploy/Caddyfile`: confirm the domain block (`finance.rahulnainala.com`). Caddy gets a
  Let's Encrypt cert automatically on first boot.

## Launch
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose logs -f caddy   # watch the cert issue
```
Visit `https://finance.rahulnainala.com` → login screen (APP_PASSWORD) → dashboard.

## When the 3070 is off (it usually is)

The GPU box doesn't need to be up for the app to be useful — that's deliberate.
Verified behaviour with Ollama unreachable (2026-07-20, measured against a live
offline 3070):

| Surface | Offline behaviour |
| --- | --- |
| Portfolio, holdings, goals, risk, basket, action plan, issues, funds, trends | Unaffected — no AI involved |
| Pilot insights, daily plan, weekly review, data health | **Served from Postgres.** Written by the nightly job, read all day |
| Morning brief | Served from the 24h Postgres cache, pre-warmed nightly |
| Chat (⌘J), fresh embeddings, retrains | Unavailable until the box is back |

The reachability probe times out in **2s**, so nothing hangs — AI surfaces fall
back rather than blocking the page. `/api/ai/status` reports
`ollama_reachable: false` honestly.

**So the 3070 only needs to be awake for the 20:30 IST nightly window.** That
run distills the day, embeds pending chunks, generates insights, builds the
action plan, and pre-generates the brief — everything you read the next day is
already in Postgres. Wake it for that hour (BIOS scheduled power-on, a WoL cron
from any always-on LAN device, or just leave it on evenings) and the app looks
fully alive from anywhere.

Embedding is resumable: chunks queue up with no vector and the next successful
run catches up, so skipped nights cost nothing permanent.

### If you want chat to work while the box sleeps
`build_ai_provider()` already falls back **Ollama → Anthropic → none**. Set
`ANTHROPIC_API_KEY` in `.env` and chat keeps working from the cloud whenever the
3070 is unreachable, with no code change. Note this is a *paid API* key — a
Claude Pro subscription is not the same thing — and it means those prompts leave
your hardware, which is the tradeoff the local-first setup exists to avoid.
Leave it unset to stay fully local and simply lose chat while the box is off.

## Notes
- **Same-origin**: Caddy proxies `/api`, `/healthz`, `/ws` to the backend and
  everything else to the frontend, so there are no CORS hops.
- **Auth is enforced** because `APP_PASSWORD` is set; every request needs a valid
  token (login mints a 7-day Fernet-signed token).
- **Backups**: `docker compose exec postgres pg_dump -U wealthpilot wealthpilot > backup.sql`
  (cron it; ship to S3/Glacier if desired).
- **Updates**: `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
- **Execution (Wave J)** stays confirm-gated + audit-logged; auth is the prerequisite
  that makes exposing it safe.
