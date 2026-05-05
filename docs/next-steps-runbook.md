# Qtown — Next Steps Runbook

**For:** Kevin Badinger  
**As of:** April 11, 2026  
**State:** All 194 v2 stories complete. qtown.ai is live but broken at root. v2 is not running in Docker yet.  

This is a prioritized, executable runbook. No fluff. Every section has exact commands, expected output, and failure modes.

---

## Priority 1 — Fix the qtown.ai 500 Error

### Root Cause Analysis

The error is in `engine/main.py` at the `index()` route handler (line ~350 in the file). The handler does this:

```python
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    prd_path = Path(__file__).resolve().parent.parent / "prd.json"
    ...
    return templates.TemplateResponse("index.html", {...})
```

Three likely culprits in production:

1. **`prd.json` is missing or malformed on Railway** — Railway's build process may not be including `prd.json` in the deploy. The file is in the repo root; if the working directory is off, `Path(__file__).resolve().parent.parent / "prd.json"` resolves to the wrong path. The code handles this gracefully with a try/except, but it's worth confirming.

2. **Template rendering fails** — `engine/templates/index.html` references a template variable or static file that doesn't exist. In production mode (`QTOWN_ENV=production`), the global exception handler returns `{"detail": "Internal server error"}` with no traceback.

3. **Startup crash** — `_auto_discover_routers()` or `_seed_world()` crashes silently, leaving the app in a broken state even though `/health` returns 200 (the health route is registered directly, so it survives a partial startup).

> **Why `/health` is 200 but `/` is 500:** The `/health` route is defined directly in `main.py` and doesn't depend on templates, DB reads, or prd.json. It always works. This rules out a server outage — it's 100% an application-level bug.

---

### Step 1 — Check Railway Logs

```bash
# Install Railway CLI if you don't have it
npm install -g @railway/cli

# Log in
railway login

# Link to your project (one-time)
railway link  # Select your qtown project

# Stream live logs
railway logs --tail 200

# Or dump recent logs to a file
railway logs --tail 500 > railway-logs.txt
```

**What to look for:**

```
# Good startup sequence looks like:
[qtown] World seeded
[qtown] X NPCs alive after startup fix
[qtown] Auto-registered router: engine.routers.xxx
[qtown] Auto-tick scheduled (every 30s)

# Bad — look for any of these:
Traceback (most recent call last):
  ...
TemplateNotFound: index.html
FileNotFoundError: ...
sqlalchemy.exc.OperationalError
```

If you see `TemplateNotFound: index.html`, skip to Step 3. If you see a SQLAlchemy error, skip to Step 4. If startup looks clean, the bug is in the route handler itself — go to Step 2.

---

### Step 2 — Reproduce Locally

```bash
git clone https://github.com/kbadinger/qtown.git
cd qtown
pip install -r requirements.txt

# Run with production env to match Railway
QTOWN_ENV=production python -m uvicorn engine.main:app --host 0.0.0.0 --port 8000

# In another terminal:
curl -v http://localhost:8000/
curl -v http://localhost:8000/health
```

**Expected:** `/health` → 200, `/` → should show the error clearly (dev mode shows `{"detail": "<error message"}`). In prod mode it'll be generic — check uvicorn stdout for the real error.

---

### Step 3 — The Most Likely Fix: Route to the Landing Page

Instead of debugging the old PixiJS renderer, replace the root route entirely. You have a landing page in `landing/`. **This is the right fix** — redirect `/` to serve the landing page HTML.

**Option A: Serve `landing/index.html` as the root (fastest fix)**

Edit `engine/main.py`:

```python
# Add this import at the top
from fastapi.responses import FileResponse

# Replace the existing index() route:
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    landing_path = Path(__file__).resolve().parent.parent / "landing" / "index.html"
    if landing_path.exists():
        return FileResponse(str(landing_path), media_type="text/html")
    # Fallback: redirect to /api/world
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/world")
```

Also mount the landing assets:

```python
# After the existing app.mount lines, add:
landing_dir = Path(__file__).resolve().parent.parent / "landing"
if landing_dir.is_dir():
    app.mount("/landing", StaticFiles(directory=str(landing_dir)), name="landing")
```

Then update `landing/index.html` — change any relative asset paths from `./style.css` to `/landing/style.css` etc. OR just inline the CSS/JS into the HTML for simplicity.

**Option B: Quick redirect while you fix the real template issue**

```python
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="https://qtown.ai/landing/index.html", status_code=302)
```

---

### Step 4 — Deploy to Railway

```bash
# Push the fix
git add engine/main.py
git commit -m "fix: serve landing page at root, fix 500 error"
git push origin main

# Railway auto-deploys on push if connected to GitHub
# Watch it deploy:
railway logs --tail 100

# Verify
curl -I https://qtown.ai/
# Expected: HTTP/2 200 or 302
```

**If Railway doesn't auto-deploy:**

```bash
railway up
```

---

### Step 5 — Verify the Fix

```bash
# All four should return non-500
curl -so /dev/null -w "%{http_code}" https://qtown.ai/        # 200
curl -so /dev/null -w "%{http_code}" https://qtown.ai/health  # 200
curl -so /dev/null -w "%{http_code}" https://qtown.ai/api/world  # 200
curl -so /dev/null -w "%{http_code}" https://qtown.ai/api/docs   # 404 (expected — disabled in prod)
```

---

## Priority 2 — Deploy Landing Page to qtown.ai

### What You Have

`landing/` contains: `index.html`, `style.css`, `base.css`, `app.js`. The `app.js` fetches from `/api/world` and falls back to a snapshot. This is already good — it means the landing page works even when the backend is down.

### Option A — Serve from the Existing FastAPI App (Recommended)

This keeps everything on one Railway service, one domain, no routing headaches.

**1. Mount the landing directory in `engine/main.py`:**

```python
# Add to the mount section (after existing mounts)
landing_dir = Path(__file__).resolve().parent.parent / "landing"
if landing_dir.is_dir():
    app.mount("/landing", StaticFiles(directory=str(landing_dir)), name="landing-assets")
```

**2. Serve `landing/index.html` at root:**

