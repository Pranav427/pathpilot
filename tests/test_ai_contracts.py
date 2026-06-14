from unittest.mock import patch

from analyzer import normalize_analysis_result
from llm_utils import (
    GeminiClientAdapter,
    LLMServiceError,
    classify_llm_error,
    create_message_with_retry,
    create_json_with_retry,
    get_llm_model,
    get_llm_provider,
    validate_anthropic_configuration,
    validate_llm_configuration,
)
from matcher import build_grounded_strongest_points


class FakeResponse:
    def __init__(self, text):
        self.content = [type("Content", (), {"text": text})()]


class FakeMessages:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return FakeResponse("not json")
        return FakeResponse(
            '{"skills": [], "tools": [], "keywords": [], "summary": "Role summary"}'
        )


class FakeClient:
    provider = "anthropic"

    def __init__(self):
        self.messages = FakeMessages()


class AlwaysFailsMessages:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        raise self.error


class AlwaysFailsClient:
    provider = "anthropic"

    def __init__(self, error):
        self.messages = AlwaysFailsMessages(error)


def test_job_analysis_allows_empty_supported_categories():
    result = normalize_analysis_result(
        {
            "skills": ["Python", "Python"],
            "tools": [],
            "keywords": [],
            "summary": "Python role.",
        }
    )

    assert result["skills"] == ["Python"]
    assert result["tools"] == []


def test_malformed_llm_json_retries_and_recovers(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = FakeClient()
    with patch("llm_utils.time.sleep"):
        result = create_json_with_retry(
            client,
            model="test",
            max_tokens=50,
            messages=[],
            required_keys=["skills", "tools", "keywords", "summary"],
            source="Test",
            attempts=2,
        )

    assert result["summary"] == "Role summary"
    assert client.messages.calls == 2


def test_quota_failure_is_not_retried(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = AlwaysFailsClient(RuntimeError("status code: 429 rate limit"))

    with patch("llm_utils.time.sleep") as sleep:
        try:
            create_message_with_retry(
                client,
                model="test",
                max_tokens=50,
                messages=[],
                attempts=3,
            )
        except LLMServiceError as exc:
            assert exc.code == "account_limit"
        else:
            raise AssertionError("Expected quota failure")

    assert client.messages.calls == 1
    sleep.assert_not_called()


def test_temporary_provider_failure_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = AlwaysFailsClient(RuntimeError("status code: 503 unavailable"))

    with patch("llm_utils.time.sleep") as sleep:
        try:
            create_message_with_retry(
                client,
                model="test",
                max_tokens=50,
                messages=[],
                attempts=3,
            )
        except LLMServiceError as exc:
            assert exc.code == "temporary_unavailable"
        else:
            raise AssertionError("Expected temporary provider failure")

    assert client.messages.calls == 3
    assert sleep.call_count == 2


def test_provider_error_classification_hides_raw_details():
    error = classify_llm_error(
        RuntimeError("authentication_error: invalid x-api-key secret-value")
    )

    assert error.code == "authentication"
    assert "secret-value" not in str(error)


def test_missing_anthropic_key_has_actionable_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    try:
        validate_anthropic_configuration()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected missing API key validation to fail")

    assert ".env.example" in message
    assert "restart ApplySmart AI" in message


def test_anthropic_is_default_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    assert get_llm_provider() == "anthropic"
    assert get_llm_model() == "claude-sonnet-4-5"


def test_missing_gemini_key_has_actionable_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    try:
        validate_llm_configuration()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected missing Gemini API key validation to fail")

    assert "GEMINI_API_KEY" in message


def test_gemini_json_requests_use_structured_response_mode(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client = GeminiClientAdapter()

    with patch.object(
        client.messages,
        "create",
        return_value=FakeResponse('{"status": "ok"}'),
    ) as create:
        result = create_json_with_retry(
            client,
            model="gemini-test",
            max_tokens=50,
            messages=[{"role": "user", "content": "Return JSON"}],
            required_keys=["status"],
            source="Gemini test",
            attempts=1,
        )

    assert result == {"status": "ok"}
    assert create.call_args.kwargs["response_mime_type"] == "application/json"


def test_strongest_points_exclude_application_only_terms():
    profile = {
        "_application_confirmed_terms": ["RAG"],
        "projects": [
            {
                "name": "Verified Project",
                "tools": ["Python"],
            }
        ],
        "education": [{"degree": "B.Tech Computer Science"}],
        "certifications": ["Verified Certificate"],
    }
    deterministic = {
        "matched_skills": ["Python", "RAG"],
        "matched_tools": [],
    }

    points = build_grounded_strongest_points({}, profile, deterministic)

    assert all("RAG" not in point for point in points)
    assert any("Verified Project" in point for point in points)
