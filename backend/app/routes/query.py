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
                code = r.code
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
