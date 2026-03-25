# Talk to Your Data — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a natural language data agent where users ask questions about a SaaS dataset and get text, table, or chart answers.

**Architecture:** React frontend (Vercel) → FastAPI backend (Railway) → PydanticAI agent with single `execute_python_code` tool → E2B sandbox for safe pandas/matplotlib execution. LLM via Genesis LiteLLM proxy (`claude-sonnet-4-5`).

**Tech Stack:** Vite, React, TypeScript, shadcn/ui, FastAPI, PydanticAI, Logfire, E2B Code Interpreter, pydantic-evals

**Spec:** `docs/superpowers/specs/2026-03-24-data-agent-design.md`

---

## File Map

### Root
- `justfile` — dev workflow commands
- `CLAUDE.md` — agent guidance (exists)
- `README.md` — assignment deliverable

### Backend (`backend/`)
- `pyproject.toml` — Python deps (uv)
- `Dockerfile` — Railway deployment
- `app/__init__.py`
- `app/main.py` — FastAPI app, CORS, lifespan, health check
- `app/config.py` — Pydantic Settings (env vars)
- `app/routes/__init__.py`
- `app/routes/query.py` — POST /api/query endpoint
- `app/agent/__init__.py`
- `app/agent/agent.py` — PydanticAI agent + system prompt builder
- `app/agent/tools.py` — execute_python_code tool (E2B)
- `app/data/__init__.py`
- `app/data/loader.py` — CSV loading + schema summary
- `app/data/sample_data.csv` — the dataset
- `tests/test_loader.py` — loader unit tests
- `tests/test_query.py` — endpoint integration test

### Frontend (`frontend/`)
- `package.json`, `tsconfig.json`, `vite.config.ts` — scaffolding
- `src/main.tsx` — entry point
- `src/App.tsx` — main layout
- `src/types.ts` — shared types
- `src/lib/api.ts` — API client
- `src/hooks/useChat.ts` — chat state + API calls
- `src/components/ChatInput.tsx`
- `src/components/ChatMessage.tsx`
- `src/components/CodeBlock.tsx`
- `src/components/ChartImage.tsx`
- `src/components/DataTable.tsx` (deferred — tables render as text in answer for v1)

### Evals (`backend/evals/`)
- `test_agent.py` — eval runner
- `cases.yaml` — test case dataset

---

## Task 1: Project Scaffolding

**Files:**
- Create: `justfile`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/data/__init__.py`
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/agent/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create backend project with uv**

```bash
mkdir -p backend && cd backend
```

Create `pyproject.toml` manually:

```toml
[project]
name = "data-agent"
version = "0.1.0"
description = "Natural language data agent"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pydantic-ai[openai,logfire]>=0.2",
    "e2b-code-interpreter>=1.2",
    "pydantic-settings>=2.7",
    "pandas>=2.2",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.28",
    "pydantic-evals>=1.0",
]
```

- [ ] **Step 2: Create `__init__.py` files**

Create empty `__init__.py` in `backend/app/`, `backend/app/data/`, `backend/app/routes/`, `backend/app/agent/`, `backend/tests/`.

- [ ] **Step 3: Create root justfile**

```just
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
```

- [ ] **Step 4: Install backend dependencies**

```bash
cd backend && uv sync
```

- [ ] **Step 5: Commit**

```bash
git add justfile backend/pyproject.toml backend/uv.lock backend/app/ backend/tests/
git commit -m "feat: scaffold backend project with uv and justfile"
```

---

## Task 2: Data Loader

**Files:**
- Create: `backend/app/data/sample_data.csv`
- Create: `backend/app/data/loader.py`
- Create: `backend/tests/test_loader.py`

- [ ] **Step 1: Download the sample CSV**

Download `sample_data.csv` from the assignment link and place at `backend/app/data/sample_data.csv`. If the link isn't accessible, create a representative sample with columns: `company_name`, `arr`, `employee_count`, `industry`, `founding_year`, `churn_rate`, `growth_rate` (at least 20 rows for testing).

- [ ] **Step 2: Write the failing test for `get_schema_summary`**

```python
# backend/tests/test_loader.py
import pandas as pd
from app.data.loader import load_dataset, get_schema_summary


