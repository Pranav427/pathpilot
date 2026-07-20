"""Reusable PathPilot application workflow for CLI and future UI clients."""

import os
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import uuid4

from analyzer import analyze_job
from cover_letter import (
    build_latex_coverletter,
    compile_to_pdf as compile_letter,
    generate_cover_letter,
    save_cover_letter,
)
from matcher import match_profile_to_job
from job_fetcher import clean_company, normalize_url
from profile import get_profile
from quality import build_ats_report
from resume import (
    build_latex_resume,
    compile_to_pdf as compile_resume,
    generate_resume,
    resume_to_text,
    save_resume,
)
from tracker import record_application
from utils import clean_filename


MIN_JD_WORDS = 50
PLACEHOLDER_IDENTITY_VALUES = {
    "company",
    "company name",
    "employer",
    "role",
    "job",
    "job title",
    "unknown",
}


@dataclass
class ApplicationDraft:
    company_name: str
    job_title: str
    source_url: str
    job_analysis: dict
    profile: dict
    match: dict
    resume: dict
    cover_letter: str
    ats_report: dict
    recruiter_message: str = ""
    application_checklist: list[str] = field(default_factory=list)
    match_explanation: str = ""


@dataclass
class SavedApplication:
    resume_pdf: str
    cover_letter_pdf: str
    application_id: int


def unique_items(items: list[str]) -> list[str]:
    """Returns non-empty strings while preserving order."""
    unique = []
    seen = set()
    for item in items:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            unique.append(text)
    return unique


def validate_job_description(job_description: str) -> None:
    """Raises ValueError when a job description is too short."""
    word_count = len(str(job_description).split())
    if word_count < MIN_JD_WORDS:
        raise ValueError(
            f"Job description seems too short ({word_count} words). "
            "Please provide the full job description."
        )


def validate_application_identity(company_name: str, job_title: str) -> None:
    """Requires useful employer and role names before document generation."""
    fields = {
        "company name": clean_company(company_name),
        "job title": str(job_title).strip(),
    }
    invalid = [
        label
        for label, value in fields.items()
        if not value or value.lower() in PLACEHOLDER_IDENTITY_VALUES
    ]
    if invalid:
        raise ValueError(
            "Add the actual " + " and ".join(invalid)
            + " before generating application documents."
        )


def normalize_optional_source_url(source_url: str) -> str:
    """Normalizes a supplied source link while allowing manual input."""
    source_url = str(source_url).strip()
    return normalize_url(source_url) if source_url else ""


def category_for_confirmed_skill(skill: str) -> str:
    """Chooses the most suitable profile category for a confirmed skill."""
    normalized = skill.lower()
    data_terms = [
        "data", "bigquery", "sql", "etl", "analytics", "analysis",
        "preprocessing", "cleaning",
    ]
    soft_terms = [
        "communication", "collaboration", "learning", "attention",
        "detail", "curiosity", "team", "feedback",
    ]
    ai_terms = [
        "genai", "agent", "rag", "embedding", "prompt", "llm",
        "vertex", "responsible ai",
    ]
    tool_terms = [
        "gcp", "cloud", "pub/sub", "cloud run", "storage",
        "api", "sdk", "github", "git",
    ]

    if any(term in normalized for term in soft_terms):
        return "Soft Skills"
    if any(term in normalized for term in ai_terms):
        return "AI & Application Development"
    if any(term in normalized for term in data_terms):
        return "Data Analysis"
    if any(term in normalized for term in tool_terms):
        return "Tools & Platforms"
    return "Software Fundamentals"


def add_confirmed_skills_to_profile(profile: dict, skills: list[str]) -> dict:
    """Returns a temporary profile copy enriched with confirmed skills."""
    enriched_profile = deepcopy(profile)
    enriched_profile.setdefault("skills", {})
    confirmed_terms = unique_items(skills)
    enriched_profile["_application_confirmed_terms"] = confirmed_terms
    enriched_profile["_permanent_skills"] = deepcopy(profile.get("skills", {}))

    for skill in confirmed_terms:
        category = category_for_confirmed_skill(skill)
        enriched_profile["skills"].setdefault(category, [])
        existing = {
            str(item).strip().lower()
            for item in enriched_profile["skills"][category]
        }
        if skill.lower() not in existing:
            enriched_profile["skills"][category].append(skill)

    return enriched_profile


