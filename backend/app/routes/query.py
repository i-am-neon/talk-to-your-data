# backend/app/routes/query.py
import re
import uuid

from pydantic import BaseModel
from fastapi import APIRouter
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart

from app.agent.agent import agent, AgentDeps
from app.data.loader import load_dataset, get_schema_summary

router = APIRouter()

_df = load_dataset()
_schema = get_schema_summary(_df)

ARTIFACT_PATTERN = re.compile(
    r'\[\[artifact:(create|update)\|([^|]+)\|([^|]*?)(?:\|(chart|table|code))?\]\]'
)


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


class QueryResponse(BaseModel):
    answer: str
    code: str = ""
    images: list[str] = []
    error: str | None = None
    artifact: ArtifactMeta | None = None


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
        result = await agent.run(req.question, deps=deps, message_history=message_history)

        # Extract code and images from deps (populated by tool)
        code = ""
        images = []
        for r in deps.results:
            if r.code:
                code = r.code
            if r.images:
                images.extend(r.images)

        # Parse artifact markers from agent response
        existing_ids = {a.id for a in req.artifacts}
        answer_text, artifact = _parse_artifact(result.output, existing_ids)

        # Auto-detect: if no marker but images were produced, auto-create a chart artifact
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
