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
        "hands-on": "practical",
        "AI-native": "AI focused",
        "early-career": "",
        "cutting-edge": "modern",
        "production-ready": "production focused",
        "results-driven": "motivated",
        "passionate": "interested",
        "recent computer science graduate": "Computer Science graduate",
        "recent B.Tech graduate": "B.Tech graduate",
        "completed multiple data science internships": (
            "completed data science training and practical ML projects"
        ),
        "multiple data science internships": (
            "data science training and practical ML projects"
        ),
        "structured internships": "structured training",
        "transforming": "building",
        "revolutionizing": "improving",
        "leveraging": "using",
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

        safe_projects.append(
            {
                "name": source.get("name", ""),
                "domain": source.get("domain", ""),
                "tools": list(source.get("tools", [])),
                "bullets": [
                    clean_resume_style(bullet)
                    for bullet in source.get("highlights", [])[:3]
                ],
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


def grounded_professional_summary(profile: dict) -> str:
    """Builds a concise summary only from durable profile evidence."""
    projects = profile.get("projects", [])
    project_names = [
        project.get("name", "")
        for project in projects[:2]
        if project.get("name")
    ]
    project_evidence = (
        " Project work includes "
        + " and ".join(project_names)
        + "."
        if project_names
        else ""
    )
    return (
        "Computer Science graduate with foundations in software engineering, "
        "artificial intelligence, machine learning, data analysis, and core "
        "computer science concepts. Skilled in Python, SQL, Java, and C++ "
        "through verified academic projects, structured training, and "
        "technical coursework."
        + project_evidence
    )


def generate_resume(job_analysis: dict, profile: dict, match: dict) -> dict:
    """Generates structured tailored resume content via Claude API."""

    experience_text = (
        profile["experience"] if profile["experience"]
        else "Fresher with strong academic projects and published research"
    )

    prompt = f"""
You are a practical resume editor.
Create clear, truthful, ATS-friendly resume content for this candidate.
Return ONLY valid JSON. No markdown. No explanation.

JOB REQUIREMENTS:
Skills: {job_analysis["skills"]}
Tools: {job_analysis["tools"]}
Keywords: {job_analysis["keywords"]}
Summary: {job_analysis["summary"]}

CANDIDATE:
Name: {profile["name"]}
Permanent Skills: {profile.get("_permanent_skills", profile["skills"])}
User-confirmed familiarity for this application only: {profile.get("_application_confirmed_terms", [])}
User-provided evidence/details for confirmed terms: {profile.get("_application_confirmed_details", {})}
Experience: {experience_text}
Projects: {profile["projects"]}
Education: {profile["education"]}
Certifications: {profile.get("certifications", [])}
Achievements: {profile.get("achievements", [])}

MATCH:
Matched Skills: {match["matched_skills"]}
Strongest Points: {match["strongest_points"]}

Return this exact JSON structure:
{{
  "professional_summary": "2-3 sentences. NO name, NO email, NO phone, NO links.",
  "skills": {{
    "Languages": ["Python", "SQL"],
    "Machine Learning": ["scikit-learn", "Regression"],
    "Data Analysis": ["EDA", "Feature Engineering"],
    "Libraries": ["pandas", "NumPy", "Matplotlib"],
    "Tools": ["Jupyter Notebook", "GitHub"],
    "Databases": ["MySQL"]
  }},
  "projects": [
    {{
      "name": "Exact project name from candidate profile",
      "domain": "Project domain",
      "tools": ["tool1", "tool2"],
      "bullets": [
        "Strong action verb + specific method + specific tool + measurable result. Max 20 words."
      ]
    }}
  ],
  "certifications": ["cert1", "cert2"],
  "ats_notes": ["note1"]
}}

STRICT RULES:
- Do NOT invent companies, jobs, or work experience
- Do NOT claim multiple internships unless they appear in verified Experience
- Prefer "training and projects" over "internships" when experience is training-based
- Use ONLY facts from the candidate profile
- Include only skills the candidate actually has; do not invent any
- User-confirmed familiarity may appear only in the Skills section
- Label confirmed terms as familiarity when wording permits
- Never describe user-confirmed familiarity as internship, project, professional, extensive, production, or hands-on experience
- Project tools and bullet highlights must be selected exclusively from the permanent project records. Do not invent, alter, or add any achievements, numbers, or technical tasks. Every bullet point must exist in the profile record.
- Each bullet max 20 words
- Summary exactly 2-3 sentences
- Use simple human wording, not marketing language
- Avoid "results-driven", "passionate", "cutting-edge", "transforming", "leveraging", and similar AI-polished phrases
- Avoid dash-heavy phrasing; use commas or normal sentences instead
- Do not overclaim professional experience
- Do not use "recent graduate", "early-career", "fresher", or "aspiring"
- Start the summary naturally with "Computer Science graduate" and verified strengths
- Mention 93.91% accuracy and 15,000+ images ONLY if relevant to this job.
- 93.91% and 15,000+ belong only to the face-authenticity project
- Never assign those figures to the medical drug-review project or its algorithms
- If the role is not ML, data science, AI, analytics, or computer vision, keep those metrics inside the project bullets only.
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
        linkedin = profile.get("linkedin", "").strip()
        github = profile.get("github", "").strip()
        portfolio = profile.get("portfolio", "").strip()
        
        contact_info = []
        if email: contact_info.append(email)
        if phone: contact_info.append(phone)
        if linkedin: contact_info.append(linkedin)
        if github: contact_info.append(github)
        if portfolio: contact_info.append(portfolio)
        
        if name:
            lines.append(name.upper())
        if contact_info:
            lines.append(" | ".join(contact_info))
        if name or contact_info:
            lines.extend(["", ""])

    lines.extend([
        "PROFESSIONAL SUMMARY",
        resume_content.get("professional_summary", ""),
        "",
        "SKILLS",
    ])
    for category, skills in resume_content.get("skills", {}).items():
        lines.append(f"{category}: {', '.join(skills)}")
    lines.extend(["", "PROJECTS"])
    for project in resume_content.get("projects", []):
        lines.append(project.get("name", "Project"))
        lines.append(
            f"{project.get('domain', '')} | Tools: "
            f"{', '.join(project.get('tools', []))}"
        )
        for bullet in project.get("bullets", []):
            lines.append(f"- {bullet}")
    lines.extend(["", "CERTIFICATIONS"])
    for cert in resume_content.get("certifications", []):
        lines.append(f"- {cert}")
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
        return (
            "Aspiring Data Scientist with practical experience in machine learning, "
            "NLP, and statistical analysis. Built classification models achieving "
            "93.91% accuracy on 15,000+ image samples, published in Springer "
            "conference proceedings. Proficient in Python, scikit-learn, pandas, "
            "NumPy, and SQL."
        )
    return cleaned


def first_sentence(text: str) -> str:
    text = str(text).strip()
    parts = text.split(". ")
    if len(parts) <= 1:
        return text
    return parts[0].strip() + "."


def build_latex_resume(
    profile: dict,
    job_analysis: dict,
    match: dict,
    resume_content
) -> str:
    """Builds a clean one-page professional LaTeX resume."""

    # ── Basic info — strip all prefixes ──────────────────────
    name     = esc(profile.get("name", ""))
    email    = profile.get("email", "")
    phone    = esc(clean_phone(profile.get("phone", "")))
    linkedin = clean_url(profile.get("linkedin", ""))
    github   = clean_url(profile.get("github", ""))
    portfolio = clean_url(profile.get("portfolio", ""))

    # ── Fallback if resume_content not a dict ─────────────────
    if not isinstance(resume_content, dict):
        resume_content = {
            "professional_summary": (
                "Aspiring Data Scientist and B.Tech Computer Science and Engineering "
                "graduate with hands-on experience in machine learning, NLP, and "
                "statistical analysis. Built classification models achieving 93.91% "
                "accuracy on 15,000+ image samples, published in Springer proceedings."
            ),
            "skills": profile.get("skills", {}),
            "projects": [],
            "certifications": profile.get("certifications", []),
            "ats_notes": [],
        }

    # ── Professional summary ──────────────────────────────────
    tailored_summary = esc(
        sanitize_summary(resume_content.get("professional_summary", ""), profile)
    )

    # ── Skills — always read from profile dict ────────────────
    # This guarantees correct key names and no empty rows
    profile_skills = profile.get("skills", {})
    matched_terms = (
        list(match.get("matched_skills", []))
        + list(match.get("matched_tools", []))
        + list(match.get("matched_keywords", []))
    )

    def get_skills(keys: list, limit: int = 7) -> str:
        items = []
        for key in keys:
            items.extend(profile_skills.get(key, []))

        preferred = []
        remaining = []
        matched_norm = {str(term).lower() for term in matched_terms}
        for item in items:
            if item.lower() in matched_norm:
                preferred.append(item)
            else:
                remaining.append(item)

        unique = []
        seen_s = set()
        for item in preferred + remaining:
            k = item.lower()
            if k not in seen_s:
                seen_s.add(k)
                unique.append(item)
        return esc(", ".join(unique[:limit]))

    lang_line  = get_skills(["Programming Languages", "Languages"], 5)
    ml_line    = get_skills(
        [
            "Artificial Intelligence & Machine Learning",
            "Deep Learning & Computer Vision",
            "Machine Learning",
            "ML & AI",
        ],
        7,
    )
    ai_line    = get_skills(
        ["AI & Application Development", "AI Engineering"],
        4,
    )
    se_line    = get_skills(
        ["Software Fundamentals", "Software Engineering"],
        5,
    )
    data_line  = get_skills(["Data Analysis", "Data"], 6)
    lib_line   = get_skills(["Libraries & Frameworks", "Libraries"], 7)
    tools_line = get_skills(["Tools & Platforms", "Visualization Tools", "Tools"], 6)
    db_line    = get_skills(["Databases"], 3)

    # ── Experience / internships ──────────────────────────────
    experience_tex = ""
    priority_titles = ["Artificial Intelligence Intern", "Full Stack Development Intern"]
    experiences = profile.get("experience", [])
    selected_experiences = []
    for title in priority_titles:
        selected_experiences.extend(
            exp for exp in experiences
            if exp.get("title") == title and exp not in selected_experiences
        )
    for exp in experiences:
        if len(selected_experiences) >= 3:
            break
        if exp not in selected_experiences:
            selected_experiences.append(exp)

    for exp in selected_experiences[:3]:
        title = esc(exp.get("title", ""))
        company = esc(exp.get("company", ""))
        duration = esc(exp.get("duration", ""))
        highlights = exp.get("highlights", [])

        bullet_lines = ""
        for h in highlights[:2]:
            bullet_lines += f"  \\item\\small {esc(clean_resume_style(h))}\n"

        experience_tex += f"""\\vspace{{2pt}}
\\noindent\\begin{{minipage}}[t]{{0.70\\linewidth}}
  \\textbf{{{title}}} \\enspace\\textbar\\enspace \\textit{{{company}}}
\\end{{minipage}}%
\\begin{{minipage}}[t]{{0.30\\linewidth}}
  \\raggedleft\\small\\textbf{{{duration}}}
\\end{{minipage}}
\\begin{{itemize}}[leftmargin=1.2em, topsep=1pt, itemsep=0pt, parsep=0pt]
{bullet_lines}\\end{{itemize}}
"""

    # ── Projects ──────────────────────────────────────────────
    projects_tex = ""
    rendered_projects = resume_content.get("projects") or profile.get("projects", [])
    for proj in rendered_projects[:2]:
        pname   = esc(proj.get("name", ""))
        ptools  = esc(", ".join(proj.get("tools", [])))
        domain  = esc(proj.get("domain", ""))
        bullets = proj.get("bullets") or proj.get("highlights", [])

        bullet_lines = ""
        for b in bullets[:3]:
            bullet_lines += f"  \\item\\small {esc(clean_resume_style(b))}\n"

        projects_tex += f"""\\vspace{{2pt}}
\\noindent\\textbf{{{pname}}}\\\\[0pt]
\\noindent\\small\\textit{{{domain}}}\\enspace\\textbar\\enspace\\textit{{Tools: {ptools}}}
\\begin{{itemize}}[leftmargin=1.2em, topsep=1pt, itemsep=0pt, parsep=0pt]
{bullet_lines}\\end{{itemize}}
"""

    # ── Education ─────────────────────────────────────────────
    education_tex = ""
    for edu in profile.get("education", [])[:2]:
        degree  = esc(edu.get("degree", ""))
        inst    = esc(edu.get("institution", ""))
        year    = esc(
            edu.get("year", "")
            .replace("\u2013", "--")
            .replace("\u2014", "--")
        )
        grade   = esc(edu.get("grade", ""))

        education_tex += f"""\\vspace{{2pt}}
\\noindent\\begin{{minipage}}[t]{{0.65\\linewidth}}
  \\textbf{{{degree}}}\\\\
  \\textit{{{inst}}}
\\end{{minipage}}%
\\begin{{minipage}}[t]{{0.35\\linewidth}}
  \\raggedleft
  \\textbf{{{year}}}\\\\
  {grade}
\\end{{minipage}}\\\\[1pt]
"""

    # ── Certifications — deduplicated, em dash style ──────────
    seen_c     = set()
    cert_lines = []
    preferred_certs = profile.get("certifications", [])[:5]

    for cert in preferred_certs:
        display = clean_resume_style(cert)
        key = cert.strip().lower()
        if key not in seen_c:
            seen_c.add(key)
            cert_lines.append(esc(display))

    certs_tex = " \\\\\n".join(
        [f"\\noindent\\small\\textbullet\\ {c}" for c in cert_lines]
    )

    # ── Achievements — max 3 ─────────────────────────────────
    achievement_lines = []
    preferred_achievements = [
        "Research paper accepted and published in Springer conference proceedings (ICETCI-2025)",
        "Achieved 93.91% accuracy in face authenticity detection project",
        "Completed 240-hour Artificial Intelligence internship through SkillDzire / APSCHE",
    ]
    for ach in preferred_achievements[:3]:
        achievement_lines.append(
            f"\\noindent\\small\\textbullet\\ {esc(ach)}"
        )
    achievements_tex = " \\\\\n".join(achievement_lines)

    # ── Full LaTeX document ───────────────────────────────────
    doc = (
        r"""\documentclass[10pt, a4paper]{article}

% ---- Packages ----
\usepackage[
  top    = 0.30in,
  bottom = 0.30in,
  left   = 0.45in,
  right  = 0.45in
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
\titlespacing{\section}{0pt}{3pt}{1pt}

% ---- Spacing ----
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}

\begin{document}
"""
        + f"""
% ===== HEADER =====
\\begin{{center}}
  {{\\large\\textbf{{{name}}}}}\\\\[2pt]
  \\small
  {phone}
  \\hspace{{3pt}}\\textbar\\hspace{{3pt}}
  \\href{{mailto:{email}}}{{{email}}}
  \\hspace{{3pt}}\\textbar\\hspace{{3pt}}
  \\href{{https://{linkedin}}}{{{linkedin}}}
  \\hspace{{3pt}}\\textbar\\hspace{{3pt}}
  \\href{{https://{github}}}{{{github}}}
  \\hspace{{3pt}}\\textbar\\hspace{{3pt}}
  \\href{{https://{portfolio}}}{{{portfolio}}}
\\end{{center}}

\\vspace{{-2pt}}

% ===== PROFESSIONAL SUMMARY =====
\\section{{Professional Summary}}
\\small
{esc(sanitize_summary(resume_content.get("professional_summary", ""), profile))}

% ===== SKILLS =====
\\section{{Skills}}
\\small
\\noindent\\textbf{{Languages:}} {lang_line}\\\\[1pt]
\\noindent\\textbf{{AI \\& ML:}} {ai_line}, {ml_line}\\\\[1pt]
\\noindent\\textbf{{Software Engineering:}} {se_line}\\\\[1pt]
\\noindent\\textbf{{Data:}} {data_line}\\\\[1pt]
\\noindent\\textbf{{Libraries/Tools:}} {lib_line}, {tools_line}\\\\[1pt]
\\noindent\\textbf{{Databases:}} {db_line}

% ===== EXPERIENCE =====
\\section{{Experience}}
\\small
{experience_tex}

% ===== PROJECTS =====
\\section{{Projects}}
\\small
{projects_tex}

% ===== EDUCATION =====
\\section{{Education}}
\\small
{education_tex}

% ===== CERTIFICATIONS & COURSES =====
\\section{{Certifications \\& Courses}}
\\vspace{{2pt}}
\\small
{certs_tex}

% ===== ACHIEVEMENTS =====
\\section{{Achievements}}
\\vspace{{2pt}}
\\small
{achievements_tex}

\\end{{document}}
"""
    )
    return doc


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
