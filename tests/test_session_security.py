import tracker
from app import SESSION_TOKEN_TTL_SECONDS, make_session_token, verify_session_token


def test_valid_token_round_trips():
    assert verify_session_token(make_session_token(7)) == 7


def test_expired_token_is_rejected():
    token = make_session_token(7, now=1_000_000)
    assert verify_session_token(token, now=1_000_000 + SESSION_TOKEN_TTL_SECONDS + 1) is None


def test_tampered_or_malformed_tokens_are_rejected():
    token = make_session_token(7)
    _, issued, sig = token.split(":")
    assert verify_session_token(f"8:{issued}:{sig}") is None
    assert verify_session_token("7:notanumber:abc") is None
    assert verify_session_token("garbage") is None
    assert verify_session_token("") is None


def test_token_not_forgeable_with_old_default_secret(monkeypatch):
    import hashlib
    import hmac
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("APP_SESSION_SECRET", raising=False)
    import time
    issued = int(time.time())
    forged_sig = hmac.new(b"pathpilot_salt", f"1:{issued}".encode(), hashlib.sha256).hexdigest()
    assert verify_session_token(f"1:{issued}:{forged_sig}") is None


def test_delete_application_only_removes_own_rows(tmp_path):
    db = str(tmp_path / "t.db")
    tracker.init_db(db)
    owner = tracker.register_user("owner@example.com", "password123", db_path=db)
    other = tracker.register_user("other@example.com", "password123", db_path=db)
    app_id = tracker.record_application(
        company_name="Acme", job_title="Analyst",
        match={"fit_score": 70}, ats_report={"keyword_coverage": 60},
        resume_path="", cover_letter_path="", job_analysis={},
        user_id=owner, db_path=db,
    )
    tracker.delete_application(app_id, user_id=other, db_path=db)
    assert tracker.get_application(app_id, db_path=db, user_id=owner) is not None
    tracker.delete_application(app_id, user_id=owner, db_path=db)
    assert tracker.get_application(app_id, db_path=db, user_id=owner) is None
