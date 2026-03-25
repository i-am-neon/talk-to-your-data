# Multi-Model Benchmark Design

## Goal

Run the existing LLM eval suite across all three available models (Haiku 4.5, Sonnet 4.6, Opus 4.6) and produce a comparison report measuring correctness, speed, and cost.

## Architecture

### Benchmark Script

**File:** `backend/evals/benchmark.py`

Standalone async Python script (no pytest). Reuses the existing `cases.yaml` eval cases and the `agent` from `app.agent.agent`.

**Flow:**

1. Load eval cases from `cases.yaml` via `pydantic_evals.Dataset`
2. For each model in `MODEL_IDS` (haiku, sonnet, opus):
   a. For each case: run the agent with the model override, capturing:
      - Wall-clock time (`time.perf_counter`)
      - Token usage (`result.usage()` → input_tokens, output_tokens)
      - Agent output text
      - Pass/fail from evaluators (Contains and LLMJudge)
   b. Record errors gracefully — if a case fails, log the error and continue
3. Print terminal summary tables
4. Save JSON report to `backend/evals/reports/`

### Judge Model

Fixed to Sonnet 4.6 for all LLMJudge evaluations, regardless of which model is being benchmarked. This ensures scores are comparable across models.

### Cost Calculation

Hardcoded price table (USD per million tokens):

| Model | Input | Output |
|-------|-------|--------|
| Haiku 4.5 | $1.00 | $5.00 |
| Sonnet 4.6 | $3.00 | $15.00 |
| Opus 4.6 | $5.00 | $25.00 |

Cost per case = `(input_tokens * input_price + output_tokens * output_price) / 1_000_000`

### Terminal Output

Two tables printed to stdout:

**1. Per-case breakdown:**

```
Case            │ Model   │ Pass │ Time (s) │ In Tok │ Out Tok │ Cost ($)
────────────────┼─────────┼──────┼──────────┼────────┼─────────┼─────────
row_count       │ haiku   │ ✓    │ 2.3      │ 1200   │ 340     │ 0.0029
row_count       │ sonnet  │ ✓    │ 3.1      │ 1180   │ 380     │ 0.0092
row_count       │ opus    │ ✓    │ 5.2      │ 1210   │ 350     │ 0.0444
...
```

**2. Model summary:**

```
Model   │ Passed │ Total │ Pass % │ Avg Time │ Total Tok │ Total Cost
────────┼────────┼───────┼────────┼──────────┼───────────┼───────────
haiku   │ 8/10   │  10   │  80%   │ 2.1s     │ 15,200    │ $0.042
sonnet  │ 10/10  │  10   │ 100%   │ 3.4s     │ 16,800    │ $0.108
opus    │ 10/10  │  10   │ 100%   │ 5.8s     │ 17,100    │ $0.520
```

### JSON Report

Saved to `backend/evals/reports/<YYYY-MM-DD-HHMMSS>.json`:

```json
{
  "timestamp": "2026-03-25T14:30:00Z",
  "git_sha": "abc1234",
  "models": {
    "haiku": {
      "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
      "cases": [
        {
          "name": "row_count",
          "passed": true,
          "time_seconds": 2.3,
          "input_tokens": 1200,
          "output_tokens": 340,
          "cost_usd": 0.0029,
          "output": "There are 500 rows...",
          "error": null
        }
      ],
      "summary": {
        "passed": 8,
        "total": 10,
        "pass_rate": 0.8,
        "avg_time_seconds": 2.1,
        "total_input_tokens": 12000,
        "total_output_tokens": 3200,
        "total_cost_usd": 0.042
      }
    }
  }
}
```

### Correctness Evaluation

We run each case individually (not via `Dataset.evaluate()`) so we can capture per-case timing and token usage.

- **Contains evaluator:** Substring check — `expected_value in agent_output`
- **LLMJudge evaluator:** Separate LLM call using the fixed Sonnet judge model with the case's rubric

The case definitions in `cases.yaml` are parsed to extract evaluator type and arguments. Each case uses exactly one evaluator type.

### Error Handling

- If the agent raises an exception for a case, record `passed=false` with the error message
- If a model is entirely unavailable (e.g. auth error), skip it and note in the report
- The benchmark never stops early — all models and cases are attempted

## Invocation

```bash
just bench    # Run multi-model benchmark
```

Justfile recipe:

```
bench:
    cd backend && uv run python evals/benchmark.py
```

## Files Changed

- `backend/evals/benchmark.py` — new benchmark script
- `backend/evals/reports/.gitkeep` — reports directory (reports themselves are gitignored)
- `.gitignore` — add `backend/evals/reports/*.json`
- `justfile` — add `bench` target
- `CLAUDE.md` — add `just bench` to Commands section
