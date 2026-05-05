"""Real-time cost estimator — tracks local electricity vs cloud API costs."""

import json
import time
from pathlib import Path

COST_FILE = Path("cost_tracking.json")

# Cloud API pricing (per million tokens)
CLOUD_PRICING = {
    "opus46": {"in": 5.0, "out": 25.0, "label": "Claude Opus 4.6"},
    "opus4": {"in": 15.0, "out": 75.0, "label": "Claude Opus 4 (legacy)"},
    "gpt4o": {"in": 2.50, "out": 10.0, "label": "GPT-4o"},
    "sonnet45": {"in": 3.0, "out": 15.0, "label": "Claude Sonnet 4.5"},
}

# Local system power draw
ACTIVE_WATTS = 500  # GPU under load + CPU + RAM
IDLE_WATTS = 150  # Between stories, during deploys
ELECTRICITY_RATE = 0.16  # $/kWh US average


def _load_totals() -> dict:
    """Load running totals from cost_tracking.json."""
    if COST_FILE.exists():
        with open(COST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "total_stories": 0,
        "total_attempts": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "total_gpu_hours": 0.0,
        "total_idle_hours": 0.0,
        "qwen_electricity_usd": 0.0,
        "opus46_equivalent_usd": 0.0,
        "opus4_equivalent_usd": 0.0,
        "gpt4o_equivalent_usd": 0.0,
        "sonnet_equivalent_usd": 0.0,
        "savings_vs_opus46_pct": 0.0,
        "last_updated": "",
    }


def _save_totals(totals: dict):
    """Save running totals to cost_tracking.json."""
    totals["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(COST_FILE, "w", encoding="utf-8") as f:
        json.dump(totals, f, indent=2)


def _cloud_cost(tokens_in: int, tokens_out: int, provider: str) -> float:
    """Calculate what this would cost on a cloud API."""
    pricing = CLOUD_PRICING[provider]
    return (tokens_in / 1_000_000 * pricing["in"]) + (
        tokens_out / 1_000_000 * pricing["out"]
    )


def _electricity_cost(active_hours: float, idle_hours: float) -> float:
    """Calculate electricity cost."""
    active_kwh = active_hours * ACTIVE_WATTS / 1000
    idle_kwh = idle_hours * IDLE_WATTS / 1000
    return (active_kwh + idle_kwh) * ELECTRICITY_RATE


def log_cost(
    tokens_in: int,
    tokens_out: int,
    gpu_time_sec: float,
    idle_time_sec: float = 0.0,
    story_completed: bool = False,
):
    """Log cost for a single Qwen call (success or failure).

    Called by Ralph after every Qwen invocation.
    """
    totals = _load_totals()

    gpu_hours = gpu_time_sec / 3600
    idle_hours = idle_time_sec / 3600

    totals["total_attempts"] += 1
    if story_completed:
        totals["total_stories"] += 1
    totals["total_tokens_in"] += tokens_in
    totals["total_tokens_out"] += tokens_out
    totals["total_gpu_hours"] += gpu_hours
    totals["total_idle_hours"] += idle_hours

    # Recalculate all costs
    totals["qwen_electricity_usd"] = round(
        _electricity_cost(totals["total_gpu_hours"], totals["total_idle_hours"]), 2
    )

    for provider_key in CLOUD_PRICING:
        cost = _cloud_cost(
            totals["total_tokens_in"], totals["total_tokens_out"], provider_key
        )
        totals[f"{provider_key}_equivalent_usd"] = round(cost, 2)

    # Savings percentage vs Opus 4.6
    if totals["opus46_equivalent_usd"] > 0:
        totals["savings_vs_opus46_pct"] = round(
            (1 - totals["qwen_electricity_usd"] / totals["opus46_equivalent_usd"])
            * 100,
            1,
        )

    _save_totals(totals)
    return totals
