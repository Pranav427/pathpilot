"""Structured job-discovery preferences shared by UI and search services."""

from dataclasses import asdict, dataclass, field
import re


EXPERIENCE_LEVELS = (
    "Internship",
    "Fresher / Entry level",
    "1-2 years",
    "2-4 years",
)
ENTRY_LEVEL_REVIEW_MAX_YEARS = 2
WORK_MODES = ("Onsite", "Hybrid", "Remote")
JOB_TYPES = ("Full-time", "Internship", "Contract")
DEFAULT_LOCATIONS_WHEN_UNSPECIFIED = ("India", "Remote")

ROLE_EVIDENCE = (
    (
        "AI/ML Engineer",
        {"artificial intelligence", "machine learning", "python"},
    ),
    (
        "Machine Learning Engineer",
        {"python", "machine learning", "model training"},
    ),
    (
        "NLP Engineer",
        {"natural language processing (nlp)", "text classification", "python"},
    ),
    (
        "Computer Vision Engineer",
        {"computer vision", "deep learning", "python"},
    ),
    (
        "Data Scientist",
        {"machine learning", "data analysis", "statistical analysis"},
    ),
    (
        "Software Engineer",
        {
            "object-oriented programming (oop)",
            "data structures & algorithms",
            "python",
        },
    ),
)

PREFERRED_SKILL_PRIORITY = (
    "Python",
    "Machine Learning",
    "Artificial Intelligence",
    "Deep Learning",
    "Natural Language Processing (NLP)",
    "Computer Vision",
    "SQL",
    "scikit-learn",
    "TensorFlow",
    "PyTorch",
    "pandas",
    "NumPy",
    "Git",
)


def split_preference_items(value: str) -> list[str]:
    """Splits comma/newline values while preserving order and casing."""
    items = []
    seen = set()
    for raw_item in str(value).replace("\n", ",").split(","):
        item = raw_item.strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            items.append(item)
    return items


@dataclass
class JobPreferences:
    """A normalized description of the jobs a candidate wants to discover."""

    target_roles: list[str]
    locations: list[str]
    experience_levels: list[str]
    work_modes: list[str]
    job_types: list[str]
    preferred_skills: list[str] = field(default_factory=list)
    excluded_keywords: list[str] = field(default_factory=list)
    maximum_job_age_days: int = 14

    def to_dict(self) -> dict:
        return asdict(self)


def flattened_profile_skills(profile: dict) -> list[str]:
    """Returns unique verified skills from a candidate profile."""
    skills = []
    seen = set()
    for values in profile.get("skills", {}).values():
        for value in values:
            item = str(value).strip()
            key = item.lower()
            if item and key not in seen:
                seen.add(key)
                skills.append(item)
    return skills


def suggest_job_preferences(profile: dict) -> dict:
    """Derives conservative discovery defaults from verified profile evidence."""
    verified_skills = flattened_profile_skills(profile)
    normalized_skills = {skill.lower() for skill in verified_skills}
    normalized_skills.update(
        str(category).strip().lower()
        for category in profile.get("skills", {})
        if str(category).strip()
    )

    roles = [
        role
        for role, required_evidence in ROLE_EVIDENCE
        if required_evidence.issubset(normalized_skills)
    ]
    if not roles:
        roles = ["Software Engineer"]

    skill_lookup = {skill.lower(): skill for skill in verified_skills}
    # Extract all candidate skills from profile
    candidate_skills = []
    preferred_categories = [
        "Programming Languages", "Languages", 
        "Artificial Intelligence & Machine Learning", "Deep Learning & Computer Vision", 
        "Machine Learning", "Libraries & Frameworks", "Databases", "Skills & Technologies Used",
        "AI", "Data"
    ]
    for cat in preferred_categories:
        for item in profile.get("skills", {}).get(cat, []):
            clean_item = re.sub(r"\s*\(familiarity\)\s*$", "", str(item).strip(), flags=re.IGNORECASE)
            if clean_item and clean_item.lower() not in {s.lower() for s in candidate_skills}:
                candidate_skills.append(clean_item)

    # 1. Prioritize candidate skills matching PREFERRED_SKILL_PRIORITY order
    preferred_skills = []
    candidate_skills_lower = {s.lower(): s for s in candidate_skills}
    for prio in PREFERRED_SKILL_PRIORITY:
        if prio.lower() in candidate_skills_lower:
            preferred_skills.append(candidate_skills_lower[prio.lower()])

    # 2. Append any other candidate skills not in the priority list
    for s in candidate_skills:
        if s.lower() not in {p.lower() for p in preferred_skills}:
            preferred_skills.append(s)

    # 3. Fallback to priority list lookup if candidate has no skills at all
    if not preferred_skills:
        preferred_skills = [
            skill_lookup[skill.lower()]
            for skill in PREFERRED_SKILL_PRIORITY
            if skill.lower() in skill_lookup
        ]
        
    preferred_skills = preferred_skills[:8]

    profile_location = str(profile.get("location", "")).strip()
    locations = (
        [profile_location]
        if profile_location
        and profile_location.lower()
        not in {"india", "your city, state, country"}
        else []
    )

    return {
        "target_roles": roles[:5],
        "locations": locations,
        "experience_levels": ["Internship", "Fresher / Entry level"],
        "work_modes": list(WORK_MODES),
        "job_types": ["Full-time", "Internship"],
        "preferred_skills": preferred_skills,
        "excluded_keywords": [
            "Senior",
            "Lead",
            "Manager",
            "Principal",
            "Staff",
            "Director",
            "Head",
        ],
        "maximum_job_age_days": 14,
    }