```python
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    landing_html = Path(__file__).resolve().parent.parent / "landing" / "index.html"
    if landing_html.exists():
        content = landing_html.read_text(encoding="utf-8")
        # Rewrite relative asset paths to absolute
        content = content.replace('href="style.css"', 'href="/landing/style.css"')
        content = content.replace('href="base.css"', 'href="/landing/base.css"')
        content = content.replace('src="app.js"', 'src="/landing/app.js"')
        return HTMLResponse(content=content)
    return HTMLResponse(content="<h1>Qtown</h1>")
```

**3. Verify the `/api/world` endpoint is CORS-accessible from the landing page:**

The existing CORS config already allows `https://qtown.ai`, so you're good.

**4. Deploy and test:**

```bash
git add engine/main.py
git commit -m "feat: serve landing page at root"
git push origin main

# Test
curl -s https://qtown.ai/ | grep -i "<title>"
curl -s https://qtown.ai/landing/style.css | head -5
```

---

### Option B — Deploy Landing Page as a Separate Railway Service

Use this if you want the landing page to be independently deployable.

**1. Create `landing/package.json`:**

```json
{
  "name": "qtown-landing",
  "version": "1.0.0",
  "scripts": {
    "start": "npx serve . -l ${PORT:-3000}"
  },
  "dependencies": {
    "serve": "^14.2.0"
  }
}
```

**2. Create `landing/railway.json`:**

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "npx serve . -l ${PORT:-3000}",
    "healthcheckPath": "/"
  }
}
```

**3. Deploy as a new Railway service:**

```bash
cd landing
railway up --service qtown-landing
```

**4. Point qtown.ai root to the landing service in Railway:**

In the Railway dashboard → your project → qtown-landing service → Settings → Domain → add custom domain `qtown.ai`.

Then in the main FastAPI service, change the domain to `api.qtown.ai` or keep it as `*.up.railway.app` and proxy from Cloudflare.

---

### Option C — Cloudflare Page Rules (Zero Code Change)

If landing is static and already deployed somewhere (e.g., Vercel, Netlify):

1. In Cloudflare dashboard → qtown.ai → Rules → Page Rules
2. Add rule: `qtown.ai/` → Forward URL → `https://landing.qtown.ai/` (301)
3. Keep `qtown.ai/api/*` → no redirect (Cloudflare passes through to Railway)

This is the least invasive but adds routing complexity.

**Recommendation:** Go with Option A. It's one service, one deploy, and the `/api/world` endpoint is already working. You're just replacing a broken Jinja2 template with a static HTML file.

---

## Priority 3 — Publish the Blog Post

The blog post is at `docs/blog-post-v1-closeout.md`. It's written for v1 — the Python monolith story. Here's how to ship it.

### Where to Publish

**Publish to all four, in this order:**

| Platform | Why | Timeline |
|---|---|---|
| Personal blog / GitHub Pages | Canonical URL so you own the content | Day 1 |
| dev.to | Developer audience, SEO, free | Day 1 (simultaneous) |
| Hacker News | Highest signal, best traffic if it hits | Day 2 |
| LinkedIn | Recruiter visibility | Day 3 |

---

### Step 1 — Set Up Your Canonical URL

If you don't have a personal blog, the fastest path is GitHub Pages:

```bash
# In the qtown repo
mkdir -p docs-site
# Or create a separate repo: github.com/kbadinger/kbadinger.github.io

# Install Jekyll (simplest GitHub Pages setup)
gem install jekyll bundler
jekyll new blog
cd blog
# Copy the blog post in
cp ../docs/blog-post-v1-closeout.md _posts/2025-06-XX-i-let-an-ai-write-88-percent.md
```

Add the Jekyll front matter at the top of the post:

```yaml
---
layout: post
title: "I Let an AI Write 88% of My Code. Here's What Happened."
date: 2025-06-15
tags: [ai, coding, ollama, llm, qtown]
---
```

Push to GitHub, enable GitHub Pages in repo settings → Source: `main` branch → `/docs` folder.

---

### Step 2 — Publish to dev.to

1. Go to dev.to → New Post
2. Paste the markdown from `docs/blog-post-v1-closeout.md`
3. Add front matter in dev.to's editor:
   - Tags: `ai`, `programming`, `llm`, `opensource`
   - Series: Leave blank for now
4. Set canonical URL to your personal blog URL (dev.to → Edit → Canonical URL field) — this prevents SEO cannibalization
5. Add a cover image — screenshot of qtown.ai or the architecture diagram
6. **Do not publish yet** — schedule it for 9am ET Tuesday (peak dev.to traffic window)

---

### Step 3 — Submit to Hacker News

**Timing:** Submit Tuesday or Wednesday, 8-10am ET. This is when HN mods are active and the submission gets maximum eyes before drifting.

**Submission:**

1. URL: Your personal blog post URL (not dev.to — HN penalizes dev.to links)
2. Title: `I Let an AI Write 88% of My Code. Here's What Happened.`
   - Alternatively: `Qtown: 1,451 commits, 88% written by a local LLM running on my GPU`
   - The second title is more HN-friendly (concrete, technical, no clickbait feel)
3. Comment immediately after posting with context: the model setup, total cost ($0 because local), what failed, what surprised you

**Reddit:**

- r/programming: Good for the technical writeup
- r/MachineLearning: Good if you angle it toward "local LLM as a developer agent"
- r/selfhosted: Good for the Ollama/local angle

Post title for Reddit: `I built a fully autonomous town simulation where an AI wrote 88% of the code using a local LLM (no cloud, no API keys)`

---

### Step 4 — Twitter/X Thread

Thread structure (12 tweets):

