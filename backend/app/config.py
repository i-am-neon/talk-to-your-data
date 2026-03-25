from pydantic_settings import BaseSettings

# Available models on the LiteLLM proxy
SONNET_4_6 = "us.anthropic.claude-sonnet-4-6"
SONNET_4_5 = "claude-sonnet-4-5"
HAIKU_4_5 = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
OPUS_4_5 = "global.anthropic.claude-opus-4-5-20251101-v1:0"
OPUS_4_6 = "global.anthropic.claude-opus-4-6-v1"

MODEL_IDS: dict[str, str] = {
    "sonnet": SONNET_4_6,
    "haiku": HAIKU_4_5,
    "opus": OPUS_4_6,
}


class Settings(BaseSettings):
    litellm_api_key: str
    litellm_base_url: str = "https://litellm-production-f079.up.railway.app"
    litellm_model: str = SONNET_4_6
    e2b_api_key: str
    logfire_token: str = ""
    logfire_environment: str = "local"
    frontend_url: str = "*"
    database_url: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
