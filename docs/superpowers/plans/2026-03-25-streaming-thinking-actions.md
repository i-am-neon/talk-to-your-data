# Streaming Thoughts & Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream the agent's thinking, tool calls, and answer tokens to the frontend in real time via SSE, with an expandable thinking section above each chat message.

**Architecture:** New `POST /api/query/stream` SSE endpoint using PydanticAI's `run_stream_events()`. Frontend reads the SSE stream via `fetch` + `ReadableStream`, progressively updates message state, and renders a `ThinkingSection` component above the chat bubble.

**Tech Stack:** FastAPI `StreamingResponse`, PydanticAI streaming API, React state updates, Lucide icons, CSS grid animations.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/routes/query.py` | Add `/api/query/stream` SSE endpoint |
| Modify | `backend/tests/test_query.py` | Add tests for streaming endpoint + SSE helper |
| Modify | `frontend/src/types.ts` | Add `ThinkingStep`, `StreamEvent` types |
| Modify | `frontend/src/lib/api.ts` | Add `queryAgentStream()` SSE client |
| Create | `frontend/src/lib/sse.ts` | SSE line parser (pure function, testable) |
| Modify | `frontend/src/hooks/useChat.ts` | Switch to streaming, progressive message updates |
| Create | `frontend/src/components/ThinkingSection.tsx` | Expandable thinking/actions UI |
| Modify | `frontend/src/components/ChatMessage.tsx` | Render `ThinkingSection` above chat bubble |
| Modify | `frontend/src/App.tsx` | Remove old loading spinner |

---

### Task 1: Backend — SSE streaming endpoint

**Files:**
- Modify: `backend/app/routes/query.py`
- Modify: `backend/tests/test_query.py`

- [ ] **Step 1: Write test for the SSE format helper**

Add to `backend/tests/test_query.py`:

```python
from app.routes.query import _sse_event


def test_sse_event_format():
    result = _sse_event({"type": "thinking", "content": "hello"})
    assert result == 'data: {"type":"thinking","content":"hello"}\n\n'