```
1/ I spent the last few months building a town simulation where an AI named Ralph 
   wrote 88% of the code. 1,451 commits. Zero cloud LLM costs. Here's what I learned:

2/ The project: Qtown. A 50x50 isometric town where NPCs eat, sleep, trade, 
   commit crimes, and gossip without any human-written behavior scripts.

3/ Ralph is a Python loop: read story → call Ollama (local LLM) → write code → 
   run tests → commit. No memory. No planning system. Just a tight loop.

4/ The model: Qwen 3.5:27b, running locally on my GPU. Not GPT-4. Not Claude.
   A model you can download and run yourself for free.

5/ The result after 510 stories shipped:
   • 88% of code written autonomously  
   • 1,451 commits
   • $0 LLM costs (fully local)
   • One test failure would halt until fixed

6/ What actually matters: the scaffold, not the model.
   Ralph works because the loop is tight and the feedback is immediate.
   A smarter model in a bad scaffold beats a worse model in a good one? Nope. 
   It's the opposite.

7/ v2 is a complete rewrite: polyglot microservices.
   Go for the order book. Rust for event validation. 
   Kafka for async flows. gRPC for service-to-service.
   9 services, 12 languages, 194 stories — all written by Ralph v2.

8/ Ralph v2 runs 3 parallel workers, routes to 4 different models 
   based on task type, and detects cross-service story conflicts automatically.

9/ The proof system: every performance claim is a runnable test.
   "Go order book handles 10K orders/sec" = go test -bench BenchmarkOrderBook
   "Fortress has zero unsafe blocks" = grep -r 'unsafe' src/ | wc -l → must be 0

10/ Full writeup: [link to blog post]
    Live: qtown.ai
    Code: github.com/kbadinger/qtown

11/ Biggest surprise: Ralph is good at boring code.
    Migrations, boilerplate, CRUD routes, test fixtures.
    The stuff that takes a human an hour takes Ralph 3 minutes.
    He's bad at: anything requiring system-level architectural reasoning.

12/ The answer to "can an AI actually be a developer?" is:
    It depends entirely on how you define the scaffold.
    With the right loop, a 27B local model ships production-quality code.
    That's the experiment. qtown.ai is the proof.
```

---

### Step 5 — LinkedIn Post

LinkedIn is for recruiters and hiring managers. Shorter, more impact-focused:

```
6 months ago I set a goal: build a real system. Not a tutorial project. 
Not a CRUD app. Something that proves I can architect and ship complex software.

The result: Qtown — a polyglot microservices platform with 9 services 
(Python, Go, Rust, TypeScript), 27 Kafka topics, gRPC inter-service comms, 
and a GraphQL gateway. 420 files, ~101K lines.

The twist: 88% of the code was written by an AI named Ralph — a local LLM 
agent I built that runs on my GPU. Zero cloud costs. Zero API keys.

Full writeup: [link]
Code: github.com/kbadinger/qtown
Live: qtown.ai

#engineering #ai #llm #softwareengineering
```

---

## Priority 4 — Get Docker Compose Actually Running

### Prerequisites Check

```bash
# Verify all tools are installed and on the right versions
docker --version          # Need 24+
docker compose version    # Need v2 (not docker-compose v1)
go version                # Need 1.22+
rustc --version           # Need stable (1.77+)
python3 --version         # Need 3.11+
node --version            # Need 22+
buf --version             # Need 1.x

# If buf is missing:
brew install bufbuild/buf/buf
# or
npm install -g @bufbuild/buf
```

### Step 1 — Boot Infrastructure First

```bash
cd qtown

# Pull all images first (avoids partial failures during up)
docker compose -f docker-compose.deps.yml pull

# Start infrastructure
docker compose -f docker-compose.deps.yml up -d

# Wait for all health checks to pass (takes ~60s for Kafka + ES)
watch -n 2 'docker compose -f docker-compose.deps.yml ps'
```

**Expected healthy state:**

```
NAME                    SERVICE         STATUS      PORTS
qtown-elasticsearch     elasticsearch   healthy     0.0.0.0:9200->9200/tcp
qtown-kafka             kafka           healthy     0.0.0.0:9092->9092/tcp
qtown-kafka-ui          kafka-ui        running     0.0.0.0:8088->8080/tcp
qtown-postgres          postgres        healthy     0.0.0.0:5432->5432/tcp
qtown-redis             redis           healthy     0.0.0.0:6379->6379/tcp
```

**Validate each service:**

```bash
# PostgreSQL
psql postgresql://qtown:qtown_dev@localhost:5432/qtown -c "SELECT version();"
# Expected: PostgreSQL 16.x

# Redis
redis-cli ping
# Expected: PONG

# Kafka
docker exec qtown-kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --list
# Expected: (empty or auto-created topics)

# Elasticsearch
curl -s http://localhost:9200/_cluster/health | python3 -m json.tool
# Expected: "status": "green" or "yellow" (yellow is fine for single-node)

# Kafka UI
open http://localhost:8088
```

---

### Step 2 — Initialize Kafka Topics

```bash
chmod +x infra/kafka-init.sh
./infra/kafka-init.sh
```

**Expected output:** 27 lines like `Created topic qtown.npc.travel`. If topics already exist: `Topic 'qtown.npc.travel' already exists` — that's fine, script is idempotent.

---

### Step 3 — Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with these values for local dev:

```bash
# Required — these differ from .env.example
DATABASE_URL=postgresql://qtown:qtown_dev@localhost:5432/qtown
KAFKA_BROKERS=localhost:9092
REDIS_URL=redis://localhost:6379
ELASTICSEARCH_URL=http://localhost:9200

# Academy needs Ollama
OLLAMA_HOST=http://localhost:11434

# Keep these as-is for local
QTOWN_ENV=development
QTOWN_ADMIN_KEY=local-dev-key-change-me

# Optional but useful
COMFY_URL=http://127.0.0.1:8188
```

> **Important:** Docker Compose uses `kafka:9092` (internal Docker DNS) for service-to-service communication. Your local `.env` uses `localhost:9092`. Docker Compose injects the right values via the `environment:` section in `docker-compose.yml` — your `.env` is for running services outside Docker.

---

### Step 4 — Build Service Images

```bash
# Build all images (takes 5-15 min first time due to Rust compilation)
docker compose build

# Or build in parallel for speed
docker compose build --parallel

# Build individual services for debugging:
docker compose build town-core
docker compose build market-district
docker compose build fortress  # This will be the slowest (~5 min for Rust release build)
docker compose build academy
docker compose build tavern
docker compose build cartographer
docker compose build library
docker compose build asset-pipeline
```

**Common build failures:**

| Error | Fix |
|---|---|
| `error[E0xxxxx]` in fortress build | Rust compile error — run `cd services/fortress && cargo build --release` locally to see full error |
| `go: no module providing X` in market-district | Run `cd services/market-district && go mod tidy` first |
| `pip install` fails in Python services | Check that `requirements.txt` is present in the service dir |
| `buf: command not found` in proto generation | `brew install bufbuild/buf/buf` |
| Dashboard `nuxi: not found` | Check `dashboard/package.json` — run `cd dashboard && npm install` first |