def build_job_preferences(
    *,
    target_roles: str,
    locations: str,
    experience_levels: list[str],
    work_modes: list[str],
    job_types: list[str],
    preferred_skills: str = "",
    excluded_keywords: str = "",
    maximum_job_age_days: int = 14,
) -> JobPreferences:
    """Builds and validates preferences submitted by a user."""
    parsed_locations = split_preference_items(locations)
    if not parsed_locations:
        parsed_locations = list(DEFAULT_LOCATIONS_WHEN_UNSPECIFIED)
    preferences = JobPreferences(
        target_roles=split_preference_items(target_roles),
        locations=parsed_locations,
        experience_levels=list(dict.fromkeys(experience_levels or [])),
        work_modes=list(dict.fromkeys(work_modes or [])),
        job_types=list(dict.fromkeys(job_types or [])),
        preferred_skills=split_preference_items(preferred_skills),
        excluded_keywords=split_preference_items(excluded_keywords),
        maximum_job_age_days=int(maximum_job_age_days),
    )
    validate_job_preferences(preferences)
    return preferences


def validate_job_preferences(preferences: JobPreferences) -> None:
    """Requires enough intent to make future discovery results useful."""
    missing = []
    if not preferences.target_roles:
        missing.append("at least one target role")
    if not preferences.experience_levels:
        missing.append("an experience level")
    if not preferences.work_modes:
        missing.append("a work mode")
    if not preferences.job_types:
        missing.append("a job type")
    if not 1 <= preferences.maximum_job_age_days <= 60:
        raise ValueError("Maximum job age must be between 1 and 60 days.")
    if missing:
        raise ValueError(
            "Complete your job preferences: " + ", ".join(missing) + "."
        )


def preference_rejection_reason(
    *,
    job_title: str,
    job_description: str,
    preferences: JobPreferences | None,
) -> str:
    """Returns a high-confidence preference rejection reason, if any."""
    if preferences is None:
        return ""

    # Exclusions describe unwanted roles, not responsibility wording such as
    # "work with senior engineers."
    searchable = str(job_title).lower()

    for keyword in preferences.excluded_keywords:
        if keyword.lower() in searchable:
            return f"Excluded keyword matched: {keyword}"

    entry_only = set(preferences.experience_levels).issubset(
        {"Internship", "Fresher / Entry level"}
    )
    experienced_title_markers = (
        "senior",
        "sr.",
        "sr ",
        "lead",
        "principal",
        "staff",
        "chief",
        "manager",
        "director",
        "head of",
        "architect",
        "expert",
    )
    if entry_only and any(
        marker in searchable for marker in experienced_title_markers
    ):
        return "Experienced role excluded by selected experience levels"
    if entry_only and re.search(
        r"\b(?:engineer|scientist|developer)\s+(?:ii|iii|iv|v|[2-9])\b",
        searchable,
    ):
        return "Experienced role level excluded by selected experience levels"

    required_years = required_experience_years(job_title, job_description)
    if (
        entry_only
        and required_years is not None
        and required_years > ENTRY_LEVEL_REVIEW_MAX_YEARS
    ):
        years = required_years
        return f"Requires {years}+ years of experience"

    title = str(job_title).lower()
    internship_role = any(
        term in title for term in ("intern", "internship", "trainee")
    )
    if internship_role and "Internship" not in preferences.job_types:
        return "Internship roles are excluded by the selected job types"

    return ""


def required_experience_years(
    job_title: str,
    job_description: str,
) -> int | None:
    """Extracts the minimum explicit experience requirement from job text."""
    title = str(job_title or "").lower()
    description = str(job_description or "").lower()
    unit = r"(?:years?|yrs?|yr)"
    separator = r"(?:-|–|—|to)"
    title_patterns = (
        rf"(\d+)\s*{separator}\s*\d+\s*{unit}",
        rf"(\d+)\s*\+\s*{unit}",
        rf"(\d+)\s*{unit}",
        rf"{unit}\s*[:\-]?\s*(\d+)\s*\+?",
    )
    description_patterns = (
        rf"experience\s*(?:required|needed)?\s*[:=\-–—]?\s*(\d+)\s*{separator}\s*\d+\s*{unit}",
        rf"experience\s*(?:required|needed)?\s*[:=\-–—]?\s*(\d+)\s*\+?\s*{unit}",
        rf"(\d+)\s*{separator}\s*\d+\s*{unit}(?:\s+of)?\s+[^.\n]{{0,45}}?experience",
        rf"(\d+)\s*\+\s*{unit}(?:\s+of)?\s+[^.\n]{{0,45}}?experience",
        rf"(?:minimum|min\.?|at\s+least)\s+(?:of\s+)?(\d+)\s*{unit}",
        rf"(\d+)\s*{unit}\s+(?:of\s+)?(?:relevant\s+)?experience",
    )
    values = [
        int(match.group(1))
        for pattern in title_patterns
        for match in re.finditer(pattern, title)
    ]
    values.extend(
        int(match.group(1))
        for pattern in description_patterns
        for match in re.finditer(pattern, description)
    )
    return min(values) if values else None
