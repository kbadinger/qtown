# Dialogue grounding — local demo

**Measured locally, not a CI gate** (needs Ollama + pgvector). The deterministic
proof is the town-event recall gate (`evals/events_recall.py`, blocking in CI); this
is the end-to-end payoff — NPC dialogue that references real town events rather than
generic roleplay. Same honesty pattern as the M7 perf report and the faithfulness
eval: run by hand, committed dated.

| | |
|---|---|
| Date | 2026-07-18 |
| Embed model | `nomic-embed-text` |
| Dialogue model | `qwen3.5:4b` |
| Events embedded | 3 synthetic town events (`doc_type='event'`) |

## The loop

1. **Embed** — three town events written to `academy.embeddings` as `doc_type='event'`
   (in production these arrive from town-core via `qtown.events.broadcast`):
   - `fire` — a fire in the market district burned down the grain stall
   - `festival` — the harvest festival filled the square with music and dancing
   - `theft` — a thief stole coins from the tavern till overnight
2. **Retrieve** — `TownHistoryRetriever.search("what happened with the fire at the
   market", doc_types=["event"])` → ranked `fire` (1.00), `festival` (0.81),
   `theft` (0.43). Scoped to events, so the docs corpus is untouched.
3. **Inject** — the top events are prepended to the dialogue prompt as a
   "Recent town history" block.
4. **Generate** — `qwen3.5:4b` writes the conversation:

```
NPC3|RELIEF|It's a miracle the fire didn't reach the bakery after all.
NPC7|AMUSED|I heard the thieves are still trying to return those stolen coins.
NPC3|GENTLE|Let's hope the harvest festival brings luck to everyone today.
NPC7|SMILING|Indeed, dancing and bread are always better than worrying about smoke.
```

Both NPCs reference the actual events (the fire, the theft, the festival) — the
grounding is working. The exact events injected are attached to the emitted
`qtown.ai.content.generated` event as `grounded_events` (an honest "why this NPC
said this").

Generation is temperature-based, so this is a point-in-time snapshot, not a fixed
string. Reproduce: embed a few `doc_type='event'` rows, then run
`GenerateDialogue` (or the retrieve→inject helpers) — see
`services/academy/academy/grpc_server.py`.
