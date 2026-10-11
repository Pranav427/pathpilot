"""Removes strength words the candidate's own profile does not support.

LLMs tend to inflate wording ("advanced Excel", "extensive datasets", "proven
ability"). A word is kept only if the candidate wrote it in their own profile.
"""

import json
import re

INTENSIFIERS = (
    "advanced", "extensive", "extensively", "expert", "proven", "highly",
    "strong", "deep", "deeply", "robust", "comprehensive", "significant",
    "significantly", "complex", "sophisticated", "exceptional", "outstanding",
    "excellent", "seasoned", "successfully", "cutting-edge", "state-of-the-art",
    "world-class", "exceptionally", "extremely", "thorough", "in-depth",
)

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in INTENSIFIERS) + r")\b\s*",
    re.IGNORECASE,
)

_EVIDENCE_KEYS = (
    "objective", "education", "experience", "projects", "skills", "achievements",
    "certifications", "courses", "publications", "_application_confirmed_details",
)


def evidence_text(profile: dict) -> str:
    """Lower-cased text of everything the candidate has told us about themselves."""
    parts = {key: profile.get(key) for key in _EVIDENCE_KEYS if profile.get(key)}
    return json.dumps(parts, ensure_ascii=False, default=str).lower()


def unsupported_intensifiers(text: str, profile: dict) -> list[str]:
    """Strength words used in `text` that do not appear in the profile."""
    evidence = evidence_text(profile)
    found = []
    for match in _PATTERN.finditer(str(text)):
        word = match.group(1).lower()
        if word not in evidence and word not in found:
            found.append(word)
    return found


def strip_unsupported_intensifiers(text: str, profile: dict) -> str:
    """Delete unsupported strength words; keep everything else unchanged."""
    evidence = evidence_text(profile)
    original = str(text)
    changed = False

    def _drop(match: re.Match) -> str:
        nonlocal changed
        if match.group(1).lower() in evidence:
            return match.group(0)
        changed = True
        return ""

    cleaned = _PATTERN.sub(_drop, original)
    if not changed:
        return original
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    # Re-capitalise where a removed word began a sentence or line.
    cleaned = re.sub(
        r"(^|[.!?]\s+|\n)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        cleaned,
    )
    return cleaned.strip()
