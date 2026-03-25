# Multi-Model Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the existing eval suite across Haiku/Sonnet/Opus, measuring correctness, speed, and cost, with terminal + JSON output.

**Architecture:** Standalone async Python script (`backend/evals/benchmark.py`) that parses `cases.yaml` directly, runs the agent per model per case with timing/token capture, evaluates correctness (substring or LLM judge), prints summary tables, and saves a JSON report.

**Tech Stack:** Python asyncio, PyYAML, PydanticAI (agent + OpenAI model), existing app.agent module

---

## File Structure

| File | Purpose |
|------|---------|
| `backend/evals/benchmark.py` | Main benchmark script — case loading, agent execution, evaluation, reporting |
| `backend/evals/reports/.gitkeep` | Reports directory placeholder |
| `.gitignore` | Add `backend/evals/reports/*.json` |
| `justfile` | Add `bench` target |
| `CLAUDE.md` | Add `just bench` to Commands section |

---

### Task 1: Scaffold benchmark script with case loading and CLI entry point

**Files:**
- Create: `backend/evals/benchmark.py`

- [ ] **Step 1: Create benchmark.py with case parsing and main structure**

```python
"""Multi-model benchmark — runs eval cases across haiku/sonnet/opus, measuring correctness, speed, and cost."""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.agent import agent, AgentDeps
from app.config import settings, MODEL_IDS, SONNET_4_6
from app.data.loader import load_dataset, get_schema_summary

# Anthropic pricing per million tokens (USD)
# https://docs.anthropic.com/en/docs/about-claude/models#model-comparison-table
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "haiku": (1.00, 5.00),
    "sonnet": (3.00, 15.00),
    "opus": (15.00, 75.00),
}


@dataclass
class CaseResult:
    name: str
    passed: bool
    time_seconds: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    output: str
    error: str | None = None


@dataclass
class ModelReport:
    model_name: str
    model_id: str
    cases: list[CaseResult] = field(default_factory=list)


@dataclass
class EvalCase:
    name: str
    question: str
    expected_output: str
    evaluator_type: str  # "Contains" or "LLMJudge"
    evaluator_args: dict


def load_cases(path: Path) -> list[EvalCase]:
    with open(path) as f:
        data = yaml.safe_load(f)
    cases = []
    for case in data["cases"]:
        ev = case["evaluators"][0]
        cases.append(
            EvalCase(
                name=case["name"],
                question=case["inputs"],
                expected_output=case.get("expected_output", ""),
                evaluator_type=ev["name"],
                evaluator_args=ev.get("arguments", {}),
            )
        )
    return cases


def calc_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = PRICE_PER_MTOK[model_name]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


async def main() -> None:
    cases = load_cases(Path("evals/cases.yaml"))
    print(f"Loaded {len(cases)} eval cases")
    print(f"Models: {', '.join(MODEL_IDS.keys())}")
    print()

    df = load_dataset()
    schema = get_schema_summary(df)

    reports: list[ModelReport] = []
    for model_name, model_id in MODEL_IDS.items():
        report = await run_model(model_name, model_id, cases, schema)
        reports.append(report)

    print_tables(reports)
    save_report(reports)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Verify the script loads cases without errors**

Run from `backend/` directory:
```bash
cd backend && uv run python -c "
from evals.benchmark import load_cases
from pathlib import Path
cases = load_cases(Path('evals/cases.yaml'))
for c in cases:
    print(f'{c.name}: {c.evaluator_type} - {c.question[:40]}...')
"
```
Expected: All 10 cases printed with their evaluator types.

- [ ] **Step 3: Commit**

```bash
git add backend/evals/benchmark.py
git commit -m "feat: scaffold multi-model benchmark with case loading"
```

---

### Task 2: Implement per-case agent execution with timing and token capture

**Files:**
- Modify: `backend/evals/benchmark.py`

- [ ] **Step 1: Add the `run_model` and `run_case` functions**

Add these functions before `main()` in `benchmark.py`:

```python
async def run_case(
    case: EvalCase,
    model_name: str,
    override_model: OpenAIChatModel,
    schema: str,
) -> CaseResult:
    deps = AgentDeps(df_schema=schema)
    input_tokens = 0
    output_tokens = 0
    output = ""
    error = None
    passed = False

    start = time.perf_counter()
    try:
        result = await agent.run(case.question, deps=deps, model=override_model)
        elapsed = time.perf_counter() - start
        output = result.output
        usage = result.usage()
        input_tokens = usage.input_tokens or 0
        output_tokens = usage.output_tokens or 0
    except Exception as exc:
        elapsed = time.perf_counter() - start
        error = str(exc)

    if error is None:
        passed = await evaluate(case, output)

    cost = calc_cost(model_name, input_tokens, output_tokens)

    return CaseResult(
        name=case.name,
        passed=passed,
        time_seconds=round(elapsed, 2),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 6),
        output=output,
        error=error,
    )


