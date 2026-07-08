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
        "early-career": "early career",
        "cutting-edge": "modern",
        "production-ready": "production focused",
        "hands-on": "practical",
        "AI-native": "AI focused",
        "next-generation": "new",
        "more than anything": "a lot",
        "revolutionizing": "working on",
        "hit the ground running": "contribute steadily",
        "drawn to": "interested in",
        "excites me": "interests me",
        "exactly the challenge I\u2019m looking for": "a strong learning opportunity for me",
        "exactly the challenge I'm looking for": "a strong learning opportunity for me",
    }
    for old, new in replacements.items():
        cleaned = re.sub(re.escape(old), new, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"(?<=\w)-(?=\w)", " ", cleaned)
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
        "at skilldzire",
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
            violations.append(sentence.strip())
    return violations


def unsupported_profile_claims(text: str) -> list[str]:
    """Finds known cross-project and internship evidence mix-ups."""
    violations = []
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", str(text))
        if paragraph.strip()
    ]

    for paragraph in paragraphs:
        lower = paragraph.lower()
        medical_project = any(
            marker in lower
            for marker in (
                "medical condition",
                "drug review",
                "tf idf",
                "tf-idf",
                "logistic regression",
                "naive bayes",
            )
        )
        face_project_metrics = (
            "93.91%" in paragraph or "15,000" in paragraph
        )
        if medical_project and face_project_metrics:
            violations.append(paragraph)
            continue

        internship_context = "internship" in lower or "skilldzire" in lower
        unsupported_internship_tools = any(
            marker in lower
            for marker in (
                "openai",
                "gemini",
                "llm api",
                "claude api",
                "prompt engineering",
                "agentic workflow",
            )
        )
        if internship_context and unsupported_internship_tools:
            violations.append(paragraph)

    return violations


def cover_letter_body_paragraphs(text: str, profile: dict) -> list[str]:
    """Extract body paragraphs without the greeting and signature."""
    name = str(profile.get("name", "")).strip().lower()
    blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n", str(text))
        if block.strip()
    ]
    body = []
    for block in blocks:
        lower = block.lower().strip()
        if lower in {
            "dear hiring team,",
            "dear hiring team",
            "sincerely,",
            "sincerely",
            name,
            f"sincerely,\n{name}",
        }:
            continue
        if lower.startswith("sincerely,"):
            continue
        body.append(block)
    return body


