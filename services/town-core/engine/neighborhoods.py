"""Neighborhood zone mapping for the 50x50 grid.

Each zone maps to a rectangular region. NPCs crossing zone boundaries
trigger the NPC travel protocol.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneBounds:
    """Rectangular bounds for a neighborhood zone."""
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    def contains(self, x: int, y: int) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


# Zone definitions — carve the 50x50 grid into neighborhoods
# These are non-overlapping rectangular regions
NEIGHBORHOOD_ZONES: dict[str, ZoneBounds] = {
    "town_core":        ZoneBounds(15, 34, 15, 34),  # Center 20x20
    "market_district":  ZoneBounds(35, 49, 15, 34),  # East strip
    "fortress":         ZoneBounds(0, 14, 0, 14),     # NW corner
    "academy":          ZoneBounds(15, 34, 0, 14),    # North center
    "tavern":           ZoneBounds(35, 49, 0, 14),    # NE corner
    "library":          ZoneBounds(0, 14, 15, 34),    # West strip
    "town_hall":        ZoneBounds(20, 29, 20, 29),   # Center of town_core (overlay)
    "asset_pipeline":   ZoneBounds(0, 14, 35, 49),    # SW corner
    "courier_network":  ZoneBounds(15, 34, 35, 49),   # South center
}

# Default zone when coordinates don't match any defined zone
DEFAULT_ZONE = "town_core"


def get_neighborhood(x: int, y: int) -> str:
    """Return the neighborhood name for grid coordinates.
    
    Checks town_hall first (it overlaps with town_core center).
    Falls back to town_core if no match.
    """
    # Town Hall is a sub-zone of Town Core — check it first
    if NEIGHBORHOOD_ZONES["town_hall"].contains(x, y):
        return "town_hall"
    
    for name, bounds in NEIGHBORHOOD_ZONES.items():
        if name == "town_hall":
            continue
        if bounds.contains(x, y):
            return name
    
    return DEFAULT_ZONE


def get_zone_center(neighborhood: str) -> tuple[int, int]:
    """Return the center coordinates of a neighborhood zone."""
    bounds = NEIGHBORHOOD_ZONES.get(neighborhood)
    if bounds is None:
        bounds = NEIGHBORHOOD_ZONES[DEFAULT_ZONE]
    return (
        (bounds.x_min + bounds.x_max) // 2,
        (bounds.y_min + bounds.y_max) // 2,
    )


def is_zone_boundary_crossing(old_x: int, old_y: int, new_x: int, new_y: int) -> tuple[str, str] | None:
    """Check if moving from (old_x, old_y) to (new_x, new_y) crosses a zone boundary.
    
    Returns (from_zone, to_zone) if crossing detected, None otherwise.
    """
    old_zone = get_neighborhood(old_x, old_y)
    new_zone = get_neighborhood(new_x, new_y)
    
    if old_zone != new_zone:
        return (old_zone, new_zone)
    return None
