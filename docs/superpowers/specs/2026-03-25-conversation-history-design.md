# Conversation History Design

Users can persist, browse, and switch between past conversations — similar to the Claude web/desktop experience. Adds a sidebar listing past conversations, full message and artifact persistence in PostgreSQL, and a three-pane layout.

## Architecture Overview

**Persistence:** PostgreSQL via Railway's managed Postgres addon. All data scoped by anonymous browser sessions (no auth).

**Approach:** Backend-first. New REST endpoints for CRUD on conversations. The existing `POST /api/query` is extended to save messages and artifacts as a side effect.

**Identity:** Anonymous sessions. The browser generates a UUID on first visit, stores it in localStorage, and sends it as an `X-Session-ID` header on every request. No login, no auth.

## Database Schema

Four tables:

```sql
CREATE TABLE sessions (
    id         UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conversations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    title      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    code            TEXT,
    images          JSONB,
    artifact        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    artifact_id     TEXT NOT NULL,
    title           TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('chart', 'table', 'code')),
    version         INTEGER NOT NULL,
    code            TEXT,
    images          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_session ON conversations(session_id, updated_at DESC);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at ASC);
CREATE INDEX idx_artifacts_conversation ON artifacts(conversation_id, artifact_id, version);
```

Key decisions:
- `sessions` is thin — just an ID and timestamp. Auto-created on first request via upsert.
- `artifacts` stores every version as a separate row (same `artifact_id`, incrementing `version`), mapping directly to the frontend's existing version navigation.
- `messages.artifact` stores the `ArtifactMeta` JSON when a message creates or updates an artifact, preserving the link between message and artifact action.
- `images` is JSONB — an array of base64 strings. Simple, avoids a separate file storage layer for a take-home.

## Backend API

All endpoints require `X-Session-ID` header (UUID).

### New Endpoints

```
GET /api/conversations
  Response: [{ id, title, created_at, updated_at }]
  Sorted by updated_at DESC. Filtered by session_id.

POST /api/conversations
  Response: { id, title, created_at, updated_at }
  Creates an empty conversation. Title is null initially.

GET /api/conversations/{id}
  Response: {
    id, title, created_at, updated_at,
    messages: [{ id, role, content, code, images, artifact, created_at }],
    artifacts: [{ id, artifact_id, title, type, version, code, images, created_at }]
  }
  Messages sorted by created_at ASC. Artifacts sorted by artifact_id, version ASC.
  Returns 404 if conversation doesn't belong to the session.

DELETE /api/conversations/{id}
  Response: 204 No Content
  Cascading delete of messages and artifacts.
  Returns 404 if conversation doesn't belong to the session.
```

### Changes to Existing `POST /api/query`

Request body changes — `history` and `artifacts` fields are removed. The backend loads conversation context from the database using `conversation_id`:
```json
{
  "question": "What was revenue by month?",
  "conversation_id": "uuid"
}
```

After the LLM response:
1. Save user message to `messages` table.
2. Save assistant message (with code, images, artifact metadata) to `messages` table.
3. If artifact metadata present, save artifact version to `artifacts` table.
4. If this is the first message in the conversation, set `conversations.title` to the first ~50 characters of the user's question.
5. Update `conversations.updated_at`.

Response gains `conversation_id`:
```json
{
  "answer": "...",
  "code": "...",
  "images": [...],
  "artifact": {...},
  "conversation_id": "uuid"
}
```

### Session ID Flow

1. Frontend checks localStorage for `session_id`.
2. If absent, generate a UUIDv4 and store it.
3. Send as `X-Session-ID` header on every request.
4. Backend upserts the session row on first sight.

### Database Library

asyncpg with raw SQL. The schema is simple (4 tables, basic CRUD), so an ORM adds weight without benefit. A single `db.py` module handles connection pooling and query functions.

## Frontend UI

### Layout: Three-Pane

```
┌──────────┬─────────────────────┬──────────────┐
│ Sidebar  │     Chat Panel      │  Workspace   │
│          │                     │   Panel      │
│ History  │  Messages + Input   │  Artifacts   │
│ list     │                     │  + Versions  │
│          │                     │              │
│ [+New]   │  [Ask a question..] │  [← v1 v2 →]│
└──────────┴─────────────────────┴──────────────┘
```

- Sidebar, chat, and workspace visible simultaneously when artifacts exist.
- When no artifacts exist, chat expands into the workspace area (current behavior preserved).
- Sidebar collapsible via toggle button. Default: expanded on desktop, collapsed on mobile.

### Component Tree

```
App
├── Sidebar (new)
│   ├── NewChatButton
│   └── ConversationList
│       └── ConversationItem (per conversation)
├── ChatPanel (existing, receives conversationId)
│   ├── MessageList
│   └── ChatInput
└── WorkspacePanel (existing, receives conversationId)
    └── ArtifactViewer with version navigation
```

### New Hooks

**`useSession()`** — generates/retrieves session UUID from localStorage. Provides it for API headers.

**`useConversations(sessionId)`** — fetches conversation list from `GET /api/conversations`. Provides `create()`, `select(id)`, `delete(id)` functions and `activeConversationId` state.

### Modified Hooks

**`useChat(conversationId)`** — when `conversationId` changes, fetches full history from `GET /api/conversations/{id}` and replaces local message state. Sends `conversation_id` with `POST /api/query`. After each response, triggers conversation list refresh (to update ordering).

**`useArtifacts(conversationId)`** — loads artifact versions from the conversation response. Continues to track new versions in state during the active session.

### Conversation Switching

1. User clicks a conversation in the sidebar → sets `activeConversationId`.
2. `useChat` and `useArtifacts` detect the ID change, fetch from API, replace state.
3. Chat panel and workspace panel re-render with loaded data.

### New Conversation

1. User clicks "+ New" → `POST /api/conversations` → receives new UUID.
2. `activeConversationId` updates, chat and artifacts clear.
3. First query auto-generates the conversation title (backend truncates first user message to ~50 chars).

### Sidebar Behavior

- **Collapse:** Toggle button (chevron) in the sidebar header. Collapses fully (hidden, not icon-only). Default expanded on desktop, collapsed on mobile.
- **Titles:** Auto-generated from first user message, truncated ~50 chars. No rename.
- **Delete:** Hover reveals trash icon. Click shows brief confirmation before `DELETE`. If active conversation is deleted, switch to most recent remaining (or empty state).
- **Active indicator:** Selected conversation has highlighted background.
- **Empty state:** "No conversations yet" in sidebar. Chat area shows centered "Ask a question about your data."
- **Loading:** Skeleton placeholders in sidebar while fetching. Brief spinner in chat panel on conversation switch.

## Migration Strategy

A single SQL migration file creates all four tables and indexes. Run on deploy via a startup script or a `just migrate` command.

## Configuration

New environment variable in `.env` / `.env.example`:
- `DATABASE_URL` — PostgreSQL connection string (e.g., `postgresql://user:pass@host:5432/dbname`)

## Dependencies Added

**Backend:**
- `asyncpg` — PostgreSQL async driver

**No new frontend dependencies** — all UI built with existing React + shadcn/ui + Tailwind.

## What This Does NOT Include

- Authentication or user accounts
- Conversation search or filtering
- Conversation renaming or pinning
- Conversation grouping by date
- Real-time sync across tabs/devices
- Export or sharing of conversations
