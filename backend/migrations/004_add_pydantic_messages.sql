ALTER TABLE conversations ADD COLUMN IF NOT EXISTS pydantic_messages JSONB;
