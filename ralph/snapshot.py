"""Visual progress capture — Playwright browser screenshot + Pillow grid + JSON state."""

import json
import os
import shutil
from pathlib import Path

SNAPSHOTS_DIR = Path("snapshots")
DEPLOY_URL = os.getenv("DEPLOY_URL", "https://your-app.up.railway.app")


def ensure_snapshots_dir():
    SNAPSHOTS_DIR.mkdir(exist_ok=True)


def take_browser_screenshot(story_id: str) -> str | None:
    """Take a full-page browser screenshot of the deployed site via Playwright.

    Returns the screenshot path, or None if Playwright is unavailable.
    """
    ensure_snapshots_dir()
    output_path = SNAPSHOTS_DIR / f"{story_id}_live.png"

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(DEPLOY_URL, wait_until="networkidle", timeout=30000)

            # Wait for PixiJS to render (status-counter updates after each render)
            try:
                page.wait_for_function(
                    "document.getElementById('status-counter')?.textContent?.includes('buildings:')",
                    timeout=15000,
                )
                # Extra wait for async sprite texture loads
                page.wait_for_timeout(3000)
            except Exception:
                pass  # Still take screenshot even if wait times out

            page.screenshot(path=str(output_path), full_page=True)
            browser.close()

        print(f"  [SNAPSHOT] Browser screenshot: {output_path}")
        _copy_latest(output_path)
        return str(output_path)
    except Exception as e:
        print(f"  [SNAPSHOT] Playwright unavailable: {e}")
        return None


def take_grid_screenshot(story_id: str, db_url: str = "sqlite:///./town.db") -> str | None:
    """Render a server-side grid image via Pillow.

    50x50 grid at 10px/tile = 500x500 image with color-coded terrain.
    Returns the screenshot path, or None on error.
    """
    ensure_snapshots_dir()
    output_path = SNAPSHOTS_DIR / f"{story_id}_grid.png"

    try:
        from PIL import Image, ImageDraw, ImageFont
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Session = sessionmaker(bind=engine)
        session = Session()

        # Import models
        from engine.models import Tile

        TILE_SIZE = 10
        WIDTH = 50 * TILE_SIZE
        HEIGHT = 50 * TILE_SIZE

        TERRAIN_COLORS = {
            "grass": (34, 139, 34),
            "water": (30, 144, 255),
            "sand": (238, 214, 175),
            "stone": (128, 128, 128),
            "forest": (0, 100, 0),
            "dirt": (139, 90, 43),
        }
        DEFAULT_COLOR = (34, 139, 34)

        img = Image.new("RGB", (WIDTH, HEIGHT), DEFAULT_COLOR)
        draw = ImageDraw.Draw(img)

        tiles = session.query(Tile).all()
        for tile in tiles:
            color = TERRAIN_COLORS.get(tile.terrain, DEFAULT_COLOR)
            x1 = tile.x * TILE_SIZE
            y1 = tile.y * TILE_SIZE
            draw.rectangle([x1, y1, x1 + TILE_SIZE - 1, y1 + TILE_SIZE - 1], fill=color)

        # Try to draw buildings
        try:
            from engine.models import Building

            buildings = session.query(Building).all()
            for b in buildings:
                bx = b.x * TILE_SIZE + TILE_SIZE // 2
                by = b.y * TILE_SIZE + TILE_SIZE // 2
                draw.rectangle(
                    [bx - 3, by - 3, bx + 3, by + 3],
                    fill=(255, 215, 0),
                    outline=(0, 0, 0),
                )
        except Exception:
            pass

        # Try to draw NPCs
        try:
            from engine.models import NPC

            npcs = session.query(NPC).all()
            for npc in npcs:
                nx = npc.x * TILE_SIZE + TILE_SIZE // 2
                ny = npc.y * TILE_SIZE + TILE_SIZE // 2
                draw.ellipse([nx - 2, ny - 2, nx + 2, ny + 2], fill=(255, 0, 0))
        except Exception:
            pass

        # Watermark with story ID
        try:
            draw.text((5, HEIGHT - 15), f"Story {story_id}", fill=(255, 255, 255))
        except Exception:
            pass

        session.close()
        img.save(str(output_path))
        print(f"  [SNAPSHOT] Grid render: {output_path}")
        _copy_latest(output_path)
        return str(output_path)
    except Exception as e:
        print(f"  [SNAPSHOT] Pillow render failed: {e}")
        return None


def capture_state_json(story_id: str) -> str | None:
    """Capture world state JSON from the deployed /api/world endpoint.

    Returns the JSON file path, or None on error.
    """
    ensure_snapshots_dir()
    output_path = SNAPSHOTS_DIR / f"{story_id}_state.json"

    try:
        import requests

        url = DEPLOY_URL.rstrip("/") + "/api/world"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(resp.json(), f, indent=2)
            print(f"  [SNAPSHOT] State JSON: {output_path}")
            return str(output_path)
        else:
            print(f"  [SNAPSHOT] /api/world returned {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [SNAPSHOT] State capture failed: {e}")
        return None


def take_all_snapshots(story_id: str) -> list[str]:
    """Take all three snapshot types. Returns list of created file paths."""
    results = []

    path = take_browser_screenshot(story_id)
    if path:
        results.append(path)

    path = take_grid_screenshot(story_id)
    if path:
        results.append(path)

    path = capture_state_json(story_id)
    if path:
        results.append(path)

    return results


def _copy_latest(source_path: Path):
    """Copy the given file to snapshots/latest.png."""
    latest = SNAPSHOTS_DIR / "latest.png"
    try:
        shutil.copy2(str(source_path), str(latest))
    except Exception:
        pass
