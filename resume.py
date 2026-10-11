# resume.py

import os
import re
import subprocess

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(path: str = ".env") -> None:
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
from analyzer import analyze_job
from document_standards import UK_ENGLISH_INSTRUCTION, strip_right_to_work_claims
from wording_checks import strip_unsupported_intensifiers
from profile import get_profile
from matcher import match_profile_to_job
from llm_utils import create_json_with_retry, get_llm_client, get_llm_model
from utils import (
    clean_phone,
    clean_url,
    latex_escape,
    normalize_candidate_status,
)

load_dotenv()


def llm_runtime():
    """Returns the configured LLM client and model when generation is requested."""
    return get_llm_client(), get_llm_model()


def clean_resume_style(text: str) -> str:
    """Keeps resume wording plain, truthful, and less AI-polished."""
    cleaned = str(text)
    replacements = {
        "\u2014": ", ",
        "\u2013": "-",
        " -- ": ", ",
        " - ": ", ",
        "recent computer science graduate": "Computer Science graduate",
        "recent B.Tech graduate": "B.Tech graduate",
        "completed multiple data science internships": (
            "completed data science training and practical ML projects"
        ),
        "multiple data science internships": (
            "data science training and practical ML projects"
        ),
        "structured internships": "structured training",
    }
    for old, new in replacements.items():
        cleaned = re.sub(re.escape(old), new, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def sanitize_resume_facts(resume_content: dict, profile: dict) -> dict:
    """Ground generated resume fields in verified profile records."""
    if not isinstance(resume_content, dict):
        return resume_content

    confirmed_terms = {
        str(term).strip().lower()
        for term in profile.get("_application_confirmed_terms", [])
    }
    permanent_skills = profile.get("_permanent_skills", profile.get("skills", {}))
    allowed_skills = {
        str(item).strip().lower()
        for items in permanent_skills.values()
        for item in items
    }

    safe_skills = {}
    for category, items in resume_content.get("skills", {}).items():
        safe_items = []
        for item in items if isinstance(items, list) else []:
            text = str(item).strip()
            base = re.sub(
                r"\s*\(familiarity\)\s*$",
                "",
                text,
                flags=re.IGNORECASE,
            )
            normalized = base.lower()
            if normalized in allowed_skills:
                safe_items.append(base)
            elif normalized in confirmed_terms:
                safe_items.append(f"{base} (familiarity)")
        if safe_items:
            safe_skills[str(category)] = safe_items
    resume_content["skills"] = safe_skills

    profile_projects = {
        project.get("name", "").strip().lower(): project
        for project in profile.get("projects", [])
    }
    safe_projects = []
    for project in resume_content.get("projects", []):
        name = str(project.get("name", "")).strip().lower()
        source = profile_projects.get(name)
        if not source:
            continue

        # Use the generated bullets if they exist, otherwise fall back to source highlights
        gen_bullets = project.get("bullets", [])
        if not gen_bullets or not isinstance(gen_bullets, list):
            gen_bullets = source.get("highlights", [])

        # Validate and clean generated bullets against hallucinated metrics
        safe_bullets = []
        source_highlights = source.get("highlights", [])
        for i, gen_b in enumerate(gen_bullets[:3]):
            gen_b_text = str(gen_b).strip()
            # Extract numbers/percentages
            numbers_in_gen = re.findall(r"\b\d+(?:[\.,]\d+)?%?", gen_b_text)
            
            has_hallucinated_metric = False
            for num in numbers_in_gen:
                # Allow matching numbers present in original highlights
                in_highlights = any(num in str(h) for h in source_highlights)
                if not in_highlights:
                    has_hallucinated_metric = True
                    break
            
            if has_hallucinated_metric or not gen_b_text:
                if i < len(source_highlights):
                    safe_bullets.append(clean_resume_style(source_highlights[i]))
            else:
                safe_bullets.append(
                    strip_unsupported_intensifiers(clean_resume_style(gen_b_text), profile)
                )

        safe_projects.append(
            {
                "name": source.get("name", ""),
                "domain": source.get("domain", ""),
                "tools": list(source.get("tools", [])),
                "bullets": safe_bullets,
            }
        )
    resume_content["projects"] = safe_projects
    resume_content["certifications"] = list(
        profile.get("certifications", [])
    )[:7]

    summary = normalize_candidate_status(
        clean_resume_style(resume_content.get("professional_summary", "")),
        profile,
    )
    summary = strip_right_to_work_claims(summary)
    summary = strip_unsupported_intensifiers(summary, profile)
    
    # Dynamic grounding validation rules from profile projects
    projects_data = []
    for project in profile.get("projects", []):
        name = project.get("name", "")
        domain = project.get("domain", "")
        metrics = project.get("grounding_metrics", [])
        if not metrics:
            continue
        # Extract keywords for the project
        project_keywords = {name.lower(), domain.lower()}
        project_keywords.update(t.lower() for t in project.get("tools", []))
        project_keywords.update(w.lower() for w in re.findall(r"\b\w{3,}\b", name))
        projects_data.append({
            "name": name,
            "metrics": [m.lower() for m in metrics],
            "keywords": project_keywords
        })
        
    safe_sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+", summary):
        lower_sentence = sentence.lower()
        if any(term in lower_sentence for term in confirmed_terms):
            continue
        
        leak_detected = False
        for p_idx, p_current in enumerate(projects_data):
            # Check if this sentence refers to the current project
            has_project_keywords = any(kw in lower_sentence for kw in p_current["keywords"])
            if has_project_keywords:
                # It must NOT contain metrics exclusive to other projects
                for other_idx, p_other in enumerate(projects_data):
                    if p_idx == other_idx:
                        continue
                    exclusive_other_metrics = [
                        m for m in p_other["metrics"] 
                        if m not in p_current["metrics"]
                    ]
                    if any(metric in lower_sentence for metric in exclusive_other_metrics):
                        leak_detected = True
                        break
            if leak_detected:
                break
                
        if leak_detected:
            continue
        safe_sentences.append(sentence)
        
    summary = " ".join(safe_sentences).strip()
    sentence_count = len(
        [
            sentence
            for sentence in re.split(r"(?<=[.!?])\s+", summary)
            if sentence.strip()
        ]
    )
    if len(summary.split()) < 28 or sentence_count < 2:
        summary = grounded_professional_summary(profile)
    resume_content["professional_summary"] = summary

    return resume_content


def _top_skills(profile: dict, limit: int = 4) -> list[str]:
    skills = profile.get("_permanent_skills", profile.get("skills", {})) or {}
    flat: list[str] = []
    for items in skills.values():
        for item in items if isinstance(items, list) else []:
            if str(item).strip() and str(item) not in flat:
                flat.append(str(item).strip())
    return flat[:limit]


def grounded_professional_summary(profile: dict) -> str:
    """Builds a concise personal profile only from durable profile evidence."""
    education = profile.get("education") or []
    first = education[0] if education and isinstance(education[0], dict) else {}
    degree = str(first.get("degree", "")).strip()
    institution = str(first.get("institution", "")).strip()
    skills = _top_skills(profile)
    projects = [
        project.get("name", "")
        for project in (profile.get("projects") or [])[:2]
        if project.get("name")
    ]

    opening = (
        f"{degree} candidate at {institution}" if degree and institution
        else (f"{degree} candidate" if degree else "Motivated early-career candidate")
    )
    sentences = [
        f"{opening} with a strong academic foundation and practical project experience."
    ]
    if skills:
        sentences.append(
            "Skilled in " + ", ".join(skills) + " through verified coursework and projects."
        )
    if projects:
        sentences.append("Project work includes " + " and ".join(projects) + ".")
    return " ".join(sentences)


def generate_application_strategy(job_analysis: dict, profile_summary: str) -> dict:
    """Invokes LLM to define strategic positioning criteria for the candidate before fact selection."""
    prompt = f"""
You are a senior executive recruiter and hiring strategist.
Analyze the target job requirements and define the optimal positioning strategy for this candidate.
Return ONLY valid JSON matching the exact structure below. No explanation. No markdown.

JOB DETAILS:
Summary: {job_analysis.get("summary", "")}
Skills: {job_analysis.get("skills", [])}
Tools: {job_analysis.get("tools", [])}
Keywords: {job_analysis.get("keywords", [])}

CANDIDATE BASE:
{profile_summary}

Return this exact JSON structure:
{{
  "positioning_strategy": "Core theme of the application (1 sentence)",
  "evidence_requirements": "Key projects, metrics, or credentials that must be surfaced as evidence (1 sentence)",
  "company_priorities": ["priority1", "priority2"],
  "interviewer_takeaway": "Key message for hiring managers (1 sentence)",
  "summary_focus": "Specific angle to highlight in professional summary (1 sentence)",
  "project_focus": ["keyword1", "keyword2"],
  "skills_focus": ["keyword1", "keyword2"],
  "what_to_deemphasize": ["topic1", "topic2"]
}}
"""
    client, model = llm_runtime()
    try:
        strategy = create_json_with_retry(
            client,
            model=model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
            required_keys=[
                "positioning_strategy",
                "evidence_requirements",
                "company_priorities",
                "interviewer_takeaway",
                "summary_focus",
                "project_focus",
                "skills_focus",
                "what_to_deemphasize"
            ],
            source="Strategy generation"
        )
        return strategy
    except Exception:
        # Fallback empty strategy
        return {
            "positioning_strategy": "Highlight core software engineering skills.",
            "evidence_requirements": "Focus on python engineering highlights and core project experience.",
            "company_priorities": [],
            "interviewer_takeaway": "Motivated engineer capable of scaling software.",
            "summary_focus": "Software development foundation.",
            "project_focus": [],
            "skills_focus": [],
            "what_to_deemphasize": []
        }


def get_matching_fact_manifest(profile: dict, job_analysis: dict, match: dict, strategy: dict = None) -> dict:
    """Deterministically filters and selects relevant profile nodes to build a factual resume manifest."""
    # 1. Select matching skills & tools
    matched_skills = set(str(s).lower() for s in match.get("matched_skills", []))
    matched_tools = set(str(t).lower() for t in match.get("matched_tools", []))
    matched_keywords = set(str(k).lower() for k in match.get("matched_keywords", []))
    all_matched = matched_skills.union(matched_tools).union(matched_keywords)

    if strategy and strategy.get("skills_focus"):
        for focus in strategy["skills_focus"]:
            all_matched.add(str(focus).lower())

    profile_skills = profile.get("skills", {})
    manifest_skills = {}
    
    # Extract only matching or top skills per category to keep it highly tailored
    for category, skills in profile_skills.items():
        cat_matches = []
        cat_others = []
        for skill in skills:
            clean_s = re.sub(r"\s*\(familiarity\)\s*$", "", str(skill).strip(), flags=re.IGNORECASE)
            if clean_s.lower() in all_matched:
                cat_matches.append(clean_s)
            else:
                cat_others.append(clean_s)
        # Prioritize matches, then fill up to 6 per category
        combined = cat_matches + cat_others
        if combined:
            manifest_skills[category] = combined[:6]

    # 2. Score and select top 2 projects
    projects = profile.get("projects", [])
    scored_projects = []
    for proj in projects:
        score = 0
        name = proj.get("name", "").lower()
        domain = proj.get("domain", "").lower()
        
        # Match keywords against name, domain, and highlights
        for term in all_matched:
            if term in name or term in domain:
                score += 3
            for h in proj.get("highlights", []):
                if term in h.lower():
                    score += 1
            for t in proj.get("tools", []):
                if term in t.lower():
                    score += 2
        
        # Strategic project alignment boosts
        if strategy and strategy.get("project_focus"):
            for keyword in strategy["project_focus"]:
                keyword_clean = str(keyword).lower()
                if keyword_clean in name or keyword_clean in domain or keyword_clean in proj.get("description", "").lower():
                    score += 10
                for h in proj.get("highlights", []):
                    if keyword_clean in h.lower():
                        score += 5
                        
        scored_projects.append((score, proj))
    
    # Sort descending by score
    scored_projects.sort(key=lambda x: x[0], reverse=True)
    selected_projects = [item[1] for item in scored_projects[:2]]

    # 3. Filter Experience/Jobs (limit to top 3 relevant)
    experience = profile.get("experience", [])
    selected_experience = []
    for exp in experience:
        score = 0
        title = exp.get("title", "").lower()
        company = exp.get("company", "").lower()
        for term in all_matched:
            if term in title or term in company:
                score += 3
            for h in exp.get("highlights", []):
                if term in h.lower():
                    score += 1
        selected_experience.append((score, exp))
    selected_experience.sort(key=lambda x: x[0], reverse=True)
    manifest_experience = [item[1] for item in selected_experience[:3]]

    # 4. Education
    manifest_education = profile.get("education", [])[:2]

    # 5. Certifications (Filter matching or top 4)
    certs = profile.get("certifications", [])
    selected_certs = []
    for c in certs:
        is_match = any(term in c.lower() for term in all_matched)
        selected_certs.append((1 if is_match else 0, c))
    selected_certs.sort(key=lambda x: x[0], reverse=True)
    manifest_certs = [item[1] for item in selected_certs[:4]]

    return {
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "linkedin": profile.get("linkedin", ""),
        "github": profile.get("github", ""),
        "portfolio": profile.get("portfolio", ""),
        "location": profile.get("location", ""),
        "skills": manifest_skills,
        "projects": selected_projects,
        "experience": manifest_experience,
        "education": manifest_education,
        "certifications": manifest_certs,
    }


def generate_resume(job_analysis: dict, profile: dict, match: dict, strategy: dict = None) -> dict:
    """Generates structured tailored resume content via Claude API."""

    if strategy is None:
        profile_summary = grounded_professional_summary(profile)
        strategy = generate_application_strategy(job_analysis, profile_summary)
    if not isinstance(strategy, dict) or "positioning_strategy" not in strategy:
        strategy = {
            "positioning_strategy": "Highlight core software engineering skills.",
            "company_priorities": [],
            "interviewer_takeaway": "Motivated engineer capable of scaling software.",
            "summary_focus": "Software development foundation.",
            "project_focus": [],
            "skills_focus": [],
            "what_to_deemphasize": []
        }
    manifest = get_matching_fact_manifest(profile, job_analysis, match, strategy)
    
    experience_text = (
        manifest["experience"] if manifest["experience"]
        else "Early-career candidate; evidence comes from education, projects and achievements"
    )

    prompt = f"""
You are a senior recruiter and professional CV writer for UK graduate and early-career applications.
Create clear, truthful, ATS-friendly CV content for this candidate aligned with the target APPLICATION STRATEGY.
{UK_ENGLISH_INSTRUCTION}
Return ONLY valid JSON. No markdown. No explanation.

APPLICATION STRATEGY:
Positioning: {strategy["positioning_strategy"]}
Evidence Requirements: {strategy.get("evidence_requirements", "")}
Interviewer Takeaway: {strategy["interviewer_takeaway"]}
Summary Focus: {strategy["summary_focus"]}
What to De-emphasize: {strategy["what_to_deemphasize"]}

JOB REQUIREMENTS:
Skills: {job_analysis["skills"]}
Tools: {job_analysis["tools"]}
Keywords: {job_analysis["keywords"]}
Summary: {job_analysis["summary"]}

CANDIDATE (FACT MANIFEST):
Name: {manifest["name"]}
Skills: {manifest["skills"]}
User-confirmed familiarity for this application only: {profile.get("_application_confirmed_terms", [])}
User-provided evidence/details for confirmed terms: {profile.get("_application_confirmed_details", {})}
Experience: {experience_text}
Projects: {manifest["projects"]}
Education: {manifest["education"]}
Certifications: {manifest["certifications"]}
Achievements: {profile.get("achievements", [])}

MATCH:
Matched Skills: {match["matched_skills"]}
Strongest Points: {match["strongest_points"]}

Return this exact JSON structure:
{{
  "professional_summary": "2-3 sentences. A personal profile that states the candidate's degree and institution (and grade only if it appears in Education), then their strongest verified strengths for THIS role. No first-person pronouns, NO name, NO contact info.",
  "skills": {{
    "Category name relevant to the candidate and role": ["skill from the candidate's verified skills"]
  }},
  "projects": [
    {{
      "name": "Exact project name from candidate profile",
      "domain": "Project domain",
      "tools": ["tool1", "tool2"],
      "bullets": [
        "Each bullet follows: [Action Verb] + [what was done and how] + [tools or methods used] + [outcome, only if it appears in the profile]. 20-35 words."
      ]
    }}
  ],
  "certifications": ["cert1", "cert2"],
  "ats_notes": ["note1"]
}}

STRICT RULES:
- Do NOT invent employers, jobs, grades, modules or work experience.
- Use ONLY facts from the candidate profile. Never invent metrics, tools or projects.
- Skill categories must fit the candidate's own field (e.g. Technical, Software, Analysis, Languages, Tools, Research, Communication); do not assume a technology role.
- Write bullets with strong active verbs (Designed, Led, Analysed, Built, Coordinated, Evaluated) rather than passive wording.
- You MUST describe the projects provided in the manifest (up to 2). Never return an empty projects list; if the field is not technical, describe the transferable methods and skills used.
- Each bullet is 20-35 words and structurally different from the others.
- The summary is exactly 2-3 sentences with no first-person pronouns.
- User-confirmed familiarity terms belong in Skills (labelled as familiarity). You may mention them in the summary or project highlights ONLY if framed as self-study, academic coursework or academic project work, never as professional experience.
- Avoid empty buzzwords ("passionate", "results-driven", "cutting-edge", "team player", "highly analytical", "proven ability").
- The JOB REQUIREMENTS describe the employer's needs, NOT facts about the candidate. Never copy a requirement into the CV as a claim.
- NEVER state or imply right to work, visa, sponsorship or immigration status. That is added only by the user.
- Project and experience bullets may only restate what the profile highlights say. Do not add tools, activities, outputs or intensifiers (advanced, extensive, complex, strong) that are not in the profile.
"""

    client, model = llm_runtime()
    result = create_json_with_retry(
        client,
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
        required_keys=[
            "professional_summary",
            "skills",
            "projects",
            "certifications",
            "ats_notes",
        ],
        source="Resume generation",
    )
    return sanitize_resume_facts(result, profile)


def resume_to_text(resume_content, profile: dict = None) -> str:
    """Converts structured resume content into readable text."""
    if isinstance(resume_content, str):
        return resume_content

    lines = []
    if profile:
        name = profile.get("name", "").strip()
        email = profile.get("email", "").strip()
        phone = profile.get("phone", "").strip()
        linkedin = clean_url(profile.get("linkedin", ""))
        github = clean_url(profile.get("github", ""))
        portfolio = clean_url(profile.get("portfolio", ""))
        
        contact_info = []
        location = profile.get("location", "").strip()
        if location: contact_info.append(location)
        if email: contact_info.append(email)
        if phone: contact_info.append(phone)
        if linkedin: contact_info.append(linkedin)
        if github: contact_info.append(github)
        if portfolio: contact_info.append(portfolio)
        
        if name:
            lines.append(name.upper())
        if contact_info:
            lines.append(" | ".join(contact_info))
        if profile.get("show_right_to_work") and str(profile.get("right_to_work", "")).strip():
            lines.append(str(profile["right_to_work"]).strip())
        if name or contact_info:
            lines.extend(["", ""])

    # 1. Professional Summary
    lines.extend([
        "PERSONAL PROFILE",
        resume_content.get("professional_summary", ""),
        "",
    ])

    # 2. Education (Extracted from profile)
    if profile and profile.get("education"):
        lines.append("EDUCATION")
        for edu in profile.get("education", []):
            if isinstance(edu, dict):
                degree = edu.get("degree", "").strip()
                inst = edu.get("institution", "").strip()
                year = edu.get("year", "").strip()
                grade = edu.get("grade", "").strip()
                lines.append(f"• {degree} — {inst} ({year})")
                if grade:
                    lines.append(f"  Grade: {grade}")
            else:
                lines.append(f"• {str(edu).strip()}")
        lines.append("")

    # 3. Experience (if any in profile)
    if profile and profile.get("experience"):
        lines.append("EXPERIENCE")
        for exp in profile.get("experience", []):
            if isinstance(exp, dict):
                title = exp.get("title", "").strip()
                company = exp.get("company", "").strip()
                duration = exp.get("duration", "").strip()
                lines.append(f"• {title} at {company} ({duration})")
                for highlight in exp.get("highlights", []):
                    lines.append(f"  - {highlight.strip()}")
            else:
                lines.append(f"• {str(exp).strip()}")
        lines.append("")

    # 4. Projects (tailored bullets)
    lines.append("PROJECTS")
    for project in resume_content.get("projects", []):
        if isinstance(project, dict):
            pname = project.get("name", "Project").strip()
            domain = project.get("domain", "").strip()
            tools = project.get("tools", [])
            
            header = pname
            if domain:
                header += f" ({domain})"
            lines.append(f"• {header}")
            if tools:
                lines.append(f"  Tools: {', '.join(tools)}")
            for bullet in project.get("bullets", []):
                lines.append(f"  - {bullet.strip()}")
        else:
            lines.append(f"• {str(project).strip()}")
    lines.append("")

    # 5. Skills
    lines.append("SKILLS")
    for category, skills in resume_content.get("skills", {}).items():
        # Clean up '(familiarity)' labels for a cleaner plain text resume
        clean_skills = [
            re.sub(r"\s*\(familiarity\)\s*$", "", s, flags=re.IGNORECASE)
            for s in skills
        ]
        lines.append(f"• {category}: {', '.join(clean_skills)}")
    lines.append("")

    # 6. Courses (from profile)
    if profile and profile.get("courses"):
        lines.append("COURSES")
        for course in profile.get("courses", []):
            if isinstance(course, dict):
                cname = course.get("name", "").strip()
                provider = course.get("provider", "").strip()
                desc = course.get("description", "").strip()
                lines.append(f"• {cname} — {provider}")
                if desc:
                    lines.append(f"  {desc}")
            else:
                lines.append(f"• {str(course).strip()}")
        lines.append("")

    # 7. Publications (if any in profile)
    if profile and profile.get("publications"):
        lines.append("PUBLICATIONS")
        for pub in profile.get("publications", []):
            if isinstance(pub, dict):
                title = pub.get("title", "").strip()
                conf = pub.get("conference", pub.get("publisher", "")).strip()
                year = pub.get("year", "").strip()
                lines.append(f"• \"{title}\" — Published in {conf} ({year})")
            else:
                lines.append(f"• {str(pub).strip()}")
        lines.append("")

    # 8. Languages (only when the profile has them)
    languages = [str(l).strip() for l in (profile or {}).get("languages", []) if str(l).strip()]
    if languages:
        lines.append("LANGUAGES")
        lines.append(", ".join(languages))
        lines.append("")

    # 9. Achievements (from the profile only)
    achievements = [str(a).strip() for a in (profile or {}).get("achievements", []) if str(a).strip()][:4]
    if achievements:
        lines.append("ACHIEVEMENTS")
        for achievement in achievements:
            lines.append(f"• {achievement}")
        lines.append("")

    # 10. Certifications (only when present)
    certifications = [str(c).strip() for c in resume_content.get("certifications", []) if str(c).strip()]
    if certifications:
        lines.append("CERTIFICATIONS")
        for cert in certifications:
            lines.append(f"• {cert}")

    return "\n".join(line for line in lines if line is not None)


def esc(text: str) -> str:
    """Escape LaTeX special characters safely."""
    return latex_escape(text)


def sanitize_summary(summary: str, profile: dict) -> str:
    """Removes accidental contact details from the summary."""
    blocked = [
        profile.get("email", ""), profile.get("phone", ""),
        profile.get("linkedin", ""), profile.get("github", ""),
        "email:", "phone:", "linkedin:", "github:",
    ]
    cleaned = str(summary).replace("\n", " ").strip()
    cleaned = normalize_candidate_status(clean_resume_style(cleaned), profile)
    if any(item and item.lower() in cleaned.lower() for item in blocked):
        return grounded_professional_summary(profile)
    return cleaned


def first_sentence(text: str) -> str:
    text = str(text).strip()
    parts = text.split(". ")
    if len(parts) <= 1:
        return text
    return parts[0].strip() + "."


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _tex_bullets(items: list[str], limit: int) -> str:
    lines = "".join(
        f"  \\item\\small {esc(clean_resume_style(item))}\n"
        for item in items[:limit]
        if str(item).strip()
    )
    if not lines:
        return ""
    return (
        "\\begin{itemize}[leftmargin=1.2em, topsep=1pt, itemsep=0pt, parsep=0pt]\n"
        f"{lines}\\end{{itemize}}\n"
    )


def _tex_entry(left_title: str, left_sub: str, right_top: str, right_sub: str = "") -> str:
    """Two-column entry: title/subtitle on the left, date/detail on the right."""
    right = f"\\textbf{{{right_top}}}" if right_top else ""
    if right_sub:
        right += f"\\\\{right_sub}"
    sub = f"\\\\\\textit{{{left_sub}}}" if left_sub else ""
    return (
        "\\vspace{2pt}\n"
        "\\noindent\\begin{minipage}[t]{0.68\\linewidth}\n"
        f"  \\textbf{{{left_title}}}{sub}\n"
        "\\end{minipage}%\n"
        "\\begin{minipage}[t]{0.32\\linewidth}\n"
        f"  \\raggedleft\\small {right}\n"
        "\\end{minipage}\n"
    )


def build_latex_resume(
    profile: dict,
    job_analysis: dict,
    match: dict,
    resume_content
) -> str:
    """Builds a UK-style CV (A4, one page by default, two when content warrants)."""

    # ── Header ────────────────────────────────────────────────
    name = esc(profile.get("name", ""))
    email = profile.get("email", "")
    phone = esc(clean_phone(profile.get("phone", "")))
    location = esc(profile.get("location", ""))
    linkedin = clean_url(profile.get("linkedin", ""))
    github = clean_url(profile.get("github", ""))
    portfolio = clean_url(profile.get("portfolio", ""))

    header_parts = []
    if location:
        header_parts.append(location)
    if phone:
        header_parts.append(phone)
    if email:
        header_parts.append(f"\\href{{mailto:{email}}}{{{esc(email)}}}")
    for link in (linkedin, github, portfolio):
        if link:
            header_parts.append(f"\\href{{https://{link}}}{{{esc(link)}}}")
    separator = "\\hspace{3pt}\\textbar\\hspace{3pt}"
    header_line = separator.join(header_parts)

    right_to_work = ""
    if profile.get("show_right_to_work") and str(profile.get("right_to_work", "")).strip():
        right_to_work = f"\\\\[1pt]\\small {esc(str(profile['right_to_work']).strip())}"

    # ── Fallback if resume_content is not a dict ──────────────
    if not isinstance(resume_content, dict):
        resume_content = {
            "professional_summary": grounded_professional_summary(profile),
            "skills": profile.get("skills", {}),
            "projects": [],
            "certifications": profile.get("certifications", []),
            "ats_notes": [],
        }

    summary = esc(
        sanitize_summary(resume_content.get("professional_summary", ""), profile)
    )

    sections = []

    sections.append(f"\\section{{Personal Profile}}\n\\small\n{summary}\n")

    # ── Education (first for students and graduates) ──────────
    education_tex = ""
    for edu in _as_list(profile.get("education"))[:3]:
        if not isinstance(edu, dict):
            education_tex += f"\\noindent\\small {esc(str(edu))}\\\\\n"
            continue
        year = esc(
            str(edu.get("year", "")).replace("\u2013", "--").replace("\u2014", "--")
        )
        education_tex += _tex_entry(
            esc(edu.get("degree", "")),
            esc(edu.get("institution", "")),
            year,
            esc(edu.get("grade", "")),
        )
        modules = [str(m) for m in _as_list(edu.get("modules")) if str(m).strip()]
        if modules:
            education_tex += (
                f"\\noindent\\small\\textit{{Relevant modules:}} {esc(', '.join(modules[:8]))}\\\\\n"
            )
    if education_tex:
        sections.append(f"\\section{{Education}}\n\\small\n{education_tex}")

    # ── Experience ────────────────────────────────────────────
    experience_tex = ""
    for exp in _as_list(profile.get("experience"))[:4]:
        if not isinstance(exp, dict):
            continue
        experience_tex += _tex_entry(
            esc(exp.get("title", "")),
            esc(exp.get("company", "")),
            esc(exp.get("duration", "")),
        )
        experience_tex += _tex_bullets(_as_list(exp.get("highlights")), 3)
    if experience_tex:
        sections.append(f"\\section{{Experience}}\n\\small\n{experience_tex}")

    # ── Projects ──────────────────────────────────────────────
    projects_tex = ""
    rendered_projects = resume_content.get("projects") or profile.get("projects", [])
    for proj in _as_list(rendered_projects)[:3]:
        if not isinstance(proj, dict):
            continue
        tools = esc(", ".join(_as_list(proj.get("tools"))))
        domain = esc(proj.get("domain", ""))
        meta = " \\textbar{} ".join(
            part for part in (domain, f"Tools: {tools}" if tools else "") if part
        )
        projects_tex += f"\\vspace{{2pt}}\n\\noindent\\textbf{{{esc(proj.get('name', ''))}}}"
        if meta:
            projects_tex += f"\\\\\\small\\textit{{{meta}}}"
        projects_tex += "\n"
        projects_tex += _tex_bullets(
            _as_list(proj.get("bullets") or proj.get("highlights")), 3
        )
    if projects_tex:
        sections.append(f"\\section{{Projects}}\n\\small\n{projects_tex}")

    # ── Skills: any categories, matched terms first ───────────
    matched_norm = {
        str(term).lower()
        for term in (
            list(match.get("matched_skills", []))
            + list(match.get("matched_tools", []))
            + list(match.get("matched_keywords", []))
        )
    }
    skills_source = resume_content.get("skills") or profile.get("skills", {})
    skill_rows = []
    for category, items in (skills_source or {}).items():
        items = [
            re.sub(r"\s*\(familiarity\)\s*$", "", str(i), flags=re.IGNORECASE)
            for i in _as_list(items)
        ]
        ordered = [i for i in items if i.lower() in matched_norm] + [
            i for i in items if i.lower() not in matched_norm
        ]
        unique = list(dict.fromkeys(ordered))[:8]
        if unique:
            skill_rows.append(
                f"\\noindent\\textbf{{{esc(str(category))}:}} {esc(', '.join(unique))}"
            )
    if skill_rows:
        sections.append(
            "\\section{Skills}\n\\small\n" + "\\\\[1pt]\n".join(skill_rows) + "\n"
        )

    # ── Languages (only when the profile has them) ────────────
    languages = [str(l) for l in _as_list(profile.get("languages")) if str(l).strip()]
    if languages:
        sections.append(
            f"\\section{{Languages}}\n\\small\n{esc(', '.join(languages))}\n"
        )

    # ── Certifications ────────────────────────────────────────
    certs = list(dict.fromkeys(
        clean_resume_style(c) for c in _as_list(profile.get("certifications"))[:5]
        if str(c).strip()
    ))
    if certs:
        sections.append(
            "\\section{Certifications}\n\\small\n"
            + " \\\\\n".join(f"\\noindent\\textbullet\\ {esc(c)}" for c in certs)
            + "\n"
        )

    # ── Achievements (from the profile only) ──────────────────
    achievements = [
        str(a).strip() for a in _as_list(profile.get("achievements")) if str(a).strip()
    ][:4]
    if achievements:
        sections.append(
            "\\section{Achievements}\n\\small\n"
            + " \\\\\n".join(f"\\noindent\\textbullet\\ {esc(a)}" for a in achievements)
            + "\n"
        )

    preamble = r"""\documentclass[10pt, a4paper]{article}

% ---- Packages ----
\usepackage[
  top    = 0.55in,
  bottom = 0.55in,
  left   = 0.65in,
  right  = 0.65in
]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[dvipsnames,svgnames,x11names]{xcolor}
\usepackage[T1]{fontenc}
\usepackage{microtype}

% Prevent hyphenation
\tolerance=1
\emergencystretch=\maxdimen
\hyphenpenalty=10000
\hbadness=10000

% ---- Page style ----
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}

% ---- Section style: bold + UPPERCASE + rule ----
\titleformat{\section}
  {\normalsize\bfseries}
  {}{0em}{\MakeUppercase}
  [{\color{black}\rule{\linewidth}{0.5pt}}]
\titlespacing{\section}{0pt}{6pt}{2pt}

% ---- Spacing ----
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}

\begin{document}
"""
    header = (
        "\n% ===== HEADER =====\n"
        "\\begin{center}\n"
        f"  {{\\Large\\textbf{{{name}}}}}\\\\[3pt]\n"
        f"  \\small {header_line}{right_to_work}\n"
        "\\end{center}\n\n\\vspace{-4pt}\n\n"
    )
    return preamble + header + "\n".join(sections) + "\n\\end{document}\n"


def compile_to_pdf(latex: str, output_path: str) -> bool:
    """Compiles LaTeX to PDF. Returns True if successful."""
    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    tex_path = output_path.replace(".pdf", ".tex")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)

    try:
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode",
                 f"-output-directory={output_dir}", tex_path],
                capture_output=True, text=True, timeout=60
            )

        for ext in [".tex", ".aux", ".log", ".out"]:
            try:
                os.remove(output_path.replace(".pdf", ext))
            except FileNotFoundError:
                pass

        if result.returncode == 0:
            print(f"✅ Resume PDF saved → {output_path}")
            return True
        else:
            print("❌ Compilation failed:")
            for line in result.stdout.split("\n"):
                if line.startswith("!"):
                    print(" ", line)
            return False

    except subprocess.TimeoutExpired:
        print("❌ Timed out")
        return False
    except FileNotFoundError:
        print("❌ pdflatex not found")
        print("   Fix: eval \"$(/usr/libexec/path_helper)\"")
        return False


