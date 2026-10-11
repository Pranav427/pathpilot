"""Locale rules for generated CVs and cover letters.

UK is the default standard. Keeping the rules here gives a single place to add
other countries later without touching the generators.
"""

import re
from datetime import date

UK_ENGLISH_INSTRUCTION = (
    "Write in British English (e.g. organised, optimised, programme, analyse, "
    "specialise)."
)

# Cover letter
COVER_LETTER_MIN_PARAGRAPHS = 3
COVER_LETTER_MAX_PARAGRAPHS = 4
COVER_LETTER_MAX_WORDS = 300

# CV (resume text length is checked in words; ~1 page ≈ 450-650, 2 pages ≈ 1100)
CV_MIN_WORDS = 300
CV_MAX_WORDS = 1100

GENERIC_SALUTATION = "Dear Hiring Manager"
SIGN_OFF_NAMED = "Yours sincerely"
SIGN_OFF_UNNAMED = "Yours faithfully"

SALUTATION_PREFIXES = ("dear ",)
SIGN_OFF_PREFIXES = ("yours sincerely", "yours faithfully", "sincerely", "kind regards", "best regards")


def format_uk_date(value: date | None = None) -> str:
    """Return a UK-style long date, e.g. '11 October 2026'."""
    value = value or date.today()
    return f"{value.day} {value.strftime('%B %Y')}"


def sign_off_for(salutation: str) -> str:
    """'Yours faithfully' for generic salutations, otherwise 'Yours sincerely'."""
    generic = salutation.lower().startswith(
        ("dear hiring", "dear sir", "dear madam", "to whom")
    )
    return SIGN_OFF_UNNAMED if generic else SIGN_OFF_NAMED


_RIGHT_TO_WORK_PATTERN = re.compile(
    r"right[- ]to[- ]work|work(?:ing)? (?:legally|authori[sz]ation)|"
    r"(?:legally|eligible|authori[sz]ed|entitled|permitted) to work|"
    r"visa|sponsorship|sponsor(?:ed)?\b|graduate route|skilled worker|"
    r"settled status|indefinite leave|\bilr\b|work permit",
    re.IGNORECASE,
)


def mentions_right_to_work(text: str) -> bool:
    return bool(_RIGHT_TO_WORK_PATTERN.search(str(text)))


def strip_right_to_work_claims(text: str) -> str:
    """Remove sentences about right to work, visas or sponsorship.

    The candidate's status is a legal fact that must come from the user, never
    from the job advert, so generated text may not state it on its own.
    """
    sentences = re.split(r"(?<=[.!?])\s+", str(text).strip())
    kept = [s for s in sentences if not mentions_right_to_work(s)]
    return " ".join(kept).strip()