def test_sse_event_escapes_newlines():
    result = _sse_event({"type": "text_delta", "content": "line1\nline2"})
    # json.dumps handles newlines inside strings as \n
    assert "\\n" in result
    assert result.startswith("data: ")
    assert result.endswith("\n\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_query.py::test_sse_event_format -v`
Expected: FAIL with `ImportError: cannot import name '_sse_event'`

- [ ] **Step 3: Write test for empty question on stream endpoint**

Add to `backend/tests/test_query.py`:

```python
def test_stream_empty_question():
    response = client.post("/api/query/stream", json={"question": ""})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # Parse SSE events from body
    events = _parse_sse_body(response.text)
    assert len(events) >= 1
    done_event = events[-1]
    assert done_event["type"] == "done"
    assert done_event["error"] == "Please enter a question."


def _parse_sse_body(body: str) -> list[dict]:
    """Parse SSE response body into list of JSON event dicts."""
    import json as json_mod
    events = []
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json_mod.loads(line[6:]))
    return events
```

- [ ] **Step 4: Write the SSE helper and streaming endpoint**

Replace the imports at the top of `backend/app/routes/query.py` and add the new endpoint. The full modified file:

```python
# backend/app/routes/query.py
import json
import re
import uuid
from collections.abc import AsyncGenerator

from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart,
    PartStartEvent, PartDeltaEvent, FunctionToolCallEvent, FunctionToolResultEvent,
    ThinkingPart, ThinkingPartDelta, TextPartDelta, ToolCallPart, RetryPromptPart,
)

from app.agent.agent import agent, AgentDeps, make_model
from app.data.loader import load_dataset, get_schema_summary

router = APIRouter()

_df = load_dataset()
_schema = get_schema_summary(_df)

ARTIFACT_PATTERN = re.compile(
    r'\[\[artifact:(create|update)\|([^|]+)\|([^|]*?)(?:\|(chart|table|code))?\]\]'
)


# --- Existing models (unchanged) ---

class HistoryMessage(BaseModel):
    role: str
    content: str


class ArtifactDescriptor(BaseModel):
    id: str
    title: str
    type: str


class ArtifactMeta(BaseModel):
    id: str
    title: str
    type: str
    action: str  # "create" | "update"


class QueryRequest(BaseModel):
    question: str
    history: list[HistoryMessage] = []
    artifacts: list[ArtifactDescriptor] = []
    model: str | None = None


class QueryResponse(BaseModel):
    answer: str
    code: str = ""
    images: list[str] = []
    error: str | None = None
    artifact: ArtifactMeta | None = None


# --- Existing helpers (unchanged) ---

def _parse_artifact(text: str, existing_ids: set[str]) -> tuple[str, ArtifactMeta | None]:
    match = ARTIFACT_PATTERN.search(text)
    if not match:
        return text, None

    action = match.group(1)
    clean_text = (text[:match.start()] + text[match.end():]).strip()

    if action == "create":
        title = match.group(2)
        art_type = match.group(4) or match.group(3) or "chart"
        artifact_id = f"artifact-{uuid.uuid4().hex[:8]}"
    else:  # update
        artifact_id = match.group(2)
        title = match.group(3) or "Updated chart"
        art_type = match.group(4) or "chart"
        if artifact_id not in existing_ids:
            action = "create"
            artifact_id = f"artifact-{uuid.uuid4().hex[:8]}"

    return clean_text, ArtifactMeta(id=artifact_id, title=title, type=art_type, action=action)


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


# --- New SSE helper ---

def _sse_event(data: dict) -> str:
    """Format a dict as an SSE event string."""
    return f"data: {json.dumps(data, separators=(',', ':'))}\n\n"


def _extract_tool_code(args: str | dict | None) -> str:
    """Extract the 'code' argument from a tool call's args."""
    if isinstance(args, dict):
        return args.get("code", "")
    if isinstance(args, str):
        try:
            return json.loads(args).get("code", "")
        except (json.JSONDecodeError, AttributeError):
            return args
    return ""


# --- Existing endpoint (unchanged) ---

@router.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    if not req.question.strip():
        return QueryResponse(answer="", error="Please enter a question.")

    deps = AgentDeps(
        df_schema=_schema,
        artifacts=[a.model_dump() for a in req.artifacts],
    )

    try:
        message_history = _build_message_history(req.history)
        override_model = make_model(req.model) if req.model else None
        result = await agent.run(req.question, deps=deps, message_history=message_history, model=override_model)

        code = ""
        images: list[str] = []
        for r in deps.results:
            if r.code:
                code = r.code
            if r.images:
                images.extend(r.images)

        existing_ids = {a.id for a in req.artifacts}
        answer_text, artifact = _parse_artifact(result.output, existing_ids)

        if artifact is None and images:
            artifact = ArtifactMeta(
                id=f"artifact-{uuid.uuid4().hex[:8]}",
                title="Chart",
                type="chart",
                action="create",
            )

        return QueryResponse(
            answer=answer_text,
            code=code,
            images=images,
            artifact=artifact,
        )
    except Exception as e:
        return QueryResponse(
            answer="",
            error=f"Unable to process your question: {str(e)}",
        )


# --- New streaming endpoint ---

@router.post("/api/query/stream")
async def query_stream(req: QueryRequest) -> StreamingResponse:
    """SSE endpoint that streams thinking, tool calls, and answer tokens."""

    async def event_generator() -> AsyncGenerator[str, None]:
        if not req.question.strip():
            yield _sse_event({"type": "done", "code": "", "images": [], "artifact": None, "error": "Please enter a question."})
            return

        deps = AgentDeps(
            df_schema=_schema,
            artifacts=[a.model_dump() for a in req.artifacts],
        )

        try:
            message_history = _build_message_history(req.history)
            override_model = make_model(req.model) if req.model else None

            full_text = ""
            results_seen = 0

            async for event in agent.run_stream_events(
                req.question,
                deps=deps,
                message_history=message_history,
                model=override_model,
            ):
                if isinstance(event, PartStartEvent):
                    if isinstance(event.part, ThinkingPart) and event.part.content:
                        yield _sse_event({"type": "thinking", "content": event.part.content})
                    elif isinstance(event.part, TextPart) and event.part.content:
                        full_text += event.part.content
                        yield _sse_event({"type": "text_delta", "content": event.part.content})

                elif isinstance(event, PartDeltaEvent):
                    if isinstance(event.delta, ThinkingPartDelta) and event.delta.content_delta:
                        yield _sse_event({"type": "thinking", "content": event.delta.content_delta})
                    elif isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
                        full_text += event.delta.content_delta
                        yield _sse_event({"type": "text_delta", "content": event.delta.content_delta})

                elif isinstance(event, FunctionToolCallEvent):
                    code = _extract_tool_code(event.part.args)
                    yield _sse_event({"type": "tool_call_start", "tool": event.part.tool_name, "code": code})

                elif isinstance(event, FunctionToolResultEvent):
                    # Check latest result added to deps by the tool
                    if len(deps.results) > results_seen:
                        last_result = deps.results[-1]
                        results_seen = len(deps.results)
                        if isinstance(event.result, RetryPromptPart):
                            yield _sse_event({"type": "tool_error", "error": last_result.error or "Unknown error"})
                        else:
                            yield _sse_event({
                                "type": "tool_result",
                                "stdout": last_result.stdout,
                                "images": last_result.images,
                                "charts_count": len(last_result.images),
                            })

                elif isinstance(event, AgentRunResultEvent):
                    # Stream complete — gather final data
                    code = ""
                    images: list[str] = []
                    for r in deps.results:
                        if r.code:
                            code = r.code
                        if r.images:
                            images.extend(r.images)

                    existing_ids = {a.id for a in req.artifacts}
                    answer_text, artifact = _parse_artifact(full_text, existing_ids)

                    if artifact is None and images:
                        artifact = ArtifactMeta(
                            id=f"artifact-{uuid.uuid4().hex[:8]}",
                            title="Chart",
                            type="chart",
                            action="create",
                        )

                    yield _sse_event({
                        "type": "done",
                        "answer": answer_text,
                        "code": code,
                        "images": images,
                        "artifact": artifact.model_dump() if artifact else None,
                        "error": None,
                    })

        except Exception as e:
            yield _sse_event({
                "type": "done",
                "answer": "",
                "code": "",
                "images": [],
                "artifact": None,
                "error": f"Unable to process your question: {str(e)}",
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 5: Run all tests**

Run: `cd backend && uv run pytest tests/test_query.py -v`
Expected: All tests PASS (existing tests unchanged, new tests pass)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/query.py backend/tests/test_query.py
git commit -m "feat: add SSE streaming endpoint for thoughts and actions"
```

---

### Task 2: Frontend — SSE parser and stream types

**Files:**
- Modify: `frontend/src/types.ts`
- Create: `frontend/src/lib/sse.ts`

- [ ] **Step 1: Add new types to `frontend/src/types.ts`**

Add at the end of the file:

```typescript
// --- Streaming types ---

export interface ThinkingStep {
  type: "thinking" | "code" | "result" | "error" | "retry";
  content: string;
  fullCode?: string;
  chartsCount?: number;
}

export type StreamEvent =
  | { type: "thinking"; content: string }
  | { type: "tool_call_start"; tool: string; code: string }
  | { type: "tool_result"; stdout: string; images: string[]; charts_count: number }
  | { type: "tool_error"; error: string }
  | { type: "text_delta"; content: string }
  | {
      type: "done";
      answer: string;
      code: string;
      images: string[];
      artifact: ArtifactMeta | null;
      error: string | null;
    };
```

Also add `steps` to the existing `Message` interface:

```typescript
export interface Message {
  role: "user" | "assistant";
  content: string;
  code?: string;
  images?: string[];
  error?: string;
  artifactId?: string;
  steps?: ThinkingStep[];  // NEW
}
```

- [ ] **Step 2: Create SSE line parser `frontend/src/lib/sse.ts`**

```typescript
import type { StreamEvent } from "../types";

/**
 * Parse a chunk of SSE text into individual events.
 * Handles partial chunks by returning unparsed remainder.
 */
export function parseSSEChunk(
  chunk: string,
  buffer: string
): { events: StreamEvent[]; remainder: string } {
  const text = buffer + chunk;
  const events: StreamEvent[] = [];
  const lines = text.split("\n");

  // Last element may be incomplete — keep as remainder
  const remainder = lines.pop() ?? "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("data: ")) {
      try {
        events.push(JSON.parse(trimmed.slice(6)) as StreamEvent);
      } catch {
        // Ignore malformed JSON
      }
    }
  }

  return { events, remainder };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts frontend/src/lib/sse.ts
git commit -m "feat: add streaming types and SSE parser"
```

---

### Task 3: Frontend — streaming API client

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add `queryAgentStream` to `frontend/src/lib/api.ts`**

Add below the existing `queryAgent` function:

```typescript
import type { QueryRequest, QueryResponse, StreamEvent } from "../types";
import { parseSSEChunk } from "./sse";

// ... existing queryAgent stays ...

export function queryAgentStream(
  req: QueryRequest,
  onEvent: (event: StreamEvent) => void,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_URL}/api/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!response.ok) {
        onEvent({
          type: "done",
          answer: "",
          code: "",
          images: [],
          artifact: null,
          error: `API error: ${response.status}`,
        });
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const { events, remainder } = parseSSEChunk(chunk, buffer);
        buffer = remainder;

        for (const event of events) {
          onEvent(event);
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        const { events } = parseSSEChunk("\n", buffer);
        for (const event of events) {
          onEvent(event);
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onEvent({
          type: "done",
          answer: "",
          code: "",
          images: [],
          artifact: null,
          error: err instanceof Error ? err.message : "Something went wrong",
        });
      }
    }
  })();

  return controller;
}
```

Update the existing import line at the top of the file to include `StreamEvent`:

```typescript
import type { QueryRequest, QueryResponse, StreamEvent } from "../types";
```

Add the `parseSSEChunk` import:

```typescript
import { parseSSEChunk } from "./sse";
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add streaming API client for SSE events"
```

---

### Task 4: Frontend — ThinkingSection component

**Files:**
- Create: `frontend/src/components/ThinkingSection.tsx`

- [ ] **Step 1: Create `frontend/src/components/ThinkingSection.tsx`**

```tsx
import { useState } from "react";
import {
  Brain,
  Play,
  BarChart3,
  CircleX,
  RefreshCw,
  ChevronDown,
  Table2,
} from "lucide-react";
import type { ThinkingStep } from "../types";

interface ThinkingSectionProps {
  steps: ThinkingStep[];
  isStreaming: boolean;
}

function buildSummary(steps: ThinkingStep[]): string {
  const parts: string[] = [];
  let codeCount = 0;

  for (const step of steps) {
    switch (step.type) {
      case "thinking":
        if (parts.length === 0 || parts[parts.length - 1] !== "thought") {
          parts.push("thought");
        }
        break;
      case "code":
        codeCount++;
        break;
      case "result":
        // Counted with code
        break;
      case "error":
        // Will be followed by retry
        break;
      case "retry":
        parts.push("ran code");
        parts.push("retried");
        codeCount = 0;
        break;
    }
  }

  if (codeCount === 1) {
    parts.push("ran code");
  } else if (codeCount > 1) {
    parts.push(`ran code ${codeCount}x`);
  }

  return parts.length > 0
    ? parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(", ")
    : "Thought";
}

const stepConfig = {
  thinking: { icon: Brain, label: "Thought", color: "text-purple-400", bg: "bg-purple-500/10" },
  code: { icon: Play, label: "Code", color: "text-amber-400", bg: "bg-amber-500/10" },
  result: { icon: BarChart3, label: "Result", color: "text-cyan-400", bg: "bg-cyan-500/10" },
  error: { icon: CircleX, label: "Error", color: "text-red-400", bg: "bg-red-500/10" },
  retry: { icon: RefreshCw, label: "Retry", color: "text-purple-400", bg: "bg-purple-500/10" },
} as const;

function StepBadge({ type }: { type: ThinkingStep["type"] }) {
  const config = stepConfig[type];
  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold whitespace-nowrap ${config.bg} ${config.color}`}
    >
      <Icon size={12} />
      {config.label}
    </span>
  );
}

