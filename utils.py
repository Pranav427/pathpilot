import re
from datetime import datetime


def clean_phone(phone: str) -> str:
    """Strips +91 country code from phone number."""
    phone = str(phone).strip()
    for prefix in ["+91 ", "+91"]:
        if phone.startswith(prefix):
            phone = phone[len(prefix):]
    return phone.strip()


def clean_url(url: str) -> str:
    """Strips http/https prefixes from display URLs."""
    return str(url).replace("https://", "").replace("http://", "").rstrip("/")


def clean_filename(text: str) -> str:
    """Converts arbitrary text into a safe lowercase filename stem."""
    text = str(text).lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", text)


def latex_escape(text: str) -> str:
    """Escape LaTeX special characters safely."""
    text = str(text)
    text = text.replace("\\", r"\textbackslash{}")
    text = text.replace("&", r"\&")
    text = text.replace("%", r"\%")
    text = text.replace("$", r"\$")
    text = text.replace("#", r"\#")
    text = text.replace("_", r"\_")
    text = text.replace("^", r"\^{}")
    text = text.replace("~", r"\textasciitilde{}")
    text = text.replace("\u2014", r"---")
    text = text.replace("\u2013", r"--")
    return text


def profile_is_graduate(profile: dict) -> bool:
    """Return whether the profile represents a completed degree."""
    objective = str(profile.get("objective", "")).lower()
    if "graduate" in objective:
        return True

    education = profile.get("education", [])
    if not education:
        return False

    years = re.findall(r"\b(20\d{2})\b", str(education[0].get("year", "")))
    return bool(years and int(years[-1]) <= datetime.now().year)


def normalize_candidate_status(text: str, profile: dict) -> str:
    """Prevent generated documents from calling a graduate a current student."""
    value = str(text)
    if not profile_is_graduate(profile):
        return value

    replacements = (
        (r"\bfinal[- ]year B\.?Tech student\b", "B.Tech graduate"),
        (
            r"\bfinal[- ]year Computer Science undergraduate\b",
            "Computer Science graduate",
        ),
        (
            r"\bfinal[- ]year Computer Science student\b",
            "Computer Science graduate",
        ),
        (
            r"\bfinal[- ]year\b.{0,40}\bundergraduate\b",
            "Computer Science graduate",
        ),
        (r"\bComputer Science undergraduate\b", "Computer Science graduate"),
        (r"\bB\.?Tech undergraduate\b", "B.Tech graduate"),
        (r"\bB\.?Tech CS student\b", "B.Tech CS graduate"),
        (
            r"\bComputer Science engineering student\b",
            "Computer Science engineering graduate",
        ),
        (
            r"\bComputer Science student at\b",
            "Computer Science graduate from",
        ),
        (r"\bComputer Science student\b", "Computer Science graduate"),
        (r"\bengineering student\b", "engineering graduate"),
    )
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return value
