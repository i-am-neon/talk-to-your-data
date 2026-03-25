# backend/app/routes/query.py
import json
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal

from pydantic import BaseModel
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart,
    PartStartEvent, PartDeltaEvent, FunctionToolCallEvent, FunctionToolResultEvent,
    ThinkingPart, ThinkingPartDelta, TextPartDelta, RetryPromptPart,
)

from app.agent.agent import agent, AgentDeps, make_model
from app import db
from app.data.loader import load_dataset, get_schema_summary

router = APIRouter()

_df = load_dataset()
_schema = get_schema_summary(_df)

ARTIFACT_PATTERN = re.compile(
    r'\[\[artifact:(create|update)\|([^|]+)\|([^|]*?)(?:\|(chart|table|code))?\]\]'
)


class ArtifactMeta(BaseModel):
    id: str
    title: str
    type: str
    action: str  # "create" | "update"


class ChartSeries(BaseModel):
    key: str
    label: str


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "area", "pie", "radar"]
    data: list[dict[str, Any]]
    x_key: str
    series: list[ChartSeries]


class QueryRequest(BaseModel):
    question: str
    conversation_id: uuid.UUID
    model: str | None = None


class QueryResponse(BaseModel):
    answer: str
    code: str = ""
    images: list[str] = []
    error: str | None = None
    artifact: ArtifactMeta | None = None
    conversation_id: str


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


def _build_message_history(messages: list[dict]) -> list[ModelMessage] | None:
    """Convert stored messages to PydanticAI message format."""
    if not messages:
        return None
    result: list[ModelMessage] = []
    for msg in messages:
        if msg["role"] == "user":
            result.append(ModelRequest(parts=[UserPromptPart(content=msg["content"])]))
        else:
            result.append(ModelResponse(parts=[TextPart(content=msg["content"])]))
    return result


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
            return ""
    return ""


async def _persist_response(
    conv_id: uuid.UUID, question: str, answer_text: str,
    code: str, images: list[str], artifact: ArtifactMeta | None,
    history: list[dict],
) -> None:
    """Persist user msg, assistant msg, artifact version, and update title."""
    await db.save_message(conv_id, "user", question)
    await db.save_message(
        conv_id, "assistant", answer_text,
        code=code or None, images=images or None,
        artifact=artifact.model_dump() if artifact else None,
    )
    if artifact:
        version = await db.next_artifact_version(conv_id, artifact.id)
        await db.save_artifact(
            conv_id, artifact.id, artifact.title, artifact.type, version,
            code=code or None, images=images or None,
        )
    if not history:
        await db.update_conversation_title(conv_id, question[:50])
    else:
        await db.touch_conversation(conv_id)


@router.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest, x_session_id: uuid.UUID = Header()) -> QueryResponse:
    conv_id = req.conversation_id

    if not req.question.strip():
        return QueryResponse(answer="", error="Please enter a question.", conversation_id=str(conv_id))

    history = await db.get_message_history(conv_id)
    artifact_descriptors = await db.get_artifact_descriptors(conv_id)

    deps = AgentDeps(
        df_schema=_schema,
        artifacts=[dict(d) for d in artifact_descriptors],
    )

    try:
        message_history = _build_message_history(history)
        override_model = make_model(req.model) if req.model else None
        result = await agent.run(req.question, deps=deps, message_history=message_history, model=override_model)

        code = ""
        images: list[str] = []
        for r in deps.results:
            if r.code:
                code = r.code
            if r.images:
                images.extend(r.images)

        existing_ids = {d["artifact_id"] for d in artifact_descriptors}
        answer_text, artifact = _parse_artifact(result.output, existing_ids)

        if artifact is None and images:
            artifact = ArtifactMeta(id=f"artifact-{uuid.uuid4().hex[:8]}", title="Chart", type="chart", action="create")

        await _persist_response(conv_id, req.question, answer_text, code, images, artifact, history)

        return QueryResponse(
            answer=answer_text, code=code, images=images,
            artifact=artifact, conversation_id=str(conv_id),
        )
    except Exception as e:
        return QueryResponse(answer="", error=f"Unable to process your question: {str(e)}", conversation_id=str(conv_id))


@router.post("/api/query/stream")
async def query_stream(req: QueryRequest, x_session_id: uuid.UUID = Header()) -> StreamingResponse:
    """SSE endpoint that streams thinking, tool calls, and answer tokens."""
    conv_id = req.conversation_id

    async def event_generator() -> AsyncGenerator[str, None]:
        if not req.question.strip():
            yield _sse_event({"type": "done", "answer": "", "code": "", "images": [], "artifact": None, "error": "Please enter a question.", "conversation_id": str(conv_id)})
            return

        history = await db.get_message_history(conv_id)
        artifact_descriptors = await db.get_artifact_descriptors(conv_id)

        deps = AgentDeps(
            df_schema=_schema,
            artifacts=[dict(d) for d in artifact_descriptors],
        )

        try:
            message_history = _build_message_history(history)
            override_model = make_model(req.model) if req.model else None

            full_text = ""
            results_seen = 0

            async for event in agent.run_stream_events(
                req.question, deps=deps, message_history=message_history, model=override_model,
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
                    tool_code = _extract_tool_code(event.part.args)
                    yield _sse_event({"type": "tool_call_start", "tool": event.part.tool_name, "code": tool_code})

                elif isinstance(event, FunctionToolResultEvent):
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
                    code = ""
                    images: list[str] = []
                    for r in deps.results:
                        if r.code:
                            code = r.code
                        if r.images:
                            images.extend(r.images)

                    existing_ids = {d["artifact_id"] for d in artifact_descriptors}
                    answer_text, artifact = _parse_artifact(full_text, existing_ids)

                    if artifact is None and images:
                        artifact = ArtifactMeta(id=f"artifact-{uuid.uuid4().hex[:8]}", title="Chart", type="chart", action="create")

                    yield _sse_event({
                        "type": "done",
                        "answer": answer_text, "code": code, "images": images,
                        "artifact": artifact.model_dump() if artifact else None,
                        "error": None, "conversation_id": str(conv_id),
                    })

                    await _persist_response(conv_id, req.question, answer_text, code, images, artifact, history)

        except Exception as e:
            yield _sse_event({
                "type": "done", "answer": "", "code": "", "images": [],
                "artifact": None, "error": f"Unable to process your question: {str(e)}",
                "conversation_id": str(conv_id),
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
