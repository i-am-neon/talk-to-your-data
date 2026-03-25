import uuid
import pytest
from app import db


async def test_upsert_session(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    await db.upsert_session(session_id)


async def test_create_and_list_conversations(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    assert conv["id"] is not None
    assert conv["title"] is None
    convs = await db.list_conversations(session_id)
    assert len(convs) == 1


async def test_get_conversation(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    result = await db.get_conversation(conv["id"], session_id)
    assert result is not None
    assert result["messages"] == []
    assert result["artifacts"] == []


async def test_get_conversation_wrong_session(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    other = uuid.uuid4()
    await db.upsert_session(other)
    assert await db.get_conversation(conv["id"], other) is None


async def test_delete_conversation(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    assert await db.delete_conversation(conv["id"], session_id) is True
    assert await db.list_conversations(session_id) == []


async def test_save_and_load_messages(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    await db.save_message(conv["id"], "user", "What is revenue?")
    await db.save_message(conv["id"], "assistant", "Revenue is $1M", code="print(df.sum())", images=["base64img"])
    result = await db.get_conversation(conv["id"], session_id)
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][1]["code"] == "print(df.sum())"
    assert result["messages"][1]["images"] == ["base64img"]


async def test_save_artifact_version(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    await db.save_artifact(conv["id"], "art-1", "Chart", "chart", 1, code="plt.show()", images=["img1"])
    await db.save_artifact(conv["id"], "art-1", "Chart v2", "chart", 2, code="plt.bar()", images=["img2"])
    result = await db.get_conversation(conv["id"], session_id)
    assert len(result["artifacts"]) == 2
    assert result["artifacts"][0]["version"] == 1
    assert result["artifacts"][1]["version"] == 2


async def test_update_conversation_title(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    await db.update_conversation_title(conv["id"], "My Analysis")
    convs = await db.list_conversations(session_id)
    assert convs[0]["title"] == "My Analysis"


async def test_get_message_history(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    await db.save_message(conv["id"], "user", "Q1")
    await db.save_message(conv["id"], "assistant", "A1")
    await db.save_message(conv["id"], "user", "Q2")
    history = await db.get_message_history(conv["id"])
    assert len(history) == 3
    assert history[2]["content"] == "Q2"


async def test_get_artifact_descriptors(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    await db.save_artifact(conv["id"], "art-1", "Chart 1", "chart", 1)
    await db.save_artifact(conv["id"], "art-1", "Chart 1 v2", "chart", 2)
    await db.save_artifact(conv["id"], "art-2", "Table 1", "table", 1)
    descriptors = await db.get_artifact_descriptors(conv["id"])
    assert len(descriptors) == 2


async def test_next_artifact_version(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)
    assert await db.next_artifact_version(conv["id"], "art-1") == 1
    await db.save_artifact(conv["id"], "art-1", "Chart", "chart", 1)
    assert await db.next_artifact_version(conv["id"], "art-1") == 2
