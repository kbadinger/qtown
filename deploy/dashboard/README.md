# Dashboard deploy — the public lab home (Vercel)

The Nuxt dashboard is the lab's real front end. It deploys to Vercel as a
**git-connected project** (auto-deploys from `main`, same as the `qtown.ai`
landing page), and is **dormant-safe**: every panel whose backend is unreachable
renders `—`, never a fabricated number. So it can go live now and light up area
by area as exhibits come online.

Validated: `NITRO_PRESET=vercel npm run build` produces a clean `.vercel/output`
(incl. the `api/market/proof` serverless function) on this box.

## One-time setup (Vercel UI — needs your account)

1. **Vercel → Add New… → Project → import the `qtown` repo.**
2. **Root Directory: `dashboard`** (this is the critical setting — it's a monorepo).
   Framework auto-detects as **Nuxt**; leave build/output on defaults.
3. **Environment variables** (Project → Settings → Environment Variables): see the
   table below. Only `MARKET_HTTP_URL` matters at first — everything else can stay
   unset so those panels render dormant (honest).
4. **Deploy.** Then add the domain **`dashboard.qtown.ai`** (Project → Settings →
   Domains). This is a *separate* project from the landing page; they don't conflict.

After this, every push to `main` that touches `dashboard/` redeploys automatically.

## Environment variables

| Var | Set to | Effect if unset |
|---|---|---|
| `MARKET_HTTP_URL` | `https://market.qtown.ai` (once the market box is up) | Market panel dormant |
| `ACADEMY_URL` | academy tunnel URL (later) | Academy panels dormant |
| `TOWN_CORE_URL` | town-core URL (later) | Town panels dormant |
| `CARTOGRAPHER_URL` | cartographer URL (later) | Orderbook/GraphQL dormant |
| `TAVERN_HTTP_URL` / `TAVERN_WS_URL` | tavern URLs (later) | Tavern panels dormant |

Notes:
- These are **server-side** runtimeConfig keys (`dashboard/nuxt.config.ts`),
  consumed by the Nitro BFF routes under `dashboard/server/api/`. Vercel exposes
  them to the serverless functions at runtime.
- Nuxt's runtime-override convention also works: `NUXT_MARKET_HTTP_URL` overrides
  `runtimeConfig.marketHttpUrl` without a rebuild. Either name is fine on Vercel.
- The `NUXT_PUBLIC_*` vars (client-exposed) can stay default; they only matter for
  the browser-side WS/GraphQL panels, which are dormant until those services host.

## Bring Market live end-to-end

1. Stand up the market box (see `deploy/market-exhibit/README.md`) → `market.qtown.ai` live.
2. Set `MARKET_HTTP_URL=https://market.qtown.ai` in the Vercel project → redeploy.
3. The dashboard's Market proof panel now shows the live book + trade tape; when the
   box sleeps, it falls back to dormant `—`.
