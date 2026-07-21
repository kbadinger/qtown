# Market exhibit — the first live, cheap qtown lab bench

This is the template for the whole "public AI lab" plan: one real qtown capability,
running live on a cheap box, reachable at a public URL, costing ~€0–5/mo, and
**honest when off** (the site shows `—`, never a fabricated number).

Market is deliberately first because it isolates *cheap hosting* from the GPU
question — it needs **no GPU, no Postgres, no Kafka**. The whole exhibit is two
~45 MB containers + a tunnel.

## What runs

| Container | What it is |
|---|---|
| `market` | The real Go matching engine + JSON read-model on `:6060` (`/api/orderbook`, `/api/trades`, `/health`). |
| `market-driver` | Synthetic NPC traders placing **real** `PlaceOrder` gRPC calls, so the book moves and trades print. Nothing is faked — prices random-walk, but every trade + latency is what the engine actually produced. |
| `cloudflared` | Cloudflare Tunnel. Publishes `:6060` at a public HTTPS hostname with **no inbound ports** open on the box. |

## One-time setup

**1. Get a cheap always-on box.** Ubuntu 22.04+, ~1 vCPU / 2 GB RAM is plenty.
   - **Hetzner** CX22 (~€4/mo) — recommended, x86, reliable.
   - **Oracle Cloud Always Free** (ARM Ampere, $0) — free but flaky to provision.
   - Install Docker: `curl -fsSL https://get.docker.com | sh`

**2. Clone the repo on the box.**
```bash
git clone https://github.com/kbadinger/qtown.git && cd qtown
```

**3. Create a Cloudflare Tunnel** (needs `qtown.ai` on Cloudflare, which it already is).
   - Cloudflare dashboard → **Zero Trust → Networks → Tunnels → Create a tunnel** → *Cloudflared*.
   - Name it `qtown-market`. Copy the **token** it shows.
   - Add a **Public Hostname**: `market.qtown.ai` → service **`http://market:6060`**.
     (`market` resolves over the compose network — cloudflared shares it.)

**4. Configure and wake.**
```bash
cp deploy/market-exhibit/.env.example deploy/market-exhibit/.env
# edit .env → paste TUNNEL_TOKEN
bash deploy/market-exhibit/wake.sh
```

**5. Verify it's live.**
```bash
curl https://market.qtown.ai/health
curl "https://market.qtown.ai/api/orderbook?resource=gold"   # real bids/asks/mid/spread
curl "https://market.qtown.ai/api/trades?resource=gold&limit=5"
```

## Surfacing it publicly (pick one — see the chat)

- **Landing widget (cheapest):** add a small client-side fetch on `qtown.ai` that
  reads `https://market.qtown.ai/api/orderbook?resource=gold` and renders a live
  mini-book, with a dormant `—` fallback when the box is asleep.
- **Full dashboard:** deploy the Nuxt dashboard and set `MARKET_HTTP_URL=https://market.qtown.ai`
  (see `dashboard/nuxt.config.ts`); its Market proof panel already consumes this shape.

## Day-to-day

```bash
bash deploy/market-exhibit/wake.sh    # start (idempotent, rebuilds)
bash deploy/market-exhibit/sleep.sh   # stop — site goes dormant, you stop paying
docker compose -f deploy/market-exhibit/docker-compose.yml logs -f market-driver
```

## Cost & honesty notes

- Near-idle CPU (gentle order rate; we don't care about speed). A €4 box runs it 24/7.
- **Asleep = honest, not broken.** With the stack down, `/api/*` is unreachable and
  every consumer falls back to dormant `—` (qtown principle #1: no fabricated data).
- `pprof` is disabled in this deploy (`ENABLE_PPROF=0`) so profiles aren't public.
- The tunnel exposes only `http://market:6060`; gRPC `:50051` and the box's ports
  stay private.
