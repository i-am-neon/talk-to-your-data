# Talk to Your Data — Design Spec

## Overview

A web application where users ask natural language questions about a SaaS company dataset and receive structured answers (text, tables, charts) along with the generated code. An LLM interprets the question, generates pandas/matplotlib code, executes it in a sandboxed environment, and returns the results.

## Architecture

```
┌─────────────────────┐         ┌─────────────────────────────┐        ┌───────────┐
│   React Frontend    │  POST   │        FastAPI Backend       │        │  LiteLLM  │
│   (Vercel)          │────────▶│                              │───────▶│  Proxy    │
│                     │◀────────│  PydanticAI Agent            │◀───────│ (Railway) │
│  - Chat UI          │  JSON   │  - System prompt w/ schema   │        └───────────┘
│  - Code display     │         │  - execute_python_code tool  │
│  - Chart rendering  │         │                              │        ┌───────────┐
│  - Chat history     │         │  Logfire tracing             │───────▶│   E2B     │
│    (client-side)    │         │                              │◀───────│  Sandbox  │
└─────────────────────┘         └─────────────────────────────┘        └───────────┘
```

### Request Flow

1. User types a question in the React UI
2. Frontend sends `POST /api/query` with `{ question, history[] }`
3. Backend builds system prompt (includes dataset schema) and passes question + history to PydanticAI agent
4. Agent calls LiteLLM proxy to generate Python code
5. Agent's `execute_python_code` tool sends code to E2B sandbox (where `df` is pre-loaded)
6. E2B returns stdout, stderr, and any generated images (base64 PNG)
7. If execution fails, PydanticAI's tool loop lets the LLM retry with fixed code (up to 3 retries)
8. Backend returns `{ answer, code, images[], error? }` to frontend
9. Frontend renders the answer as text, table, and/or chart image

## Stack

| Layer | Technology | Hosting |
|-------|-----------|---------|
| Frontend | Vite + React + TypeScript + shadcn/ui | Vercel (auto-deploy on push to main) |
| Backend | FastAPI + PydanticAI + Logfire | Railway (auto-deploy on push to main) |
| Sandbox | E2B Code Interpreter (custom template) | E2B cloud (free tier, $100 credit) |
| LLM | Genesis-provided LiteLLM Proxy | Already hosted on Railway |

## Backend Design

### Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, CORS, lifespan
│   ├── config.py            # Settings (API keys, URLs)
│   ├── routes/
│   │   └── query.py         # POST /api/query endpoint
│   ├── agent/
│   │   ├── agent.py         # PydanticAI agent definition + system prompt builder
│   │   └── tools.py         # execute_python_code tool (E2B integration)
│   └── data/
│       ├── loader.py        # CSV loading + schema summary generation
│       └── sample_data.csv  # The dataset
├── pyproject.toml
└── Dockerfile
```

### Key Components

**`agent.py`** — PydanticAI agent with a dynamic system prompt. The prompt includes dataset schema (column names, types, sample values, row count) and instructions for writing pandas/matplotlib code. Configured to use the LiteLLM proxy as its model endpoint.

**`tools.py`** — Single tool: `execute_python_code(code: str) → ExecutionResult`. Creates an E2B sandbox, sends the code, returns stdout/stderr/images. On startup, the sandbox runs "launch code" that loads the CSV into `df` and imports pandas/matplotlib/numpy.

**`loader.py`** — Loads CSV into a DataFrame on startup. Generates a schema summary string (column names, dtypes, 3 sample values per column, basic stats like min/max/mean for numeric columns). Injected into the system prompt.

**`query.py`** — Single endpoint. Takes `{ question: str, history: list[{role, content}] }`. Builds the system prompt via loader, runs the PydanticAI agent, returns `{ answer: str, code: str, images: list[str], table: list[dict] | None, error: str | None }`. The `table` field contains structured tabular data when the agent produces a DataFrame result; `images` contains base64 PNG strings for charts.

### System Prompt Strategy

Dataset schema is baked into the system prompt rather than exposed as a tool. This avoids a wasted tool call on every request since the data is static. When file upload is added later, the schema section is regenerated dynamically before each agent call.

```python
def build_system_prompt(df: pd.DataFrame) -> str:
    schema = get_schema_summary(df)
    return f"""You are a data analyst. The user's dataset is loaded as `df`.

{schema}

Write pandas/matplotlib code to answer the user's question..."""
```

### LiteLLM Proxy Configuration

PydanticAI is configured with an OpenAI-compatible model pointing at the Genesis LiteLLM proxy. API key and base URL stored in environment variables (`LITELLM_API_KEY`, `LITELLM_BASE_URL`). Model name to request will be discovered by probing the proxy's `/v1/models` endpoint during setup.

### CORS

`CORSMiddleware` configured with `allow_origins=["*"]` for the take-home. Would be restricted to the Vercel domain in production.

### Health Check

`GET /health` — returns 200. Used to verify Railway deployment is running.

### E2B Sandbox Lifecycle

Fresh sandbox created per request. The sandbox lives for the duration of one agent run (which may include retries). No persistence between requests. The CSV file is uploaded to the sandbox on creation via `sandbox.files.write()`, then launch code loads it into `df` and imports pandas/matplotlib/numpy. Expected latency: ~3-5 seconds total per request (sandbox creation + LLM call + code execution).

## Frontend Design

### Project Structure

```
frontend/
├── src/
│   ├── App.tsx              # Main layout
│   ├── main.tsx             # Entry point
│   ├── components/
│   │   ├── ChatInput.tsx    # Text input + submit button
│   │   ├── ChatMessage.tsx  # Single message (user or assistant)
│   │   ├── CodeBlock.tsx    # Syntax-highlighted code display (collapsible)
│   │   ├── ChartImage.tsx   # Renders base64 chart images
│   │   └── DataTable.tsx    # Renders tabular results
│   ├── hooks/
│   │   └── useChat.ts       # Chat state management + API calls
│   ├── lib/
│   │   └── api.ts           # API client (POST /api/query)
│   └── types.ts             # Shared types
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### UI

