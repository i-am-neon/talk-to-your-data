# backend/app/routes/query.py
import asyncio
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
    ModelMessagesTypeAdapter, TextPart,
    PartStartEvent, PartDeltaEvent, FunctionToolCallEvent, FunctionToolResultEvent,
    ThinkingPart, ThinkingPartDelta, TextPartDelta, RetryPromptPart,
)

from app.agent.agent import agent, AgentDeps, make_model
from app import db
from app.data.loader import load_dataset, get_schema_summary
from app.errors import ErrorCode, USER_MESSAGES, MAX_QUESTION_LENGTH, classify_error, REQUEST_TIMEOUT_SECONDS

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


class ColumnDef(BaseModel):
    key: str
    label: str
    dtype: str


class TableSpec(BaseModel):
    columns: list[ColumnDef]
    rows: list[dict[str, Any]]


class QueryRequest(BaseModel):
    question: str
    conversation_id: uuid.UUID
    model: str | None = None


class QueryResponse(BaseModel):
    answer: str
    code: str = ""
    chart: ChartSpec | None = None
    table: TableSpec | None = None
    images: list[str] = []
    error: str | None = None
    error_code: str | None = None
    artifact: ArtifactMeta | None = None
    conversation_id: str


def _parse_artifact(text: str, existing_ids: set[str], existing_descriptors: list[dict] | None = None) -> tuple[str, ArtifactMeta | None]:
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
            # LLM may use the title instead of the ID — try to resolve by title
            resolved = False
            if existing_descriptors:
                for d in existing_descriptors:
                    if d["title"] == artifact_id:
                        artifact_id = d["artifact_id"]
                        resolved = True
                        break
            if not resolved:
                action = "create"
                artifact_id = f"artifact-{uuid.uuid4().hex[:8]}"

    return clean_text, ArtifactMeta(id=artifact_id, title=title, type=art_type, action=action)


async def _load_message_history(conv_id: uuid.UUID):
    """Load the full PydanticAI message history from the database."""
    raw = await db.get_pydantic_messages(conv_id)
    if raw is None:
        return None
    return ModelMessagesTypeAdapter.validate_json(raw)


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
    code: str, images: list[str], chart: dict | None, table: dict | None,
    artifact: ArtifactMeta | None, is_first_message: bool,
    pydantic_messages_json: bytes,
) -> None:
    """Persist user msg, assistant msg, artifact version, pydantic history, and update title."""
    await db.save_message(conv_id, "user", question)
    await db.save_message(
        conv_id, "assistant", answer_text,
        code=code or None, images=images or None,
        chart=chart, table=table, artifact=artifact.model_dump() if artifact else None,
    )
    await db.save_pydantic_messages(conv_id, pydantic_messages_json)
    if artifact:
        version = await db.next_artifact_version(conv_id, artifact.id)
        await db.save_artifact(
            conv_id, artifact.id, artifact.title, artifact.type, version,
            code=code or None, images=images or None, chart=chart, table=table,
        )
    if is_first_message:
        await db.update_conversation_title(conv_id, question[:50])
    else:
        await db.touch_conversation(conv_id)


@router.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest, x_session_id: uuid.UUID = Header()) -> QueryResponse:
    conv_id = req.conversation_id

    if not req.question.strip():
        return QueryResponse(
            answer="", error=USER_MESSAGES[ErrorCode.EMPTY_QUESTION],
            error_code=ErrorCode.EMPTY_QUESTION,
            conversation_id=str(conv_id),
        )
    if len(req.question) > MAX_QUESTION_LENGTH:
        return QueryResponse(
            answer="", error=USER_MESSAGES[ErrorCode.QUESTION_TOO_LONG],
            error_code=ErrorCode.QUESTION_TOO_LONG,
            conversation_id=str(conv_id),
        )

    message_history = await _load_message_history(conv_id)
    artifact_descriptors = await db.get_artifact_descriptors(conv_id)

    deps = AgentDeps(
        df_schema=_schema,
        artifacts=[dict(d) for d in artifact_descriptors],
    )

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            override_model = make_model(req.model) if req.model else None
            result = await agent.run(req.question, deps=deps, message_history=message_history, model=override_model)

        code = ""
        images: list[str] = []
        chart = None
        table = None
        for r in deps.results:
            if r.code:
                code = r.code
            if r.images:
                images.extend(r.images)
            if r.chart is not None and chart is None:
                try:
                    chart = ChartSpec(**r.chart)
                except Exception:
                    pass  # invalid spec, fall back to images
            if r.table is not None and table is None:
                try:
                    table = TableSpec(**r.table)
                except Exception:
                    pass

        existing_ids = {d["artifact_id"] for d in artifact_descriptors}
        answer_text, artifact = _parse_artifact(result.output, existing_ids, artifact_descriptors)

        if artifact is None and table:
            table_title = next((r.table.get("title", "Table") for r in deps.results if r.table), "Table")
            artifact = ArtifactMeta(id=f"artifact-{uuid.uuid4().hex[:8]}", title=table_title, type="table", action="create")
        elif artifact is None and (images or chart):
            artifact = ArtifactMeta(id=f"artifact-{uuid.uuid4().hex[:8]}", title="Chart", type="chart", action="create")

        chart_dict = chart.model_dump() if chart else None
        table_dict = table.model_dump() if table else None
        await _persist_response(
            conv_id, req.question, answer_text, code, images, chart_dict, table_dict,
            artifact, is_first_message=message_history is None,
            pydantic_messages_json=result.all_messages_json(),
        )

        return QueryResponse(
            answer=answer_text, code=code, chart=chart, table=table, images=images,
            artifact=artifact, conversation_id=str(conv_id),
        )
    except Exception as e:
        error_code, error_msg = classify_error(e)
        return QueryResponse(
            answer="", error=error_msg, error_code=error_code,
            conversation_id=str(conv_id),
        )


