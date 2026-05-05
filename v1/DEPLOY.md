# Qtown v1 — Deploy Notes

v1 deploys to Railway. The repo root is now the v2 polyglot project; v1 lives under `/v1`.

## One-time Railway service reconfiguration

After the v1 → `/v1` move, the existing Railway service must be told to build from this subdirectory:

1. Open the Railway project dashboard for `qtown` (the v1 service).
2. Go to **Settings → Build → Root Directory**.
3. Set it to `/v1`.
4. Save. Railway will trigger a redeploy automatically.

Once that flag is set, every push to `main` rebuilds v1 from `/v1` using:
- Builder: NIXPACKS (per `railway.json`)
- Start command: `python -m uvicorn engine.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Health check: `/health`
- Python deps: `requirements.txt` (alongside this file)

## Domain

After the move, the production domain handover is:

- **qtown.ai** (apex) → **v2** (Vercel coming-soon page during transition; eventually the Nuxt dashboard)
- **v1.qtown.ai** → this Railway service (read-only archive of v1)

Steps to flip:
1. In Railway → Settings → Networking → remove `qtown.ai` from custom domains.
2. Add `v1.qtown.ai` as the new custom domain. Railway will give you a CNAME target.
3. At the DNS registrar: replace the `qtown.ai` A/ALIAS record (currently pointing at Railway) with whatever apex destination you choose for v2. Add a `CNAME v1.qtown.ai → <Railway target>`.
4. Verify `https://v1.qtown.ai/health` returns 200 once DNS propagates (5–60 min).

## Local v1 dev

From the **repo root** (not `/v1`):
```
cd v1
QTOWN_ENV=development python -m uvicorn engine.main:app --host 0.0.0.0 --port 8000
open http://localhost:8000
```

The CWD-relative paths in `engine/main.py` (e.g. `Path("prd.json")`, `Path("snapshots/...")`) resolve correctly when the working directory is `v1/`.
