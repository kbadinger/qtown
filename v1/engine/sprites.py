"""Sprite generation — thin sync wrapper around ComfyUI asset generation.

Qwen can import this module to generate sprites on demand:

    from engine.sprites import generate_building, generate_npc

Both functions return the file path (str) on success, or None if ComfyUI
is unavailable. They never raise — failures are logged and return None.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


def generate_building(building_type: str) -> str | None:
    """Generate an isometric building sprite via ComfyUI.

    Args:
        building_type: e.g. "bakery", "tavern", "smithy"

    Returns:
        Path to the generated sprite under assets/buildings/, or None.
    """
    try:
        from ralph.asset_gen import generate_building_sprite
        return asyncio.run(generate_building_sprite(building_type))
    except Exception:
        logger.warning("Sprite generation unavailable for building '%s'", building_type, exc_info=True)
        return None


def generate_npc(role: str) -> str | None:
    """Generate an isometric NPC sprite via ComfyUI.

    Args:
        role: e.g. "villager", "merchant", "guard"

    Returns:
        Path to the generated sprite under assets/npcs/, or None.
    """
    try:
        from ralph.asset_gen import generate_npc_sprite
        return asyncio.run(generate_npc_sprite(role))
    except Exception:
        logger.warning("Sprite generation unavailable for NPC '%s'", role, exc_info=True)
        return None


def ensure_all_assets() -> None:
    """Scan DB for all building types and NPC roles, generate missing sprites.

    Safe to call at any time — skips gracefully if ComfyUI is down.
    """
    try:
        from ralph.asset_gen import ensure_default_assets
        asyncio.run(ensure_default_assets())
    except Exception:
        logger.warning("Bulk asset generation failed", exc_info=True)
