"""Application configuration loaded from environment variables and ``.env`` files.

The ``.env`` file is searched in the repository root first (the documented
location), then next to this file, then in the current working directory.
Later files override earlier ones; real environment variables override all.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

SUPPORTED_LLM_PROVIDERS: tuple[str, ...] = (
    "bedrock",
    "openai",
    "anthropic",
    "gemini",
    "ollama",
    "unsloth",
)
SUPPORTED_CLOUD_PROVIDERS: tuple[str, ...] = ("aws", "azure", "gcp", "digitalocean")

_DEFAULT_DB_PATH = REPO_ROOT / "data" / "shimo.db"


class Settings(BaseSettings):
    """Runtime settings for the Shimo backend, CLI and agent harness."""

    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Shimo"
    app_version: str = "2.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = f"sqlite:///{_DEFAULT_DB_PATH}"

    # AWS
    aws_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("AWS_REGION", "AWS_DEFAULT_REGION"),
    )
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_profile: str = ""
    aws_account_id: str = ""

    # Azure
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_subscription_id: str = ""

    # GCP
    gcp_project_id: str = ""
    gcp_service_account_json: str = ""  # Path to a key file, or the JSON itself
    gcp_billing_project_id: str = ""  # Project hosting the billing export (defaults to gcp_project_id)
    gcp_billing_dataset: str = "billing_export"
    gcp_billing_table: str = ""  # Empty = wildcard over gcp_billing_export_v1_*

    # DigitalOcean
    digitalocean_api_token: str = ""

    # LLM provider
    llm_provider: str = "bedrock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = ""  # Optional OpenAI-compatible endpoint
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    unsloth_base_url: str = "http://127.0.0.1:8888"
    unsloth_username: str = "unsloth"
    unsloth_password: str = "12345678"
    unsloth_model: str = ""
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    bedrock_region: str = "us-west-2"

    # Agent / memory behaviour
    agent_max_tokens: int = 8192
    memory_compression_threshold: int = 20  # Compress after this many stored messages
    memory_recent_window: int = 10  # Messages replayed to the LLM on resume
    memory_context_word_limit: int = 6000  # Hard cap on assembled memory injection
    memory_llm_summaries: bool = True  # Use the LLM to summarise compressed history

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:5035"

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalise_llm_provider(cls, value: object) -> str:
        return str(value or "bedrock").strip().lower()

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def llm_model_name(self, provider: str | None = None) -> str:
        """Return the configured model name for an LLM provider."""
        name = (provider or self.llm_provider).lower()
        mapping = {
            "bedrock": self.bedrock_model_id,
            "openai": self.openai_model,
            "anthropic": self.anthropic_model,
            "gemini": self.gemini_model,
            "ollama": self.ollama_model,
            "unsloth": self.unsloth_model or "(auto-detected)",
        }
        return mapping.get(name, "")

    def provider_status(self) -> dict[str, dict[str, object]]:
        """Describe which cloud providers have credentials configured.

        AWS is special: boto3 can also pick up ambient credentials (profiles,
        instance roles), so "configured" only reflects explicit settings.
        """
        return {
            "aws": {
                "configured": bool(self.aws_access_key_id or self.aws_profile),
                "region": self.aws_region,
                "account_id": self.aws_account_id,
            },
            "azure": {
                "configured": bool(
                    self.azure_tenant_id and self.azure_client_id and self.azure_client_secret
                ),
                "subscription_id": self.azure_subscription_id,
            },
            "gcp": {
                "configured": bool(self.gcp_service_account_json),
                "project_id": self.gcp_project_id,
                "billing_dataset": self.gcp_billing_dataset,
            },
            "digitalocean": {
                "configured": bool(self.digitalocean_api_token),
            },
        }


settings = Settings()
