# memL

Self-hosted cloud memory service for OpenClaw (multi-instance ready, observable, governable).

> ⚠️ Positioning: **memL is an external-memory service** (deployed as a standalone server), **not a local in-Lobster plugin process**.
>
> ✅ Stress-tested and verified on **Ubuntu 24.02**.

> Recommended release: `v0.3.3`

## Features

- Multi-tenant isolation (token -> collection)
- Memory CRUD + semantic search + tag filters
- Hybrid retrieval (vector + keyword) with explain mode
- Recency decay + tag boost ranking
- Dedup writes (configurable threshold)
- Idempotent writes (`Idempotency-Key`)
- Async embedding backfill (degraded accept + later repair)
- Tenant quota + write rate limiting
- RBAC (`viewer` / `editor` / `admin`)
- Admin audit logs (`/admin/audit`)
- Visual console (`/ui`)
- Prometheus metrics (`/metrics/prom`) + alert templates
- Auto routing to short-term / long-term collections with unified reads
- DR tooling (backup/restore, tenant export/import)

## Quick Start

```bash
git clone https://github.com/xuzhe1368-lgtm/memL.git
cd memL
cp .env.example .env
# edit .env and tenants.yaml
chmod +x deploy.sh
sudo ./deploy.sh
sudo systemctl enable --now memL
curl http://127.0.0.1:8000/health/live
```

### One-shot CLI block (for Lobster users)

```bash
# 0) install into /opt/memL
sudo mkdir -p /opt && cd /opt
sudo git clone https://github.com/xuzhe1368-lgtm/memL.git || true
cd /opt/memL

# 1) create env
sudo cp -n .env.example .env

# 2) edit required values
# MEML_ADMIN_TOKEN=your strong admin token
# MEML_EMBED_API_URL=your embedding endpoint
# MEML_EMBED_API_KEY=your embedding key
sudo nano /opt/memL/.env

# 3) deploy + start
sudo chmod +x /opt/memL/deploy.sh
sudo /opt/memL/deploy.sh
sudo systemctl enable --now memL

# 4) verify
curl -sS http://127.0.0.1:8000/health/live
curl -sS http://127.0.0.1:8000/metrics/prom | head
```


## Storage Routing (v0.3.3)

For tenant `collection=personal`, memL uses:

- `personal_short` for lower-value memory
- `personal_long` for high-value memory
- `personal` as legacy compatibility store

Write routing:

- `importance_score >= MEML_IMPORTANCE_LONGTERM_THRESHOLD` OR `promote_to_longterm=true` -> `*_long`
- else -> `*_short`

Read path automatically merges short + long + legacy.

## Standard Tag Schema

Recommended normalized tags:

- `type:*` (`type:project`, `type:test`, `type:ops`, `type:milestone`)
- `source:*` (`source:runtime`, `source:migration`)
- `scope:*` (`scope:personal`)

## Key APIs

Auth header:

```text
Authorization: Bearer <token>
```

- `POST /memory` (supports `importance_score`, `promote_to_longterm`)
- `POST /memory/milestone`
- `GET /memory?q=&tags=&limit=&explain=`
- `GET /memory/{id}`
- `PATCH /memory/{id}`
- `DELETE /memory/{id}`
- `GET /stats`
- `GET /metrics`
- `GET /metrics/prom`
- `GET /ui`
- `GET /admin/tenants`
- `POST /admin/tenants`
- `POST /admin/tenants/{token}/disable`
- `GET /admin/audit`

## OpenClaw Integration

In `~/.openclaw/openclaw.json`:

```json
{
  "plugins": {
    "allow": ["meml"],
    "slots": { "memory": "meml" },
    "entries": {
      "meml": {
        "enabled": true,
        "config": {
          "apiUrl": "http://<MEML_HOST>:8000",
          "apiKey": "<YOUR_MEML_API_KEY>",
          "autoInject": true,
          "maxMemories": 10
        }
      }
    }
  }
}
```

## Ops Docs

- `UPGRADE.md` – upgrade & rollback
- `ops/ALERTING.md` – monitoring & alerts
- `ops/AUDIT.md` – audit logging
- `ops/RBAC.md` – role model
- `DR_RUNBOOK.md` – disaster recovery drill
- `ops/caddy.meml.example` – Caddy HTTPS reverse proxy example
- `ops/nginx.meml.example` – Nginx HTTPS reverse proxy example