def test_get_schema_summary_contains_column_names():
    df = pd.DataFrame({
        "company_name": ["Acme", "Beta", "Gamma"],
        "arr": [1000000, 2000000, 3000000],
        "employee_count": [50, 100, 150],
    })
    summary = get_schema_summary(df)
    assert "company_name" in summary
    assert "arr" in summary
    assert "employee_count" in summary


def test_get_schema_summary_contains_row_count():
    df = pd.DataFrame({"x": [1, 2, 3]})
    summary = get_schema_summary(df)
    assert "3" in summary


def test_load_dataset_returns_dataframe():
    df = load_dataset()
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "company_name" in df.columns or "Company" in df.columns
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_loader.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 4: Implement loader**

```python
# backend/app/data/loader.py
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent
CSV_PATH = DATA_DIR / "sample_data.csv"


def load_dataset(path: Path = CSV_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def get_schema_summary(df: pd.DataFrame) -> str:
    lines = [f"Dataset: {len(df)} rows, {len(df.columns)} columns\n"]
    lines.append("Columns:")

    for col in df.columns:
        dtype = df[col].dtype
        samples = df[col].dropna().head(3).tolist()
        sample_str = ", ".join(str(s) for s in samples)
        line = f"  - {col} ({dtype}): e.g. {sample_str}"

        if pd.api.types.is_numeric_dtype(df[col]):
            line += f" | min={df[col].min()}, max={df[col].max()}, mean={df[col].mean():.2f}"

        lines.append(line)

    return "\n".join(lines)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_loader.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/data/ backend/tests/test_loader.py
git commit -m "feat: add CSV loader and schema summary generation"
```

---

## Task 3: Config

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/.env.example`

- [ ] **Step 1: Create config with pydantic-settings**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    litellm_api_key: str
    litellm_base_url: str = "https://litellm-production-f079.up.railway.app"
    litellm_model: str = "claude-sonnet-4-5"
    e2b_api_key: str
    logfire_token: str = ""
    frontend_url: str = "*"

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 2: Create `.env.example`**

```
LITELLM_API_KEY=sk-your-key-here
LITELLM_BASE_URL=https://litellm-production-f079.up.railway.app
LITELLM_MODEL=claude-sonnet-4-5
E2B_API_KEY=e2b_your-key-here
LOGFIRE_TOKEN=
```

- [ ] **Step 3: Create `.env` with real keys (do NOT commit)**

Copy `.env.example` to `.env` and fill in real values. The LiteLLM key is in `ASSIGNMENT.md`. Get the E2B key from https://e2b.dev dashboard (free signup). Logfire token from https://logfire.pydantic.dev (optional).

Verify `.env` is in `.gitignore`.

- [ ] **Step 3.5: Verify LiteLLM proxy model**

```bash
curl https://litellm-production-f079.up.railway.app/v1/models -H "Authorization: Bearer $LITELLM_API_KEY"
```

Verify `claude-sonnet-4-5` is in the list. If not, update `LITELLM_MODEL` in `.env` to match an available model.

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/.env.example
git commit -m "feat: add pydantic-settings config with env vars"
```

---

## Task 4: E2B Tool

**Files:**
- Create: `backend/app/agent/tools.py`

- [ ] **Step 1: Create the execute_python_code tool**

```python
# backend/app/agent/tools.py
import base64
from dataclasses import dataclass
from pathlib import Path

from e2b_code_interpreter import Sandbox
from pydantic_ai import ModelRetry, RunContext

from app.config import settings
from app.data.loader import CSV_PATH

LAUNCH_CODE = """\
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_theme()

df = pd.read_csv('/tmp/data.csv')
"""

MAX_OUTPUT_LENGTH = 50_000


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    images: list[str]  # base64 PNG strings
    code: str = ""
    error: str | None = None


def execute_python_code(code: str) -> ExecutionResult:
    """Execute Python code in an E2B sandbox. Returns structured result."""
    sbx = Sandbox(api_key=settings.e2b_api_key, timeout=60)
    try:
        # Upload CSV to sandbox
        with open(CSV_PATH, "rb") as f:
            sbx.files.write("/tmp/data.csv", f.read())

        # Run launch code
        sbx.run_code(LAUNCH_CODE)

        # Execute user code
        execution = sbx.run_code(code, timeout=30)

        stdout = execution.logs.stdout
        stderr = execution.logs.stderr

        # Truncate long output
        if len(stdout) > MAX_OUTPUT_LENGTH:
            stdout = stdout[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"
        if len(stderr) > MAX_OUTPUT_LENGTH:
            stderr = stderr[:MAX_OUTPUT_LENGTH] + "\n... (output truncated)"

        # Collect images
        images = []
        for result in execution.results:
            if hasattr(result, "png") and result.png:
                images.append(result.png)

        error = None
        if execution.error:
            error = f"{execution.error.name}: {execution.error.value}\n{execution.error.traceback}"

        return ExecutionResult(
            stdout=stdout, stderr=stderr, images=images, code=code, error=error,
        )

    finally:
        sbx.kill()
```

