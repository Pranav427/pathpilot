"""Recognises UK early-career programme types from a job title and advert text.

Labels: spring/insight week, placement year, graduate scheme, apprenticeship,
internship, graduate role. Used to flag early-career suitability and to show a
badge; the checks are keyword based and conservative.
"""

import re

SPRING_WEEK = "Spring / insight week"
PLACEMENT_YEAR = "Placement year"
GRADUATE_SCHEME = "Graduate scheme"
APPRENTICESHIP = "Apprenticeship"
INTERNSHIP = "Internship"
GRADUATE_ROLE = "Graduate role"

_SPRING = re.compile(
    r"\b(?:spring\s+(?:week|insight|programme|program)|insight\s+(?:week|programme|program|day)s?)\b",
    re.IGNORECASE,
)
_PLACEMENT = re.compile(
    r"\b(?:placement\s+year|industrial\s+placement|sandwich\s+(?:year|placement|course)|"
    r"year\s+in\s+industry|(?:12|twelve)[- ]month\s+placement|year[- ]long\s+placement|"
    r"placement\s+student|placement\s+(?:analyst|engineer|developer))\b",
    re.IGNORECASE,
)
_SCHEME = re.compile(
    r"\b(?:graduate\s+(?:scheme|programme|program|development\s+programme|trainee)|"
    r"management\s+trainee|future\s+leaders?\s+programme|early\s+careers?\s+programme)\b",
    re.IGNORECASE,
)
_APPRENTICE = re.compile(
    r"\b(?:degree\s+apprentice(?:ship)?|higher\s+apprentice(?:ship)?|apprentice(?:ship)?)\b",
    re.IGNORECASE,
)
_INTERN = re.compile(r"\b(?:summer\s+intern(?:ship)?|intern(?:ship)?)\b", re.IGNORECASE)
_GRADUATE_TITLE = re.compile(r"\bgraduate\b", re.IGNORECASE)


def classify_programme(title: str, description: str = "") -> str:
    """Return the early-career programme label, or '' when none is evident.

    Strong programme phrases may appear in the advert body; the generic word
    'graduate' only counts in the title (adverts say 'graduate' in many other ways).
    """
    title = str(title or "")
    body = f"{title} {description or ''}"
    for label, pattern in (
        (SPRING_WEEK, _SPRING),
        (PLACEMENT_YEAR, _PLACEMENT),
        (GRADUATE_SCHEME, _SCHEME),
    ):
        if pattern.search(body):
            return label
    if _APPRENTICE.search(title):
        return APPRENTICESHIP
    if _INTERN.search(title):
        return INTERNSHIP
    if _GRADUATE_TITLE.search(title):
        return GRADUATE_ROLE
    return ""


def programme_experience_fields(label: str) -> tuple[str, str]:
    """Map a programme label to PathPilot's (job_type, experience_level)."""
    if label in {SPRING_WEEK, PLACEMENT_YEAR, APPRENTICESHIP, INTERNSHIP}:
        return "Internship", "Internship"
    if label in {GRADUATE_SCHEME, GRADUATE_ROLE}:
        return "", "Fresher / Entry level"
    return "", ""