---

### Step 5 — Generate Protobuf Code

Before starting services, proto-generated code must exist:

```bash
make proto

# Expected output per language:
# proto/gen/go/     — used by market-district
# proto/gen/python/ — used by town-core, academy, library, asset-pipeline
# proto/gen/ts/     — used by cartographer, tavern, dashboard

# Verify
ls proto/gen/go/qtown/
ls proto/gen/python/qtown/
ls proto/gen/ts/qtown/
```

---

### Step 6 — Start All Services

```bash
# Start full stack (deps + all services)
docker compose up -d

# Watch startup sequence
docker compose logs -f --tail 20
```

**Expected startup order and health check timeline:**

```
t=0s    postgres, redis, kafka, elasticsearch start
t=15s   postgres, redis healthy
t=30s   kafka healthy, kafka-init runs
t=40s   elasticsearch healthy
t=45s   town-core starts (waits for postgres + kafka health)
t=50s   market-district, fortress start (waits for kafka + postgres)
t=55s   academy starts (waits for postgres + kafka)
t=60s   tavern, library, cartographer, asset-pipeline start
t=90s   all services healthy
```

**Check all health endpoints:**

```bash
# Town Core
curl -s http://localhost:8000/health | python3 -m json.tool

# Market District metrics
curl -s http://localhost:6060/health

# Fortress
curl -s http://localhost:8080/health

# Academy
curl -s http://localhost:8001/health

# Cartographer (GraphQL)
curl -s http://localhost:4000/health

# Library
curl -s http://localhost:8003/health

# Kafka UI
open http://localhost:8088

# Elasticsearch
curl -s http://localhost:9200/_cat/indices?v
```

---

### Step 7 — Common Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| `town-core` exits immediately | DB migration fails | `docker compose logs town-core` — look for SQLAlchemy error. Run `docker compose exec postgres psql -U qtown -c "\dt"` to check schema |
| `fortress` OOMKilled | Docker memory limit too low for Rust binary | Add to fortress service in docker-compose.yml: `mem_limit: 512m` |
| `kafka` never becomes healthy | KRaft init fails | `docker compose logs kafka \| grep -i error`. Try `docker compose down -v` (deletes volumes) then `up` again |
| Academy `OLLAMA_HOST` connection refused | Ollama not running on host | Start Ollama: `ollama serve` in a separate terminal |
| Cartographer can't reach town-core | GraphQL resolver timeout | Check town-core is healthy first, then restart cartographer: `docker compose restart cartographer` |
| Port already in use | Existing process on port | `lsof -ti:8000 \| xargs kill` |
| `init-db.sql` error | Schema mismatch | `docker compose down -v && docker compose up -d` (wipes DB volumes — dev only) |

---

### Step 8 — Validate the Full Stack

```bash
# Run the make test targets against running services
make test

# Run proof targets
make proof-market
# Expected: PASS: Order book benchmark shows <5ms p99

make proof-fortress
# Expected: PASS: Zero unsafe blocks
# + PASS: Validation benchmark

# Test the GraphQL gateway
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ world { tick day weather } }"}' \
  | python3 -m json.tool
```

---

## Priority 5 — Activate Ralph v2 Locally

### Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| GPU VRAM | 8GB (qwen3-coder-next only) | 24GB (all models loaded simultaneously) |
| RAM | 32GB | 64GB |
| Disk | 80GB free | 120GB free |
| OS | Linux or macOS (Apple Silicon) | Linux with CUDA GPU |

**Without a GPU:** qwen3-coder-next will run on CPU, but expect 10-30 minute story completion times vs 2-3 minutes on GPU. `deepseek-r1:14b` and `qwen3.5:27b` will be very slow.

---

### Step 1 — Install and Start Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama server (keep this running in a separate terminal)
ollama serve

# Verify
curl -s http://localhost:11434/api/version
# Expected: {"version":"0.x.x"}
```

---

### Step 2 — Pull Models

```bash
chmod +x ralph/v2_setup_models.sh
./ralph/v2_setup_models.sh
```

This pulls 5 models (~60GB total). Expect 30-90 minutes on a fast connection. The script is:

```bash
# What it pulls:
ollama pull qwen3-coder-next    # ~8GB  — primary coding model
ollama pull qwen3.5:27b         # ~20GB — architecture/design
ollama pull qwen3.5:35b-a3b     # ~16GB — NPC content/dialogue
ollama pull deepseek-r1:14b     # ~16GB — debugging/reasoning
ollama pull nomic-embed-text    # ~274MB — embeddings for RAG
```

**If you have limited disk:** Pull only the primary model first:

```bash
ollama pull qwen3-coder-next
ollama pull nomic-embed-text  # Required for Academy RAG
```

The orchestrator will fall back gracefully if heavy/debug models aren't available.

**Verify all models:**

```bash
ollama list
# Expected:
# NAME                    ID              SIZE    MODIFIED
# qwen3-coder-next:latest xxxxxxxx        8.2 GB  X minutes ago
# qwen3.5:27b:latest      xxxxxxxx        20.1 GB ...
# deepseek-r1:14b:latest  xxxxxxxx        16.0 GB ...
# qwen3.5:35b-a3b:latest  xxxxxxxx        16.4 GB ...
# nomic-embed-text:latest xxxxxxxx        274 MB  ...
```

---

### Step 3 — Start Infrastructure

```bash
# Must be running before Ralph starts
docker compose -f docker-compose.deps.yml up -d

# Wait for kafka healthy
docker compose -f docker-compose.deps.yml ps
# All should show "healthy"
```

---

### Step 4 — Test Ralph on a Single Story

Before letting Ralph loose on all pending stories, test with one story to verify the loop works:

```bash
# Check what stories are available
python3 -c "
import json
d = json.load(open('ralph/worklist.json'))
s = d['stories']
pending = [x for x in s if x['status'] == 'pending']
print(f'Pending: {len(pending)}')
if pending:
    print('First pending:', json.dumps(pending[0], indent=2))
