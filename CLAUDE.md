# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Natural language data agent — users ask questions about a SaaS dataset in plain English and get text, table, or chart answers. See `ASSIGNMENT.md` for requirements and `docs/superpowers/specs/2026-03-24-data-agent-design.md` for the design spec.

## Architecture

- **Frontend** (`frontend/`): Vite + React + TypeScript + shadcn/ui → Vercel
- **Backend** (`backend/`): FastAPI + PydanticAI + Logfire → Railway
- **Sandbox**: E2B Code Interpreter for executing LLM-generated pandas/matplotlib code
- **LLM**: Genesis LiteLLM Proxy (OpenAI-compatible)

Request flow: React UI → `POST /api/query` → PydanticAI agent → LiteLLM → agent calls `execute_python_code` tool → E2B sandbox → returns answer + code + images

## Commands

```
just dev              # Start backend + frontend dev servers
just dev-backend      # Start backend only
just dev-frontend     # Start frontend only
just test             # Run backend tests
just evals            # Run evals (real LLM + E2B calls)
```

## When I say "make a target for that"

- Create a recipe in the root `justfile`
- Add a one-line description to the Commands section above
