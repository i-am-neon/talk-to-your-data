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

# Run database migrations
migrate:
    cd backend && psql "$DATABASE_URL" -f migrations/001_create_tables.sql

# Run multi-model benchmark (correctness, speed, cost)
bench:
    cd backend && uv run python -m evals.benchmark

# Run red team evals (adversarial security tests)
red-team:
    cd backend && uv run pytest evals/test_red_team.py -v

# Install all dependencies
install:
    cd backend && uv sync
    cd frontend && npm install