function CodeStep({ step }: { step: ThinkingStep }) {
  const [expanded, setExpanded] = useState(false);
  const firstLine = step.content.split("\n")[0];

  return (
    <div className="flex flex-col gap-1.5 flex-1 min-w-0">
      <div className="flex items-center gap-2">
        <code className="text-xs bg-white/5 px-2 py-0.5 rounded truncate max-w-[400px]">
          {firstLine}
        </code>
        {step.fullCode && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-purple-400 text-xs font-medium inline-flex items-center gap-1 whitespace-nowrap hover:text-purple-300"
          >
            <ChevronDown
              size={11}
              className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            />
            {expanded ? "hide" : "show full"}
          </button>
        )}
      </div>
      <div
        className="grid transition-[grid-template-rows] duration-250 ease-in-out"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <pre className="overflow-hidden text-xs bg-black/30 rounded-md text-gray-300 whitespace-pre-wrap leading-relaxed m-0"
          style={{ padding: expanded ? "10px" : "0 10px" }}
        >
          {step.fullCode}
        </pre>
      </div>
    </div>
  );
}

function StepItem({ step }: { step: ThinkingStep }) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <StepBadge type={step.type} />
      {step.type === "code" ? (
        <CodeStep step={step} />
      ) : step.type === "result" ? (
        <span className="text-gray-300 text-xs">
          {step.content}
          {step.chartsCount ? ` + ${step.chartsCount} chart(s)` : ""}
        </span>
      ) : step.type === "error" ? (
        <span className="text-red-400 text-xs">{step.content}</span>
      ) : (
        <span className="text-muted-foreground text-xs leading-relaxed">
          {step.content}
        </span>
      )}
    </div>
  );
}