Note: `execute_python_code` is a pure helper — it takes code, returns a structured result. It does NOT depend on PydanticAI's `RunContext`. The agent tool in `agent.py` calls this helper and handles the `ModelRetry` / deps logic.

- [ ] **Step 2: Commit**

```bash
git add backend/app/agent/tools.py
git commit -m "feat: add execute_python_code tool with E2B sandbox"
```

---

## Task 5: PydanticAI Agent

**Files:**
- Create: `backend/app/agent/agent.py`

- [ ] **Step 1: Create the agent**

```python
# backend/app/agent/agent.py
from dataclasses import dataclass, field

import logfire
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.tools import execute_python_code, ExecutionResult
from app.config import settings

logfire.configure(token=settings.logfire_token if settings.logfire_token else None)


@dataclass
class AgentDeps:
    df_schema: str
    results: list[ExecutionResult] = field(default_factory=list)


model = OpenAIChatModel(
    settings.litellm_model,
    provider=OpenAIProvider(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    ),
)

agent = Agent(
    model,
    deps_type=AgentDeps,
    retries=3,
)


@agent.system_prompt
def build_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return f"""\
You are a data analyst assistant. Users ask questions about a dataset in plain English.
You have access to a pandas DataFrame loaded as `df`.

{ctx.deps.df_schema}

Instructions:
- Write Python code using pandas to answer the user's question.
- Use print() to output text/numeric results.
- Use matplotlib/seaborn with plt.show() for charts when visualization is appropriate.
- For tabular results, print the DataFrame (it will be formatted as a table).
- Always provide a clear, concise text explanation along with any code output.
- If the question is unclear or cannot be answered with the data, explain why and suggest alternatives.
"""


@agent.tool
def run_code(ctx: RunContext[AgentDeps], code: str) -> str:
    """Execute Python code to analyze the dataset.

    The DataFrame is pre-loaded as `df`. pandas, numpy, matplotlib, and seaborn are available.
    Use plt.show() to display charts. Use print() to output text results.

    Args:
        code: Python code to execute. `df` is already loaded with the dataset.
    """
    result = execute_python_code(code)
    ctx.deps.results.append(result)

    if result.error:
        raise ModelRetry(
            f"Code execution failed:\n{result.error}\n"
            "Fix the code and try again."
        )

    # Build response for the LLM
    response_parts = []
    if result.stdout:
        response_parts.append(f"Output:\n{result.stdout}")
    if result.images:
        response_parts.append(f"{len(result.images)} chart(s) generated and will be shown to the user.")
    if not response_parts:
        response_parts.append("Code executed successfully with no output.")

    return "\n\n".join(response_parts)
```

Key design: `tools.py` is a pure helper (no PydanticAI dependency). `agent.py` owns the tool registration, deps management, and retry logic.

- [ ] **Step 2: Commit**

```bash
git add backend/app/agent/agent.py
git commit -m "feat: add PydanticAI agent with system prompt and LiteLLM config"
```

---

## Task 6: FastAPI App + Query Endpoint

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/routes/query.py`
- Create: `backend/tests/test_query.py`

- [ ] **Step 1: Create the query route**

```python
# backend/app/routes/query.py
from pydantic import BaseModel
from fastapi import APIRouter
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart

from app.agent.agent import agent, AgentDeps
from app.data.loader import load_dataset, get_schema_summary

router = APIRouter()

