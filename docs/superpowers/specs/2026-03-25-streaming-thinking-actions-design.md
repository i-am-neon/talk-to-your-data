# Streaming Thoughts & Actions

Show the model's reasoning, tool calls, and execution results in real time via an expandable thinking section above each assistant message.

## Context

Currently, `POST /api/query` returns a complete `QueryResponse` after all processing finishes. The user sees a loading spinner for 3-10 seconds with no visibility into what's happening. This feature introduces SSE streaming so the user watches the agent think, run code, handle errors, and produce the final answer in real time.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Streaming transport | SSE (Server-Sent Events) | Request-response pattern; unidirectional server→client is sufficient. Same approach as Claude web and ChatGPT. |
| Thinking content | Real model reasoning tokens | PydanticAI's `run_stream()` emits `ThinkingPart` events; Claude Sonnet 4.6 supports adaptive thinking. More transparent than status labels. |
| Collapse behavior | Auto-collapse when answer tokens start | Keeps focus on the answer. User can re-expand to review steps. |
| Collapsed summary | Generated from step types | No LLM call — string formatted from collected steps (e.g. "Thought, ran code, retried, ran code"). |
| Code display in steps | First-line preview + expandable full code | Avoids duplication with workspace/inline code while keeping steps glanceable. |
| "Responding" state | None | Redundant — answer tokens stream directly into the chat bubble. |

## SSE Event Protocol

The backend streams newline-delimited SSE events. Each event has a `type` field and type-specific data.

### Event Types

```typescript
// Model reasoning tokens (chunked — append to current thinking step)
{ type: "thinking", content: string }

// Agent is calling the run_code tool
{ type: "tool_call_start", tool: "run_code", code: string }

// Tool execution finished successfully
{ type: "tool_result", stdout: string, images: string[], charts_count: number }

// Tool execution failed (agent will retry)
{ type: "tool_error", error: string }

// Final answer text (streamed token by token)
{ type: "text_delta", content: string }

// Stream complete — includes final structured data
{ type: "done", code: string, images: string[], artifact: ArtifactMeta | null }
```

### Example SSE Stream

```
data: {"type":"thinking","content":"I need to group by region and calculate mean revenue..."}

data: {"type":"tool_call_start","tool":"run_code","code":"import pandas as pd\n\nresult = df.groupby('region')['revenue'].mean()\nresult = result.sort_values(ascending=False)\nprint(result.to_string())"}

data: {"type":"tool_result","stdout":"North America    142500\nEurope            98200\nAsia-Pacific     115800","images":[],"charts_count":0}

data: {"type":"text_delta","content":"The average"}
data: {"type":"text_delta","content":" revenue by"}
data: {"type":"text_delta","content":" region is..."}

data: {"type":"done","code":"import pandas as pd\n\nresult = df.groupby('region')['revenue'].mean()...","images":[],"artifact":null}
```

## Backend Changes

### New Streaming Endpoint

Add `POST /api/query/stream` alongside the existing `/api/query` (keep the original for tests/evals).

```python
# backend/app/routes/query.py

@router.post("/api/query/stream")
async def query_stream(req: QueryRequest) -> StreamingResponse:
    """SSE endpoint that streams thinking, tool calls, and answer tokens."""
    ...
```

### Implementation Approach

1. Switch from `agent.run()` to `agent.run_stream()` which returns an async context manager yielding streamed events
2. Iterate over the stream, mapping PydanticAI events to our SSE event types:
   - `ThinkingPart` / `ThinkingPartDelta` → `thinking` event
   - `ToolCallPart` → `tool_call_start` event (extract `code` argument)
   - Tool result (after execution) → `tool_result` or `tool_error` event
   - `TextPart` / `TextPartDelta` → `text_delta` event
3. After the stream completes, emit a `done` event with the final code, images, and artifact metadata
4. Artifact parsing (`_parse_artifact`) runs on the complete answer text in the `done` event, same as today
5. Tool execution (`execute_python_code`) remains synchronous — it runs in the E2B sandbox during the agent's tool call step. The result is emitted as a `tool_result` or `tool_error` event before the agent continues.

### Key Detail: Tool Call Flow

PydanticAI's `run_stream()` handles the tool call loop internally. When the agent emits a `ToolCallPart`, PydanticAI calls our `run_code` tool function, gets the result (or `ModelRetry` on error), and feeds it back to the model. We hook into this by iterating the stream events:

- See `ToolCallPart` → emit `tool_call_start` with the code
- Tool executes → we observe the result in `AgentDeps.results` and emit `tool_result` or `tool_error`
- If `ModelRetry` was raised → the next `ThinkingPart` is the model's retry reasoning

## Frontend Changes

### New Types

