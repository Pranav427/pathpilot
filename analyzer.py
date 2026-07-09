import os

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
from llm_utils import create_json_with_retry, get_llm_client, get_llm_model

# Load API key
load_dotenv()


def llm_runtime():
    """Returns the configured LLM client and model when analysis is requested."""
    return get_llm_client(), get_llm_model()


def normalize_analysis_result(result: dict) -> dict:
    """Validate analyzer output without forcing unsupported filler terms."""
    normalized = {}
    for field in ("skills", "tools", "keywords"):
        value = result.get(field)
        if not isinstance(value, list):
            raise ValueError(f"Job analysis field '{field}' must be a list")

        items = []
        seen = set()
        for item in value:
            text = str(item).strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                items.append(text)
        normalized[field] = items

    summary = str(result.get("summary", "")).strip()
    if not summary:
        raise ValueError("Job analysis summary is empty")
    normalized["summary"] = summary
    return normalized


def analyze_job(job_description: str) -> dict:
    """
    Takes a raw job description string.
    Returns a structured dictionary with skills, tools, keywords, summary.
    """

    prompt = f"""
You are an expert job description analyst with deep knowledge of tech recruiting.

Analyze the job description below and extract structured information.

---JOB DESCRIPTION START---
{job_description}
---JOB DESCRIPTION END---

Return ONLY a valid JSON object. No explanation, no markdown, no extra text.
Use exactly this structure:

{{
  "skills": ["skill1", "skill2", "skill3"],
  "tools": ["tool1", "tool2"],
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "summary": "2 sentence summary of what this role needs"
}}

Rules:
- skills: technical and soft skills mentioned or implied
- tools: specific software, platforms, or technologies
- keywords: important role, qualification, seniority, and ATS phrases
- Preserve explicit experience requirements such as "3+ years"
- Preserve explicit degree requirements such as "Bachelor's degree"
- Return only the number of items supported by the description
- An empty tools list is valid when the description names no specific tools
- Only include what is actually in the job description
"""

    client, model = llm_runtime()
    result = create_json_with_retry(
        client,
        model=model,
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        required_keys=["skills", "tools", "keywords", "summary"],
        source="Job analysis",
    )

    return normalize_analysis_result(result)


def display_analysis(analysis: dict):
    """
    Prints the analysis result in a readable format.
    """
    print("\n" + "="*50)
    print("       JOB DESCRIPTION ANALYSIS")
    print("="*50)

    print("\n📌 SKILLS:")
    for skill in analysis["skills"]:
        print(f"   • {skill}")

    print("\n🛠  TOOLS & PLATFORMS:")
    for tool in analysis["tools"]:
        print(f"   • {tool}")

    print("\n🔑 ATS KEYWORDS:")
    for keyword in analysis["keywords"]:
        print(f"   • {keyword}")

    print("\n📝 SUMMARY:")
    print(f"   {analysis['summary']}")

    print("\n" + "="*50)