def get_missing_profile_terms(match: dict, limit: int = 8) -> list[str]:
    """Returns deduplicated gaps suitable for user confirmation."""
    terms = unique_items(
        list(match.get("missing_skills", []))
        + list(match.get("missing_tools", []))
    )
    return terms[:limit]


def attach_confirmed_familiarity(
    match: dict,
    confirmed_terms: list[str],
) -> dict:
    """Annotates a match without treating familiarity as verified evidence."""
    annotated = deepcopy(match)
    terms = unique_items(confirmed_terms)[:8]
    annotated["base_match_score"] = int(match.get("match_score", 0))
    annotated["familiarity_adjustment"] = 0
    annotated["user_confirmed_terms"] = terms
    return annotated


def prepare_match(
    job_description: str,
    job_analysis: dict | None = None,
    profile: dict | None = None,
    match: dict | None = None,
) -> tuple[dict, dict, dict]:
    """Validates input, analyzes the job, loads the profile, and calculates fit."""
    validate_job_description(job_description)
    job_analysis = job_analysis or analyze_job(job_description)
    profile = profile or get_profile()
    match = match or match_profile_to_job(job_analysis, profile)
    return job_analysis, profile, match


def build_final_resume_text(resume: dict, profile: dict) -> str:
    """Builds ATS-check text from all content rendered in the final resume."""
    lines = [resume_to_text(resume)]

    lines.append("SKILLS")
    for category, skills in profile.get("skills", {}).items():
        if category.startswith("_"):
            continue
        lines.append(f"{category}: {', '.join(skills)}")

    lines.append("EXPERIENCE")
    for experience in profile.get("experience", []):
        lines.append(
            f"{experience.get('title', '')} {experience.get('company', '')}"
        )
        lines.extend(experience.get("highlights", []))

    lines.append("EDUCATION")
    for education in profile.get("education", []):
        lines.append(
            " ".join(
                [
                    education.get("degree", ""),
                    education.get("institution", ""),
                    education.get("year", ""),
                    education.get("grade", ""),
                ]
            )
        )

    lines.append("CERTIFICATIONS")
    lines.extend(profile.get("certifications", []))
    lines.append("ACHIEVEMENTS")
    lines.extend(profile.get("achievements", []))
    return "\n".join(str(line) for line in lines if line)


def build_match_explanation(match: dict) -> str:
    """Creates a concise, grounded explanation of application fit."""
    score = int(match.get("match_score", 0))
    verdict = str(match.get("fit_verdict_label") or "Fit scored")
    recommendation = str(match.get("application_recommendation") or "").strip()
    strongest = unique_items(list(match.get("strongest_points", [])))[:2]
    gaps = unique_items(
        list(match.get("missing_skills", []))
        + list(match.get("missing_tools", []))
    )[:4]

    lines = [f"{verdict}: profile fit is {score}/100."]
    if recommendation:
        lines.append(f"Suggested action: {recommendation}.")
    if strongest:
        lines.append("Best evidence: " + " ".join(strongest))
    if gaps:
        lines.append("Check before applying: " + ", ".join(gaps) + ".")
    else:
        lines.append("No major missing skill/tool gaps were detected.")
    return " ".join(lines)


def build_recruiter_message(
    *,
    profile: dict,
    company_name: str,
    job_title: str,
    match: dict,
) -> str:
    """Creates a short outreach note from verified profile and match evidence."""
    name = str(profile.get("name") or "Pranav").strip()
    matched = unique_items(
        list(match.get("matched_skills", []))
        + list(match.get("matched_tools", []))
    )[:3]
    evidence = unique_items(list(match.get("strongest_points", [])))[:1]
    skill_line = (
        " with experience in " + ", ".join(matched)
        if matched
        else ""
    )
    evidence_line = f" {evidence[0]}" if evidence else ""
    return (
        f"Hi, I am {name}. I am interested in the {job_title} role at "
        f"{company_name}{skill_line}.{evidence_line} I would appreciate the "
        "opportunity to be considered and can share tailored application "
        "materials or project details if helpful."
    )


