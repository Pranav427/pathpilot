"""Private-beta controls: an optional sign-up invite code and a daily AI cap.

BETA_INVITE_CODE        when set, registration requires this code (sign-in and
                        the demo account are unaffected).
MAX_AI_ACTIONS_PER_DAY  AI requests allowed per user per UTC day (default 40;
                        set 0 to disable). A full application uses about 5.
"""

import contextvars
import hmac
import os
from datetime import datetime, timezone

import db_client

INVITE_CODE_ENV = "BETA_INVITE_CODE"
DAILY_LIMIT_ENV = "MAX_AI_ACTIONS_PER_DAY"
DEFAULT_DAILY_LIMIT = 40

_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "pathpilot_current_user_id", default=None
)


class AIUsageLimitError(RuntimeError):
    """The user has used today's AI allowance."""


# -- invite code -----------------------------------------------------------
def invite_code_required() -> bool:
    return bool(os.getenv(INVITE_CODE_ENV, "").strip())


def invite_code_valid(code: str) -> bool:
    """True when no code is configured, or the supplied code matches."""
    expected = os.getenv(INVITE_CODE_ENV, "").strip()
    if not expected:
        return True
    return hmac.compare_digest(str(code or "").strip().encode(), expected.encode())


# -- daily AI cap ----------------------------------------------------------
def set_current_user(user_id: int | None) -> None:
    """Record whose request is running so AI calls can be counted per user."""
    _current_user_id.set(user_id)


def ai_actions_per_day() -> int:
    raw = os.getenv(DAILY_LIMIT_ENV, "").strip()
    if not raw:
        return DEFAULT_DAILY_LIMIT
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_DAILY_LIMIT


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def ai_actions_used_today(user_id: int, db_path: str | None = None) -> int:
    db_client.init_db_schema(db_path)
    rows = db_client.execute_query(
        "SELECT count FROM ai_usage WHERE user_id = ? AND day = ?",
        (user_id, _today()),
        db_path=db_path,
    )
    return int(rows[0]["count"]) if rows else 0


def check_and_record_ai_action(user_id: int | None = None, db_path: str | None = None) -> None:
    """Count one AI request for the user, or raise AIUsageLimitError at the cap.

    Requests with no known user (scripts, tests) are not limited.
    """
    user_id = user_id if user_id is not None else _current_user_id.get()
    limit = ai_actions_per_day()
    if user_id is None or limit <= 0:
        return
    used = ai_actions_used_today(user_id, db_path)
    if used >= limit:
        raise AIUsageLimitError(
            f"You have used today's {limit} AI actions. The allowance resets "
            "at midnight UTC."
        )
    day = _today()
    updated = db_client.execute_write(
        "UPDATE ai_usage SET count = count + 1 WHERE user_id = ? AND day = ?",
        (user_id, day),
        db_path=db_path,
    )
    if not updated:
        try:
            db_client.execute_write(
                "INSERT INTO ai_usage (user_id, day, count) VALUES (?, ?, 1)",
                (user_id, day),
                db_path=db_path,
            )
        except Exception:
            # A concurrent request created the row first; count against it.
            db_client.execute_write(
                "UPDATE ai_usage SET count = count + 1 WHERE user_id = ? AND day = ?",
                (user_id, day),
                db_path=db_path,
            )