_df = load_dataset()
_schema = get_schema_summary(_df)


class HistoryMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    question: str
    history: list[HistoryMessage] = []


class QueryResponse(BaseModel):
    answer: str
    code: str = ""
    images: list[str] = []
    error: str | None = None


def _build_message_history(history: list[HistoryMessage]) -> list[ModelMessage] | None:
    """Convert frontend history to PydanticAI message format."""
    if not history:
        return None
    messages: list[ModelMessage] = []
    for msg in history:
        if msg.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=msg.content)]))
    return messages


@router.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    if not req.question.strip():
        return QueryResponse(answer="", error="Please enter a question.")

    deps = AgentDeps(df_schema=_schema)

    try:
        message_history = _build_message_history(req.history)
        result = await agent.run(req.question, deps=deps, message_history=message_history)

        # Extract code and images from deps (populated by tool)
        code = ""
        images = []
        for r in deps.results:
            if r.code:
                code = r.code  # use the last executed code
            if r.images:
                images.extend(r.images)

        return QueryResponse(
            answer=result.output,
            code=code,
            images=images,
        )
    except Exception as e:
        return QueryResponse(
            answer="",
            error=f"Unable to process your question: {str(e)}",
        )
```

- [ ] **Step 2: Create the FastAPI app**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.query import router

app = FastAPI(title="Data Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Verify the server starts**

```bash
cd backend && uv run uvicorn app.main:app --reload
```

Then in another terminal:

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Write integration test for query endpoint**

```python
# backend/tests/test_query.py
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_empty_question():
    response = client.post("/api/query", json={"question": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == "Please enter a question."
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/routes/ backend/tests/test_query.py
git commit -m "feat: add FastAPI app with query endpoint and health check"
```

---

## Task 7: End-to-End Backend Test

**Files:** None new — this is a manual verification step.

- [ ] **Step 1: Ensure `.env` has real keys**

Verify `backend/.env` contains valid `LITELLM_API_KEY`, `E2B_API_KEY`, and optionally `LOGFIRE_TOKEN`.

- [ ] **Step 2: Start the server and test a real query**

```bash
cd backend && uv run uvicorn app.main:app --reload
```

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many rows are in the dataset?"}'
```

Expected: JSON response with `answer` containing the row count, `code` containing the pandas code used.

- [ ] **Step 3: Test a chart query**

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me a bar chart of average ARR by industry"}'
```

Expected: JSON response with `images` array containing at least one base64 PNG string.

- [ ] **Step 4: Debug and fix any issues**

If queries fail, check:
- E2B sandbox creation (API key valid?)
- LiteLLM proxy connection (model name correct?)
- Tool execution (does the code run in E2B?)

- [ ] **Step 5: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve issues from end-to-end backend testing"
```

---

## Task 8: Frontend Scaffold

**Files:**
- Create: `frontend/` (Vite scaffold)
- Create: `frontend/src/types.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create Vite React TypeScript project**

```bash
cd /Users/silver/dev/genesis-take-home
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] **Step 2: Install shadcn/ui and dependencies**

```bash
cd frontend
npx shadcn@latest init -d
npx shadcn@latest add button input card scroll-area collapsible
```

- [ ] **Step 3: Create shared types**

```typescript
// frontend/src/types.ts
export interface Message {
  role: "user" | "assistant";
  content: string;
  code?: string;
  images?: string[];
  error?: string;
}

export interface QueryRequest {
  question: string;
  history: { role: string; content: string }[];
}

export interface QueryResponse {
  answer: string;
  code: string;
  images: string[];
  error: string | null;
}
```

- [ ] **Step 4: Create API client**

```typescript
// frontend/src/lib/api.ts
import type { QueryRequest, QueryResponse } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function queryAgent(req: QueryRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}
```

- [ ] **Step 5: Verify dev server starts**

```bash
cd frontend && npm run dev
```

Expected: Vite dev server at http://localhost:5173

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold frontend with Vite, React, TypeScript, shadcn/ui"
```

---

## Task 9: Chat UI Components

**Files:**
- Create: `frontend/src/hooks/useChat.ts`
- Create: `frontend/src/components/ChatInput.tsx`
- Create: `frontend/src/components/ChatMessage.tsx`
- Create: `frontend/src/components/CodeBlock.tsx`
- Create: `frontend/src/components/ChartImage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create useChat hook**

```typescript
// frontend/src/hooks/useChat.ts
import { useState, useRef, useCallback } from "react";
import type { Message } from "../types";
import { queryAgent } from "../lib/api";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const sendMessage = useCallback(async (question: string) => {
    const userMessage: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Use ref to avoid stale closure over messages
      const history = [...messagesRef.current, userMessage].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await queryAgent({ question, history });

      const assistantMessage: Message = {
        role: "assistant",
        content: response.answer,
        code: response.code || undefined,
        images: response.images.length > 0 ? response.images : undefined,
        error: response.error || undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        role: "assistant",
        content: "",
        error: err instanceof Error ? err.message : "Something went wrong",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { messages, isLoading, sendMessage };
}
```

- [ ] **Step 2: Create ChatInput component**

```tsx
// frontend/src/components/ChatInput.tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSend(value.trim());
      setValue("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask a question about the data..."
        disabled={disabled}
        autoFocus
      />
      <Button type="submit" disabled={disabled || !value.trim()}>
        {disabled ? "Thinking..." : "Ask"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 3: Create CodeBlock component**

```tsx
// frontend/src/components/CodeBlock.tsx
import { useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface CodeBlockProps {
  code: string;
}

export function CodeBlock({ code }: CodeBlockProps) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="text-sm text-muted-foreground hover:underline cursor-pointer">
        {open ? "Hide code" : "Show code"}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-2 p-3 bg-muted rounded-md overflow-x-auto text-sm">
          <code>{code}</code>
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}
```

- [ ] **Step 4: Create ChartImage component**

```tsx
// frontend/src/components/ChartImage.tsx
interface ChartImageProps {
  src: string; // base64 PNG
}

export function ChartImage({ src }: ChartImageProps) {
  return (
    <img
      src={`data:image/png;base64,${src}`}
      alt="Chart"
      className="mt-2 rounded-md max-w-full"
    />
  );
}
```

- [ ] **Step 5: Create ChatMessage component**

```tsx
// frontend/src/components/ChatMessage.tsx
import { Card, CardContent } from "@/components/ui/card";
import { CodeBlock } from "./CodeBlock";
import { ChartImage } from "./ChartImage";
import type { Message } from "../types";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <Card
        className={`max-w-[80%] ${isUser ? "bg-primary text-primary-foreground" : ""}`}
      >
        <CardContent className="p-4">
          {message.error ? (
            <p className="text-destructive">{message.error}</p>
          ) : (
            <>
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.code && <CodeBlock code={message.code} />}
              {message.images?.map((img, i) => (
                <ChartImage key={i} src={img} />
              ))}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 6: Wire up App.tsx**

```tsx
// frontend/src/App.tsx
import { useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatInput } from "./components/ChatInput";
import { ChatMessage } from "./components/ChatMessage";
import { useChat } from "./hooks/useChat";

export default function App() {
  const { messages, isLoading, sendMessage } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Talk to Your Data</h1>

      <ScrollArea className="flex-1 mb-4">
        <div className="space-y-4 pr-4">
          {messages.length === 0 && (
            <p className="text-muted-foreground text-center mt-8">
              Ask a question about the SaaS company dataset. Try: "What's the
              average ARR for fintech companies?"
            </p>
          )}
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <Card className="max-w-[80%]">
                <CardContent className="p-4 text-muted-foreground">
                  Analyzing...
                </CardContent>
              </Card>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
```

- [ ] **Step 7: Verify the UI renders**

```bash
cd frontend && npm run dev
```

Open http://localhost:5173 — should see the chat UI with the placeholder text and input.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: add chat UI with message display, code blocks, and chart rendering"
```

---

## Task 10: Full-Stack Integration Test

**Files:** None new — manual verification.

- [ ] **Step 1: Start backend and frontend**

Terminal 1:
```bash
cd backend && uv run uvicorn app.main:app --reload
```

Terminal 2:
```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Test the four assignment example questions**

Open http://localhost:5173 and try each:
1. "What's the average ARR for fintech companies?"
2. "Which company has the highest growth rate?"
3. "Show me companies founded after 2020 with less than 5% churn."
4. "How many companies have more than 100 employees?"

For each, verify:
- Answer is displayed
- Code block is visible (expandable)
- No errors

- [ ] **Step 3: Test a chart question**

Ask: "Show me a bar chart of average ARR by industry"

Verify a chart image renders in the chat.

- [ ] **Step 4: Test error handling**

- Submit an empty question (should be blocked by UI)
- Ask "asdfghjkl" (should get a graceful response)

- [ ] **Step 5: Fix any issues and commit**

```bash
git add -u
git commit -m "fix: resolve issues from full-stack integration testing"
```

---

## Task 11: Eval Setup

**Files:**
- Create: `backend/evals/test_agent.py`
- Create: `backend/evals/cases.yaml`

- [ ] **Step 1: Create one eval test case**

```yaml
# backend/evals/cases.yaml
cases:
  - name: row_count
    inputs: "How many rows are in the dataset?"
    metadata:
      expects_number: true
evaluators:
  - type: MaxDuration
    seconds: 30
```

- [ ] **Step 2: Create eval runner**

```python
# backend/evals/test_agent.py
import pytest
from pydantic_evals import Dataset

from app.agent.agent import agent, AgentDeps
from app.data.loader import load_dataset, get_schema_summary

_df = load_dataset()
_schema = get_schema_summary(_df)


async def run_agent(question: str) -> str:
    deps = AgentDeps(df_schema=_schema)
    result = await agent.run(question, deps=deps)
    return result.output


@pytest.mark.asyncio
async def test_eval():
    dataset = Dataset.from_file("evals/cases.yaml")
    report = await dataset.evaluate(run_agent)
    report.print(include_input=True, include_output=True)
    # Don't assert pass/fail for now — just run and print
```

- [ ] **Step 3: Run the eval**

```bash
cd backend && uv run pytest evals/test_agent.py -v -s
```

Expected: eval runs, prints a report table with the one test case.

- [ ] **Step 4: Commit**

```bash
git add backend/evals/
git commit -m "feat: add pydantic-evals setup with initial test case"
```

---

## Task 12: Dockerfile + Deployment

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/.env.production` (or configure in Vercel dashboard)

- [ ] **Step 1: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ app/

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Test Docker build locally**

```bash
cd backend && docker build -t data-agent .
```

Expected: builds successfully.

- [ ] **Step 3: Deploy backend to Railway**

1. Go to Railway dashboard, create new project
2. Connect GitHub repo, set root directory to `backend/`
3. Set environment variables: `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL`, `E2B_API_KEY`, `LOGFIRE_TOKEN`
4. Deploy — Railway will use the Dockerfile
5. Note the public URL (e.g., `https://data-agent-production.up.railway.app`)
6. Test: `curl https://<railway-url>/health`

- [ ] **Step 4: Deploy frontend to Vercel**

1. Go to Vercel dashboard, import the GitHub repo
2. Set root directory to `frontend/`
3. Set environment variable: `VITE_API_URL=https://<railway-url>`
4. Deploy
5. Note the public URL

- [ ] **Step 5: Test the live deployment**

Open the Vercel URL and test the same questions from Task 10.

- [ ] **Step 6: Commit Dockerfile**

```bash
git add backend/Dockerfile
git commit -m "feat: add Dockerfile for Railway deployment"
```

---

## Task 13: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README (max 500 words per assignment)**

Cover:
- Which AI tools used and how (Claude Code for design + implementation)
- Interesting challenges (E2B sandboxing, PydanticAI tool retry loop, LiteLLM proxy integration)
- What you'd improve with more time (streaming, conversation memory, file upload, more eval cases)
- Design decisions (single-tool agent pattern, E2B for security, pandas over SQL for visualization flexibility)

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with design decisions and AI tool usage"
```

---

## Task 14: Loom Video

**Files:** None — this is a recording task.

- [ ] **Step 1: Record Loom video (max 5 minutes)**

Cover:
- Demo the app: ask 2-3 questions including one that produces a chart
- Walk through the architecture (frontend → backend → PydanticAI agent → E2B)
- Explain key design decisions: why pandas over SQL, why E2B, single-tool agent pattern
- Mention what you'd improve with more time

- [ ] **Step 2: Add Loom link to README**
