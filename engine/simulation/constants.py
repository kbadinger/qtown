# Drought to famine cascade threshold
DROUGHT_FAMINE_THRESHOLD = 5
"""Simulation constants."""

# Building types available in the simulation
BUILDING_TYPES = [
    'residential',
    'food',
    'guard',
    'market',
    'religious',
    'school',
    'hospital',
    'tavern',
    'library',
    'bakery',
    'blacksmith',
    'farm',
    'church',
    'mine',
    'lumber_mill',
    'fishing_dock',
    'guard_tower',
    'wall',
    'gate',
    'fountain',
    'well',
    'warehouse',
    'bank',
    'theater',
    'arena',
    'prison',
    'graveyard',
    'garden',
    'watchtower',
    'health',
    'entertainment',
    'economic',
    'infrastructure',
    'windmill',
]




DEFAULT_BASE_PRICE = 100
DEFAULT_DEMAND = 10




RESOURCE_DEMAND = {"Food": 10, "Art": 20, "Books": 10}




SATURATION_TICK_THRESHOLD = 10

DROUGHT_FAMINE_THRESHOLD = 5



PLAGUE_OVERWHELM_THRESHOLD = 0.5
"""Threshold of sick NPCs (50%) that triggers hospital_overwhelmed cascade."""




FLOOD_PRICE_SPIKE_DURATION = 30
"""Number of ticks food price remains tripled after flood."""

FLOOD_PRICE_MULTIPLIER = 3
"""Food price multiplier during flood cascade."""