"
```

If all 194 stories are `complete`, Ralph is already done. You'd be running him on new stories added to `worklist.json`.

**To add a test story and run it:**

```bash
# Add a new story to worklist.json:
# Open ralph/worklist.json, find the "stories" array, add at the end:
{
  "id": "TEST-001",
  "title": "Add a /api/ping endpoint to town-core that returns {\"pong\": true}",
  "service": "town-core",
  "language": "python",
  "deps": [],
  "status": "pending",
  "phase": 6,
  "group": "6.1"
}
```

```bash
# Run Ralph in dry-run mode first (no code written, just plans)
./ralph/v2_start.sh --dry-run

# Then run for real with 1 parallel worker
RALPH_MAX_PARALLEL=1 ./ralph/v2_start.sh
```

---

### Step 5 — Run Ralph at Full Speed

```bash
# Standard run — 3 parallel workers
./ralph/v2_start.sh

# Or with more workers if your machine can handle it
./ralph/v2_start.sh --max-parallel 5

# Pipe logs to jq for readability
./ralph/v2_start.sh 2>&1 | tee ralph.log | jq '.'
```

---

### Step 6 — Monitor Ralph's Progress

```bash
# Real-time progress check
python3 -c "
import json
d = json.load(open('ralph/worklist.json'))
s = d['stories']
by_status = {}
for story in s:
    by_status.setdefault(story['status'], []).append(story['id'])
for status, ids in sorted(by_status.items()):
    print(f'{status}: {len(ids)} stories')
print(f'Total: {len(s)}')
"

# Watch git commits as Ralph commits
watch -n 5 'git log --oneline -10'

# Check if Ralph needs help
cat .ralph-needs-help.json 2>/dev/null || echo "No escalations"

# Check Ralph's log
tail -f ralph.log | jq '.level, .message'
```

**Controlling Ralph at runtime** (via `HUMAN.md`):

```bash
# Pause after current story completes
echo -e "action: pause\nreason: reviewing work" > HUMAN.md

# Skip a stuck story
echo -e "action: skip\nstory_id: P3-042\nreason: known issue" > HUMAN.md

# Resume
echo -e "action: none" > HUMAN.md
```

---

## Priority 6 — Integration Testing

### Step 1 — Install Integration Test Dependencies

```bash
# Python integration testing
pip install pytest pytest-asyncio httpx testcontainers kafka-python grpcio

# For the test suite in /tests
cd tests
pip install -r requirements.txt 2>/dev/null || pip install pytest pytest-asyncio httpx
```

---

### Step 2 — Core Cross-Service Flows to Test

**Flow 1: Market District trade → Kafka → Town Core**

This is the most critical flow. A trade in Market District must publish to `qtown.economy.trade`, which Town Core consumes to update NPC gold.

```python
# tests/integration/test_market_town_core_flow.py
import pytest
import httpx
import asyncio
from kafka import KafkaConsumer, KafkaProducer
import json

MARKET_GRPC = "localhost:50051"
TOWN_CORE_URL = "http://localhost:8000"
KAFKA_BROKER = "localhost:9092"

@pytest.mark.asyncio
async def test_trade_propagates_to_town_core():
    """A trade event published to Kafka must update NPC gold in Town Core."""
    consumer = KafkaConsumer(
        "qtown.economy.trade.settled",
        bootstrap_servers=KAFKA_BROKER,
        auto_offset_reset="latest",
        consumer_timeout_ms=10000,
    )
    
    # Trigger a trade via Market District gRPC
    # (use grpc channel to call PlaceOrder RPC)
    import grpc
    from proto.gen.python.qtown import market_pb2, market_pb2_grpc
    
    channel = grpc.insecure_channel(MARKET_GRPC)
    stub = market_pb2_grpc.MarketServiceStub(channel)
    
    # Place a buy order
    order = stub.PlaceOrder(market_pb2.PlaceOrderRequest(
        npc_id="test-npc-1",
        item_type="food",
        order_type="BUY",
        quantity=1,
        price=10,
    ))
    assert order.order_id is not None
    
    # Wait for settlement event on Kafka
    settled = None
    for msg in consumer:
        settled = json.loads(msg.value)
        break
    
    assert settled is not None, "Trade settlement event not received within 10s"
    assert settled["item_type"] == "food"
    
    consumer.close()
```

**Flow 2: Fortress validation pipeline**

```python
# tests/integration/test_fortress_validation.py
import grpc
from proto.gen.python.qtown import fortress_pb2, fortress_pb2_grpc

def test_fortress_validates_event():
    channel = grpc.insecure_channel("localhost:50052")
    stub = fortress_pb2_grpc.FortressServiceStub(channel)
    
    # Valid event — should pass
    result = stub.ValidateEvent(fortress_pb2.ValidationRequest(
        event_type="NPC_TRADE",
        npc_id="npc-001",
        payload='{"item": "food", "quantity": 1, "price": 10}'
    ))
    assert result.valid == True
    assert result.error_code == ""
    
    # Invalid event — should fail
    result = stub.ValidateEvent(fortress_pb2.ValidationRequest(
        event_type="NPC_TRADE",
        npc_id="npc-001",
        payload='{"item": "gold", "quantity": -1}'  # negative quantity
    ))
    assert result.valid == False
```

**Flow 3: Academy inference**

```python
# tests/integration/test_academy.py
import httpx

def test_academy_generates_npc_dialogue():
    resp = httpx.post("http://localhost:8001/api/generate/dialogue", json={
        "npc_id": "npc-001",
        "context": "The baker is greeting a customer at the market.",
        "mood": "happy"
    }, timeout=30.0)
    assert resp.status_code == 200
    data = resp.json()
    assert "dialogue" in data
    assert len(data["dialogue"]) > 0

