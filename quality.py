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
    "john doe",
    "johndoe",
}

ATS_CONTEXT_ONLY_TERMS = {
    "6 months",
    "analytical mindset",
    "artificial intelligence",
    "aerospace",
    "b tech",
    "b.tech",
    "bachelor s degree",
    "bachelor's degree",
    "computer science",
    "data engineering",
    "data science",
    "digital engineering",
    "full time internship",
    "full-time internship",
    "innovation centre",
    "innovation center",
    "mathematics",
    "ml applications",
    "m.eng",
    "m.eng.",
    "m.sc",
    "m.sc.",
    "meng",
    "msc",
    "permanent",
    "production grade",
    "production-grade",
    "professional",
    "remote",
    "verbal communication",
    "written communication",
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


def _is_context_only_term(term: str) -> bool:
    normalized = normalize(term)
    compact = normalized.replace(".", "")
    return normalized in ATS_CONTEXT_ONLY_TERMS or compact in ATS_CONTEXT_ONLY_TERMS


def _is_redundant_missing_term(term: str, covered_terms: list[str]) -> bool:
    normalized_term = normalize(term)
    if not normalized_term:
        return False

    for covered in covered_terms:
        normalized_covered = normalize(covered)
        if normalized_covered and normalized_covered in normalized_term:
            return True
    return False


def build_ats_report(resume_text, job_analysis: dict) -> dict:
    resume_text = _resume_text(resume_text)
    priority_terms = []
    context_terms = []
    excluded_terms = []
    for term in (
        list(job_analysis.get("skills", []))
        + list(job_analysis.get("tools", []))
    ):
        normalized = normalize(term)
        if normalized in ATS_NOISE_TERMS:
            excluded_terms.append(term)
        else:
            priority_terms.append(term)

    for term in job_analysis.get("keywords", []):
        normalized = normalize(term)
        if normalized in ATS_NOISE_TERMS:
            excluded_terms.append(term)
        elif _is_context_only_term(term):
            context_terms.append(term)
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
    priority_keys = {normalize(term) for term in priority_terms}
    missing = [
        term for term in unique_terms
        if (
            normalize(term) in priority_keys
            and term not in covered
            and not _is_redundant_missing_term(term, covered)
        )
    ]
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
        if cover_text and unsupported_profile_claims(cover_text, profile=profile):
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

    # Dynamic resume project section validations
    if resume_text and profile.get("projects"):
        lower_resume = resume_text.lower()
        
        projects_data = []
        for project in profile.get("projects", []):
            name = project.get("name", "").strip()
            metrics = project.get("grounding_metrics", [])
            if not metrics:
                continue
            projects_data.append({
                "name": name,
                "name_lower": name.lower(),
                "metrics": [m.lower() for m in metrics]
            })
            
        for idx, current_p in enumerate(projects_data):
            p_start = lower_resume.find(current_p["name_lower"])
            if p_start >= 0:
                section_ends = [
                    lower_resume.find("certifications"), 
                    lower_resume.find("education"),
                    lower_resume.find("experience")
                ]
                for other_p in projects_data:
                    if other_p["name_lower"] != current_p["name_lower"]:
                        other_start = lower_resume.find(other_p["name_lower"])
                        if other_start > p_start:
                            section_ends.append(other_start)
                valid_ends = [end for end in section_ends if end > p_start]
                p_end = min(valid_ends) if valid_ends else len(lower_resume)
                
                project_section = lower_resume[p_start:p_end]
                
                for other_idx, other_p in enumerate(projects_data):
                    if idx == other_idx:
                        continue
                    exclusive_other_metrics = [
                        m for m in other_p["metrics"] 
                        if m not in current_p["metrics"]
                    ]
                    for metric in exclusive_other_metrics:
                        if metric in project_section:
                            issues.append(
                                f"Project '{current_p['name']}' contains metrics belonging to another project."
                            )
                            break

    # Dynamic resume experience section validations
    if resume_text and profile.get("experience"):
        experience_data = []
        for exp in profile.get("experience", []):
            company = exp.get("company", "").lower()
            title = exp.get("title", "").lower()
            exp_text = (exp.get("description", "") + " " + " ".join(exp.get("highlights", []))).lower()
            restricted_tools = [
                "openai", "gemini", "llm api", "claude api", 
                "prompt engineering", "agentic workflow", "agentic ai",
                "rag", "production grade", "production-grade"
            ]
            experience_data.append({
                "company": company,
                "title": title,
                "restricted_terms": [t for t in restricted_tools if t not in exp_text]
            })

        for line in resume_text.splitlines():
            lower_line = line.lower()
            exp_leak_detected = False
            for exp in experience_data:
                if not exp["company"]:
                    continue
                is_matching_exp = (
                    exp["company"] in lower_line 
                    or (len(exp["title"]) > 5 and exp["title"] in lower_line)
                    or ("internship" in lower_line and exp["company"] in lower_line)
                )
                if is_matching_exp:
                    if any(term in lower_line for term in exp["restricted_terms"]):
                        issues.append(
                            f"Experience line at '{exp['company'].title()}' contains unsupported tool claims."
                        )
                        exp_leak_detected = True
                        break
            if exp_leak_detected:
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