def build_application_checklist(match: dict, ats_report: dict) -> list[str]:
    """Returns review actions to complete before applying."""
    checklist = [
        "Open the original listing and confirm the role is still active.",
        "Verify company name, job title, location, work mode, and job type.",
        "Review every resume and cover-letter claim for factual accuracy.",
        "Confirm contact details and public profile links are current.",
    ]
    missing = unique_items(
        list(match.get("missing_skills", []))
        + list(match.get("missing_tools", []))
        + list(ats_report.get("missing_terms", []))
    )
    if missing:
        checklist.append(
            "Prepare honest talking points for gaps: "
            + ", ".join(missing[:5])
            + "."
        )
    if int(ats_report.get("keyword_coverage", 0)) < 70:
        checklist.append(
            "Improve ATS coverage only with skills and evidence you can verify."
        )
    checklist.append(
        "After submitting externally, update Tracker status to Applied."
    )
    return checklist


def generate_application_draft(
    company_name: str,
    job_title: str,
    job_description: str,
    tone: str = "professional",
    source_url: str = "",
    confirmed_terms: list[str] | None = None,
    job_analysis: dict | None = None,
    profile: dict | None = None,
    match: dict | None = None,
    confirmed_details: dict[str, str] | None = None,
) -> ApplicationDraft:
    """Generates a complete application draft without saving it."""
    company_name = clean_company(company_name)
    job_title = job_title.strip()
    validate_application_identity(company_name, job_title)
    source_url = normalize_optional_source_url(source_url)
    job_analysis, profile, match = prepare_match(
        job_description,
        job_analysis,
        profile,
        match,
    )

    confirmed_terms = unique_items(confirmed_terms or [])
    if confirmed_terms:
        confirmed_terms = confirmed_terms[:8]
        profile = add_confirmed_skills_to_profile(profile, confirmed_terms)
        if confirmed_details:
            profile["_application_confirmed_details"] = confirmed_details
        match = attach_confirmed_familiarity(match, confirmed_terms)

    from resume import generate_application_strategy, grounded_professional_summary
    profile_summary = grounded_professional_summary(profile)
    strategy = generate_application_strategy(job_analysis, profile_summary)

    resume = generate_resume(job_analysis, profile, match, strategy=strategy)
    cover_letter = generate_cover_letter(
        job_analysis=job_analysis,
        profile=profile,
        match=match,
        company_name=company_name,
        job_title=job_title,
        tone=tone,
        strategy=strategy,
    )
    ats_report = build_ats_report(
        build_final_resume_text(resume, profile),
        job_analysis,
    )
    recruiter_message = build_recruiter_message(
        profile=profile,
        company_name=company_name,
        job_title=job_title,
        match=match,
    )
    application_checklist = build_application_checklist(match, ats_report)
    match_explanation = build_match_explanation(match)

    return ApplicationDraft(
        company_name=company_name,
        job_title=job_title,
        source_url=source_url,
        job_analysis=job_analysis,
        profile=profile,
        match=match,
        resume=resume,
        cover_letter=cover_letter,
        ats_report=ats_report,
        recruiter_message=recruiter_message,
        application_checklist=application_checklist,
        match_explanation=match_explanation,
    )


def build_tracker_notes(match: dict) -> str:
    """Creates concise tracker notes from generation-time decisions."""
    confirmed_terms = match.get("user_confirmed_terms") or []
    if not confirmed_terms:
        return ""
    return (
        "User-confirmed for this application only: "
        + ", ".join(confirmed_terms)
    )


