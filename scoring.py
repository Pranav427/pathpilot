import re
from typing import Iterable


GENERIC_MATCH_WORDS = {
    "ai",
    "model",
    "models",
    "system",
    "systems",
    "tool",
    "tools",
    "modern",
    "framework",
    "frameworks",
    "learning",
    "data",
    "code",
    "development",
    "programming",
    "proficiency",
    "foundational",
    "understanding",
    "basic",
}


SKILL_ALIASES: dict[str, list[str]] = {
    "oop": ["object oriented programming", "object-oriented programming"],
    "oops": ["oop", "object oriented programming", "object-oriented programming"],
    "object oriented programming": ["oop", "oops", "object-oriented programming"],
    "object-oriented programming": ["oop", "oops", "object oriented programming"],
    "coding": ["python", "java", "c++", "software engineering"],
    "programming": ["python", "java", "c++", "sql"],
    "python coding": ["python", "coding", "python programming"],
    "python programming": ["python", "coding", "programming"],
    "software development": ["software engineering", "coding", "python", "java"],
    "machine learning development": [
        "machine learning",
        "ml",
        "model evaluation",
        "model validation",
        "predictive modeling",
        "scikit learn",
        "scikit-learn",
    ],
    "supervised learning": ["regression", "classification", "predictive modeling"],
    "unsupervised learning": ["clustering"],
    "model training and evaluation": [
        "model evaluation",
        "model validation",
        "regression",
        "classification",
        "clustering",
    ],
    "version control": ["git", "github"],
    "collaboration": ["team collaboration", "communication"],
    "communication": ["communication", "team collaboration"],
    "teamwork": ["team collaboration", "collaboration"],
    "independent work": ["self learning", "self-learning"],
    "independent learning": ["self learning", "self-learning"],
    "eagerness to learn": ["self learning", "continuous learning"],
    "cross functional collaboration": ["team collaboration", "communication"],
    "cross-functional collaboration": ["team collaboration", "communication"],
    "requirements gathering": ["requirements understanding", "technical documentation"],
    "documentation": ["technical documentation"],
    "testing": ["model evaluation", "model validation", "debugging"],
    "analytical aptitude": ["analytical thinking", "statistical analysis", "eda"],
    "nlp": ["natural language processing", "tf idf", "tf-idf", "text classification"],
    "natural language processing": ["nlp", "tf idf", "tf-idf", "text classification"],
    "statistics": ["statistical analysis", "exploratory data analysis"],
    "data handling": [
        "data cleaning",
        "data preprocessing",
        "data analysis",
        "exploratory data analysis",
        "eda",
        "database management",
    ],
    "data visualization": ["tableau", "matplotlib", "seaborn"],
    "computer vision": ["image preprocessing", "image processing"],
    "database": ["database management", "mysql", "relational databases"],
    "databases": ["database management", "mysql", "relational databases"],
    "database knowledge": ["database management", "mysql", "relational databases"],
    "index and query systems": [
        "database indexing and query systems conceptual foundation",
        "database management",
        "relational databases",
    ],
    "linear programming": ["linear programming conceptual foundation"],
    "bachelor's degree": [
        "b tech in computer science and engineering",
        "b.tech in computer science and engineering",
        "b.tech computer science",
        "b tech computer science",
        "btech in computer science and engineering",
    ],
    "bachelor s degree": [
        "b tech in computer science and engineering",
        "b.tech in computer science and engineering",
        "b.tech computer science",
        "b tech computer science",
        "btech in computer science and engineering",
    ],
    "bachelors degree": [
        "b tech in computer science and engineering",
        "b.tech in computer science and engineering",
        "b.tech computer science",
        "b tech computer science",
        "btech in computer science and engineering",
    ],
    "bachelor degree": [
        "b tech in computer science and engineering",
        "b.tech in computer science and engineering",
        "b.tech computer science",
        "b tech computer science",
        "btech in computer science and engineering",
    ],
    "backend": ["backend development", "restful api development"],
    "rest api": ["restful api development", "api integration"],
    "restful api": ["restful api development", "api integration"],
    "sdlc": ["software development life cycle", "software development life cycle sdlc"],
    "software development life cycle": ["sdlc", "software development life cycle sdlc"],
}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9+#. ]+", " ", str(text).lower()).strip()


