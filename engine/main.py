"""FastAPI app with security middleware — PROTECTED from Qwen modification."""

import importlib
import json
import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from starlette.datastructures import URL
from starlette.middleware.trustedhost import TrustedHostMiddleware as _TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from engine.auth import hash_key
from engine.db import Base, SessionLocal, engine, get_db, init_db
from engine.models import AdminUser, Building, NPC, Tile, WorldState

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

QTOWN_ENV = os.getenv("QTOWN_ENV", "development")
IS_PROD = QTOWN_ENV == "production"

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="Qwen Town",
    description="A self-evolving 2D town simulation built by Qwen 3.5",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://qtown.ai",
        "https://www.qtown.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealthBypassTrustedHost:
    """TrustedHostMiddleware that exempts /health for Railway probes."""

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]):
        self.app = app
        self.inner = _TrustedHostMiddleware(app, allowed_hosts=allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return
        await self.inner(scope, receive, send)


if IS_PROD:
    app.add_middleware(
        HealthBypassTrustedHost,
        allowed_hosts=[
            "qtown.ai",
            "www.qtown.ai",
            "*.up.railway.app",
        ],
    )

# ---------------------------------------------------------------------------
# Templates & Static
# ---------------------------------------------------------------------------

templates = Jinja2Templates(directory="engine/templates")
app.mount("/static/assets", StaticFiles(directory="assets"), name="assets")

# Mount snapshots directory (Ralph writes screenshots here)
os.makedirs("snapshots", exist_ok=True)
app.mount("/static/snapshots", StaticFiles(directory="snapshots"), name="snapshots")

app.mount("/static", StaticFiles(directory="engine/static"), name="static")

# ---------------------------------------------------------------------------
# Global exception handler — never leak stack traces
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if IS_PROD:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    # In dev, include the error message (but not the full traceback)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
def startup():
    init_db()
    _seed_admin()
    _seed_world()
    _auto_discover_routers()


def _seed_world():
    """Seed grid, buildings, NPCs, and world state on first run. All idempotent."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs, init_world_state

    db = SessionLocal()
    try:
        init_grid(db)
        seed_buildings(db)
        seed_npcs(db)
        init_world_state(db)
        print("[qtown] World seeded")
    finally:
        db.close()


def _seed_admin():
    """Create admin user from env var if it doesn't exist."""
    admin_key = os.getenv("QTOWN_ADMIN_KEY")
    if not admin_key:
        return

    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter_by(username="admin").first()
        if not existing:
            admin = AdminUser(
                username="admin",
                key_hash=hash_key(admin_key),
            )
            db.add(admin)
            db.commit()
            print("[qtown] Admin user seeded")
    finally:
        db.close()


def _auto_discover_routers():
    """Scan engine/routers/ for .py files with a `router` attribute and include them."""
    routers_dir = Path("engine/routers")
    if not routers_dir.is_dir():
        return

    for py_file in sorted(routers_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = f"engine.routers.{py_file.stem}"
        try:
            mod = importlib.import_module(module_name)
            router_obj = getattr(mod, "router", None)
            if router_obj is not None:
                app.include_router(router_obj)
                print(f"[qtown] Auto-registered router: {module_name}")
        except Exception as e:
            print(f"[qtown] Failed to load router {module_name}: {e}")


# ---------------------------------------------------------------------------
# Index page — PixiJS isometric renderer
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    import json
    from pathlib import Path
    prd_path = Path(__file__).resolve().parent.parent / "prd.json"
    stories_done = 0
    stories_total = 265
    if prd_path.exists():
        try:
            prd = json.loads(prd_path.read_text(encoding="utf-8"))
            stories_total = len(prd.get("stories", []))
            stories_done = sum(1 for s in prd.get("stories", []) if s.get("status") == "done")
        except Exception:
            pass
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stories_done": stories_done,
        "stories_total": stories_total,
    })


