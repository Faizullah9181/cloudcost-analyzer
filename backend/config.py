"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "Cloud Analytics"
    debug: bool = False

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""

    # LLM Provider
    llm_provider: str = "bedrock"  # bedrock | openai | anthropic | ollama
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_region: str = "us-west-2"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:5035"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