def write_fallback_pdf(text: str, output_path: str) -> bool:
    """Creates a readable, beautifully formatted PDF without relying on a system LaTeX install."""
    try:
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            HRFlowable,
        )
        from xml.sax.saxutils import escape
    except ImportError:
        return False

    try:
        styles = getSampleStyleSheet()
        
        # Define clean, professional color palette (slate charcoal & black)
        primary_color = HexColor("#111111")
        secondary_color = HexColor("#555555")
        line_color = HexColor("#222222")

        body_style = ParagraphStyle(
            "PathPilotBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=primary_color,
            spaceAfter=3,
        )
        
        bullet_style = ParagraphStyle(
            "PathPilotBullet",
            parent=body_style,
            leftIndent=18,
            firstLineIndent=-10,
            spaceAfter=2,
        )

        heading_style = ParagraphStyle(
            "PathPilotHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=primary_color,
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True,
        )

        name_style = ParagraphStyle(
            "PathPilotName",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=primary_color,
            alignment=TA_LEFT,
            spaceAfter=2,
        )
        
        contact_style = ParagraphStyle(
            "PathPilotContact",
            parent=body_style,
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=secondary_color,
            alignment=TA_LEFT,
            spaceAfter=6,
        )

        meta_style = ParagraphStyle(
            "PathPilotMeta",
            parent=body_style,
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=11,
            textColor=secondary_color,
        )

        document = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title="PathPilot application document",
        )
        
        story = []
        lines = [line.strip() for line in str(text).splitlines()]
        
        # Header Parsing - Left-Aligned Grid
        first_line_idx = 0
        while first_line_idx < len(lines) and not lines[first_line_idx]:
            first_line_idx += 1
            
        if first_line_idx < len(lines):
            name_text = escape(lines[first_line_idx])
            story.append(Paragraph(name_text, name_style))
            first_line_idx += 1
            
            # Check if next line is Contact Info
            if first_line_idx < len(lines) and lines[first_line_idx]:
                contact_raw = lines[first_line_idx]
                # Replace standard pipes or commas with bullet separators for visual design
                contact_clean = contact_raw.replace(" | ", "  •  ").replace(" |", "  •  ")
                contact_text = escape(contact_clean)
                story.append(Paragraph(contact_text, contact_style))
                first_line_idx += 1
        
        # Body Parsing
        section_headers = {
            "PROFESSIONAL SUMMARY",
            "EDUCATION",
            "EXPERIENCE",
            "PROJECTS",
            "SKILLS",
            "COURSES",
            "PUBLICATIONS",
            "CERTIFICATIONS",
            "ACHIEVEMENTS",
        }

        from reportlab.platypus import Table, TableStyle

        in_skills = False
        skills_accumulator = []

        def flush_skills(acc, story_list):
            if not acc:
                return
            # Pair consecutive items up as a two-column table
            pairs = []
            for k in range(0, len(acc), 2):
                left = acc[k]
                right = acc[k+1] if k+1 < len(acc) else ""
                left_para = Paragraph(left, body_style)
                right_para = Paragraph(right, body_style)
                pairs.append([left_para, right_para])
            t = Table(pairs, colWidths=[250, 250])
            t.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                ('TOPPADDING', (0,0), (-1,-1), 1),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            story_list.append(t)
            acc.clear()

        idx = first_line_idx
        while idx < len(lines):
            line = lines[idx]
            if not line:
                if in_skills:
                    flush_skills(skills_accumulator, story)
                story.append(Spacer(1, 2))
                idx += 1
                continue
            if line == "\f":
                if in_skills:
                    flush_skills(skills_accumulator, story)
                story.append(PageBreak())
                idx += 1
                continue

            escaped_line = escape(line)
            
            # Identify headings
            if line.upper() in section_headers:
                if in_skills:
                    flush_skills(skills_accumulator, story)
                
                if line.upper() == "SKILLS":
                    in_skills = True
                else:
                    in_skills = False

                story.append(Spacer(1, 4))
                story.append(Paragraph(f"<b>{escaped_line}</b>", heading_style))
                story.append(HRFlowable(
                    width="100%",
                    thickness=0.8,
                    color=line_color,
                    spaceBefore=1,
                    spaceAfter=4
                ))
            # Identify bullets
            elif line.startswith(("- ", "• ")):
                if in_skills:
                    flush_skills(skills_accumulator, story)
                    in_skills = False
                bullet_content = escape(line[2:].strip())
                story.append(Paragraph(f"&#8226; {bullet_content}", bullet_style))
            # Bold role details or companies
            elif " — " in line or " at " in line:
                if in_skills:
                    flush_skills(skills_accumulator, story)
                    in_skills = False
                parts = escaped_line.split(" — ")
                if len(parts) == 2:
                    # Format as: Title/Company (Bold) and Date/Loc (Oblique) side-by-side using Table
                    left_para = Paragraph(f"<b>{parts[0]}</b>", body_style)
                    right_para = Paragraph(parts[1], meta_style)
                    t = Table([[left_para, right_para]], colWidths=[350, 150])
                    t.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                        ('TOPPADDING', (0,0), (-1,-1), 1),
                        ('LEFTPADDING', (0,0), (-1,-1), 0),
                        ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ]))
                    story.append(t)
                else:
                    story.append(Paragraph(f"<b>{escaped_line}</b>", body_style))
            else:
                if in_skills:
                    skills_accumulator.append(escaped_line)
                else:
                    story.append(Paragraph(escaped_line, body_style))
            idx += 1

        if in_skills:
            flush_skills(skills_accumulator, story)

        document.build(story)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