def parse_resume_text(resume_text: str) -> dict:
    """Parses raw resume text using the LLM and returns a structured profile dict."""
    client, model = llm_runtime()
    
    prompt = f"""
Analyze the following candidate's raw resume text and extract the information into a structured JSON profile.
Be accurate and ground all extractions in the provided text. Do not invent any facts.

Resume text:
{resume_text}

Extract the details using this exact JSON schema:
{{
    "name": "Candidate's full name",
    "email": "Email address",
    "phone": "Phone number",
    "location": "City, State, Country",
    "linkedin": "LinkedIn profile URL (or empty string)",
    "github": "GitHub profile URL (or empty string)",
    "portfolio": "Portfolio URL (or empty string)",
    "objective": "A professional summary or career objective statement (minimum 8 words)",
    "skills": {{
        "Programming Languages": ["list of programming languages found"],
        "Artificial Intelligence & Machine Learning": ["AI/ML concepts, architectures, or models"],
        "Deep Learning & Computer Vision": ["CV, deep learning frameworks or techniques"],
        "Software Fundamentals": ["algorithms, data structures, system design, OOP"],
        "Data Analysis": ["data analysis, statistics, visualization methods"],
        "Libraries & Frameworks": ["libraries, framework names like PyTorch, NumPy, etc."],
        "Databases": ["database systems like PostgreSQL, SQLite, MySQL"],
        "Tools & Platforms": ["tools, cloud platforms, CI/CD, Git, Docker"],
        "Soft Skills": ["soft skills, leadership, communication"]
    }},
    "education": [
        {{
            "degree": "Degree name (e.g. B.S. in Computer Science)",
            "institution": "University/College name",
            "year": "Graduation year or duration (e.g. 2026)",
            "grade": "GPA/Grade (e.g. 9.1 CGPA or 3.8 GPA)"
        }}
    ],
    "experience": [
        {{
            "title": "Role/Job Title",
            "company": "Company Name",
            "duration": "Duration (e.g. Jan 2024 - Present)",
            "highlights": ["specific achievements, highlights, or responsibilities"]
        }}
    ],
    "projects": [
        {{
            "name": "Project Name",
            "domain": "Project domain/topic",
            "tools": ["tools and languages used in the project"],
            "description": "Short description of what was built and measured"
        }}
    ],
    "certifications": ["certification names"],
    "courses": ["course names (e.g. Full Stack Development - Pantech)"],
    "achievements": ["key professional achievements, metrics, or career milestones"],
    "publications": ["research papers, articles, patents, or publications"],
    "volunteer_experience": ["volunteering, leadership, or NGO activities"],
    "languages": ["spoken and written languages (e.g. English, Spanish)"],
    "awards": ["prizes, fellowships, or scholarship honors"],
    "areas_of_interest": ["career fields, topics of interest, or focus areas"]
}}

Make sure the output is a valid JSON object matching the keys above. If any section is not found in the resume, leave it as an empty string, empty list, or empty dictionary as appropriate.
"""
    
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
        }
    ]
    
    required_keys = (
        "name", "email", "phone", "location", "linkedin", "github", "portfolio",
        "objective", "skills", "education", "experience", "projects", "certifications",
        "courses", "achievements", "publications", "volunteer_experience", "languages",
        "awards", "areas_of_interest"
    )
    
    result = create_json_with_retry(
        client,
        model=model,
        max_tokens=4000,
        messages=messages,
        required_keys=required_keys,
        source="Resume Parser",
    )
    
    if "experience" in result and isinstance(result["experience"], list):
        for exp in result["experience"]:
            if "highlights" in exp:
                exp["highlights"] = [str(h) for h in exp["highlights"]]
                exp["description"] = " ".join(exp["highlights"])
                exp["type"] = "Experience"
                
    if "projects" in result and isinstance(result["projects"], list):
        for proj in result["projects"]:
            desc = proj.get("description", "")
            from profile import extract_metrics_from_text
            proj["highlights"] = [desc] if desc else []
            proj["github"] = result.get("github", "")
            proj["grounding_metrics"] = extract_metrics_from_text(desc)
            
    return result


if __name__ == "__main__":

    sample_job = """
Job Title: Data Science Intern
Company: Skillzenloop
Location: Remote
Job Type: Full-time Internship
Duration: 1–3 Months
Stipend: ₹19,000 per month


About Skillzenloop:
Skillzenloop is a growing skill development and training organization dedicated to bridging the gap between academic learning and industry requirements. We offer structured internship programs, real-world projects, and mentorship to help candidates build job-ready skills in data analytics, technology, and business domains.


Role Overview:
We are looking for a Data Science Intern who is passionate about analyzing data, building models, and deriving actionable insights. This role provides hands-on exposure to data science workflows and real-world problem solving.


Key Responsibilities:


* Aggregate and preprocess data from diverse sources for analysis
* Perform statistical analysis to uncover trends and correlations
* Develop basic predictive or classification models
* Create visualizations and analytical summaries for stakeholders
* Work with Python libraries such as pandas, NumPy, and scikit-learn
* Assist in translating business problems into data solutions
* Document methodologies, experiments, and outputs


Required Qualifications:


* Currently pursuing or recently completed a degree in Data Science, Computer Science, Statistics, or a related field
* Strong knowledge of Python programming
* Basic understanding of machine learning algorithms
* Familiarity with data visualization tools
* Understanding of statistics and probability concepts
* Strong analytical and problem-solving skills
* Ability to work independently in a remote setup


Preferred Skills:


* Experience with data science projects or coursework
* Familiarity with TensorFlow or PyTorch
* Basic knowledge of SQL


What You Will Gain:


* Hands-on experience in data science and analytics projects
* Exposure to real-world datasets and workflows
* Mentorship from experienced professionals
* Opportunity to enhance technical and analytical skills
* Certificate of completion based on performance


Skillzenloop is an equal opportunity employer. We value diversity and are committed to creating an inclusive environment for all interns.


    """

    print("Analyzing job description...")
    analysis = analyze_job(sample_job)
    display_analysis(analysis)
