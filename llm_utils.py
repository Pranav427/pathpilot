import json
import os
import re
import time
from typing import Iterable


DEFAULT_PROVIDER = "anthropic"
PROVIDER_SETTINGS = {
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "placeholder": "your_gemini_api_key",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-2.5-flash",
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "placeholder": "your_anthropic_api_key",
        "model_env": "ANTHROPIC_MODEL",
        "default_model": "claude-sonnet-4-5",
    },
}


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
                # ApplySmart needs concise, visible structured output rather
                # than spending the token budget on model reasoning.
                "thinking_config": {"thinking_budget": 0},
            },
        )
        return _TextResponse(response.text or "")


class GeminiClientAdapter:
    """Exposes Gemini through the message interface used by ApplySmart."""

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
            "restart ApplySmart AI."
        )


def validate_anthropic_configuration() -> None:
    """Backward-compatible Anthropic validator."""
    settings = PROVIDER_SETTINGS["anthropic"]
    api_key = os.getenv(settings["api_key_env"], "").strip()
    if not api_key or api_key == settings["placeholder"]:
        raise RuntimeError(
            "Anthropic API key is not configured. Copy .env.example to .env, "
            "set ANTHROPIC_API_KEY to a valid key, and restart ApplySmart AI."
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
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"AI request failed after {attempts} attempts: {last_error}")


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
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(1.5 * attempt)
    raise RuntimeError(
        f"{source} failed after {attempts} attempts: {last_error}"
    )
