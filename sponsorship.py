"""Detects what a job advert says about visa sponsorship and right to work.

Statuses:
  no_sponsorship        the advert says it will not sponsor a visa
  sponsorship_offered   the advert says it can or will sponsor a visa
  right_to_work_needed  the advert requires existing right to work (unclear on sponsorship)
  unknown               nothing stated
Only the first is ever used to hide a job, and only for candidates who said they
will need sponsorship.
"""

import re

NO_SPONSORSHIP = "no_sponsorship"
SPONSORSHIP_OFFERED = "sponsorship_offered"
RIGHT_TO_WORK_NEEDED = "right_to_work_needed"
UNKNOWN = "unknown"

_SPONSOR = r"(?:visa\s+)?sponsor(?:ship|ing)?"

_NO_PATTERNS = [
    rf"\bno\s+(?:visa\s+)?{_SPONSOR}",
    rf"\b(?:unable|not able|cannot|can't|can not|won't|will not|do not|does not|don't|doesn't|are not|is not|isn't|aren't)\s+(?:currently\s+|able\s+to\s+|in a position to\s+|offer\s+|provide\s+|to\s+)*{_SPONSOR}",
    rf"\bnot\s+(?:be\s+|currently\s+|presently\s+|able\s+to\s+|in a position to\s+)*(?:offer|provide|support)\s+(?:any\s+)?(?:visa\s+)?{_SPONSOR}",
    rf"\b(?:unable|not able)\s+to\s+(?:consider|accept|take)\b[^.]{{0,60}}\b(?:requir\w+|need\w*)\s+(?:visa\s+)?{_SPONSOR}",
    rf"\b(?:not|cannot|unable)\b[^.]{{0,40}}\b(?:consider|accept)\w*\b[^.]{{0,60}}\b(?:requir\w+|need\w*)\s+(?:visa\s+)?{_SPONSOR}",
    rf"\b(?:requir\w+|need\w*)\s+(?:visa\s+)?{_SPONSOR}\w*[^.]{{0,60}}\b(?:will not|cannot|can not|won't|not)\s+(?:be\s+)?(?:considered|accepted|eligible)",
    rf"\bwithout\s+(?:requiring\s+|the need for\s+|needing\s+)?(?:visa\s+)?{_SPONSOR}",
    rf"\b(?:not|never)\s+require\s+(?:visa\s+)?{_SPONSOR}",
    rf"\b{_SPONSOR}\s+(?:is|are)\s+not\s+(?:available|offered|provided)",
    r"\bunable to (?:support|offer) (?:work )?visas?\b",
    r"\bnot (?:able to )?(?:offer|provide|support)\s+(?:work\s+)?visas?\b",
    r"\bmust\s+(?:not\s+require|not\s+need)\s+(?:visa\s+)?sponsor",
    r"\bcandidates\s+requiring\s+(?:visa\s+)?sponsorship\s+(?:will\s+)?(?:cannot|can not|not)\b",
]

_YES_PATTERNS = [
    rf"\b{_SPONSOR}\s+(?:is|are|may be|can be|could be)\s+(?:available|offered|provided|possible|considered)",
    rf"\b(?:we|company|employer)\s+(?:can|will|do|does|may|are able to|are happy to|are willing to)\s+(?:also\s+)?(?:offer\s+|provide\s+)?{_SPONSOR}",
    rf"\b(?:offer|offers|offering|provide|provides|providing)\s+(?:visa\s+)?{_SPONSOR}",
    r"\blicen[cs]ed sponsor\b",
    r"\bskilled worker (?:visa )?sponsorship\b",
    rf"\bhappy to\s+{_SPONSOR}",
    rf"\bcan\s+{_SPONSOR}",
]

_RTW_PATTERNS = [
    r"\bright[- ]to[- ]work\b",
    r"\b(?:legally|eligible|entitled|authori[sz]ed|permitted)\s+to\s+work\s+in\s+the\s+(?:uk|united kingdom)\b",
    r"\bwork\s+(?:permit|authori[sz]ation)\b",
]


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def classify_sponsorship(text: str) -> str:
    """Classify an advert's sponsorship stance. Negatives win over positives."""
    value = " ".join(str(text or "").split())
    if _any(_NO_PATTERNS, value):
        return NO_SPONSORSHIP
    if _any(_YES_PATTERNS, value):
        return SPONSORSHIP_OFFERED
    if _any(_RTW_PATTERNS, value):
        return RIGHT_TO_WORK_NEEDED
    return UNKNOWN


SPONSORSHIP_LABELS = {
    NO_SPONSORSHIP: "No visa sponsorship",
    SPONSORSHIP_OFFERED: "Visa sponsorship mentioned",
    RIGHT_TO_WORK_NEEDED: "Right to work required",
}


def sponsorship_label(status: str) -> str:
    return SPONSORSHIP_LABELS.get(status, "")