```typescript
// types.ts

interface ThinkingStep {
  type: "thinking" | "code" | "result" | "error" | "retry";
  content: string;        // reasoning text, code preview, stdout, error message
  fullCode?: string;      // full code for "code" steps
  chartsCount?: number;   // for "result" steps
}

interface Message {
  role: "user" | "assistant";
  content: string;
  code?: string;
  images?: string[];
  error?: string;
  artifactId?: string;
  steps?: ThinkingStep[];  // NEW — populated during streaming
}
```

### API Layer (`lib/api.ts`)

Add a `queryAgentStream` function that:
1. POSTs to `/api/query/stream`
2. Reads the response body as a `ReadableStream`
3. Parses SSE events line by line
4. Calls a callback for each parsed event

```typescript
export function queryAgentStream(
  req: QueryRequest,
  onEvent: (event: StreamEvent) => void,
): AbortController
```

Returns an `AbortController` so the caller can cancel the stream (future use).

### Chat Hook (`hooks/useChat.ts`)

Modify `sendMessage` to:
1. Immediately append an assistant message with empty content and empty `steps: []`
2. Call `queryAgentStream` with an `onEvent` callback that progressively updates the message:
   - `thinking` → if the last step is type "thinking", append content to it; otherwise create a new step
   - `tool_call_start` → append a step of type "code"
   - `tool_result` → append a step of type "result"
   - `tool_error` → append a step of type "error", then the next `thinking` event becomes type "retry"
   - `text_delta` → append to message `content` (triggers auto-collapse of thinking)
   - `done` → set final `code`, `images`, `artifact`; process artifact via `artifactHandlers`

### ThinkingSection Component

New component rendered above the chat bubble in `ChatMessage`:

**Expanded state (during streaming):**
- Pulsing status header showing current activity ("Thinking...", "Running code...", "Retrying...")
- Vertical step list with left border line
- Each step shows a colored badge (Lucide icon + label) and content
- Code steps show first-line preview with "show full" toggle

**Collapsed state (after answer starts streaming):**
- Single-line toggle: brain icon + summary text + chevron
- Summary built from step types: "Thought, ran code" / "Thought, ran code, retried, ran code"
- Click to expand with CSS grid animation (`grid-template-rows: 0fr → 1fr`)
- Code "show full" uses the same grid animation

**Step badge styles:**
| Step Type | Icon | Color |
|-----------|------|-------|
| Thinking | `brain` | purple `#a78bfa` |
| Code | `play` | amber `#fbbf24` |
| Result | `chart-no-axes-column` or `table-2` | cyan `#67e8f9` |
| Error | `circle-x` | red `#fca5a5` |
| Retry | `refresh-cw` | purple `#a78bfa` |

### Loading State

Replace the current loading spinner with the live thinking section. The `isLoading` state in `useChat` is no longer needed for showing a spinner — the presence of an in-progress streaming message (empty content + active steps) serves as the loading indicator.

## Scenarios

### 1. Simple Question (No Code)
`"What columns are in the dataset?"`

Events: `thinking` → `text_delta` (multiple) → `done`

User sees: Thinking section appears with reasoning → auto-collapses as answer streams in → collapsed shows "Thought"

### 2. Query → Code → Result → Answer
`"What's the average revenue by region?"`

Events: `thinking` → `tool_call_start` → `tool_result` → `text_delta` (multiple) → `done`

User sees: Thinking → "Running code..." with code preview → result badge → auto-collapse → answer streams in → collapsed shows "Thought, ran code"

### 3. Code Fails → Retry → Success
`"Plot revenue trends"` (agent uses wrong column name)

Events: `thinking` → `tool_call_start` → `tool_error` → `thinking` (retry) → `tool_call_start` → `tool_result` → `text_delta` (multiple) → `done`

User sees: Thinking → code preview → error in red → "Retrying..." with new reasoning → new code → result → answer → collapsed shows "Thought, ran code, retried, ran code"

### 4. Multiple Tool Calls
`"Compare Q1 vs Q2 revenue with a table and chart"`

Events: `thinking` → `tool_call_start` → `tool_result` → `thinking` → `tool_call_start` → `tool_result` → `text_delta` (multiple) → `done`

User sees: Thinking → code (table) → result → more thinking → code (chart) → result → answer → collapsed shows "Thought, ran code 2x"

## Migration & Compatibility

- Keep existing `POST /api/query` unchanged — used by tests and evals
- Frontend switches to `/api/query/stream` for the chat UI
- `QueryResponse` model stays the same for the non-streaming endpoint
- The `done` SSE event carries the same data as the current `QueryResponse`

## Visual Reference

Interactive mockups of all states are in `.superpowers/brainstorm/52438-1774462891/content/design-mockup.html`.