def flatten_profile_terms(profile: dict) -> set[str]:
    terms = set()

    terms.update(tokenize_phrase(profile.get("objective", "")))

    for items in profile.get("skills", {}).values():
        for item in items:
            terms.add(normalize(item))

    for project in profile.get("projects", []):
        terms.add(normalize(project.get("name", "")))
        terms.add(normalize(project.get("domain", "")))
        for tool in project.get("tools", []):
            terms.add(normalize(tool))
        for highlight in project.get("highlights", []):
            terms.update(tokenize_phrase(highlight))

    for exp in profile.get("experience", []):
        terms.add(normalize(exp.get("title", "")))
        terms.add(normalize(exp.get("company", "")))
        terms.add(normalize(exp.get("type", "")))
        terms.update(tokenize_phrase(exp.get("description", "")))
        for highlight in exp.get("highlights", []):
            terms.update(tokenize_phrase(highlight))

    for cert in profile.get("certifications", []):
        terms.add(normalize(cert))
        terms.update(tokenize_phrase(cert))

    for course in profile.get("courses", []):
        terms.add(normalize(course.get("name", "")))
        terms.add(normalize(course.get("provider", "")))
        terms.update(tokenize_phrase(course.get("description", "")))

    for education in profile.get("education", []):
        terms.add(normalize(education.get("degree", "")))
        terms.add(normalize(education.get("institution", "")))
        terms.update(tokenize_phrase(education.get("degree", "")))
        if re.search(
            r"\b(b\.?\s*tech|btech|bachelor)\b",
            education.get("degree", ""),
            flags=re.IGNORECASE,
        ):
            terms.update(
                {
                    "bachelor degree",
                    "bachelors degree",
                    "bachelor's degree",
                }
            )

    for interest in profile.get("interests", []):
        terms.add(normalize(interest))
        terms.update(tokenize_phrase(interest))

    return {term for term in terms if term}


def tokenize_phrase(text: str) -> set[str]:
    normalized = normalize(text)
    words = {word for word in normalized.split() if len(word) > 2}
    return words | {normalized}


def has_term(candidate_terms: set[str], requirement: str) -> bool:
    req = normalize(requirement)
    if not req:
        return False

    if req in candidate_terms:
        return True

    aliases = SKILL_ALIASES.get(req, [])
    if any(normalize(alias) in candidate_terms for alias in aliases):
        return True

    req_tokens = set(req.split())
    if len(req_tokens) == 1:
        return False

    meaningful_tokens = {
        token for token in req_tokens
        if token not in GENERIC_MATCH_WORDS and len(token) > 2
    }
    if not meaningful_tokens:
        return False

    for term in candidate_terms:
        term_tokens = set(term.split())

        # Strong phrase evidence: requirement appears inside a profile phrase.
        if req in term:
            return True

        term_aliases = SKILL_ALIASES.get(term, [])
        if any(req == normalize(alias) for alias in term_aliases):
            return True

        # Token evidence: all meaningful requirement tokens appear together.
        if meaningful_tokens.issubset(term_tokens):
            return True

    return False


def split_matches(requirements: Iterable[str], candidate_terms: set[str]) -> tuple[list[str], list[str]]:
    matched = []
    missing = []
    for requirement in requirements:
        if has_term(candidate_terms, requirement):
            matched.append(requirement)
        else:
            missing.append(requirement)
    return matched, missing


def coverage_score(matched: list[str], missing: list[str]) -> int:
    total = len(matched) + len(missing)
    if total == 0:
        return 0
    return round((len(matched) / total) * 100)


def fit_verdict(score: int) -> str:
    if score >= 80:
        return "STRONG_MATCH"
    if score >= 65:
        return "MODERATE_MATCH"
    if score >= 45:
        return "STRETCH_MATCH"
    return "NOT_RECOMMENDED"