def test_academy_uses_local_model():
    """Verify ≥85% of requests route to local Ollama, not cloud."""
    resp = httpx.get("http://localhost:8001/metrics/model-routing", timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["local_pct"] >= 85, f"Local routing {data['local_pct']}% < 85%"
```

---

### Step 3 — Run Integration Tests Against Live Stack

```bash
# Make sure full stack is up
docker compose up -d
# Wait for all services healthy

# Run integration tests
pytest tests/ -v --tb=short -x

# Run with markers to target specific flows
pytest tests/ -v -m "integration" --tb=short

# Run proof tests
make proof
```

---

### Step 4 — Testcontainers for CI (No Pre-running Docker Needed)

For integration tests that need to spin up their own infra:

```python
# tests/conftest.py
import pytest
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def kafka():
    with KafkaContainer() as kafka:
        yield kafka.get_bootstrap_server()

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        yield pg.get_connection_url()
```

```bash
pip install testcontainers[kafka,postgres]
pytest tests/integration/ -v
```

---

## Priority 7 — CI/CD Pipeline Validation

### Step 1 — Verify All 9 CI Jobs Pass

```bash
# Create a test branch to trigger CI without touching main
git checkout -b ci-validation-test
git commit --allow-empty -m "ci: trigger validation run"
git push origin ci-validation-test

# Open the Actions tab
open https://github.com/kbadinger/qtown/actions
```

**Expected:** All 9 jobs green within 15 minutes. The `docker-build` job only runs on PRs, so create a PR from this branch to trigger it.

```bash
gh pr create --title "ci: validate all jobs" \
  --body "Trigger full CI including docker-build job" \
  --base main --head ci-validation-test
```

---

### Step 2 — Fix Common CI Failures

**proto-lint fails:**

```bash
# Run locally first
cd proto && buf lint
buf breaking --against 'https://github.com/kbadinger/qtown.git#subdir=proto,branch=main'

# If breaking changes are intentional, update the breaking check:
# In .github/workflows/ci.yml, change the breaking check to reference a specific commit:
buf breaking --against '.git#subdir=proto,ref=<commit-before-breaking-change>'
```

**test-tavern / test-cartographer fail with `|| true`:**

Check the CI file — these have `|| true` on test and lint steps, meaning they're non-blocking. If you want them to actually gate PRs, remove `|| true`:

```yaml
# In .github/workflows/ci.yml:
- name: Test
  run: cd services/tavern && npm test  # Remove: || true
```

**Rust build slow in CI (5-10 min):**

The `Swatinem/rust-cache@v2` action is already in the workflow, but it only caches after the first run. After the first green run, Rust builds should be ~2 minutes.

**test-library fails:**

```yaml
# Current CI has a fragile install step:
run: cd services/library && pip install -e ".[dev]" || pip install -r requirements.txt 2>/dev/null && pip install pytest ruff
# This is brittle. If library/ has a pyproject.toml, fix it:
run: |
  cd services/library
  pip install -e ".[dev]"
```

---

### Step 3 — Set Up GHCR Push

The `docker-push` job in CI is already written — it pushes to `ghcr.io/kbadinger/qtown/SERVICE:latest` on merges to main. To enable it:

1. Go to GitHub → Settings → Actions → General → Workflow permissions → set to "Read and write permissions"

2. Or add a PAT: GitHub → Settings → Developer Settings → Personal Access Tokens → New token with `write:packages` scope. Add as repo secret `GHCR_TOKEN`.

3. Verify in `.github/workflows/ci.yml` — the docker-push job should have:

```yaml
docker-push:
  if: github.ref == 'refs/heads/main'
  needs: [proto-lint, test-town-core, test-market, test-fortress, test-tavern, test-academy, test-cartographer, test-library, test-dashboard]
  steps:
    - uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}  # GITHUB_TOKEN works if permissions are set
```

**Verify push worked:**

```bash
# After a main branch merge
open https://github.com/kbadinger/qtown/pkgs/container
# Should show packages for each service
```

---

### Step 4 — Branch Protection Rules

Go to GitHub → Settings → Branches → Add rule for `main`:

- [x] Require a pull request before merging
- [x] Require status checks to pass before merging
  - Required checks: `proto-lint`, `test-town-core`, `test-market`, `test-fortress`, `test-academy`
  - Note: leave tavern/cartographer/library/dashboard as optional until `|| true` is removed
- [x] Require branches to be up to date before merging
- [x] Restrict who can push to matching branches (just yourself)

```bash
# Via gh CLI
gh api repos/kbadinger/qtown/branches/main/protection \
  --method PUT \
  --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["proto-lint", "test-town-core", "test-market", "test-fortress", "test-academy"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
EOF
```

---

## Priority 8 — Kubernetes Deployment (If Pursuing)

### Prerequisites

```bash
# Install minikube for local K8s testing
brew install minikube kubectl helm

# Install Linkerd CLI (service mesh)
brew install linkerd

# Start minikube with enough resources for this stack
minikube start --cpus=8 --memory=16384 --driver=docker
minikube addons enable metrics-server
```

---

### Step 1 — Validate Helm Charts Locally

```bash
# Check the Helm chart structure
ls infra/helm/qtown/

# Lint the charts
helm lint infra/helm/qtown/

# Dry run to see what would be deployed
helm install qtown infra/helm/qtown/ \
  --namespace qtown \
  --create-namespace \
  --dry-run \
  --debug \
  2>&1 | head -200
```

**Fix common Helm issues:**

```bash
# If values.yaml has placeholder values:
helm install qtown infra/helm/qtown/ \
  --namespace qtown \
  --create-namespace \
  --set image.registry=ghcr.io \
  --set image.tag=latest \
  --dry-run
```

---

### Step 2 — Deploy to Minikube

```bash
# Build and push images to minikube's local registry
eval $(minikube docker-env)
docker compose build  # builds into minikube's Docker daemon

# Install the Linkerd service mesh
linkerd check --pre  # pre-flight checks
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check  # wait until all checks pass

# Install Qtown
helm install qtown infra/helm/qtown/ \
  --namespace qtown \
  --create-namespace \
  --set image.pullPolicy=Never  # Use local images

# Watch the rollout
kubectl -n qtown get pods --watch

# Port-forward to test
kubectl -n qtown port-forward svc/cartographer 4000:4000 &
kubectl -n qtown port-forward svc/town-core 8000:8000 &

# Test
curl -s http://localhost:8000/health
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ world { tick } }"}'
```

---

### Step 3 — AWS Setup via Terraform

The Terraform config is at `infra/terraform/`. Before applying:

```bash
# Install AWS CLI and Terraform
brew install awscli terraform

# Configure AWS credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1 or us-west-2)

# Inspect the Terraform config
cat infra/terraform/main.tf
cat infra/terraform/variables.tf

# Initialize
cd infra/terraform
terraform init

# Plan — see what will be created
terraform plan -var="region=us-east-1" -out=tfplan