async def run_model(
    model_name: str,
    model_id: str,
    cases: list[EvalCase],
    schema: str,
) -> ModelReport:
    print(f"--- {model_name} ({model_id}) ---")
    provider = OpenAIProvider(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    )
    override_model = OpenAIChatModel(model_id, provider=provider)
    report = ModelReport(model_name=model_name, model_id=model_id)

    for case in cases:
        print(f"  {case.name}...", end=" ", flush=True)
        result = await run_case(case, model_name, override_model, schema)
        status = "PASS" if result.passed else "FAIL"
        if result.error:
            status = "ERROR"
        print(f"{status} ({result.time_seconds}s)")
        report.cases.append(result)

    return report
```

- [ ] **Step 2: Verify the functions are syntactically correct**

```bash
cd backend && uv run python -c "from evals.benchmark import run_model, run_case; print('OK')"
```
Expected: `OK` (the `evaluate` function doesn't exist yet, but import should work)

- [ ] **Step 3: Commit**

```bash
git add backend/evals/benchmark.py
git commit -m "feat: add per-case agent execution with timing and token capture"
```

---

### Task 3: Implement correctness evaluation (Contains + LLMJudge)

**Files:**
- Modify: `backend/evals/benchmark.py`

- [ ] **Step 1: Add the `evaluate` function**

Add this function before `run_case()` in `benchmark.py`:

```python
async def evaluate(case: EvalCase, output: str) -> bool:
    if case.evaluator_type == "Contains":
        value = case.evaluator_args["value"]
        return value in output

    if case.evaluator_type == "LLMJudge":
        return await llm_judge(case, output)

    return False


async def llm_judge(case: EvalCase, output: str) -> bool:
    """Use a fixed Sonnet judge to evaluate LLMJudge cases."""
    provider = OpenAIProvider(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    )
    judge_model = OpenAIChatModel(SONNET_4_6, provider=provider)

    from pydantic_ai import Agent

    judge = Agent(
        judge_model,
        system_prompt="You are an evaluation judge. Given an input, expected behavior, and actual output, determine if the output meets the rubric. Respond with exactly 'PASS' or 'FAIL' followed by a brief explanation.",
    )

    rubric = case.evaluator_args.get("rubric", "")
    prompt_parts = [f"Rubric: {rubric}"]
    if case.evaluator_args.get("include_input"):
        prompt_parts.append(f"Input: {case.question}")
    if case.evaluator_args.get("include_expected_output"):
        prompt_parts.append(f"Expected: {case.expected_output}")
    prompt_parts.append(f"Actual output: {output}")

    result = await judge.run("\n\n".join(prompt_parts))
    return result.output.strip().upper().startswith("PASS")
```

- [ ] **Step 2: Verify Contains evaluation works**

```bash
cd backend && uv run python -c "
import asyncio
from evals.benchmark import evaluate, EvalCase

case = EvalCase(
    name='test', question='test', expected_output='500',
    evaluator_type='Contains', evaluator_args={'value': '500'},
)
assert asyncio.run(evaluate(case, 'There are 500 rows')) == True
assert asyncio.run(evaluate(case, 'There are 400 rows')) == False
print('Contains evaluation OK')
"
```
Expected: `Contains evaluation OK`

- [ ] **Step 3: Commit**

```bash
git add backend/evals/benchmark.py
git commit -m "feat: add correctness evaluation with Contains and LLMJudge"
```

---

### Task 4: Implement terminal output tables

**Files:**
- Modify: `backend/evals/benchmark.py`

- [ ] **Step 1: Add the `print_tables` function**

Add this function after the evaluation functions in `benchmark.py`:

```python
def print_tables(reports: list[ModelReport]) -> None:
    # Per-case breakdown
    print()
    print("=" * 90)
    print("PER-CASE RESULTS")
    print("=" * 90)
    header = f"{'Case':<22} {'Model':<9} {'Pass':<6} {'Time':>8} {'In Tok':>8} {'Out Tok':>9} {'Cost':>10}"
    print(header)
    print("-" * 90)

    # Group by case name for readability
    case_names = [c.name for c in reports[0].cases]
    for case_name in case_names:
        for report in reports:
            case = next(c for c in report.cases if c.name == case_name)
            mark = "PASS" if case.passed else ("ERR" if case.error else "FAIL")
            print(
                f"{case.name:<22} {report.model_name:<9} {mark:<6} "
                f"{case.time_seconds:>7.1f}s {case.input_tokens:>8,} {case.output_tokens:>9,} "
                f"${case.cost_usd:>9.4f}"
            )
        print()

    # Model summary
    print("=" * 90)
    print("MODEL SUMMARY")
    print("=" * 90)
    header = f"{'Model':<9} {'Passed':<9} {'Pass %':>8} {'Avg Time':>10} {'Total Tok':>11} {'Total Cost':>12}"
    print(header)
    print("-" * 90)

    for report in reports:
        total = len(report.cases)
        passed = sum(1 for c in report.cases if c.passed)
        avg_time = sum(c.time_seconds for c in report.cases) / total if total else 0
        total_tokens = sum(c.input_tokens + c.output_tokens for c in report.cases)
        total_cost = sum(c.cost_usd for c in report.cases)
        print(
            f"{report.model_name:<9} {passed}/{total:<7} {passed / total * 100:>7.0f}% "
            f"{avg_time:>9.1f}s {total_tokens:>11,} ${total_cost:>11.4f}"
        )

    print()
