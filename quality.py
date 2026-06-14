import os
import re

from scoring import has_term, normalize, tokenize_phrase
from utils import profile_is_graduate


ATS_NOISE_TERMS = {
    "customer obsession",
    "innovation",
    "innovative",
    "software development engineer",
    "sde",
    "equal opportunity employer",
    "fast paced environment",
}


def _contains(text: str, phrase: str) -> bool:
    candidate_terms = _candidate_terms_from_text(text)
    return has_term(candidate_terms, phrase)


def _candidate_terms_from_text(text: str) -> set[str]:
    """Builds searchable evidence terms from generated resume text."""
    normalized_text = normalize(text)
    terms = tokenize_phrase(normalized_text)
    for line in str(text).splitlines():
        normalized_line = normalize(line)
        terms.update(tokenize_phrase(normalized_line))
        words = normalized_line.split()
        for size in (2, 3):
            for index in range(len(words) - size + 1):
                terms.add(" ".join(words[index:index + size]))
    return {term for term in terms if term}


def _resume_text(resume_text) -> str:
    if isinstance(resume_text, str):
        return resume_text
    if not isinstance(resume_text, dict):
        return str(resume_text)

    lines = [resume_text.get("professional_summary", "")]
    lines.extend(resume_text.get("targeted_role_terms", []))
    for skills in resume_text.get("skills", {}).values():
        lines.extend(skills)
    for project in resume_text.get("projects", []):
        lines.append(project.get("name", ""))
        lines.append(project.get("domain", ""))
        lines.extend(project.get("tools", []))
        lines.extend(project.get("bullets", []))
    lines.extend(resume_text.get("certifications", []))
    return "\n".join(lines)


def build_ats_report(resume_text, job_analysis: dict) -> dict:
    resume_text = _resume_text(resume_text)
    priority_terms = (
        list(job_analysis.get("skills", []))
        + list(job_analysis.get("tools", []))
    )
    context_terms = []
    excluded_terms = []
    for term in job_analysis.get("keywords", []):
        normalized = normalize(term)
        if normalized in ATS_NOISE_TERMS:
            excluded_terms.append(term)
        elif re.search(
            r"\b(?:bachelor|master|phd|degree|\d+\s*\+?\s*(?:years?|yrs?))\b",
            normalized,
        ):
            context_terms.append(term)
        else:
            priority_terms.append(term)

    required_terms = priority_terms + context_terms
    seen = set()
    unique_terms = []
    for term in required_terms:
        key = normalize(term)
        if key and key not in seen:
            seen.add(key)
            unique_terms.append(term)

    candidate_terms = _candidate_terms_from_text(resume_text)
    covered = [term for term in unique_terms if has_term(candidate_terms, term)]
    missing = [term for term in unique_terms if term not in covered]
    coverage = round((len(covered) / len(unique_terms)) * 100) if unique_terms else 0

    checks = {
        "has_summary": _contains(resume_text, "summary") or _contains(resume_text, "objective"),
        "has_skills_section": _contains(resume_text, "skills"),
        "has_projects_or_experience": _contains(resume_text, "project") or _contains(resume_text, "experience"),
        "has_education": _contains(resume_text, "education"),
        "reasonable_length": 350 <= len(resume_text.split()) <= 900,
    }

    issues = []
    if coverage < 65:
        issues.append("Keyword coverage is low; add more supported role-specific terms.")
    if not checks["has_skills_section"]:
        issues.append("Resume should include a clear Skills section.")
    if not checks["has_projects_or_experience"]:
        issues.append("Resume should show relevant project or experience evidence.")
    if not checks["reasonable_length"]:
        issues.append("Resume length is outside the recommended one-page range.")

    return {
        "keyword_coverage": coverage,
        "covered_terms": covered,
        "missing_terms": missing,
        "priority_terms": priority_terms,
        "context_terms": context_terms,
        "excluded_terms": excluded_terms,
        "checks": checks,
        "issues": issues,
        "note": (
            "ATS coverage is a keyword signal, not a final application score. "
            "Low coverage can happen when a job page includes generic, noisy, "
            "or process-related terms. Add missing terms only when they are true."
        ),
    }


def _source_text_path(pdf_path: str) -> str:
    root, _ = os.path.splitext(str(pdf_path or ""))
    return root + ".txt" if root else ""


