# cover_letter.py

import os
import re
import subprocess
from datetime import date

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
from wording_checks import strip_unsupported_intensifiers
from document_standards import (
    COVER_LETTER_MAX_PARAGRAPHS,
    COVER_LETTER_MAX_WORDS,
    COVER_LETTER_MIN_PARAGRAPHS,
    GENERIC_SALUTATION,
    SALUTATION_PREFIXES,
    SIGN_OFF_PREFIXES,
    UK_ENGLISH_INSTRUCTION,
    mentions_right_to_work,
    strip_right_to_work_claims,
    format_uk_date,
    sign_off_for,
)
from profile import get_profile
from matcher import match_profile_to_job
from llm_utils import create_message_with_retry, get_llm_client, get_llm_model
from utils import (
    clean_phone,
    clean_url,
    latex_escape,
    normalize_candidate_status,
    profile_is_graduate,
)

load_dotenv()


def llm_runtime():
    """Returns the configured LLM client and model when generation is requested."""
    return get_llm_client(), get_llm_model()


def clean_cover_letter_style(text: str) -> str:
    """Makes generated cover letters sound simpler and less AI-polished."""
    cleaned = str(text)

    replacements = {
        "\u2014": ", ",
        "\u2013": ", ",
        " -- ": ", ",
        " - ": ", ",
    }
    for old, new in replacements.items():
        cleaned = re.sub(re.escape(old), new, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def unsupported_confirmed_claims(
    text: str,
    confirmed_terms: list[str],
) -> list[str]:
    """Finds sentences that turn familiarity into unsupported experience."""
    evidence_markers = (
        "internship",
        "worked with",
        "worked on",
        "built with",
        "developed with",
        "used in my project",
        "project experience",
        "production experience",
        "professional experience",
    )
    violations = []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", str(text))
    for sentence in sentences:
        lower = sentence.lower()
        has_confirmed_term = any(
            str(term).lower() in lower for term in confirmed_terms
        )
        if has_confirmed_term and any(marker in lower for marker in evidence_markers):
            # Allow if qualified as academic, self-study, or coursework
            qualifiers = ("self-study", "self-taught", "coursework", "academic", "university", "classroom", "course", "studying", "studied")
            if not any(q in lower for q in qualifiers):
                violations.append(sentence.strip())
    return violations


def unsupported_profile_claims(text: str, profile: dict = None) -> list[str]:
    """Finds known cross-project and internship evidence mix-ups dynamically."""
    if profile is None:
        profile = get_profile()
        
    violations = []
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", str(text))
        if paragraph.strip()
    ]

    # Dynamic grounding validation rules from profile projects
    projects_data = []
    for project in profile.get("projects", []):
        name = project.get("name", "")
        domain = project.get("domain", "")
        metrics = project.get("grounding_metrics", [])
        if not metrics:
            continue
        project_keywords = {name.lower(), domain.lower()}
        project_keywords.update(t.lower() for t in project.get("tools", []))
        project_keywords.update(w.lower() for w in re.findall(r"\b\w{3,}\b", name))
        projects_data.append({
            "name": name,
            "metrics": [m.lower() for m in metrics],
            "keywords": project_keywords
        })

    # Dynamic restricted experience validations
    experience_data = []
    for exp in profile.get("experience", []):
        company = exp.get("company", "").lower()
        title = exp.get("title", "").lower()
        exp_text = (exp.get("description", "") + " " + " ".join(exp.get("highlights", []))).lower()
        restricted_terms = [
            "openai", "gemini", "llm api", "claude api", 
            "prompt engineering", "agentic workflow", "agentic ai",
            "rag", "production grade", "production-grade"
        ]
        experience_data.append({
            "company": company,
            "title": title,
            "exp_text": exp_text,
            "restricted_terms": [t for t in restricted_terms if t not in exp_text]
        })

    for paragraph in paragraphs:
        lower = paragraph.lower()
        
        # Check cross-project metric leaks
        leak_detected = False
        for p_idx, p_current in enumerate(projects_data):
            has_project_keywords = any(kw in lower for kw in p_current["keywords"])
            if has_project_keywords:
                for other_idx, p_other in enumerate(projects_data):
                    if p_idx == other_idx:
                        continue
                    exclusive_other_metrics = [
                        m for m in p_other["metrics"] 
                        if m not in p_current["metrics"]
                    ]
                    if any(metric in lower for metric in exclusive_other_metrics):
                        leak_detected = True
                        break
            if leak_detected:
                break
        if leak_detected:
            violations.append(paragraph)
            continue

        # Check experience restricted tool leaks
        exp_leak_detected = False
        for exp in experience_data:
            if not exp["company"]:
                continue
            is_matching_exp = (
                exp["company"] in lower 
                or (len(exp["title"]) > 5 and exp["title"] in lower)
                or ("internship" in lower and exp["company"] in lower)
            )
            if is_matching_exp:
                if any(term in lower for term in exp["restricted_terms"]):
                    exp_leak_detected = True
                    break
        if exp_leak_detected:
            violations.append(paragraph)

    return violations