# Review the plan carefully before applying
terraform show tfplan | head -100
```

**Expected resources from the Terraform plan:**

- EKS cluster (3 nodes, t3.medium = ~$150/mo)
- RDS Postgres (db.t3.micro = ~$25/mo)
- ElastiCache Redis (cache.t3.micro = ~$25/mo)
- MSK Kafka (kafka.t3.small = ~$100/mo)
- Application Load Balancer (~$20/mo)
- **Total estimate: ~$350-450/month for a minimal production setup**

```bash
# Apply only if you're ready for the cost
terraform apply tfplan
```

---

### Step 4 — Cost Reduction Options

If $350/mo is too much for a portfolio project:

1. **EKS + Spot instances:** Add `capacity_type = "SPOT"` to node group config → 60-70% cost reduction
2. **Single t3.medium node:** Enough for demo purposes, not HA
3. **RDS → local Postgres on the node:** Not production-grade but fine for demos
4. **Stay on Railway:** Railway's paid plan is ~$20/mo for a small workload. Keep v1 on Railway, document that v2 is K8s-ready but run it locally.

---

## Priority 9 — Portfolio Presentation

### Resume Bullet Points

Copy-paste these (customize the numbers to match actual benchmarks you've run):

```
• Built Qtown: polyglot microservices simulation platform — 9 services (Python/Go/Rust/TypeScript), 
  27 Kafka topics, gRPC inter-service comms, GraphQL gateway, 420 files, ~101K LOC across 12 languages

• Engineered Go order book service with verified <5ms p99 latency at 10K orders/sec; 
  Rust event validation service at 100K validations/sec with zero unsafe blocks (grep-verified in CI)

• Built Ralph, an AI developer agent that autonomously wrote 88% of the v1 codebase 
  (1,451 commits, 510 stories) and 100% of the v2 microservices using local LLMs via Ollama

• Implemented v2 Ralph with 3-parallel-worker orchestration, 4-model routing, 
  conflict detection across services, and per-model/per-language success rate tracking

• Deployed to production (qtown.ai) via Railway + Cloudflare CDN; 
  CI/CD pipeline with 9 parallel GitHub Actions jobs including GHCR image push
```

---

### Interview Talking Points

**"Walk me through the architecture"**

> "Qtown v2 is a microservices platform where each service is written in the language best suited to its domain. The Go service handles the order book — Go's goroutines are a natural fit for concurrent order matching. The Rust service validates every event before it hits the state layer — Rust's ownership model makes it impossible to write a null dereference in that path, and I verify that in CI with a grep check. The Python services handle simulation logic, AI inference, and search. Everything communicates over Kafka for async flows and gRPC for synchronous service-to-service calls. The only public-facing endpoint is a GraphQL gateway in TypeScript that fans out queries to up to five services and returns a unified response."

**"Why so many languages?"**

> "Performance requirements drove it. The order book needs to handle 10,000 orders per second — I benchmarked Python vs Go for that and Go was 50x faster. Event validation needs to be bulletproof — Rust's type system enforces safety guarantees at compile time that you simply can't get in Python or Go. For the simulation engine and AI inference, Python has the ecosystem. The polyglot choice isn't aesthetic — each language is justified by a benchmark."

**"You said an AI wrote this — did you actually write any of it?"**

> "I wrote the architecture, the story specs, and Ralph — the agent. Ralph wrote the implementation. The distinction is: I made every design decision. What services to create, what protocols to use, where to put the boundaries. Ralph executed those decisions story by story. That's actually how real software teams work — architects design systems, developers implement them. I played the architect role. Ralph played the developer role. The proof is in the commit history: every commit has a story reference, and the stories are in `worklist.json`."

**"How do you know it actually works?"**

> "The proof system. Every performance claim in the README has a runnable test. `make proof-market` runs a 30-second Go benchmark and asserts p99 latency. `make proof-fortress` checks that the unsafe block count is literally zero. The Academy service has a live metrics endpoint that reports local model routing percentage — CI fails if it drops below 85%. Claims without proofs are marketing copy. I didn't want marketing copy."

---

### 5-Minute Demo Script

**Setup before the demo:**

```bash
# Start everything
docker compose up -d
# Wait for all healthy (2 min)

# Open these in browser tabs:
open http://localhost:3000          # Dashboard (Nuxt 3)
open http://localhost:8088          # Kafka UI
open http://localhost:4000/graphql  # GraphQL sandbox (Apollo Studio)
open https://qtown.ai               # Live production site
```

**Demo flow:**

1. **(0:00-0:30) — The live site**
   - "This is qtown.ai — it's running on Railway right now."
   - Show `/api/world` response in a browser: "87KB of live game state — NPCs, buildings, world tick."
   - "The landing page pulls this live data."

2. **(0:30-1:30) — Architecture overview**
   - Open the Dashboard at `localhost:3000`
   - "Each panel here is a separate service responding to a GraphQL query from the gateway."
   - Show Kafka UI at `localhost:8088` — "27 topics. Every state change flows through Kafka."
   - "The market district is Go — order book runs here. Let me show you the benchmark."
   - Run: `make proof-market` — show the output

3. **(1:30-2:30) — The Rust service**
   - `make proof-fortress` — show it pass
   - `grep -r 'unsafe' services/fortress/src/ | wc -l` — show 0
   - "Rust enforces that at compile time. CI enforces it on every PR."

4. **(2:30-3:30) — Ralph**
   - Show `ralph/worklist.json` — "194 stories, all complete."
   - Show a git log: `git log --oneline | head -20`
   - "Most of these commits are Ralph's. He runs on a local LLM — no cloud costs."
   - Show `ralph/v2_model_router.py` briefly: "Routes each story to a different model based on task type."

5. **(3:30-4:30) — CI/CD**
   - Open GitHub Actions: `open https://github.com/kbadinger/qtown/actions`
   - "9 parallel jobs — proto lint, per-service test and lint, Docker build, GHCR push."
   - Show the zero-unsafe check in the CI YAML

6. **(4:30-5:00) — Close**
   - "The whole point was to prove I can build and ship complex systems. This is running, benchmarked, and version-controlled. The code is at github.com/kbadinger/qtown."

---

### What Interviewers Actually Care About

In approximate order of importance for senior/staff engineering roles:

