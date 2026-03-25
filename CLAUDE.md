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

## Git Workflow — Atomic Commits

- Commit after each completed logical subtask, not at the end of implementation
- Each commit should be one self-contained change that passes tests independently
- Never mix refactoring with feature work in the same commit
- Use conventional commit messages: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Workflow per subtask: implement → verify/test → commit → next subtask
- If a task has multiple logical steps, each step gets its own commit
- The test: if you need "and" to describe the commit, split it into two

## When I say "make a target for that"

- Create a recipe in the root `justfile`
- Add a one-line description to the Commands section above
