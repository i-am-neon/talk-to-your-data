# genesis-take-home

> Natural language data agent — FastAPI + PydanticAI backend, Vite + React + shadcn/ui frontend, E2B sandbox for code execution.

I want you to set up this project for local development. Execute all the steps below, asking me when you hit a decision point.

## OBJECTIVE

Get `just dev` running with both backend (port 8000) and frontend (port 5173) serving successfully.

## DONE WHEN

- `just dev` starts both servers without errors
- `curl http://localhost:8000/docs` returns the FastAPI OpenAPI page
- Frontend loads at `http://localhost:5173`
- `just test` passes

## TODO

- [ ] Ensure `uv` is installed (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [ ] Ensure `just` is installed (`brew install just`)
- [ ] Ensure Node 22+ is available (check `.nvmrc` in `frontend/` if present)
- [ ] Run `just install` to install backend (uv sync) and frontend (npm install) dependencies
- [ ] Copy `backend/.env.example` to `backend/.env`
- [ ] **[INTERACTIVE]** Fill in API keys in `backend/.env`:
  - `LITELLM_API_KEY` — Genesis LiteLLM proxy key (see ASSIGNMENT.md)
  - `E2B_API_KEY` — Ask me for this, or skip if you just want to run tests without sandbox execution
  - `LOGFIRE_TOKEN` — Optional, leave blank to disable tracing
- [ ] Run `just test` to verify backend tests pass
- [ ] Run `just dev` to start both servers
- [ ] Verify: `curl http://localhost:8000/docs` returns HTML
- [ ] Verify: frontend loads at `http://localhost:5173`

## EXECUTE NOW

Complete the TODO list above to achieve the OBJECTIVE. Pause at [INTERACTIVE] steps to ask me before continuing.