function LiveHeader({ steps }: { steps: ThinkingStep[] }) {
  const last = steps[steps.length - 1];
  if (!last) return null;

  let icon = Brain;
  let label = "Thinking...";
  let color = "text-purple-400";

  if (last.type === "code") {
    icon = Play;
    label = "Running code...";
    color = "text-amber-400";
  } else if (last.type === "retry") {
    icon = RefreshCw;
    label = "Retrying...";
    color = "text-purple-400";
  }

  const Icon = icon;

  return (
    <div className={`flex items-center gap-2 text-sm mb-2.5 ${color}`}>
      <Icon size={14} className="animate-pulse" />
      <span>{label}</span>
    </div>
  );
}

export function ThinkingSection({ steps, isStreaming }: ThinkingSectionProps) {
  const [expanded, setExpanded] = useState(false);

  if (steps.length === 0) return null;

  // While streaming: always show expanded
  if (isStreaming) {
    return (
      <div className="mb-1 bg-purple-500/5 border border-purple-500/10 rounded-xl px-4 py-3">
        <LiveHeader steps={steps} />
        <div className="ml-1 pl-4 border-l-2 border-purple-500/20 flex flex-col gap-2.5">
          {steps.map((step, i) => (
            <StepItem key={i} step={step} />
          ))}
        </div>
      </div>
    );
  }

  // After streaming: collapsible with summary
  const summary = buildSummary(steps);

  return (
    <div className="mb-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1.5 bg-purple-500/8 border border-purple-500/15 rounded-lg px-3 py-1.5 text-sm text-purple-400 hover:bg-purple-500/12 transition-colors cursor-pointer"
      >
        <Brain size={14} />
        <span>{summary}</span>
        <ChevronDown
          size={12}
          className={`transition-transform duration-250 ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-in-out"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="mt-2 ml-1 pl-4 border-l-2 border-purple-500/20 flex flex-col gap-2.5">
            {steps.map((step, i) => (
              <StepItem key={i} step={step} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ThinkingSection.tsx
git commit -m "feat: add ThinkingSection component with expand/collapse"
```

---

### Task 5: Frontend — Wire useChat to streaming

**Files:**
- Modify: `frontend/src/hooks/useChat.ts`

- [ ] **Step 1: Rewrite `frontend/src/hooks/useChat.ts` to use streaming**

```typescript
import { useState, useRef, useCallback } from "react";
import type { Message, ArtifactMeta, ModelOption, ThinkingStep, StreamEvent } from "../types";
import { queryAgentStream } from "../lib/api";

interface ArtifactHandlers {
  getDescriptors: () => { id: string; title: string; type: string }[];
  processArtifact: (meta: ArtifactMeta, content: { answer: string; code?: string; images?: string[] }) => void;
}

export function useChat(artifactHandlers: ArtifactHandlers, model: ModelOption) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Track whether the last tool_error was followed by a thinking event (= retry)
  const lastWasErrorRef = useRef(false);

  const updateLastMessage = useCallback((updater: (msg: Message) => Message) => {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last && last.role === "assistant") {
        updated[updated.length - 1] = updater(last);
      }
      return updated;
    });
  }, []);

  const handleEvent = useCallback(
    (event: StreamEvent) => {
      switch (event.type) {
        case "thinking": {
          updateLastMessage((msg) => {
            const steps = [...(msg.steps ?? [])];
            const last = steps[steps.length - 1];

            if (lastWasErrorRef.current) {
              // Thinking after error = retry
              steps.push({ type: "retry", content: event.content });
              lastWasErrorRef.current = false;
            } else if (last && (last.type === "thinking" || last.type === "retry")) {
              // Append to existing thinking/retry step
              steps[steps.length - 1] = { ...last, content: last.content + event.content };
            } else {
              steps.push({ type: "thinking", content: event.content });
            }

            return { ...msg, steps };
          });
          break;
        }

        case "tool_call_start": {
          const firstLine = event.code.split("\n")[0];
          updateLastMessage((msg) => ({
            ...msg,
            steps: [
              ...(msg.steps ?? []),
              { type: "code", content: firstLine, fullCode: event.code },
            ],
          }));
          break;
        }

        case "tool_result": {
          const desc = event.stdout
            ? event.stdout.slice(0, 80) + (event.stdout.length > 80 ? "..." : "")
            : "Code executed";
          updateLastMessage((msg) => ({
            ...msg,
            steps: [
              ...(msg.steps ?? []),
              { type: "result", content: desc, chartsCount: event.charts_count },
            ],
          }));
          break;
        }

        case "tool_error": {
          lastWasErrorRef.current = true;
          updateLastMessage((msg) => ({
            ...msg,
            steps: [...(msg.steps ?? []), { type: "error", content: event.error }],
          }));
          break;
        }

        case "text_delta": {
          updateLastMessage((msg) => ({
            ...msg,
            content: msg.content + event.content,
          }));
          break;
        }

        case "done": {
          lastWasErrorRef.current = false;

          updateLastMessage((msg) => {
            const updated: Message = {
              ...msg,
              // Replace with cleaned answer (artifact markers stripped)
              content: event.answer ?? msg.content,
              code: event.artifact ? undefined : event.code || undefined,
              images: event.artifact
                ? undefined
                : event.images.length > 0
                  ? event.images
                  : undefined,
              error: event.error || undefined,
              artifactId: event.artifact?.id,
            };
            return updated;
          });

          if (event.artifact) {
            artifactHandlers.processArtifact(event.artifact, {
              answer: event.answer ?? "",
              code: event.code || undefined,
              images: event.images.length > 0 ? event.images : undefined,
            });
          }

          setIsStreaming(false);
          break;
        }
      }
    },
    [updateLastMessage, artifactHandlers]
  );

  const sendMessage = useCallback(
    (question: string) => {
      const userMessage: Message = { role: "user", content: question };
      const assistantMessage: Message = { role: "assistant", content: "", steps: [] };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);
      lastWasErrorRef.current = false;

      const history = messagesRef.current.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      queryAgentStream(
        {
          question,
          history,
          artifacts: artifactHandlers.getDescriptors(),
          model,
        },
        handleEvent
      );
    },
    [artifactHandlers, model, handleEvent]
  );

  return { messages, isStreaming, sendMessage };
}
```

**Key changes from the original:**
- `isLoading` → `isStreaming` (semantic rename)
- `sendMessage` is now synchronous (fires off stream, doesn't await)
- Immediately appends empty assistant message with `steps: []`
- `handleEvent` progressively updates the last message via `updateLastMessage`
- `thinking` chunks after a `tool_error` become `retry` steps
- `done` event sets final state and processes artifacts

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useChat.ts
git commit -m "feat: switch useChat to SSE streaming with progressive updates"
```

---

### Task 6: Frontend — Integrate ThinkingSection into ChatMessage and App

**Files:**
- Modify: `frontend/src/components/ChatMessage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update `frontend/src/components/ChatMessage.tsx`**

```tsx
import { Card, CardContent } from "@/components/ui/card";
import { CodeBlock } from "./CodeBlock";
import { ChartImage } from "./ChartImage";
import { Markdown } from "./Markdown";
import { ThinkingSection } from "./ThinkingSection";
import type { Message } from "../types";

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
  onArtifactClick?: (id: string) => void;
}

export function ChatMessage({ message, isStreaming = false, onArtifactClick }: ChatMessageProps) {
  const isUser = message.role === "user";
  const hasSteps = message.steps && message.steps.length > 0;
  const hasContent = message.content.length > 0 || message.error;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[80%]">
        {!isUser && hasSteps && (
          <ThinkingSection
            steps={message.steps!}
            isStreaming={isStreaming && !hasContent}
          />
        )}
        {(hasContent || !isStreaming) && (
          <Card className={isUser ? "bg-primary text-primary-foreground" : ""}>
            <CardContent className="p-4">
              {message.error ? (
                <p className="text-destructive">{message.error}</p>
              ) : (
                <>
                  <Markdown>{message.content}</Markdown>
                  {message.artifactId ? (
                    <button
                      onClick={() => onArtifactClick?.(message.artifactId!)}
                      className="mt-2 text-sm text-primary hover:underline cursor-pointer"
                    >
                      View in workspace &rarr;
                    </button>
                  ) : (
                    <>
                      {message.code && <CodeBlock code={message.code} />}
                      {message.images?.map((img, i) => (
                        <ChartImage key={i} src={img} />
                      ))}
                    </>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
```

**Key changes:**
- Wraps content in a `<div>` to stack ThinkingSection above Card
- `ThinkingSection` renders above the card when steps exist
- `isStreaming` prop passed through to control expanded vs collapsed state
- Card is hidden during streaming until content starts arriving
- `max-w-[80%]` moved to wrapper div

- [ ] **Step 2: Update `frontend/src/App.tsx` — remove old loading spinner, pass `isStreaming`**

Replace the messages rendering and loading spinner section. Change:

```tsx
const { messages, isLoading, sendMessage } = useChat({
```

to:

```tsx
const { messages, isStreaming, sendMessage } = useChat({
```

Replace the messages map + loading spinner block:

```tsx
{messages.map((msg, i) => (
  <ChatMessage
    key={i}
    message={msg}
    isStreaming={isStreaming && i === messages.length - 1}
    onArtifactClick={artifactStore.setSelectedId}
  />
))}
```

Remove the loading spinner block entirely (the `{isLoading && (` block with `<Card>Analyzing...</Card>`).

Update the ChatInput `disabled` prop:

```tsx
<ChatInput onSend={sendMessage} disabled={isStreaming} model={model} onModelChange={setModel} />
```

- [ ] **Step 3: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ChatMessage.tsx frontend/src/App.tsx
git commit -m "feat: integrate ThinkingSection into chat UI, remove loading spinner"
```

---

### Task 7: Manual smoke test

- [ ] **Step 1: Start the dev servers**

Run: `just dev`

- [ ] **Step 2: Test Scenario 1 — simple question**

Ask: "What columns are in the dataset?"

Expected: Thinking section appears with reasoning → auto-collapses when answer starts streaming → collapsed shows summary like "Thought" → click to expand and see reasoning text.

- [ ] **Step 3: Test Scenario 2 — code execution**

Ask: "What's the average ARR by industry?"

Expected: Thinking → "Running code..." with code preview → result → auto-collapse → answer streams in → collapsed shows "Thought, ran code" → "show full" button works on code step.

- [ ] **Step 4: Verify existing non-streaming endpoint still works**

Run: `cd backend && uv run pytest tests/test_query.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address smoke test findings"
```