def fit_verdict_label(score: int) -> str:
    labels = {
        "STRONG_MATCH": "Strong Match",
        "MODERATE_MATCH": "Moderate Match",
        "STRETCH_MATCH": "Stretch Match",
        "NOT_RECOMMENDED": "Not Recommended",
    }
    return labels[fit_verdict(score)]


def fit_guidance(score: int, missing_skills: list[str], missing_tools: list[str]) -> str:
    verdict = fit_verdict(score)
    if verdict == "STRONG_MATCH":
        return "This role is worth prioritizing. Tailor the resume closely and apply."
    if verdict == "MODERATE_MATCH":
        return "This role is realistic. Apply, but address the top gaps clearly."
    if verdict == "STRETCH_MATCH":
        gaps = ", ".join((missing_skills + missing_tools)[:5])
        return (
            "This is a stretch role. Apply only with honest positioning"
            + (f" and be ready to explain gaps: {gaps}." if gaps else ".")
        )
    gaps = ", ".join((missing_skills + missing_tools)[:5])
    return (
        "This role is not recommended right now because too many core requirements are missing"
        + (f": {gaps}." if gaps else ".")
    )


def seniority_penalty(job_analysis: dict) -> tuple[int, str]:
    """Returns a conservative penalty for explicit experienced-hire requirements."""
    searchable = " ".join(
        str(item)
        for field in ("skills", "tools", "keywords")
        for item in job_analysis.get(field, [])
    )
    normalized = normalize(searchable)
    years = [
        int(value)
        for value in re.findall(
            r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b",
            normalized,
        )
    ]
    required_years = max(years, default=0)

    if required_years >= 5:
        return 20, f"Role explicitly requests {required_years}+ years of experience."
    if required_years >= 3:
        return 12, f"Role explicitly requests {required_years}+ years of experience."
    if required_years >= 2:
        return 6, f"Role explicitly requests {required_years}+ years of experience."

    senior_titles = (
        "staff engineer",
        "principal engineer",
        "lead engineer",
        "senior engineer",
        "senior software",
        "senior data",
        "senior machine learning",
    )
    if any(title in normalized for title in senior_titles):
        return 12, "Role is explicitly positioned at senior, lead, staff, or principal level."
    return 0, ""


def calculate_fit_score(job_analysis: dict, profile: dict) -> dict:
    """
    Builds a transparent score that can be shown to users and audited later.
    The LLM can still explain the fit, but this keeps the number grounded.
    """
    candidate_terms = flatten_profile_terms(profile)
    matched_skills, missing_skills = split_matches(job_analysis.get("skills", []), candidate_terms)
    matched_tools, missing_tools = split_matches(job_analysis.get("tools", []), candidate_terms)
    matched_keywords, missing_keywords = split_matches(job_analysis.get("keywords", []), candidate_terms)

    skill_score = coverage_score(matched_skills, missing_skills)
    tool_score = coverage_score(matched_tools, missing_tools)
    keyword_score = coverage_score(matched_keywords, missing_keywords)

    project_bonus = 5 if profile.get("projects") else 0
    education_bonus = 5 if profile.get("education") else 0
    experience_penalty, experience_reason = seniority_penalty(job_analysis)

    final_score = round(
        (skill_score * 0.45)
        + (tool_score * 0.25)
        + (keyword_score * 0.20)
        + project_bonus
        + education_bonus
        - experience_penalty
    )
    final_score = max(0, min(final_score, 100))

    return {
        "match_score": final_score,
        "fit_verdict": fit_verdict(final_score),
        "fit_verdict_label": fit_verdict_label(final_score),
        "fit_guidance": fit_guidance(final_score, missing_skills, missing_tools),
        "score_components": {
            "skills": skill_score,
            "tools": tool_score,
            "ats_keywords": keyword_score,
            "project_evidence_bonus": project_bonus,
            "education_bonus": education_bonus,
            "seniority_penalty": -experience_penalty,
        },
        "seniority_penalty": experience_penalty,
        "seniority_reason": experience_reason,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_tools": matched_tools,
        "missing_tools": missing_tools,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
    }
