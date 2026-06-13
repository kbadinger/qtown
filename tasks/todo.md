# v2 Build — Fire-Off Structure, Assets, Full Stories

Goal (Kevin, 2026-06-12): make the v2 plan pack *executable*. Build the complete
story structure, figure out the assets + a plan for what's missing, materialize the
full story backlog, and tag each story for the Opus-plans / Ralph-executes /
Opus-cleans-up operating model.

## Operating model (decided)
- **Opus in-session** = author well-structured stories/plans + periodic cleanup passes.
- **Ralph (local Ollama loop)** = bulk executor of mechanical code stories.
- Cadence: Ralph runs → stop → Opus cleanup session fixes/restructures → resume.
- No Opus path is added to the orchestrator. Grade tag drives the cleanup scrutiny.

## Ground truth (verified this session)
- `asset-gen/output/` empty; `workflows/` has only INSTALL.md; `run_batch.py` untested.
  → **0 of ~235 v2 assets exist; the pipeline code is unfinished.**
- `services/town-core/assets/` = 39 v1 pixel buildings + 37 v1 NPCs (off-taxonomy; v1 fallback only).
- `ralph/worklist.json`: 194 complete, 26 P6 pending. Schema:
  `{id,title,service,language,deps,phase,group,description,acceptance_criteria[],status,attempts,last_error,labels[]}`.
- Ralph orchestrator runs **local Ollama only** — no Opus code path (confirmed).

## Todos
- [ ] **Decide story-schema extension** — `labels[]` carries `grade:opus|grade:ralph`,
      `gate:A|B|C|D`, `track:kevin-gpu`; pick phase encoding for 6.5/7A/7B/7.5/8
      (check orchestrator's phase assumptions first).
- [ ] **Materialize Phase 6.5 stories** (Plan 03+04): perf report, health model, OTel ×3,
      CI security gates, STATE.md, topic catalog — P6.5-001..017.
- [ ] **Materialize Phase 7-A stories** (Plan 02): asset pipeline — P7A-001..006.
- [ ] **Materialize Phase 7-B stories** (Plan 01): rooms — P7-001..031.
- [ ] **Materialize Phase 7.5 stories** (Plan 04): docs — P7.5-001..023.
- [ ] **Materialize Phase 8 stories** (Plan 05): 2026 gaps — P8-001..010.
- [ ] **Write `docs/plans/ASSET-INVENTORY.md`** — every one of ~235 assets: have/missing,
      source (gen vs v1-fallback), size, output path, generation step. The "plan for
      missing assets" Kevin asked for. Cross-checked against the locked taxonomy.
- [ ] **Validate** worklist.json parses, deps resolve (no dangling/cyclic), all IDs unique,
      every story has acceptance_criteria + a grade tag.
- [ ] **Sequencing doc / fire-off checklist** — exact order + gate dependencies so the
      Ralph loop + Opus cleanup cadence has a defined start.
- [ ] Guardian: record the operating-model decision + progress.
- [ ] Commit; update auto-memory.

## Review

**What was built (2026-06-12):**
- **Full backlog materialized** — `ralph/build_v2_backlog.py` authored 87 new stories
  (P6.5/P7A/P7/P7.5/P8) into `ralph/worklist.json` in the real schema, and enriched all
  220 existing stories with grade tags. Total **307 stories, 113 pending** (61 Opus /
  52 Ralph). Dependency graph validated: no dupes, no dangling deps, no cycles; Ralph's
  own `v2_worklist.py` parses it and `next_available` returns 36 ready stories.
- **Grade tagging** — every story carries `grade:opus` (judgment-heavy: architecture,
  perf, proof, security, ADR voice, tracing, evals) or `grade:ralph` (mechanical code).
  Grades live in `labels[]` so they round-trip through `to_dict()`. This operationalizes
  the Opus-cleanup cadence. Extra labels: `gate:A-D`, `track:kevin-gpu`, `voice-pass`,
  `proto`.
- **`docs/plans/ASSET-INVENTORY.md`** — the have/missing ledger: **0 of ~235 v2 assets
  exist**, pipeline code ~30% built. Full manifest from the locked taxonomy (19 buildings,
  35 rooms, 60 NPC sprites, ~100 poses, ~21 extras), build steps mapped to P7A-001..006,
  3090 execution protocol. v1 pixel assets are fallback-only.
- **`docs/plans/FIRE-OFF.md`** — operational runbook: operating model, the cadence diagram,
  per-phase counts, hard sequencing rules, 6 lanes in start order, first commands.

**Key facts surfaced:** Ralph executes local Ollama only (no Opus path in the
orchestrator — confirmed); `phase`/`group` are pure metadata (scheduling is status+deps);
the asset lane is the only fully-unblocked work and needs Kevin's hands on the 3090.

**Decisions:** Opus-in-session = planner + janitor (no orchestrator changes); enrich ALL
stories (not just P6) for a uniform cleanup cadence; phases encoded as strings
("6.5"/"7A"/"7B"/"7.5"/"8") since no code does integer math on phase.

**Not done / next:** actually firing the lanes — start Ralph on `grade:ralph` P6 work +
Opus on the `grade:opus` P6 stories; author P7A-001..003 so Kevin can test-gen on the 3090.
