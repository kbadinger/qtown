"""One-time script to generate all missing building sprites.

Reads BUILDING_TYPES from engine/simulation.py, checks which sprites
exist in assets/buildings/, and generates any missing ones via ComfyUI.

Usage:
    python -m ralph.backfill_sprites
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ralph.asset_gen import (
    BUILDINGS_DIR,
    check_comfyui_health,
    generate_building_sprite,
)


def get_building_types() -> list[str]:
    """Import BUILDING_TYPES from engine/simulation.py."""
    from engine.simulation import BUILDING_TYPES
    return BUILDING_TYPES


async def backfill():
    building_types = get_building_types()
    print(f"Found {len(building_types)} building types in BUILDING_TYPES")

    BUILDINGS_DIR.mkdir(parents=True, exist_ok=True)
    existing = {p.stem for p in BUILDINGS_DIR.glob("*.png")}
    missing = [bt for bt in building_types if bt not in existing]

    if not missing:
        print("All building sprites exist — nothing to do")
        return

    print(f"Missing sprites: {', '.join(missing)}")

    for bt in missing:
        print(f"  Generating {bt}...", end=" ", flush=True)
        try:
            path = await generate_building_sprite(bt)
            print(f"OK -> {path}")
        except Exception as e:
            print(f"FAILED: {e}")
            raise


def main():
    if not check_comfyui_health():
        print("ERROR: ComfyUI is not reachable — start it first")
        sys.exit(1)

    print("ComfyUI is up — starting backfill")
    asyncio.run(backfill())
    print("Done!")


if __name__ == "__main__":
    main()