def cover_letter_format_issues(text: str, profile: dict) -> list[str]:
    """Return deterministic format and candidate-status violations."""
    paragraphs = cover_letter_body_paragraphs(text, profile)
    issues = []
    if len(paragraphs) != 3:
        issues.append(
            f"Cover letter has {len(paragraphs)} body paragraphs; expected 3."
        )
    word_count = len(" ".join(paragraphs).split())
    if word_count > 220:
        issues.append(
            f"Cover letter body has {word_count} words; maximum is 220."
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


def enforce_cover_letter_constraints(text: str, profile: dict) -> str:
    """Normalize candidate status, structure, and the 220-word body limit."""
    cleaned = normalize_candidate_status(clean_cover_letter_style(text), profile)
    paragraphs = cover_letter_body_paragraphs(cleaned, profile)

    if len(paragraphs) > 3:
        paragraphs = [paragraphs[0], paragraphs[1], " ".join(paragraphs[2:])]
    elif len(paragraphs) < 3:
        sentences = re.split(
            r"(?<=[.!?])\s+",
            " ".join(paragraphs).strip(),
        )
        if len(sentences) >= 3:
            cut1 = max(1, len(sentences) // 3)
            cut2 = max(cut1 + 1, (len(sentences) * 2) // 3)
            paragraphs = [
                " ".join(sentences[:cut1]),
                " ".join(sentences[cut1:cut2]),
                " ".join(sentences[cut2:]),
            ]

    if len(paragraphs) == 3:
        paragraphs = [
            _cap_paragraph_words(paragraphs[0], 65),
            _cap_paragraph_words(paragraphs[1], 100),
            _cap_paragraph_words(paragraphs[2], 55),
        ]

    return (
        "Dear Hiring Team,\n\n"
        + "\n\n".join(paragraphs)
        + f"\n\nSincerely,\n{profile.get('name', '')}"
    ).strip()


def generate_cover_letter(
    job_analysis: dict,
    profile: dict,
    match: dict,
    company_name: str,
    job_title: str,
    tone: str = "professional"
) -> str:
    """Generates personalized cover letter using Claude API."""

    experience_text = (
        f"{profile['experience'][0]['title']} at {profile['experience'][0]['company']}"
        if profile["experience"]
        else "Fresher with strong academic projects and Springer-published research"
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

    relevant_project = (
        max(profile["projects"], key=project_relevance)
        if profile["projects"]
        else {}
    )
    best_project = (
        f"{relevant_project.get('name', '')} -- "
        f"{relevant_project.get('description', '')}"
        if relevant_project
        else "No projects"
    )
    project_highlights = relevant_project.get("highlights", [])

    education_text = (
        f"{profile['education'][0]['degree']} -- "
        f"{profile['education'][0]['institution']} -- "
        f"{profile['education'][0]['grade']}"
        if profile["education"] else "Not provided"
    )

    publications = profile.get("publications", [])
    pub_text = (
        f"Published in {publications[0]['publisher']} ({publications[0]['conference']})"
        if publications else ""
    )
    permanent_skills = profile.get("_permanent_skills", profile.get("skills", {}))
    confirmed_terms = profile.get("_application_confirmed_terms", [])
    evidence_matched_skills = [
        skill for skill in match.get("matched_skills", [])
        if str(skill).lower() not in {
            str(term).lower() for term in confirmed_terms
        }
    ]

    prompt = f"""
You are an expert cover letter writer.
Write a simple, natural, fresher-friendly cover letter.

JOB DETAILS:
Job Title: {job_title}
Company: {company_name}
Job Summary: {job_analysis["summary"]}
Key Skills Needed: {job_analysis["skills"][:5]}

CANDIDATE:
Name: {profile["name"]}
Background: {experience_text}
Education: {education_text}
Publication: {pub_text}
Permanent Skills: {permanent_skills}
User-confirmed familiarity for this application only: {confirmed_terms}
Evidence-backed Matched Skills: {evidence_matched_skills}
Strongest Points: {match["strongest_points"]}
Best Project: {best_project}
Project Highlights: {project_highlights}

FACTUAL BOUNDARIES:
- The Medical Condition Classification project has no recorded dataset-size or accuracy result
- 15,000+ images and 93.91% accuracy belong only to the face-authenticity project
- Do not assign 15,000+ or 93.91% to drug reviews, NLP, TF-IDF, Logistic Regression, Naive Bayes, or SVM
- SkillDzire records foundational AI training only; do not claim OpenAI, Gemini, Claude API, LLM API, prompt-engineering, or agentic-workflow implementation there

STRICT RULES:
1. MAXIMUM 220 words total in body paragraphs
2. Exactly 3 paragraphs
3. Do NOT start with "I am writing to apply"
4. Paragraph 1: Simple opening + who you are + why this role
    5. Paragraph 2: Best relevant project with specific numbers and real methods
6. Paragraph 3: Why this company specifically + confident call to action
7. Sound human, calm, confident, and specific
8. Tone: {tone}
9. Do NOT mention https://, http://, or any URLs
10. Do NOT say "results-driven" or "passionate learner"
    11. Mention "93.91%" and "15,000+" only if relevant to this job
    12. Mention Springer publication naturally only if relevant
13. Do NOT use em dashes, en dashes, or dash-heavy phrases
14. Avoid AI-sounding phrases like "cutting-edge", "revolutionizing", "more than anything", and "ready to hit the ground running"
15. Avoid overclaiming. Do not imply professional GCP, RAG, or GenAI production experience unless clearly present in the candidate profile
16. Write like an early-career candidate who is honest, capable, and eager to contribute
17. Do not sound dramatic. Prefer direct sentences a real student would write
18. User-confirmed familiarity is not work, internship, project, extensive, or production experience
19. Do not say the candidate used a confirmed term at SkillDzire or in a project unless the permanent profile explicitly says so
20. Preserve the exact job title "{job_title}" when naming the role
21. Use the project with the strongest overlap to this job, not simply the first project in the profile

OUTPUT FORMAT — follow this EXACTLY:
Dear Hiring Team,

[Paragraph 1 text here]

[Paragraph 2 text here]

[Paragraph 3 text here]

Sincerely,
{profile["name"]}
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
    )
    if violations:
        correction_prompt = f"""
Rewrite the cover letter below using the same structure and truthful tone.

The following terms are user-confirmed familiarity only:
{confirmed_terms}

Do not connect those terms to internships, employment, projects, production
work, or professional experience. You may say the candidate is familiar with
them or interested in developing them further.

Unsupported sentences detected:
{violations}

Factual boundaries:
- The medical drug-review project has no recorded sample count or accuracy
- 15,000+ images and 93.91% accuracy belong only to the face-authenticity project
- SkillDzire does not prove implementation with OpenAI, Gemini, Claude API, LLM APIs, prompt engineering, or agentic workflows

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
    today    = date.today().strftime("%B %d, %Y")
    job_safe = s(job_title)
    co_safe  = s(company_name)
    name_lower = profile.get("name", "").lower().strip()

    # ── Extract body paragraphs only ──────────────────────────
    # Build exact skip set — all lowercase for comparison
    exact_skip = {
        "dear hiring team,",
        "dear hiring team",
        "sincerely,",
        "sincerely",
        name_lower,
        "hiring team,",
        "hiring team",
        f"sincerely, {name_lower}",
        f"sincerely,\n{name_lower}",
        f"sincerely,{name_lower}",
    }

    paragraphs = []
    for para in cover_letter_content.split("\n\n"):
        para = para.strip()
        if not para:
            continue

        para_lower = para.strip().lower()

        # Skip if entire paragraph is a salutation or closing
        if para_lower in exact_skip:
            continue

        # Skip if paragraph starts with "sincerely" (catches all variants)
        if para_lower.startswith("sincerely"):
            continue

        # Skip if paragraph starts with "dear hiring"
        if para_lower.startswith("dear hiring"):
            continue

        # Skip if paragraph is only the candidate name
        if para_lower == name_lower:
            continue

        paragraphs.append(s(para))

    body = "\n\n".join(paragraphs)

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
  {s(email)}\\\\
  {phone}\\\\
  {linkedin}\\\\
  {portfolio}\\\\[2pt]
  {today}
\\end{{flushright}}

\\vspace{{6pt}}

% ===== RECIPIENT =====
\\noindent Hiring Team\\\\
\\noindent {co_safe}

\\vspace{{8pt}}

% ===== SUBJECT =====
\\noindent\\textbf{{Re: Application for {job_safe}}}

\\vspace{{8pt}}

% ===== SALUTATION =====
\\noindent Dear Hiring Team,

\\vspace{{2pt}}

% ===== BODY =====
{body}

\\vspace{{10pt}}

% ===== CLOSING =====
\\noindent Sincerely,

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
