import json
import os
import re
import socket
import time
from typing import Iterable


DEFAULT_PROVIDER = "anthropic"
PROVIDER_SETTINGS = {
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "placeholder": "your_gemini_api_key",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-2.0-flash",
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "placeholder": "your_anthropic_api_key",
        "model_env": "ANTHROPIC_MODEL",
        "default_model": "claude-sonnet-4-5",
    },
}


class LLMServiceError(RuntimeError):
    """Normalized AI-provider failure safe for application-level handling."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def classify_llm_error(exc: Exception) -> LLMServiceError:
    """Maps provider-specific failures to stable PathPilot error categories."""
    if isinstance(exc, LLMServiceError):
        return exc

    text = str(exc).strip()
    lower = text.lower()
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    if status_code is None:
        status_match = re.search(r"status(?:\s+code)?\s*[:=]\s*(\d{3})", lower)
        if status_match:
            status_code = int(status_match.group(1))

    if status_code == 401 or any(
        marker in lower
        for marker in (
            "authentication_error",
            "invalid api key",
            "invalid x-api-key",
            "authentication method",
            "unauthorized",
        )
    ):
        return LLMServiceError(
            "authentication",
            "The configured AI API key was rejected.",
        )

    if status_code == 403 or any(
        marker in lower
        for marker in ("permission_error", "permission denied", "forbidden")
    ):
        return LLMServiceError(
            "permission",
            "The configured AI API key does not have permission for this request.",
        )

    if status_code == 404 or any(
        marker in lower
        for marker in ("model not found", "not_found_error", "unknown model")
    ):
        return LLMServiceError(
            "model_unavailable",
            "The configured AI model is unavailable for this account.",
        )

    if status_code == 429 or any(
        marker in lower
        for marker in (
            "credit balance",
            "rate limit",
            "quota exceeded",
            "resource_exhausted",
        )
    ):
        return LLMServiceError(
            "account_limit",
            "The AI account has reached a credit, quota, or rate limit.",
        )

    if status_code in {408, 500, 502, 503, 504, 529} or any(
        marker in lower
        for marker in (
            "overloaded_error",
            "service unavailable",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
        )
    ):
        return LLMServiceError(
            "temporary_unavailable",
            "The AI service is temporarily unavailable.",
            retryable=True,
        )

    if isinstance(exc, (TimeoutError, socket.timeout)) or any(
        marker in lower for marker in ("timed out", "timeout")
    ):
        return LLMServiceError(
            "timeout",
            "The AI request timed out.",
            retryable=True,
        )

    return LLMServiceError(
        "request_failed",
        "The AI request failed.",
    )


def _retry_delay(attempt: int) -> float:
    """Returns a short bounded backoff for transient provider failures."""
    return min(1.5 * attempt, 4.5)


class _TextContent:
    def __init__(self, text: str):
        self.text = text


class _TextResponse:
    def __init__(self, text: str):
        self.content = [_TextContent(text)]


class _GeminiMessages:
    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        response_mime_type: str = "text/plain",
    ):
        from google import genai

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "").strip())
        prompt = "\n\n".join(
            str(message.get("content", ""))
            for message in messages
            if message.get("content")
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "max_output_tokens": max_tokens,
                "response_mime_type": response_mime_type,
                # PathPilot needs concise, visible structured output rather
                # than spending the token budget on model reasoning.
                "thinking_config": {"thinking_budget": 0},
            },
        )
        return _TextResponse(response.text or "")


class GeminiClientAdapter:
    """Exposes Gemini through the message interface used by PathPilot."""

    provider = "gemini"

    def __init__(self):
        self.messages = _GeminiMessages()


def get_llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in PROVIDER_SETTINGS:
        supported = ", ".join(PROVIDER_SETTINGS)
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER '{provider}'. Use one of: {supported}."
        )
    return provider


def get_llm_model(provider: str | None = None) -> str:
    provider = provider or get_llm_provider()
    settings = PROVIDER_SETTINGS[provider]
    return os.getenv(
        settings["model_env"],
        settings["default_model"],
    ).strip()


def get_llm_client():
    provider = get_llm_provider()
    if provider == "gemini":
        return GeminiClientAdapter()

    from anthropic import Anthropic

    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def validate_llm_configuration(client=None) -> None:
    """Raises a clear error before an unauthenticated AI request is attempted."""
    provider = getattr(client, "provider", None)
    if not provider:
        provider = "anthropic" if client is not None else get_llm_provider()
    settings = PROVIDER_SETTINGS[provider]
    api_key = os.getenv(settings["api_key_env"], "").strip()
    if not api_key or api_key == settings["placeholder"]:
        raise RuntimeError(
            f"{provider.title()} API key is not configured. Copy .env.example "
            f"to .env, set {settings['api_key_env']} to a valid key, and "
            "restart PathPilot."
        )


def validate_anthropic_configuration() -> None:
    """Backward-compatible Anthropic validator."""
    settings = PROVIDER_SETTINGS["anthropic"]
    api_key = os.getenv(settings["api_key_env"], "").strip()
    if not api_key or api_key == settings["placeholder"]:
        raise RuntimeError(
            "Anthropic API key is not configured. Copy .env.example to .env, "
            "set ANTHROPIC_API_KEY to a valid key, and restart PathPilot."
        )


def extract_json_object(raw_text: str) -> dict:
    """Extracts the first JSON object from an LLM response."""
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")

    return json.loads(text[start:end + 1])


def require_keys(data: dict, keys: Iterable[str], source: str) -> dict:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ValueError(f"{source} response missing required keys: {missing}")
    return data


def create_message_with_retry(
    client,
    *,
    model: str,
    max_tokens: int,
    messages: list[dict],
    attempts: int = 3,
):
    """Calls the selected LLM with retries for transient failures."""
    validate_llm_configuration(client)
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            last_error = classify_llm_error(exc)
            if not last_error.retryable or attempt == attempts:
                raise last_error from exc
            time.sleep(_retry_delay(attempt))
    raise last_error


def create_json_with_retry(
    client,
    *,
    model: str,
    max_tokens: int,
    messages: list[dict],
    required_keys: Iterable[str],
    source: str,
    attempts: int = 3,
) -> dict:
    """Calls the selected LLM and retries invalid structured responses."""
    validate_llm_configuration(client)
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            request = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if getattr(client, "provider", "") == "gemini":
                request["response_mime_type"] = "application/json"
            response = client.messages.create(**request)
            data = extract_json_object(response.content[0].text)
            return require_keys(data, required_keys, source)
        except (KeyboardInterrupt, SystemExit):
            raise
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt == attempts:
                raise RuntimeError(
                    f"{source} returned invalid structured output."
                ) from exc
            time.sleep(_retry_delay(attempt))
        except Exception as exc:
            last_error = classify_llm_error(exc)
            if not last_error.retryable or attempt == attempts:
                raise last_error from exc
            time.sleep(_retry_delay(attempt))
    raise last_error