def _is_salutation_or_sign_off(block: str, name: str) -> bool:
    lower = block.lower().strip()
    if lower == name:
        return True
    if lower.startswith(SALUTATION_PREFIXES) and len(lower.split()) <= 6:
        return True
    first_line = lower.splitlines()[0].rstrip(",").strip()
    return first_line in SIGN_OFF_PREFIXES


def cover_letter_body_paragraphs(text: str, profile: dict) -> list[str]:
    """Extract body paragraphs without the greeting and sign-off."""
    name = str(profile.get("name", "")).strip().lower()
    blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n", str(text))
        if block.strip()
    ]
    return [block for block in blocks if not _is_salutation_or_sign_off(block, name)]


def cover_letter_format_issues(text: str, profile: dict) -> list[str]:
    """Return deterministic format and candidate-status violations."""
    paragraphs = cover_letter_body_paragraphs(text, profile)
    issues = []
    if not (
        COVER_LETTER_MIN_PARAGRAPHS <= len(paragraphs) <= COVER_LETTER_MAX_PARAGRAPHS
    ):
        issues.append(
            f"Cover letter has {len(paragraphs)} body paragraphs; expected "
            f"{COVER_LETTER_MIN_PARAGRAPHS}-{COVER_LETTER_MAX_PARAGRAPHS}."
        )
    word_count = len(" ".join(paragraphs).split())
    if word_count > COVER_LETTER_MAX_WORDS:
        issues.append(
            f"Cover letter body has {word_count} words; maximum is "
            f"{COVER_LETTER_MAX_WORDS}."
        )
    if profile_is_graduate(profile) and re.search(
        r"\b(final[- ]year|current)\b.{0,45}\bstudent\b"
        r"|\bComputer Science student\b"
        r"|\bengineering student\b",
        str(text),
        flags=re.IGNORECASE,
    ):
        issues.append("Cover letter incorrectly describes the graduate as a student.")
    return issues


def _cap_paragraph_words(paragraph: str, limit: int) -> str:
    """Trim at sentence boundaries while preserving readable prose."""
    words = paragraph.split()
    if len(words) <= limit:
        return paragraph.strip()

    sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    kept = []
    count = 0
    for sentence in sentences:
        sentence_words = sentence.split()
        if kept and count + len(sentence_words) > limit:
            break
        if not kept and len(sentence_words) > limit:
            return " ".join(sentence_words[:limit]).rstrip(",;:") + "."
        kept.append(sentence)
        count += len(sentence_words)
    return " ".join(kept).strip()


def enforce_cover_letter_constraints(
    text: str,
    profile: dict,
    salutation: str = GENERIC_SALUTATION,
) -> str:
    """Normalise status, structure (3-4 paragraphs), length and UK sign-off."""
    cleaned = normalize_candidate_status(clean_cover_letter_style(text), profile)
    paragraphs = cover_letter_body_paragraphs(cleaned, profile)

    if len(paragraphs) > COVER_LETTER_MAX_PARAGRAPHS:
        head = paragraphs[: COVER_LETTER_MAX_PARAGRAPHS - 1]
        tail = " ".join(paragraphs[COVER_LETTER_MAX_PARAGRAPHS - 1 :])
        paragraphs = head + [tail]
    elif len(paragraphs) < COVER_LETTER_MIN_PARAGRAPHS:
        sentences = re.split(
            r"(?<=[.!?])\s+",
            " ".join(paragraphs).strip(),
        )
        if len(sentences) >= COVER_LETTER_MIN_PARAGRAPHS:
            size = len(sentences) / COVER_LETTER_MIN_PARAGRAPHS
            paragraphs = [
                " ".join(sentences[round(i * size) : round((i + 1) * size)])
                for i in range(COVER_LETTER_MIN_PARAGRAPHS)
            ]

    # Keep the total within the word limit by trimming each paragraph proportionally.
    total_words = len(" ".join(paragraphs).split())
    if total_words > COVER_LETTER_MAX_WORDS:
        ratio = COVER_LETTER_MAX_WORDS / total_words
        paragraphs = [
            _cap_paragraph_words(p, max(25, int(len(p.split()) * ratio)))
            for p in paragraphs
        ]

    return (
        f"{salutation},\n\n"
        + "\n\n".join(paragraphs)
        + f"\n\n{sign_off_for(salutation)},\n{profile.get('name', '')}"
    ).strip()


