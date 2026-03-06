"""Simulation package — re-exports everything for backward compatibility.

Existing imports like `from engine.simulation import process_tick` continue to work.
"""

from engine.simulation.constants import *  # noqa: F401,F403
from engine.simulation.init import *  # noqa: F401,F403
from engine.simulation.buildings import *  # noqa: F401,F403
from engine.simulation.production import *  # noqa: F401,F403
from engine.simulation.effects import *  # noqa: F401,F403
from engine.simulation.npcs import *  # noqa: F401,F403
from engine.simulation.economy import *  # noqa: F401,F403
from engine.simulation.weather import *  # noqa: F401,F403
from engine.simulation.events import *  # noqa: F401,F403
from engine.simulation.tick import *  # noqa: F401,F403
