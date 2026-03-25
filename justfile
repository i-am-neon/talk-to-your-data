# Start backend dev server
dev-backend:
    cd backend && uv run uvicorn app.main:app --reload

# Start frontend dev server
dev-frontend:
    cd frontend && npm run dev

# Start everything (requires parallel execution)
dev:
    just dev-backend & just dev-frontend & wait

# Run backend tests
test:
    cd backend && uv run pytest tests/ -v

# Run evals (real LLM + E2B calls)
evals:
    cd backend && uv run pytest evals/ -v

# Install all dependencies
install:
    cd backend && uv sync
    cd frontend && npm install