def save_resume(
    resume_text,
    filename: str = "outputs/tailored_resume.txt"
):
    """Saves plain text backup."""
    output_dir = os.path.dirname(filename) or "."
    os.makedirs(output_dir, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(resume_to_text(resume_text))
    print(f"✅ Resume text saved → {filename}")


def display_resume(resume_text):
    """Prints resume in terminal."""
    print("\n" + "="*55)
    print("           TAILORED RESUME")
    print("="*55)
    print(resume_to_text(resume_text))
    print("="*55)


def optimize_resume_bullet(bullet: str) -> dict:
    """Uses LLM to generate 3 high-impact, metrics-driven professional bullet points based on a draft bullet, 
    with structural placeholders and clarifying questions to avoid metrics fabrication.
    """
    if not bullet.strip():
        return {"suggestions": [], "clarifying_questions": []}
    
    prompt = f"""You are a senior professional resume writer and career coach.
Review the following draft resume bullet point or experience description:
"{bullet}"

Task:
1. Generate exactly 3 optimized, high-impact, action-oriented bullet points for a professional resume.
2. Under no circumstances should you fabricate or invent specific numbers, percentages, team sizes, dollar amounts, or business results.
3. If you want to show how a metric fits into the bullet structure, you MUST use brackets/placeholders like "[X]%" or "[number]".
   For example: "Optimized backend API response time by [X]% by implementing Redis caching."
4. Generate 2-3 target clarifying questions that will help the candidate recall their actual achievements or metrics for this specific bullet (e.g. "How many daily active users supported?", "What was the estimated decrease in database load?").

Respond ONLY with a JSON object containing keys "suggestions" and "clarifying_questions". E.g.:
{{
  "suggestions": [
    "bullet suggestion 1 with placeholders",
    "bullet suggestion 2 with placeholders",
    "bullet suggestion 3 with placeholders"
  ],
  "clarifying_questions": [
    "Clarifying question 1",
    "Clarifying question 2"
  ]
}}
"""
    client, model = llm_runtime()
    result = create_json_with_retry(
        client,
        model=model,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
        required_keys=["suggestions", "clarifying_questions"],
        source="Bullet optimization",
    )
    return result


if __name__ == "__main__":

    sample_job = """
    Data Science Intern -- Python, pandas, NumPy,
    scikit-learn, SQL, machine learning, statistics,
    data visualization, EDA.
    """

    print("Step 1: Analyzing job...")
    job_analysis = analyze_job(sample_job)
    print("✅ Done")

    print("Step 2: Loading profile...")
    profile = get_profile()
    print("✅ Done")

    print("Step 3: Matching...")
    match = match_profile_to_job(job_analysis, profile)
    print("✅ Done")

    print("Step 4: Generating content...")
    resume_content = generate_resume(job_analysis, profile, match)
    print("✅ Done")

    print("Step 5: Building PDF...")
    latex = build_latex_resume(
        profile=profile,
        job_analysis=job_analysis,
        match=match,
        resume_content=resume_content
    )
    compile_to_pdf(latex, "outputs/resume_test.pdf")

    display_resume(resume_content)
    save_resume(resume_content)

    print("\n🎉 Open: open outputs/resume_test.pdf")