def audit_application_documents(
    resume_path: str,
    cover_letter_path: str,
    profile: dict,
    notes: str = "",
) -> list[str]:
    """Audit saved text sources and flag legacy documents needing review."""
    from cover_letter import (
        cover_letter_format_issues,
        unsupported_confirmed_claims,
        unsupported_profile_claims,
    )

    issues = []
    confirmed_terms = []
    marker = "User-confirmed for this application only:"
    if marker.lower() in str(notes).lower():
        confirmed_text = str(notes).split(":", 1)[-1]
        confirmed_terms = [
            item.strip()
            for item in confirmed_text.split(",")
            if item.strip()
        ]

    resume_text_path = _source_text_path(resume_path)
    cover_text_path = _source_text_path(cover_letter_path)
    resume_text = ""
    cover_text = ""

    if resume_text_path and os.path.exists(resume_text_path):
        with open(resume_text_path, encoding="utf-8") as file:
            resume_text = file.read()
    elif resume_path:
        issues.append("Resume source text is unavailable for factual review.")

    if cover_text_path and os.path.exists(cover_text_path):
        with open(cover_text_path, encoding="utf-8") as file:
            cover_text = file.read()
    elif cover_letter_path:
        issues.append("Cover letter source text is unavailable for factual review.")

    combined = "\n\n".join([resume_text, cover_text])
    if combined:
        if cover_text and unsupported_profile_claims(cover_text):
            issues.append("Known project or internship evidence is mixed incorrectly.")
        if confirmed_terms and unsupported_confirmed_claims(
            combined,
            confirmed_terms,
        ):
            issues.append(
                "Application-only familiarity is presented as project or work experience."
            )
        if profile_is_graduate(profile) and re.search(
            r"\b(final[- ]year|current)\b.{0,45}\bstudent\b"
            r"|\bComputer Science student\b"
            r"|\bengineering student\b",
            combined,
            flags=re.IGNORECASE,
        ):
            issues.append("Candidate status is outdated: graduate described as student.")
        if re.search(
            r"\bproduction[- ]ready\b|\bproduction experience\b",
            combined,
            flags=re.IGNORECASE,
        ):
            issues.append("Production-level experience wording requires manual proof.")

    if resume_text:
        lower_resume = resume_text.lower()
        medical_start = lower_resume.find("medical condition classification")
        if medical_start >= 0:
            section_end_candidates = [
                index for index in (
                    lower_resume.find(
                        "modern security system",
                        medical_start + 1,
                    ),
                    lower_resume.find("certifications", medical_start + 1),
                )
                if index >= 0
            ]
            medical_end = min(section_end_candidates) if section_end_candidates \
                else len(resume_text)
            medical_section = resume_text[medical_start:medical_end]
            if "93.91%" in medical_section or "15,000" in medical_section:
                issues.append(
                    "Medical project contains metrics belonging to the face project."
                )

        for line in resume_text.splitlines():
            lower_line = line.lower()
            internship_context = (
                "internship" in lower_line or "skilldzire" in lower_line
            )
            unsupported_tools = any(
                marker in lower_line
                for marker in (
                    "openai",
                    "gemini",
                    "llm api",
                    "claude api",
                    "prompt engineering",
                    "agentic workflow",
                )
            )
            if internship_context and unsupported_tools:
                issues.append(
                    "Internship line contains unsupported AI implementation claims."
                )
                break

    if cover_text:
        issues.extend(cover_letter_format_issues(cover_text, profile))

    unique = []
    seen = set()
    for issue in issues:
        key = issue.lower()
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique


def display_ats_report(report: dict):
    print("\n" + "=" * 55)
    print("             ATS QUALITY REPORT")
    print("=" * 55)
    print(f"\nKeyword Coverage: {report['keyword_coverage']}/100")

    if report.get("note"):
        print("\nNote:")
        print(f"   {report['note']}")

    if report["missing_terms"]:
        print("\nMissing important terms:")
        for term in report["missing_terms"][:10]:
            print(f"   • {term}")

    if report["issues"]:
        print("\nQuality issues to fix:")
        for issue in report["issues"]:
            print(f"   • {issue}")
    else:
        print("\nNo major ATS issues detected.")

    print("\n" + "=" * 55)
