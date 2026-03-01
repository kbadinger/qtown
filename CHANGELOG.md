# Human Intervention Log

Every time a human or Claude (not Qwen) touches the codebase, it gets logged here. This is the transparency record — proof of what Qwen built vs. what needed human help.

Ralph auto-appends entries when `HUMAN.md` actions are used (instruction, skip, retry, pause).

## Format

```
### YYYY-MM-DD HH:MM — [WHO] — [ACTION]
What was done and why.
Files touched: list
```

---

### 2025-02-28 — Human + Claude — Scaffolding (Day 0)
Full project scaffolding before Ralph takes over. No game logic written — only safety, plumbing, and presentation.
- Created all ralph/ modules (orchestrator, alerter, deployer, file_writer, test_runner, cost_tracker)
- Created engine/ skeleton (main.py, db.py, auth.py, models.py, templates)
- Created prd.json with 215 stories
- Created tests/ (all failing — Qwen builds the code to pass them)
- Created AGENTS.md, HUMAN.md, docs/
- Created dashboard at /dashboard
- Created PixiJS renderer (engine/static/js/town.js)
- Set up Railway deployment, Neon Postgres

### 2025-03-01 — Human + Claude — Deploy fix (Day 0 hardening)
Railway healthcheck was returning 400 because TrustedHostMiddleware blocked internal probes.
- Added `*.railway.internal` to allowed_hosts in engine/main.py
- Rewrote ralph/deployer.py to capture deploy IDs and fetch build+runtime logs on failure
- Added HUD subtitle and Dashboard link to index.html
Files touched: engine/main.py, ralph/deployer.py, engine/templates/index.html