def _right_to_work_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(text))
        if mentions_right_to_work(sentence)
    ]


def _factual_boundaries(profile: dict) -> str:
    """Per-project metric boundaries derived from the candidate's own profile."""
    lines = [
        "- Only use details that appear in the CANDIDATE section above.",
        "- Never transfer a metric or result from one project or role to another.",
    ]
    for project in profile.get("projects") or []:
        metrics = project.get("grounding_metrics") or []
        name = project.get("name", "")
        if name and metrics:
            lines.append(f"- {', '.join(map(str, metrics))} belong only to \"{name}\".")
        elif name:
            lines.append(f"- \"{name}\" has no recorded metrics; do not attach numbers to it.")
    return "\n".join(lines)


def generate_cover_letter(
    job_analysis: dict,
    profile: dict,
    match: dict,
    company_name: str,
    job_title: str,
    tone: str = "professional",
    strategy: dict = None
) -> str:
    """Generates personalized cover letter using Claude API."""

    if strategy is None:
        from resume import generate_application_strategy, grounded_professional_summary
        profile_summary = grounded_professional_summary(profile)
        strategy = generate_application_strategy(job_analysis, profile_summary)

    experiences = profile.get("experience") or []
    experience_text = (
        f"{experiences[0].get('title', '')} at {experiences[0].get('company', '')}"
        if experiences
        else "Early-career candidate with academic and project experience"
    )

    requirement_text = " ".join(
        [
            str(job_analysis.get("summary", "")),
            " ".join(job_analysis.get("skills", [])),
            " ".join(job_analysis.get("tools", [])),
            " ".join(job_analysis.get("keywords", [])),
        ]
    ).lower()

    def project_relevance(project: dict) -> int:
        project_text = " ".join(
            [
                str(project.get("name", "")),
                str(project.get("domain", "")),
                str(project.get("description", "")),
                " ".join(project.get("tools", [])),
                " ".join(project.get("highlights", [])),
            ]
        ).lower()
        terms = {
            term
            for term in requirement_text.replace("/", " ").split()
            if len(term) >= 4
        }
        return sum(1 for term in terms if term in project_text)

    projects = profile.get("projects") or []
    relevant_project = max(projects, key=project_relevance) if projects else {}
    best_project = (
        f"{relevant_project.get('name', '')} -- "
        f"{relevant_project.get('description', '')}"
        if relevant_project
        else "No projects"
    )
    project_highlights = relevant_project.get("highlights", [])

    education = profile.get("education") or []
    education_text = (
        f"{education[0].get('degree', '')} -- "
        f"{education[0].get('institution', '')} -- "
        f"{education[0].get('grade', '')}"
        if education and isinstance(education[0], dict)
        else "Not provided"
    )

    publications = profile.get("publications", [])
    pub_text = ""
    if publications:
        pub = publications[0]
        if isinstance(pub, dict):
            pub_title = pub.get("title", "")
            pub_publisher = pub.get("publisher", "")
            pub_conf = pub.get("conference", "")
            details = []
            if pub_publisher:
                details.append(pub_publisher)
            if pub_conf:
                details.append(pub_conf)
            pub_text = f"Published in {', '.join(details)}" if details else pub_title
        else:
            pub_text = str(pub)
    permanent_skills = profile.get("_permanent_skills", profile.get("skills", {}))
    confirmed_terms = profile.get("_application_confirmed_terms", [])
    evidence_matched_skills = [
        skill for skill in match.get("matched_skills", [])
        if str(skill).lower() not in {
            str(term).lower() for term in confirmed_terms
        }
    ]

    factual_boundaries = _factual_boundaries(profile)

    prompt = f"""
You are an expert cover letter writer for UK graduate and early-career job applications.
Write a natural, specific, honest cover letter aligned with the target APPLICATION STRATEGY.
{UK_ENGLISH_INSTRUCTION}

APPLICATION STRATEGY:
Positioning: {strategy.get("positioning_strategy", "")}
Evidence Requirements: {strategy.get("evidence_requirements", "")}
Interviewer Takeaway: {strategy.get("interviewer_takeaway", "")}
Summary Focus: {strategy.get("summary_focus", "")}
What to De-emphasize: {strategy.get("what_to_deemphasize", "")}

JOB DETAILS:
Job Title: {job_title}
Company: {company_name}
Job Summary: {job_analysis["summary"]}
Key Skills Needed: {job_analysis["skills"][:5]}

CANDIDATE:
Name: {profile.get("name", "")}
Background: {experience_text}
Education: {education_text}
Publication: {pub_text}
Permanent Skills: {permanent_skills}
User-confirmed familiarity for this application only: {confirmed_terms}
User-provided evidence/details for confirmed terms: {profile.get("_application_confirmed_details", {})}
Evidence-backed Matched Skills: {evidence_matched_skills}
Strongest Points: {match.get("strongest_points", [])}
Best Project: {best_project}
Project Highlights: {project_highlights}

FACTUAL BOUNDARIES:
{factual_boundaries}

STRICT RULES:
1. Maximum {COVER_LETTER_MAX_WORDS} words in total across the body paragraphs.
2. {COVER_LETTER_MIN_PARAGRAPHS} to {COVER_LETTER_MAX_PARAGRAPHS} short paragraphs.
3. Do NOT start with "I am writing to apply" or similar generic openings.
4. Paragraph 1: a specific hook that shows why this role at {company_name} fits the candidate, based on something concrete in the job details. Name the role "{job_title}" exactly.
5. Paragraph 2: the candidate's strongest relevant evidence from their own profile (a project, placement, module or achievement), with a concrete example of what they did and what it shows. Use the candidate's actual field; do not assume a technical role.
6. Paragraph 3 (and optionally 4): a second point on skills or fit, then a short, confident close inviting the next step.
7. Use ONLY facts, numbers and tools present in the candidate details above. Never invent employers, grades, metrics or experience.
8. Avoid clichés and buzzwords ("passionate", "results-driven", "team player", "hard-working").
9. Do NOT mention URLs. NEVER state or imply right to work, visa, sponsorship or immigration status.
9b. The job details describe the employer's needs, NOT facts about the candidate. Do not turn a requirement into a claim.
9c. Describe project and experience evidence exactly as given; do not add tools, activities or intensifiers (advanced, extensive, strong) that are not in the candidate details.
10. Write smooth connected prose, not lists.
11. If user-provided evidence/details are present for confirmed familiarity terms, you may weave in those terms strictly as self-study, coursework or academic learning, never as professional or commercial experience.

OUTPUT FORMAT, follow this EXACTLY:
{GENERIC_SALUTATION},

[Paragraph 1]

[Paragraph 2]

[Paragraph 3]

{sign_off_for(GENERIC_SALUTATION)},
{profile.get("name", "")}
"""

    client, model = llm_runtime()
    response = create_message_with_retry(
        client,
        model=model,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    generated = response.content[0].text
    violations = (
        unsupported_confirmed_claims(generated, confirmed_terms)
        + unsupported_profile_claims(generated)
        + cover_letter_format_issues(generated, profile)
        + _right_to_work_sentences(generated)
    )
    if violations:
        correction_prompt = f"""
Rewrite the cover letter below using the same structure, British English and a truthful tone. Keep it under {COVER_LETTER_MAX_WORDS} words.

The following terms are user-confirmed familiarity only:
{confirmed_terms}

Do not connect those terms to internships, employment, commercial projects, production work, or professional experience. You may say the candidate is familiar with them, studied them in academic coursework, or did self-study on them.

Unsupported sentences detected:
{violations}

Factual boundaries:
{factual_boundaries}

COVER LETTER:
{generated}

Return only the corrected cover letter.
"""
        response = create_message_with_retry(
            client,
            model=model,
            max_tokens=800,
            messages=[{"role": "user", "content": correction_prompt}],
        )
        generated = response.content[0].text

    remaining_violations = (
        unsupported_confirmed_claims(generated, confirmed_terms)
        + unsupported_profile_claims(generated)
    )
    for sentence in remaining_violations:
        generated = generated.replace(sentence, "")

    generated = "\n\n".join(
        strip_right_to_work_claims(block) if not _is_salutation_or_sign_off(block, "") else block
        for block in re.split(r"\n\s*\n", generated)
    )
    generated = strip_unsupported_intensifiers(generated, profile)
    return enforce_cover_letter_constraints(generated, profile)


def build_latex_coverletter(
    profile: dict,
    cover_letter_content: str,
    company_name: str,
    job_title: str
) -> str:
    """Builds professional LaTeX cover letter."""

    def escape(text: str) -> str:
        return latex_escape(text)

    def s(text) -> str:
        return escape(str(text))

    # ── Header fields ─────────────────────────────────────────
    name     = s(profile.get("name", ""))
    email    = profile.get("email", "")
    phone    = s(clean_phone(profile.get("phone", "")))
    linkedin = s(clean_url(profile.get("linkedin", "")))
    portfolio = s(clean_url(profile.get("portfolio", "")))
    today    = format_uk_date()
    job_safe = s(job_title)
    co_safe  = s(company_name)

    # ── Extract body paragraphs only (greeting and sign-off are re-added) ──
    paragraphs = [s(p) for p in cover_letter_body_paragraphs(cover_letter_content, profile)]
    salutation = GENERIC_SALUTATION
    sign_off = sign_off_for(salutation)

    body = "\n\n".join(paragraphs)

    header_lines = [
        s(profile.get("location", "")),
        s(email),
        phone,
        linkedin,
        portfolio,
    ]
    header_block = "\\\\\n  ".join(line for line in header_lines if line)
    header_block += ("\\\\[2pt]\n  " if header_block else "") + today

    return f"""\\documentclass[11pt, a4paper]{{article}}

\\usepackage[
  top    = 1.0in,
  bottom = 1.0in,
  left   = 1.0in,
  right  = 1.0in
]{{geometry}}
\\usepackage[hidelinks]{{hyperref}}
\\usepackage{{fancyhdr}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{microtype}}

% Prevent hyphenation
\\tolerance=1
\\emergencystretch=\\maxdimen
\\hyphenpenalty=10000
\\hbadness=10000

\\pagestyle{{fancy}}
\\fancyhf{{}}
\\renewcommand{{\\headrulewidth}}{{0pt}}

\\setlength{{\\parindent}}{{0pt}}
\\setlength{{\\parskip}}{{8pt}}
\\raggedright

\\begin{{document}}

% ===== HEADER =====
\\begin{{flushright}}
  {{\\large\\textbf{{{name}}}}}\\\\[3pt]
  \\small
  {header_block}
\\end{{flushright}}

\\vspace{{6pt}}

% ===== RECIPIENT =====
\\noindent Hiring Manager\\\\
\\noindent {co_safe}

\\vspace{{8pt}}

% ===== SUBJECT =====
\\noindent\\textbf{{Re: Application for {job_safe}}}

\\vspace{{8pt}}

% ===== SALUTATION =====
\\noindent {salutation},

\\vspace{{2pt}}

% ===== BODY =====
{body}

\\vspace{{10pt}}

% ===== CLOSING =====
\\noindent {sign_off},

\\vspace{{22pt}}

\\noindent\\textbf{{{name}}}

\\end{{document}}
"""


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
            print(f"✅ Cover letter PDF saved → {output_path}")
            return True
        else:
            print("❌ Cover letter compilation failed")
            for line in result.stdout.split("\n"):
                if line.startswith("!"):
                    print(" ", line)
            return False

    except subprocess.TimeoutExpired:
        print("❌ Timed out")
        return False
    except FileNotFoundError:
        print("❌ pdflatex not found")
        return False


def save_cover_letter(
    cover_letter_text: str,
    filename: str = "outputs/cover_letter.txt"
):
    """Saves plain text backup."""
    output_dir = os.path.dirname(filename) or "."
    os.makedirs(output_dir, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(cover_letter_text)
    print(f"✅ Cover letter text saved → {filename}")


def display_cover_letter(cover_letter_text: str):
    """Prints cover letter in terminal."""
    print("\n" + "="*55)
    print("           COVER LETTER")
    print("="*55)
    print(cover_letter_text)
    print("="*55)


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

    print("Step 4: Generating cover letter...")
    cover_letter = generate_cover_letter(
        job_analysis=job_analysis,
        profile=profile,
        match=match,
        company_name="Skillzenloop",
        job_title="Data Science Intern",
        tone="professional"
    )
    print("✅ Done")

    print("Step 5: Building PDF...")
    latex = build_latex_coverletter(
        profile=profile,
        cover_letter_content=cover_letter,
        company_name="Skillzenloop",
        job_title="Data Science Intern"
    )
    compile_to_pdf(latex, "outputs/coverletter_test.pdf")

    display_cover_letter(cover_letter)
    save_cover_letter(cover_letter)

    print("\n🎉 Open: open outputs/coverletter_test.pdf")
