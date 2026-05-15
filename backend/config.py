"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "Cloud Analytics"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./cloud_analytics.db"

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""

    # Azure
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_subscription_id: str = ""

    # GCP
    gcp_project_id: str = ""
    gcp_service_account_json: str = ""  # Path or JSON string

    # DigitalOcean
    digitalocean_api_token: str = ""

    # LLM Provider
    llm_provider: str = (
        "bedrock"  # bedrock | openai | anthropic | ollama | gemini | unsloth
    )
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    unsloth_base_url: str = "http://127.0.0.1:8888"
    unsloth_username: str = "unsloth"
    unsloth_password: str = "12345678"
    unsloth_model: str = ""
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_region: str = "us-west-2"

    # CORS
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,http://localhost:5035"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