def save_application_draft(
    draft: ApplicationDraft,
    output_dir: str = "outputs",
    user_id: int = 1,
) -> SavedApplication:
    """Writes text/PDF outputs and records the approved draft."""
    if user_id != 1:
        output_dir = os.path.join(output_dir, "users", str(user_id))
    os.makedirs(output_dir, exist_ok=True)
    candidate_clean = clean_filename(draft.profile.get("name", "candidate"))
    company_clean = clean_filename(draft.company_name)
    unique_id = uuid4().hex[:6]
    resume_stem = f"{candidate_clean}_resume_{company_clean}_{unique_id}"
    letter_stem = f"{candidate_clean}_cover_letter_{company_clean}_{unique_id}"

    resume_txt = os.path.join(output_dir, f"{resume_stem}.txt")
    letter_txt = os.path.join(output_dir, f"{letter_stem}.txt")
    resume_pdf = os.path.join(output_dir, f"{resume_stem}.pdf")
    letter_pdf = os.path.join(output_dir, f"{letter_stem}.pdf")

    created_paths = [resume_txt, letter_txt, resume_pdf, letter_pdf]
    try:
        save_resume(draft.resume, resume_txt)
        save_cover_letter(draft.cover_letter, letter_txt)

        resume_ok = compile_resume(
            build_latex_resume(
                profile=draft.profile,
                job_analysis=draft.job_analysis,
                match=draft.match,
                resume_content=draft.resume,
            ),
            resume_pdf,
        )
        letter_ok = compile_letter(
            build_latex_coverletter(
                profile=draft.profile,
                cover_letter_content=draft.cover_letter,
                company_name=draft.company_name,
                job_title=draft.job_title,
            ),
            letter_pdf,
        )

        if not resume_ok:
            resume_ok = write_fallback_pdf(
                resume_to_text(draft.resume, profile=draft.profile),
                resume_pdf,
            )
        if not letter_ok:
            letter_ok = write_fallback_pdf(
                draft.cover_letter,
                letter_pdf,
            )

        if not resume_ok or not letter_ok:
            failed = []
            if not resume_ok:
                failed.append("resume PDF")
            if not letter_ok:
                failed.append("cover letter PDF")
            raise RuntimeError(
                "Could not save complete application materials: "
                + ", ".join(failed)
            )

        application_id = record_application(
            company_name=draft.company_name,
            job_title=draft.job_title,
            match=draft.match,
            ats_report=draft.ats_report,
            resume_path=resume_pdf,
            cover_letter_path=letter_pdf,
            job_analysis=draft.job_analysis,
            status="DRAFT_GENERATED",
            source_url=draft.source_url,
            notes=build_tracker_notes(draft.match),
            user_id=user_id,
        )
    except Exception:
        for path in created_paths:
            if os.path.exists(path):
                os.remove(path)
        raise
    return SavedApplication(
        resume_pdf=resume_pdf,
        cover_letter_pdf=letter_pdf,
        application_id=application_id,
    )
