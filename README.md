# Talk to Your Data — Genesis Take-Home

Live URL: TBD
Loom Demo: TBD

## What it does

A natural language data agent: type a question about a SaaS dataset in plain English, get a text answer, a table, or a chart back. The agent generates pandas/matplotlib code, runs it in an isolated sandbox, and returns the result.

## Stack

- **Frontend**: Vite + React + TypeScript + shadcn/ui, deployed to Vercel
- **Backend**: FastAPI + PydanticAI + Logfire, deployed to Railway
- **Sandbox**: E2B Code Interpreter (Firecracker microVMs)
- **LLM**: Genesis LiteLLM Proxy (OpenAI-compatible, claude-sonnet-4-5)

Request flow: question typed in React UI → `POST /api/query` → PydanticAI agent generates pandas/matplotlib code → E2B sandbox executes it → text answer + code + chart images returned.

## AI Tools Used

I used Claude Code (claude-sonnet-4-6) throughout — for architecture design, scaffolding both services, writing the PydanticAI agent wiring, and debugging integration issues in real time. I also used Claude for design discussions before writing any code. The commit history reflects genuine iteration rather than a single dump.

## Interesting Challenges

**PydanticAI tool retry loop**: PydanticAI's `ModelRetry` mechanism lets the agent automatically attempt to fix broken code when E2B returns an execution error. Getting the retry context right — passing stdout/stderr back as the retry message — took some careful wiring.

**LiteLLM proxy through PydanticAI**: PydanticAI uses its own provider abstraction. Pointing it at the Genesis proxy required using `OpenAIChatModel` with a custom `OpenAIProvider` that overrides the base URL and injects the API key. The provider docs are sparse so this took some digging.

**Stale closures in React**: The `useChat` hook accumulated stale closure bugs where message history referenced old state. Solved by moving message history into a `useRef` so the callback always sees the latest value without re-registering on every render.

## Design Decisions

**Single-tool agent**: One `execute_python_code` tool instead of multiple specialized tools. The LLM writes arbitrary Python and E2B runs it. This is simpler to prompt and more flexible — the same tool handles aggregations, filters, and charts.

**E2B for sandboxing**: Running LLM-generated code in the same process is a security hole. E2B provides Firecracker microVM isolation with ~150ms cold starts — safer than `subprocess`, more capable than RestrictedPython.

**Pandas over SQL**: pandas enables data analysis and visualization (matplotlib/seaborn) in the same execution context. A SQL approach would need a separate charting pipeline.

**Schema injection**: The dataset schema (column names, types, value ranges) is baked into the system prompt on each request so the LLM knows the data shape without a separate discovery tool call.

## What I'd Improve With More Time

- Streaming responses so answers appear incrementally
- Conversation memory so follow-up questions reference prior context
- File upload so users can bring their own CSV
- More eval cases covering edge cases (ambiguous questions, missing data, multi-step reasoning)

## Getting Started

```bash
cp backend/.env.example backend/.env   # fill in E2B_API_KEY, LITELLM_API_KEY
just dev                                # starts backend + frontend
```

Open `http://localhost:5173`.
