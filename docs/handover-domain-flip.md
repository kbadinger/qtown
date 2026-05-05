# Domain handover — qtown.ai → v2 placeholder, v1.qtown.ai → v1 (Railway-only)

This document describes the manual steps Kevin needs to take in Railway and the DNS registrar to complete the v1/v2 split. The repo-side work is already done.

**Architecture (after this handover):**

```
qtown.ai       → Railway service "qtown-landing"   (Caddy serves landing/)
v1.qtown.ai    → Railway service "qtown" (existing, rebuilt from /v1/)
```

Both services live in the **same Railway project**. One Postgres, one bill, one dashboard. No Vercel, no second vendor.

When v2 ships (Phase 6 closes), `qtown-landing` is replaced by the actual v2 deploy (or qtown.ai is reattached to a new service for the v2 stack). v1.qtown.ai stays as the archive.

---

## Sequence

Order matters. Do steps **in order** and verify each one.

### Step 1 — Reconfigure the existing v1 Railway service

The repo just moved v1's code into `/v1`. Railway must build from that subdirectory now.

1. Open Railway → the `qtown` project → the existing v1 web service.
2. **Settings → Build → Root Directory**: set to `v1`.
3. **Settings → Build → Watch Paths** (if used): change `engine/**` → `v1/engine/**`.
4. Verify settings make sense:
   - Builder: NIXPACKS (auto-detects `v1/requirements.txt`)
   - Start: from `v1/Procfile` → `python -m uvicorn engine.main:app --host 0.0.0.0 --port ${PORT:-8000}`
   - Health: `/health` (per `v1/railway.json`)
5. Push the branch / merge to `main`. Railway redeploys.
6. Hit the temporary Railway URL `<service>.up.railway.app/health` — should be 200.
7. Hit `/` — should render the v1 dashboard, not 500.

If `/` 500s: check that `v1/snapshots/`, `v1/prd.json`, `v1/cost_tracking.json`, and `v1/progress.txt` are present in the deployed image (they're CWD-relative file reads in `v1/engine/main.py`).

### Step 2 — Create the second Railway service for the landing page

Same Railway project. New service.

1. In the `qtown` project dashboard → **+ New Service** → **GitHub Repo** → select `kbadinger/qtown` → **Deploy**.
2. **Settings → Build → Root Directory**: set to `landing`.
3. **Settings → Build → Builder**: should auto-detect Dockerfile (per `landing/railway.json`).
4. **Settings → Networking** → **Generate Domain**: gives you a temporary `qtown-landing-production-xxxx.up.railway.app` URL.
5. Wait for first deploy. Hit the temporary URL — should render the landing page (badge: "v2 in development · v1 live at v1.qtown.ai", live data section pulling from v1.qtown.ai/api/world).

### Step 3 — Add `v1.qtown.ai` to the v1 service

Still in Railway → existing v1 service → **Settings → Networking → Custom Domains**:

1. **Add Domain** → `v1.qtown.ai`.
2. Railway gives you a CNAME target like `xxx.up.railway.app`. Copy it.
3. **Don't remove `qtown.ai` yet.**

In your DNS registrar:

4. Add `CNAME v1` → `<railway-cname-target>` for the v1 service.
5. Wait for propagation (`dig v1.qtown.ai` should return Railway's target).
6. Verify: `curl -I https://v1.qtown.ai/health` → `HTTP/2 200`.
7. Open `https://v1.qtown.ai/` in a browser. Confirm the v1 dashboard renders.

### Step 4 — Flip qtown.ai apex from the v1 service to the landing service

The v1 service currently owns qtown.ai. Move it to the landing service in Railway.

**In Railway, on the v1 service**:
1. **Settings → Networking → Custom Domains** → remove `qtown.ai`. (Keep `v1.qtown.ai`.)

**In Railway, on the landing service**:
2. **Settings → Networking → Custom Domains** → **Add Domain** → `qtown.ai`.
3. **Add Domain** → `www.qtown.ai`.
4. Railway gives a CNAME target for the landing service. Copy it.

**In your DNS registrar**:
5. Update the `qtown.ai` apex. If your registrar supports ALIAS/ANAME records, point apex to the landing service's CNAME target. Otherwise, Railway provides A records — use those.
6. Update `www` CNAME to the landing service's CNAME target.

Wait 5–60 min for propagation.

### Step 5 — Sanity sweep

```sh
curl -sI https://qtown.ai | head -3                      # should hit landing service (Caddy)
curl -sI https://v1.qtown.ai/health | head -3            # 200, hits Railway/uvicorn
curl -s  https://qtown.ai | grep "v1 live at v1.qtown.ai"   # confirms placeholder content
dig +short qtown.ai                                       # Railway IP for landing service
dig +short v1.qtown.ai                                    # Railway IP for v1 service
```

Open `https://qtown.ai` in a browser:
- Hero badge: "v2 in development · v1 live at v1.qtown.ai"
- Header has "v1 Archive" link → goes to v1.qtown.ai
- "Live from v1" section renders KPIs and the world map (pulls from v1.qtown.ai/api)
- CTA: "Visit v1 (live)" + "View on GitHub"

If the live data section is blank, hit `https://v1.qtown.ai/api/world` directly — the placeholder's `app.js` fetches that URL via the browser. If v1's API is healthy and CORS allows the qtown.ai origin, the fetch works. (CORS may need to be configured in `v1/engine/main.py` if the request is blocked.)

## Rollback

If qtown.ai is broken after Step 4 and you can't fix forward in <30 min:

1. In Railway: re-attach `qtown.ai` to the v1 service (and remove from landing).
2. In DNS registrar: revert apex back to v1's CNAME target.
3. Wait for propagation. v1 is live again at qtown.ai while you debug landing.

Set DNS TTL to 300s before Step 4 if you want faster recovery.

## What this leaves you with

- **qtown.ai** → Railway/landing service (Caddy, Dockerfile build, ~$5/mo).
- **v1.qtown.ai** → Railway/v1 service (existing setup, just rebadged, builds from `/v1`).
- One Railway project, two services, one bill, one auth.
- Repo: v1 isolated under `/v1`, v2 owns the root, landing/ is its own deployable.
- Future: when Phase 6 closes, replace the landing service with the v2 dashboard build (or attach qtown.ai to a brand-new v2 service in this same project). DNS doesn't move.
