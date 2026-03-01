# Cost Tracking Methodology

Full transparency on how Qwen Town calculates and compares costs.

## Local Electricity Cost Formula

```
cost = (active_hours × 0.5 kW + idle_hours × 0.15 kW) × $0.16/kWh
```

### Components

| Component | Value | Source |
|-----------|-------|--------|
| Active system draw | 500W (0.5 kW) | GPU under load (3090 Ti ~350W) + CPU + RAM + system |
| Idle system draw | 150W (0.15 kW) | System idle between stories, during deploys |
| Electricity rate | $0.16/kWh | US average residential rate (EIA, 2025) |

### What Counts as Active vs Idle

- **Active**: Time during `call_qwen()` — GPU is processing tokens
- **Idle**: Time between Qwen calls — test runs, git operations, deploy waits, file I/O

## Token Counting

Token counts are extracted directly from the Ollama API response:
- `prompt_eval_count` → tokens_in (input/prompt tokens)
- `eval_count` → tokens_out (output/completion tokens)

These are exact counts from the model's tokenizer, not estimates.

## Cloud API Pricing (for comparison)

All prices per million tokens, sourced from official pricing pages:

| Provider | Input ($/MTok) | Output ($/MTok) | Source |
|----------|---------------|-----------------|--------|
| Claude Opus 4.6 | $5.00 | $25.00 | anthropic.com/pricing (Feb 2026) |
| Claude Opus 4 (legacy) | $15.00 | $75.00 | anthropic.com/pricing (Feb 2026) |
| GPT-4o | $2.50 | $10.00 | openai.com/pricing (Feb 2026) |
| Claude Sonnet 4.5 | $3.00 | $15.00 | anthropic.com/pricing (Feb 2026) |

Cloud cost formula:
```
cost = (tokens_in / 1,000,000 × input_price) + (tokens_out / 1,000,000 × output_price)
```

## Per-Story Averages (Estimated)

Based on early testing:
- Average tokens in per attempt: ~25,000 (prompt + context files)
- Average tokens out per attempt: ~3,000 (code output)
- Average attempts per story: 2.5 (including retries)
- So per story: ~62,500 tokens in, ~7,500 tokens out

## 2-Week Projection (~850 stories)

| Provider | Projected Cost | Calculation |
|----------|---------------|-------------|
| Qwen (local) | ~$12 | ~75 GPU hours × 0.5kW × $0.16/kWh + idle |
| Claude Opus 4.6 | ~$425 | 53M tokens in + 6.4M tokens out |
| Claude Opus 4 | ~$1,277 | Same token counts, higher prices |
| GPT-4o | ~$197 | Same token counts |
| Claude Sonnet 4.5 | ~$106 | Same token counts |

## Assumptions

1. Token counts are exact (from Ollama API), not estimated
2. Electricity rate uses US national average ($0.16/kWh) — your rate may vary
3. System power draw is estimated (500W active, 150W idle) — actual varies by hardware
4. Cloud API prices are point-in-time — they may change
5. Per-story averages will shift as complexity increases (later stories use more context)
6. Cloud comparison assumes the same token counts — in practice, different models may need more/fewer tokens

## Files

- `cost_tracking.json` — running totals, updated after every Qwen call
- `metrics.jsonl` — per-attempt details (tokens, timing, pass/fail)
- Both files are committed to the repo for full transparency
