import uuid

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel

from app import db

router = APIRouter()


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: str
    updated_at: str
    messages: list[dict]
    artifacts: list[dict]


@router.get("/api/conversations")
async def list_conversations(x_session_id: uuid.UUID = Header()) -> list[ConversationSummary]:
    await db.upsert_session(x_session_id)
    convs = await db.list_conversations(x_session_id)
    return [ConversationSummary(**_serialize(c)) for c in convs]


@router.post("/api/conversations")
async def create_conversation(x_session_id: uuid.UUID = Header()) -> ConversationSummary:
    await db.upsert_session(x_session_id)
    conv = await db.create_conversation(x_session_id)
    return ConversationSummary(**_serialize(conv))


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID, x_session_id: uuid.UUID = Header()) -> ConversationDetail:
    await db.upsert_session(x_session_id)
    conv = await db.get_conversation(conversation_id, x_session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail(**_serialize(conv))


@router.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID, x_session_id: uuid.UUID = Header()) -> Response:
    await db.upsert_session(x_session_id)
    deleted = await db.delete_conversation(conversation_id, x_session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=204)


def _serialize(obj: dict) -> dict:
    result = {}
    for k, v in obj.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [_serialize(i) if isinstance(i, dict) else (i.isoformat() if hasattr(i, "isoformat") else i) for i in v]
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        else:
            result[k] = v
    return result