1. **Architecture decisions** — Can you justify why each service exists and why it uses its tech stack? Yes. You have benchmarks.
2. **Production mindset** — Health checks, CI/CD, observability (Jaeger, Prometheus, Grafana). All present.
3. **That you actually built it** — The 1,451 commit history, the worklist, the proof system. Hard to fake.
4. **Communication** — Can you explain the architecture in 5 minutes to a non-expert? Practice the demo script above until you can do it cleanly.
5. **What you'd do differently** — "Ralph v1 used a single model. I'd use the routing system from v2 from day one. And I'd have written integration tests earlier — the testcontainers setup would have caught three cross-service bugs I found by hand."

---

## Quick Reference

### Daily Commands

```bash
# Check production
curl -so /dev/null -w "%{http_code}" https://qtown.ai/health

# Start local dev
docker compose -f docker-compose.deps.yml up -d
make build
docker compose up -d

# Check all service health
for port in 8000 8001 8003 8080 6060; do
  echo "Port $port: $(curl -so /dev/null -w '%{http_code}' http://localhost:$port/health)"
done

# Run tests
make test

# Run proofs
make proof

# Check Ralph worklist
python3 -c "
import json; d = json.load(open('ralph/worklist.json')); s = d['stories']
by_status = {}
for x in s: by_status.setdefault(x['status'], 0); by_status[x['status']] += 1
print(by_status)
"

# View Railway logs
railway logs --tail 100

# Push a fix
git add -p && git commit -m "fix: <description>" && git push origin main
```

### Key File Locations

| What | Where |
|---|---|
| FastAPI v1 app | `v1/engine/main.py` |
| Landing page (coming-soon) | `landing/` |
| Blog post (source) | `docs/blog-post-v1-closeout.md` |
| Blog post (publish target) | `~/Projects/KevinBadingerWebsite/content/blog/2026-05-05-qtown-v1-an-ai-wrote-88-percent.md` |
| Domain handover guide | `docs/handover-domain-flip.md` |
| v2 audit (TBD) | `docs/v2-audit.md` |
| Docker Compose (all) | `docker-compose.yml` |
| Docker Compose (infra only) | `docker-compose.deps.yml` |
| Ralph v2 orchestrator | `ralph/v2_orchestrator.py` |
| Ralph v2 worklist | `ralph/worklist.json` |
| Ralph v1 orchestrator | `v1/ralph/ralph.py` |
| CI workflow | `.github/workflows/ci.yml` |
| Helm chart | `infra/helm/qtown/` |
| Terraform | `infra/terraform/` |
| Kafka init script | `infra/kafka-init.sh` |
| Railway config (v1) | `v1/railway.json` |
| Railway deploy notes | `v1/DEPLOY.md` |
| Port map | README.md → Port Map section |
| Makefile targets | `Makefile` (40+ targets, all documented in README) |

### Service Port Map

| Service | Port | Protocol |
|---|---|---|
| Town Core | 8000 | HTTP/FastAPI |
| Academy | 8001 | HTTP/FastAPI |
| Library | 8003 | HTTP |
| Fortress | 8080 (HTTP), 50052 (gRPC) | HTTP + gRPC |
| Market District | 50051 (gRPC), 6060 (metrics) | gRPC + HTTP |
| Tavern | 3001 | WebSocket |
| Cartographer | 4000 | GraphQL/HTTP |
| Dashboard | 3000 | HTTP/SSR |
| Kafka | 9092 | Kafka protocol |
| Postgres | 5432 | PostgreSQL |
| Redis | 6379 | Redis protocol |
| Elasticsearch | 9200 | HTTP |
| Kafka UI | 8088 | HTTP |

---

## Distribution — After the Blog Post is Live

The v1 closeout post lives at `kevinbadinger.com/blog/qtown-v1-an-ai-wrote-88-percent` (publish target). Once that URL is live and indexed, fan it out:

### Substack

1. Create a new post on Kevin's Substack.
2. Title: "I Let an AI Write 88% of My Code. Here's What Happened."
3. Body: paste the markdown from `~/Projects/KevinBadingerWebsite/content/blog/2026-05-05-qtown-v1-an-ai-wrote-88-percent.md` (drop the frontmatter; Substack ignores it).
4. **Set canonical URL** to `https://kevinbadinger.com/blog/qtown-v1-an-ai-wrote-88-percent` (Settings → SEO → Canonical URL). This avoids SEO cannibalization — search engines treat kevinbadinger.com as the source of truth.
5. Publish. Schedule for the same week as the kbadinger.com publish.

### Hacker News

Wait at least 24 hours after kbadinger.com is live so the post is indexed.

- Title: `Show HN: I let an AI write 88% of my town simulation`
- URL: `https://kevinbadinger.com/blog/qtown-v1-an-ai-wrote-88-percent`
- First comment (post immediately after submission): brief context — what Qtown is, link to repo, link to v1.qtown.ai live demo, what makes Ralph different from a copilot.
- Don't submit Friday/Saturday/Sunday — weekday mornings (US) get more eyeballs.

### Dev.to

- Title: same
- Cover image: same hero image used on kbadinger.com
- **Set canonical URL** to `https://kevinbadinger.com/blog/qtown-v1-an-ai-wrote-88-percent`
- Tags: `ai`, `agents`, `python`, `experimentation`
- Cross-post via the Dev.to GitHub action if Kevin uses one, otherwise paste manually.

### LinkedIn / Twitter / X

- Quote-style: "I let an AI named Ralph write 88% of a town simulation. 1,451 commits. 550 stories. Zero cloud LLM cost. Wrote up what worked and what broke: kevinbadinger.com/blog/qtown-v1-an-ai-wrote-88-percent"
- LinkedIn: post in full long-form using the article feature, or share the link with a 2-3 sentence intro pulled from the post's hook.

### Reddit

- r/MachineLearning, r/programming, r/LocalLLaMA — the local-Ollama angle is the hook for the LocalLLaMA crowd.
- Always reply with substance to comments — Reddit downvotes drive-by self-promotion.

### Tracking

- Add UTM parameters per channel: `?utm_source=substack&utm_medium=newsletter`, `?utm_source=hn`, etc. on the kbadinger.com URL when sharing.
- Watch GA / Plausible (whichever kbadinger.com uses) for which channel actually drives readers vs. clicks.
