# Last Z Bot Backend — Docker deployment

## Getting started
1. Copy `.env.example` to `.env` and fill in the keys (JWT_SECRET >= 32 chars;
   set real Stripe keys instead of the `sk_live_...` / `whsec_...` / `price_...`
   placeholders, otherwise checkout and webhooks will not work).
2. `docker compose --env-file .env up -d --build`

## Verification
`curl http://localhost:8000/docs` — Swagger API.
`docker compose logs -f backend`

## Important
- SQLite is stored in the `backend_data` volume (`/data/joaxx.db`).
- Stripe webhooks require public HTTPS; use a reverse proxy (Caddy/Nginx) with TLS.
- Webhook idempotency and rate limiting require Redis (shared container).
- The backend will not start without a strong JWT_SECRET (startup validation).
- Stripe key placeholders trigger a startup warning (not a hard failure).