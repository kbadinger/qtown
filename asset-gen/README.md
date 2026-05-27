# Qtown v2 Asset Generation

Build-time pre-gen tool for the v2 sprite library. **Not** the runtime asset-pipeline service (that's `services/asset-pipeline/` — Kafka-triggered gens during sim operation). This tool is the one-shot batch that generates the entire v2 visual library *before* Ralph activates for Phase 6 + 7, so the dashboard has assets ready the moment the sim runs.

## Why this exists

Per `docs/v2-phase-7-rooms.md` and Guardian decision `2f7c20c8`: v2 is a full futuristic-style reboot, both overhead town view AND interior rooms. Per Kevin's call on 2026-05-26, the full asset library is pre-generated against a locked spec before Ralph runs — avoiding GPU contention with Ollama and ensuring v2 ships looking like v2.

## Files

| File | Purpose |
|---|---|
| `style-spec.md` | Locked solarpunk + tech-accents visual spec; prompt scaffolding |
| `taxonomy.yaml` | Asset inventory — buildings, rooms per building, NPC roles, activity poses, interiors |
| `workflows/` | ComfyUI workflow JSON templates (one per asset class) |
| `run_batch.py` | Python batch driver — reads taxonomy, submits to ComfyUI, downloads outputs |
| `requirements.txt` | Python deps (`httpx`, `pyyaml`) |
| `output/` | Generated images land here, structured by asset class |

## How to run (on the 3090 box)

```sh
# one-time setup
cd asset-gen
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ensure ComfyUI is running on this box at :8188
# (or set COMFYUI_URL env var)

# test-gen — small batch against Flux.1-schnell for direction validation
python3 run_batch.py --mode test --limit 10

# full production gen — Flux.1-dev, all taxonomy entries
python3 run_batch.py --mode production
```

Output structure:

```
output/
├── overhead/
│   ├── buildings/
│   │   ├── tavern.png
│   │   ├── market.png
│   │   └── …
│   └── npcs/
│       ├── trader_idle.png
│       └── …
├── interior/
│   ├── backgrounds/
│   │   ├── tavern_bar.png
│   │   ├── tavern_kitchen.png
│   │   └── …
│   └── activities/
│       ├── trader_haggling.png
│       ├── student_studying.png
│       └── …
```

## Status

- [x] `style-spec.md` — locked
- [ ] `taxonomy.yaml` — drafted, **Kevin to review + lock**
- [ ] `workflows/*.json` — pending taxonomy lock
- [ ] `run_batch.py` — pending workflows
- [ ] Test-gens — pending workflows
- [ ] Production batch — pending test-gens approval

## Decisions encoded

- **Style:** Solarpunk + tech accents (`docs/v2-phase-7-rooms.md`, decisions `bb54cecf` + `2f7c20c8`)
- **Rendering grammar:** Pokémon-style 2.5D — characters always front-facing, environment perspective changes per view (top-down for overhead, side-view for interiors)
- **Base model:** Flux.1-dev fp8 (production), Flux.1-schnell fp8 (test-gens)
- **Run target:** Kevin's i9 + RTX 3090 box, separate from Mac where Ollama/Ralph live (zero GPU contention)