```

- [ ] **Step 2: Verify print_tables compiles**

```bash
cd backend && uv run python -c "from evals.benchmark import print_tables; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/evals/benchmark.py
git commit -m "feat: add terminal summary tables for benchmark output"
```

---

### Task 5: Implement JSON report saving

**Files:**
- Modify: `backend/evals/benchmark.py`
- Create: `backend/evals/reports/.gitkeep`

- [ ] **Step 1: Add the `save_report` function**

Add this function after `print_tables` in `benchmark.py`:

```python
def save_report(reports: list[ModelReport]) -> None:
    reports_dir = Path("evals/reports")
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    report_path = reports_dir / f"{timestamp}.json"

    data: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "models": {},
    }

    for report in reports:
        total = len(report.cases)
        passed = sum(1 for c in report.cases if c.passed)
        avg_time = sum(c.time_seconds for c in report.cases) / total if total else 0
        total_input = sum(c.input_tokens for c in report.cases)
        total_output = sum(c.output_tokens for c in report.cases)
        total_cost = sum(c.cost_usd for c in report.cases)

        data["models"][report.model_name] = {
            "model_id": report.model_id,
            "cases": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "time_seconds": c.time_seconds,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "cost_usd": c.cost_usd,
                    "output": c.output,
                    "error": c.error,
                }
                for c in report.cases
            ],
            "summary": {
                "passed": passed,
                "total": total,
                "pass_rate": round(passed / total, 2) if total else 0,
                "avg_time_seconds": round(avg_time, 2),
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_cost_usd": round(total_cost, 4),
            },
        }

    with open(report_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Report saved to {report_path}")
```

- [ ] **Step 2: Create the reports directory with .gitkeep**

```bash
mkdir -p backend/evals/reports && touch backend/evals/reports/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add backend/evals/benchmark.py backend/evals/reports/.gitkeep
git commit -m "feat: add JSON report saving for benchmark results"
```

---

### Task 6: Add justfile target, gitignore, and CLAUDE.md update

**Files:**
- Modify: `justfile`
- Modify: `.gitignore`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add `bench` recipe to justfile**

Append to `justfile`:

```
# Run multi-model benchmark (correctness, speed, cost)
bench:
    cd backend && uv run python evals/benchmark.py
```

- [ ] **Step 2: Add reports JSON to .gitignore**

Append to `.gitignore`:

```
# Benchmark reports
backend/evals/reports/*.json
```

- [ ] **Step 3: Add `just bench` to CLAUDE.md Commands section**

In `CLAUDE.md`, add to the Commands code block:

```
just bench             # Run multi-model benchmark (correctness, speed, cost)
```

- [ ] **Step 4: Commit**

```bash
git add justfile .gitignore CLAUDE.md
git commit -m "chore: add bench target, gitignore reports, update CLAUDE.md"
```

---

### Task 7: Run the benchmark and verify end-to-end

**Files:**
- None (verification only)

- [ ] **Step 1: Run the benchmark**

```bash
just bench
```

Expected: The script runs all 10 cases across 3 models (30 total agent calls), printing progress as it goes, then printing two summary tables and saving a JSON report.

- [ ] **Step 2: Verify the JSON report was saved**

```bash
ls -la backend/evals/reports/*.json
cat backend/evals/reports/*.json | python -m json.tool | head -30
```

Expected: A JSON file with timestamp, git_sha, and model data.

- [ ] **Step 3: Verify pricing URL comment is in the code**

Check that the `PRICE_PER_MTOK` dict has the Anthropic docs URL as a comment.

- [ ] **Step 4: Commit the spec (if not already committed)**

```bash
git add docs/superpowers/specs/2026-03-25-multi-model-benchmark-design.md
git commit -m "docs: add multi-model benchmark design spec"
```

---

### Task 8: Add benchmark findings to README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README**

Check what's in the README currently to find the right place to add benchmark results.

- [ ] **Step 2: Add a concise "Model Comparison" section to README**

After running the benchmark, add a section with the actual results showing the model summary table and key findings. Keep it concise — just the summary table and 2-3 bullet points about what the data shows.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add model comparison benchmark findings to README"
```
