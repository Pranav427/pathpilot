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


# ── Test it with a sample job description ────────────────────────────────────
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
