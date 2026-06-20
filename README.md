# Talk to Your Data

**[▶ Watch the demo](https://www.loom.com/share/712eac8a08c84ab491be7dd7e1eed04c)** | **[API](https://genesis-take-home-production.up.railway.app/docs)**

Ask questions about a SaaS dataset in plain English. Get text, interactive charts, or sortable tables back. The agent writes pandas/matplotlib code, runs it in a sandboxed VM, and streams the result.


[![Talk to Your Data — demo video](https://cdn.loom.com/sessions/thumbnails/712eac8a08c84ab491be7dd7e1eed04c-303f7806b42610d9.jpg)](https://www.loom.com/share/712eac8a08c84ab491be7dd7e1eed04c)

> ▶ Click to watch the full walkthrough (~4 min).

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Vite + React + TypeScript + shadcn/ui → Vercel |
| Backend | FastAPI + PydanticAI + PostgreSQL → Railway |
| Sandbox | E2B Code Interpreter (Firecracker microVMs) |
| LLM | Genesis LiteLLM Proxy (OpenAI-compatible) |
| Observability | [Logfire](https://logfire-us.pydantic.dev/tommywilczek/genesis-take-home?last=300000) |
| Evals | pydantic-evals |
| CI | GitHub CLI |

**Flow:** React UI → PydanticAI agent → LLM generates pandas code → E2B executes → streamed answer + artifacts

## AI Tools Used

Claude Code (Opus 4.6, 1M context, max thinking) for everything. I use Anthropic's "superpowers" skill pack to force structured brainstorming before implementation, letting the agent plan and execute 15+ minute runs autonomously. I also gave it CLI skills for Railway, Vercel, shadcn/ui, and Playwright so it can deploy, scaffold UI, and visually verify its own work without me in the loop.

## Interesting Challenges

- **PydanticAI retry loop** — wiring `ModelRetry` so the agent sees stdout/stderr from failed E2B executions and self-corrects instead of looping uselessly.
- **Conversation memory** — PydanticAI's full message history (including tool calls/results) needed to round-trip through JSONB serialization correctly across turns.
- **Stale closures** — `useChat` callbacks captured old message arrays, causing flicker and duplicate responses. Solved with `useRef` for stable references.

## Design Decisions

- **E2B sandboxing** — LLM-generated code runs in Firecracker microVMs, not in-process. Arbitrary Python without risking the server, ~150ms cold starts.
- **Pandas over SQL** — analysis and visualization in one execution context. SQL would need a separate charting pipeline and can't do correlation matrices or custom plots.
- **Workspace artifacts** — charts and tables are versioned objects, not inline message content. The agent can update an existing artifact ("now color it by industry") and the UI tracks version history.
  - Standard charts/tables render as Recharts/shadcn components matching the design system. Exotic visualizations (heatmaps, violin plots) fall back to matplotlib PNGs.

## Model Comparison

Benchmarked all three models against 25 eval cases (10 functional + 15 red team security) run in parallel. `just bench` to reproduce.

| Model | Pass Rate | Avg Latency | Cost (25 queries) |
|-------|-----------|-------------|-------------------|
| **Haiku 4.5** | **100%** | **3.7s** | **$0.09** |
| **Sonnet 4.6** | **100%** | 5.7s | $0.24 |
| **Opus 4.6** | **100%** | 6.1s | $0.41 |

**Findings:** All three models pass every case — functional, edge-case, and security. Haiku is 2x faster and 4-5x cheaper than Sonnet/Opus. Default model is Sonnet for open-ended reasoning quality; Haiku is viable for cost-sensitive deployments.

## Red Team Evals

15 adversarial test cases across 4 attack categories (prompt injection, data exfiltration, sandbox abuse, output integrity) using a custom `RedTeamJudge` evaluator. Run `just red-team` to reproduce. Initial run found 2 vulnerabilities (role override compliance, system prompt leakage) — both fixed via system prompt hardening. All 15 cases pass.

## What I'd Improve

- Broader eval suite — more edge cases like ambiguous questions, empty results, and multi-step reasoning chains
- Component catalog (Storybook-style) for the artifact renderers so charts/tables/code blocks can be developed and tested in isolation

## Local Setup

Use Claude Code's `/install` skill, or point your agent at `install.md`. Manual:

```bash
cp backend/.env.example backend/.env   # fill in API keys
just dev                                # starts backend + frontend
```