# ---------------------------------------------------------------------------
# Dashboard — human-protected progress view
# ---------------------------------------------------------------------------


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/dashboard-data")
def dashboard_data():
    """Return project progress data from flat files — no DB dependency."""
    # Story counts from prd.json
    prd_path = Path("prd.json")
    stories = {"total": 0, "done": 0, "failed": 0, "pending": 0, "in_progress": 0}
    if prd_path.exists():
        try:
            prd = json.loads(prd_path.read_text(encoding="utf-8"))
            all_stories = prd.get("stories", [])
            stories["total"] = len(all_stories)
            for s in all_stories:
                status = s.get("status", "pending")
                if status == "done":
                    stories["done"] += 1
                elif status == "failed":
                    stories["failed"] += 1
                elif status == "in_progress":
                    stories["in_progress"] += 1
                else:
                    stories["pending"] += 1
        except (json.JSONDecodeError, OSError):
            pass

    # Cost data from cost_tracking.json
    cost = {}
    cost_path = Path("cost_tracking.json")
    if cost_path.exists():
        try:
            cost = json.loads(cost_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Latest snapshot
    snapshot_url = None
    latest_snap = Path("snapshots/latest.png")
    if latest_snap.exists():
        snapshot_url = "/static/snapshots/latest.png"

    # Recent learnings from progress.txt
    learnings = []
    progress_path = Path("progress.txt")
    if progress_path.exists():
        try:
            lines = progress_path.read_text(encoding="utf-8").strip().split("\n")
            # Take last 5 non-empty lines
            learnings = [l for l in lines if l.strip()][-5:]
        except OSError:
            pass

    # Alerts from alerts.log
    alerts = []
    alerts_path = Path("alerts.log")
    if alerts_path.exists():
        try:
            lines = alerts_path.read_text(encoding="utf-8").strip().split("\n")
            alerts = [l for l in lines if l.strip()][-10:]
        except OSError:
            pass

    return {
        "stories": stories,
        "cost": cost,
        "snapshot_url": snapshot_url,
        "learnings": learnings,
        "alerts": alerts,
    }


# ---------------------------------------------------------------------------
# World state — main page PixiJS renderer polls this
# ---------------------------------------------------------------------------


@app.get("/api/world")
def world_state(db: Session = Depends(get_db)):
    """Return current world state for the PixiJS renderer."""
    ws = db.query(WorldState).first()
    tick = ws.tick if ws else 0

    tiles = [
        {"x": t.x, "y": t.y, "terrain": t.terrain}
        for t in db.query(Tile).all()
    ]
    buildings = [
        {
            "id": b.id, "name": b.name, "building_type": b.building_type,
            "x": b.x, "y": b.y, "capacity": b.capacity,
        }
        for b in db.query(Building).all()
    ]
    npcs = [
        {
            "id": n.id, "name": n.name, "role": n.role,
            "x": n.x, "y": n.y, "gold": n.gold,
            "hunger": n.hunger, "energy": n.energy,
        }
        for n in db.query(NPC).all()
    ]

    return {
        "tick": tick,
        "day": tick // 24 + 1,
        "total_gold": sum(n["gold"] for n in npcs),
        "tiles": tiles,
        "buildings": buildings,
        "npcs": npcs,
    }


# ---------------------------------------------------------------------------
# Stories — individual story detail view
# ---------------------------------------------------------------------------


@app.get("/stories", response_class=HTMLResponse)
def stories_page(request: Request):
    return templates.TemplateResponse("stories.html", {"request": request})


@app.get("/api/stories-data")
def stories_data():
    """Return all stories with status, attempts, tags, and commit links."""
    prd_path = Path("prd.json")
    if not prd_path.exists():
        return {"stories": []}

    try:
        prd = json.loads(prd_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"stories": []}

    all_stories = prd.get("stories", [])

    # Build story_id -> commit SHA map from git log
    commit_map = {}
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--all"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            m = re.match(r"^([0-9a-f]+) \[Ralph\] Story (\d+):", line)
            if m:
                sha, story_id = m.group(1), m.group(2)
                commit_map[story_id] = sha
    except Exception:
        pass

    github_url = "https://github.com/kbadinger/qtown"
    out = []
    for s in all_stories:
        sid = s.get("id", "")
        status = s.get("status", "pending")
        sha = commit_map.get(sid) if status == "done" else None
        out.append({
            "id": sid,
            "title": s.get("title", ""),
            "status": status,
            "attempts": s.get("attempts", 0),
            "tags": s.get("tags", []),
            "commit_url": f"{github_url}/commit/{sha}" if sha else None,
        })

    return {"stories": out}


# ---------------------------------------------------------------------------
# Timeline — visual snapshot history
# ---------------------------------------------------------------------------


@app.get("/timeline", response_class=HTMLResponse)
def timeline(request: Request):
    return templates.TemplateResponse("timeline.html", {"request": request})


@app.get("/api/timeline-data")
def timeline_data():
    """Return snapshot history with story metadata."""
    snapshots_dir = Path("snapshots")
    prd_path = Path("prd.json")

    # Load story titles from prd.json
    story_titles = {}
    if prd_path.exists():
        try:
            prd = json.loads(prd_path.read_text(encoding="utf-8"))
            for s in prd.get("stories", []):
                story_titles[s["id"]] = s.get("title", "")
        except (json.JSONDecodeError, OSError):
            pass

    # Scan snapshots directory for _live.png files (browser screenshots)
    entries = []
    if snapshots_dir.is_dir():
        for f in sorted(snapshots_dir.glob("*_live.png")):
            story_id = f.stem.replace("_live", "")
            entry = {
                "story_id": story_id,
                "title": story_titles.get(story_id, ""),
                "live_url": f"/static/snapshots/{f.name}",
            }
            # Check for grid render
            grid = snapshots_dir / f"{story_id}_grid.png"
            if grid.exists():
                entry["grid_url"] = f"/static/snapshots/{grid.name}"
            # Check for state JSON
            state = snapshots_dir / f"{story_id}_state.json"
            if state.exists():
                entry["state_url"] = f"/static/snapshots/{state.name}"
            entries.append(entry)

    return {"snapshots": entries}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}
