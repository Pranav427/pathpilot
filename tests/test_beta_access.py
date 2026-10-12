import pytest

import beta_access
import llm_utils
from beta_access import (
    AIUsageLimitError,
    ai_actions_per_day,
    ai_actions_used_today,
    check_and_record_ai_action,
    invite_code_required,
    invite_code_valid,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "beta.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return path


def test_invite_code_is_optional_and_checked_when_set(monkeypatch):
    monkeypatch.delenv("BETA_INVITE_CODE", raising=False)
    assert not invite_code_required() and invite_code_valid("")
    monkeypatch.setenv("BETA_INVITE_CODE", "leicester-beta")
    assert invite_code_required()
    assert invite_code_valid("leicester-beta")
    assert invite_code_valid("  leicester-beta  ")
    assert not invite_code_valid("wrong")
    assert not invite_code_valid("")


def test_daily_limit_setting(monkeypatch):
    monkeypatch.delenv("MAX_AI_ACTIONS_PER_DAY", raising=False)
    assert ai_actions_per_day() == 40
    monkeypatch.setenv("MAX_AI_ACTIONS_PER_DAY", "7")
    assert ai_actions_per_day() == 7
    monkeypatch.setenv("MAX_AI_ACTIONS_PER_DAY", "0")
    assert ai_actions_per_day() == 0
    monkeypatch.setenv("MAX_AI_ACTIONS_PER_DAY", "abc")
    assert ai_actions_per_day() == 40


def test_cap_counts_per_user_and_blocks_at_the_limit(db, monkeypatch):
    monkeypatch.setenv("MAX_AI_ACTIONS_PER_DAY", "3")
    for _ in range(3):
        check_and_record_ai_action(user_id=101, db_path=db)
    assert ai_actions_used_today(101, db) == 3
    with pytest.raises(AIUsageLimitError, match="3 AI actions"):
        check_and_record_ai_action(user_id=101, db_path=db)
    assert ai_actions_used_today(101, db) == 3  # a blocked call is not counted
    check_and_record_ai_action(user_id=202, db_path=db)  # another user is unaffected
    assert ai_actions_used_today(202, db) == 1


def test_no_user_or_zero_limit_means_unlimited(db, monkeypatch):
    monkeypatch.setenv("MAX_AI_ACTIONS_PER_DAY", "1")
    beta_access.set_current_user(None)
    for _ in range(5):
        check_and_record_ai_action(db_path=db)  # no user: not limited
    monkeypatch.setenv("MAX_AI_ACTIONS_PER_DAY", "0")
    for _ in range(5):
        check_and_record_ai_action(user_id=1, db_path=db)
    assert ai_actions_used_today(1, db) == 0


def test_llm_calls_are_blocked_with_a_readable_error(db, monkeypatch):
    monkeypatch.setenv("MAX_AI_ACTIONS_PER_DAY", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    beta_access.set_current_user(555)
    # The first request is allowed; use the limiter directly to avoid a network call.
    check_and_record_ai_action(db_path=db)
    from types import SimpleNamespace

    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(AssertionError("must not call the API")))
    )
    monkeypatch.setattr(llm_utils, "validate_llm_configuration", lambda c: None)
    monkeypatch.setattr(beta_access, "check_and_record_ai_action", lambda *a, **k: (_ for _ in ()).throw(AIUsageLimitError("limit reached")))
    with pytest.raises(llm_utils.LLMServiceError) as info:
        llm_utils.create_message_with_retry(client, model="m", max_tokens=5, messages=[])
    assert info.value.code == "daily_limit" and "limit reached" in str(info.value)
    beta_access.set_current_user(None)