Single-page chat interface. Messages scroll vertically. User messages right-aligned, assistant responses left-aligned. Each assistant response can contain:
- Text answer
- Collapsible code block showing the generated pandas code
- Chart image(s) if the agent produced any

### State Management

`useChat` hook manages conversation as React state: `messages[]` with `{role, content, code?, images?[]}`. On submit, appends user message, calls API with full history, appends response. Loading indicator shown while waiting.

### No Streaming for v1

API returns a complete response. Agent may take a few seconds (LLM call + E2B execution). Streaming could be added later but adds complexity with tool calls + E2B results.

## Error Handling

**LLM errors** (proxy down, rate limit, bad response): PydanticAI surfaces as exceptions. Endpoint returns `{ error: "Unable to process your question. Please try again." }` with 502. Frontend shows inline in chat.

**Code execution errors** (buggy generated code): Most common failure. PydanticAI's tool loop returns the error/traceback to the LLM, which retries with fixed code (up to 3 retries). If still failing, agent returns the error with explanation.

**E2B errors** (sandbox creation fails, timeout): Tool catches and returns structured error. Execution timeout: 30 seconds. If E2B is down entirely, user-facing error.

**Malformed questions** (gibberish, empty): LLM handles naturally — responds saying it doesn't understand and suggests example questions. Frontend checks for empty string.

## Evaluation

Using `pydantic-evals` — natural fit with PydanticAI + Logfire. Start with one test case, grow from there.

```
evals/
├── test_agent.py            # Eval runner
└── cases.yaml               # Test case dataset (serialized)
```

Custom evaluators for domain-specific assertions (e.g., `HasImage`, `HasNumericAnswer`). Span-based evaluation via Logfire to assert tool usage patterns.

## Dev Workflows

Root `justfile` wraps common commands. Grows organically as friction shows up.

```just
dev-backend      # Start backend dev server
dev-frontend     # Start frontend dev server
dev              # Start everything
test             # Run backend tests
evals            # Run evals (real LLM + E2B calls)
```

Commands documented in `CLAUDE.md` for agent discoverability.

## Deployment

Both Vercel and Railway auto-deploy on push to main. No manual deploy steps.

- **Vercel**: Connected to repo, root directory set to `frontend/`
- **Railway**: Connected to repo, root directory set to `backend/`, Dockerfile-based

## Monorepo Structure

```
genesis-take-home/
├── backend/
├── frontend/
├── evals/
├── justfile
├── CLAUDE.md
├── ASSIGNMENT.md
└── README.md
```

## Future Additions (Not in v1)

- **Conversation memory**: Add server-side chat storage (SQLite or similar). Frontend already sends history; backend just needs to persist it.
- **File upload**: Accept user CSVs. Regenerate system prompt schema dynamically. Load into E2B sandbox instead of bundled CSV.
- **Streaming**: SSE from FastAPI, progressive rendering in frontend.
- **Multiple data sources**: Extend loader to handle multiple files, join across datasets.
