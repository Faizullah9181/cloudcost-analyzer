"""LLM provider factory: builds a Strands ``Model`` for the configured provider."""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from strands.models.model import Model

from backend.config import SUPPORTED_LLM_PROVIDERS, Settings, settings as default_settings

logger = logging.getLogger(__name__)

_unsloth_token: str | None = None
_unsloth_active_model: str | None = None


def _bedrock(config: Settings) -> Model:
    import boto3  # pylint: disable=import-outside-toplevel
    from strands.models import BedrockModel  # pylint: disable=import-outside-toplevel

    kwargs: dict[str, Any] = {
        "model_id": config.bedrock_model_id,
        "region_name": config.bedrock_region,
        "streaming": True,
        "max_tokens": config.agent_max_tokens,
    }
    if config.aws_profile or (config.aws_access_key_id and config.aws_secret_access_key):
        session_kwargs: dict[str, Any] = {"region_name": config.bedrock_region}
        if config.aws_profile:
            session_kwargs["profile_name"] = config.aws_profile
        if config.aws_access_key_id and config.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = config.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = config.aws_secret_access_key
            if config.aws_session_token:
                session_kwargs["aws_session_token"] = config.aws_session_token
        kwargs["boto_session"] = boto3.session.Session(**session_kwargs)
    return BedrockModel(**kwargs)


def _openai_compatible(model_id: str, api_key: str, base_url: str | None) -> Model:
    from strands.models.openai import OpenAIModel  # pylint: disable=import-outside-toplevel

    client_args: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_args["base_url"] = base_url
    return OpenAIModel(client_args=client_args, model_id=model_id)


def _openai(config: Settings) -> Model:
    api_key = config.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
    return _openai_compatible(config.openai_model, api_key, config.openai_base_url or None)


def _gemini(config: Settings) -> Model:
    if not config.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
    return _openai_compatible(config.gemini_model, config.gemini_api_key, config.gemini_base_url)


def _anthropic(config: Settings) -> Model:
    from strands.models.anthropic import AnthropicModel  # pylint: disable=import-outside-toplevel

    api_key = config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id=config.anthropic_model,
        max_tokens=config.agent_max_tokens,
    )


def _ollama(config: Settings) -> Model:
    from strands.models.ollama import OllamaModel  # pylint: disable=import-outside-toplevel

    return OllamaModel(config.ollama_host, model_id=config.ollama_model)


def _unsloth(config: Settings) -> Model:
    try:
        token = unsloth_login(config)
        model_name = config.unsloth_model or unsloth_active_model(token, config)
        return _openai_compatible(model_name, token, f"{config.unsloth_base_url.rstrip('/')}/v1")
    except RuntimeError as exc:
        if not config.gemini_api_key:
            raise RuntimeError(
                "Unsloth Studio is unavailable and GEMINI_API_KEY is not configured for fallback"
            ) from exc
        logger.warning("Unsloth unavailable (%s); falling back to Gemini model '%s'", exc, config.gemini_model)
        return _gemini(config)


_BUILDERS = {
    "bedrock": _bedrock,
    "openai": _openai,
    "gemini": _gemini,
    "anthropic": _anthropic,
    "ollama": _ollama,
    "unsloth": _unsloth,
}


def build_model(provider: str | None = None, config: Settings | None = None) -> Model:
    """Instantiate the Strands model for ``provider`` (defaults to ``settings.llm_provider``)."""
    config = config or default_settings
    name = (provider or config.llm_provider or "").strip().lower()
    builder = _BUILDERS.get(name)
    if builder is None:
        raise ValueError(
            f"Unsupported LLM provider {name!r}. Supported providers: {', '.join(SUPPORTED_LLM_PROVIDERS)}"
        )
    logger.info("Using LLM provider %s (model %s)", name, config.llm_model_name(name))
    return builder(config)


def describe_model(provider: str | None = None, config: Settings | None = None) -> str:
    """Human-readable ``provider/model`` label."""
    config = config or default_settings
    name = (provider or config.llm_provider).lower()
    return f"{name}/{config.llm_model_name(name)}"


# ----- Unsloth Studio helpers -----------------------------------------------------------


def unsloth_login(config: Settings | None = None) -> str:
    """Authenticate with Unsloth Studio and return a bearer token (cached)."""
    global _unsloth_token  # pylint: disable=global-statement
    config = config or default_settings
    if _unsloth_token:
        return _unsloth_token

    request = Request(
        f"{config.unsloth_base_url.rstrip('/')}/api/auth/login",
        data=json.dumps({"username": config.unsloth_username, "password": config.unsloth_password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - configured local endpoint
            parsed = json.loads(response.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise RuntimeError(f"Unable to authenticate to Unsloth Studio at {config.unsloth_base_url}") from exc

    token = str(parsed.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Unsloth login response missing access_token")
    _unsloth_token = token
    return token


def unsloth_active_model(token: str, config: Settings | None = None) -> str:
    """Detect the active model from Unsloth's status endpoint (cached)."""
    global _unsloth_active_model  # pylint: disable=global-statement
    config = config or default_settings
    if _unsloth_active_model:
        return _unsloth_active_model

    request = Request(
        f"{config.unsloth_base_url.rstrip('/')}/v1/status",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310
            parsed = json.loads(response.read().decode("utf-8", errors="replace"))
        model = str(parsed.get("active_model", "")).strip()
        if model:
            _unsloth_active_model = model
            return model
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        logger.warning("Unable to auto-detect the Unsloth active model; using 'default'")
    return "default"


def reset_unsloth_cache() -> None:
    """Forget cached Unsloth credentials (used by tests / reconnects)."""
    global _unsloth_token, _unsloth_active_model  # pylint: disable=global-statement
    _unsloth_token = None
    _unsloth_active_model = None