@router.post("/api/query/stream")
async def query_stream(req: QueryRequest, x_session_id: uuid.UUID = Header()) -> StreamingResponse:
    """SSE endpoint that streams thinking, tool calls, and answer tokens."""
    conv_id = req.conversation_id

    async def event_generator() -> AsyncGenerator[str, None]:
        if not req.question.strip():
            yield _sse_event({"type": "done", "answer": "", "code": "", "images": [], "artifact": None, "error": USER_MESSAGES[ErrorCode.EMPTY_QUESTION], "error_code": ErrorCode.EMPTY_QUESTION, "conversation_id": str(conv_id)})
            return
        if len(req.question) > MAX_QUESTION_LENGTH:
            yield _sse_event({"type": "done", "answer": "", "code": "", "images": [], "artifact": None, "error": USER_MESSAGES[ErrorCode.QUESTION_TOO_LONG], "error_code": ErrorCode.QUESTION_TOO_LONG, "conversation_id": str(conv_id)})
            return

        message_history = await _load_message_history(conv_id)
        artifact_descriptors = await db.get_artifact_descriptors(conv_id)

        deps = AgentDeps(
            df_schema=_schema,
            artifacts=[dict(d) for d in artifact_descriptors],
        )

        try:
            override_model = make_model(req.model) if req.model else None

            full_text = ""
            results_seen = 0

            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
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
                        chart_dict = None
                        table_dict = None
                        for r in deps.results:
                            if r.code:
                                code = r.code
                            if r.images:
                                images.extend(r.images)
                            if r.chart is not None and chart_dict is None:
                                try:
                                    ChartSpec(**r.chart)  # validate
                                    chart_dict = r.chart
                                except Exception:
                                    pass
                            if r.table is not None and table_dict is None:
                                try:
                                    TableSpec(**r.table)  # validate
                                    table_dict = r.table
                                except Exception:
                                    pass

                        existing_ids = {d["artifact_id"] for d in artifact_descriptors}
                        answer_text, artifact = _parse_artifact(full_text, existing_ids, artifact_descriptors)

                        if artifact is None and table_dict:
                            table_title = next((r.table.get("title", "Table") for r in deps.results if r.table), "Table")
                            artifact = ArtifactMeta(id=f"artifact-{uuid.uuid4().hex[:8]}", title=table_title, type="table", action="create")
                        elif artifact is None and (images or chart_dict):
                            artifact = ArtifactMeta(id=f"artifact-{uuid.uuid4().hex[:8]}", title="Chart", type="chart", action="create")

                        yield _sse_event({
                            "type": "done",
                            "answer": answer_text, "code": code,
                            "chart": chart_dict, "table": table_dict,
                            "images": images,
                            "artifact": artifact.model_dump() if artifact else None,
                            "error": None, "error_code": None, "conversation_id": str(conv_id),
                        })

                        await _persist_response(
                            conv_id, req.question, answer_text, code, images, chart_dict, table_dict,
                            artifact, is_first_message=message_history is None,
                            pydantic_messages_json=event.result.all_messages_json(),
                        )

        except Exception as e:
            error_code, error_msg = classify_error(e)
            yield _sse_event({
                "type": "done", "answer": "", "code": "", "images": [],
                "artifact": None, "error": error_msg, "error_code": error_code,
                "conversation_id": str(conv_id),
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
