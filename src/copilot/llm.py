"""Configurable language-model provider for the IT Ops Copilot agent.

Configuration (read from environment variables; a project-root ``.env``
file is loaded automatically when present — see ``.env.example``):

    LLM_PROVIDER        "openai" | "anthropic" | "none" (default: auto-detect
                        from the presence of OPENAI_API_KEY / ANTHROPIC_API_KEY)
    OPENAI_API_KEY      API key for OpenAI or any OpenAI-compatible endpoint
    ANTHROPIC_API_KEY   API key for Anthropic
    LLM_API_KEY         Generic fallback key used when the provider-specific
                        key variable is not set
    LLM_MODEL           Model name (e.g. "gpt-4o-mini" or
                        "claude-3-5-haiku-latest"); a sensible default is used
                        when omitted
    LLM_BASE_URL        Base URL override for OpenAI-compatible providers
                        (default https://api.openai.com) — useful for Azure,
                        OpenRouter, Groq, vLLM, Ollama, LM Studio, etc.
    ANTHROPIC_BASE_URL  Base URL override for Anthropic
                        (default https://api.anthropic.com)

API keys are never hardcoded; they only come from the environment. All HTTP
traffic uses ``httpx`` which is already a project dependency, so no extra
LLM SDK packages are needed.
"""
import os
from dataclasses import dataclass

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
REQUEST_TIMEOUT_SECONDS = 30


class LLMUnavailableError(RuntimeError):
    """Raised when no usable language-model provider is configured or reachable."""


@dataclass
class LLMConfig:
    provider: str  # "openai" | "anthropic" | "none"
    api_key: str = ""
    model: str = ""
    base_url: str = ""


def get_llm_config() -> LLMConfig:
    """Build the current provider configuration from environment variables."""
    configured = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    generic_key = os.getenv("LLM_API_KEY") or ""

    if configured in ("none", "disabled", "off", "false"):
        return LLMConfig(provider="none")

    if configured == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY") or generic_key
        return LLMConfig(
            provider="anthropic",
            api_key=key,
            model=os.getenv("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL,
            base_url=(os.getenv("ANTHROPIC_BASE_URL") or "").strip() or DEFAULT_ANTHROPIC_BASE_URL,
        )

    if configured == "openai":
        key = os.getenv("OPENAI_API_KEY") or generic_key
        return LLMConfig(
            provider="openai",
            api_key=key,
            model=os.getenv("LLM_MODEL") or DEFAULT_OPENAI_MODEL,
            base_url=(os.getenv("LLM_BASE_URL") or "").strip() or DEFAULT_OPENAI_BASE_URL,
        )

    # Auto-detect based on which provider key exists in the environment.
    if os.getenv("ANTHROPIC_API_KEY"):
        return get_llm_config_from_provider("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        return get_llm_config_from_provider("openai")

    return LLMConfig(provider="none")


def get_llm_config_from_provider(provider: str) -> LLMConfig:
    if provider == "anthropic":
        return LLMConfig(
            provider="anthropic",
            api_key=os.getenv("ANTHROPIC_API_KEY") or "",
            model=os.getenv("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL,
            base_url=(os.getenv("ANTHROPIC_BASE_URL") or "").strip() or DEFAULT_ANTHROPIC_BASE_URL,
        )
    return LLMConfig(
        provider="openai",
        api_key=os.getenv("OPENAI_API_KEY") or "",
        model=os.getenv("LLM_MODEL") or DEFAULT_OPENAI_MODEL,
        base_url=(os.getenv("LLM_BASE_URL") or "").strip() or DEFAULT_OPENAI_BASE_URL,
    )


def is_provider_configured(config: LLMConfig) -> bool:
    return bool(config.provider and config.provider != "none" and config.api_key)


def configuration_hint() -> str:
    """A user-facing explanation of how to enable AI responses."""
    return (
        "AI responses are unavailable because no language-model provider is "
        "configured. To enable one, set one of the following in your "
        "environment or in a `.env` file at the project root:\n"
        "- `OPENAI_API_KEY` (or `LLM_API_KEY`), optionally `LLM_MODEL` and "
        "`LLM_BASE_URL` for an OpenAI-compatible endpoint\n"
        "- `ANTHROPIC_API_KEY` (or `LLM_API_KEY`), optionally `LLM_MODEL`\n"
        "- `LLM_PROVIDER=openai|anthropic|none` to force a specific provider\n\n"
        "Until then, I can still answer basic ticket questions using the "
        "deterministic queries built into this app."
    )


def chat(config: LLMConfig, messages: list, max_tokens: int = 900) -> str:
    """Send ``messages`` to the configured provider and return the reply text."""
    if not is_provider_configured(config):
        raise LLMUnavailableError(configuration_hint())

    try:
        if config.provider == "anthropic":
            return _chat_anthropic(config, messages, max_tokens)
        return _chat_openai(config, messages, max_tokens)
    except LLMUnavailableError:
        raise
    except Exception as exc:  # network / HTTP / parsing issues
        raise LLMUnavailableError(
            f"The configured AI provider failed: {exc}\n\n{configuration_hint()}"
        ) from exc


def _chat_openai(config: LLMConfig, messages: list, max_tokens: int) -> str:
    url = f"{config.base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {config.api_key}"}
    payload = {
        "model": config.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(f"Unexpected response from provider: {data}") from exc


def _chat_anthropic(config: LLMConfig, messages: list, max_tokens: int) -> str:
    url = f"{config.base_url.rstrip('/')}/v1/messages"
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
    }

    system_text = "\n\n".join(
        m["content"] for m in messages if m.get("role") == "system"
    )
    convo = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant")
    ]
    payload = {
        "model": config.model,
        "messages": convo,
        "system": system_text or None,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        try:
            parts = [
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            ]
            return "".join(parts)
        except (AttributeError, TypeError) as exc:
            raise LLMUnavailableError(f"Unexpected response from provider: {data}") from exc
