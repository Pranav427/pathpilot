"""Locale rules for generated CVs and cover letters.

UK is the default standard. Keeping the rules here gives a single place to add
other countries later without touching the generators.
"""

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
