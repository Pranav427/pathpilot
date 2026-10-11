import os
import re
from copy import deepcopy

from dotenv import load_dotenv


load_dotenv()


def split_profile_items(value: str) -> list[str]:
    """Splits comma or newline separated profile values without duplicates."""
    items = []
    seen = set()
    for raw_item in str(value).replace("\n", ",").split(","):
        item = raw_item.strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            items.append(item)
    return items


def extract_metrics_from_text(text: str) -> list[str]:
    """Auto-extracts potential grounding metrics (percentages, sizes, counts) from text."""
    if not text:
        return []
    # Match metrics like 91.2%, 96%, 140K, 12,000
    pattern = r"\b\d+(?:\.\d+)?%|\b\d+K\b|\b\d{1,3}(?:,\d{3})+\b"
    matches = re.findall(pattern, text)
    seen = set()
    return [m for m in matches if not (m.lower() in seen or seen.add(m.lower()))]


def parse_profile_rows(value: str, fields: list[str]) -> list[dict]:
    """Parses one pipe-delimited profile record per line."""
    records = []
    for line_number, raw_line in enumerate(str(value).splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        values = [part.strip() for part in line.split("|")]
        if len(values) != len(fields):
            raise ValueError(
                f"Line {line_number} must contain {len(fields)} values "
                "separated by |."
            )
        records.append(dict(zip(fields, values)))
    return records


def build_session_profile(
    *,
    name: str,
    email: str,
    phone: str,
    location: str,
    linkedin: str,
    github: str,
    portfolio: str,
    objective: str,
    skills: dict[str, str],
    education_text: str,
    experience_text: str,
    projects_text: str,
    certifications_text: str,
) -> dict:
    """Builds a validated, session-only candidate profile from UI fields."""
    profile = {
        "name": str(name).strip(),
        "email": str(email).strip(),
        "phone": str(phone).strip(),
        "linkedin": str(linkedin).strip(),
        "github": str(github).strip(),
        "portfolio": str(portfolio).strip(),
        "location": str(location).strip(),
        "objective": str(objective).strip(),
        "skills": {
            category: split_profile_items(value)
            for category, value in skills.items()
            if split_profile_items(value)
        },
        "education": parse_profile_rows(
            education_text,
            ["degree", "institution", "year", "grade"],
        ),
        "experience": [],
        "projects": [],
        "certifications": [
            line.strip()
            for line in str(certifications_text).splitlines()
            if line.strip()
        ],
        "courses": [],
        "publications": [],
        "achievements": [],
        "languages": [],
        "interests": [],
    }

    for record in parse_profile_rows(
        experience_text,
        ["title", "company", "duration", "highlights"],
    ):
        highlights = split_profile_items(record.pop("highlights"))
        profile["experience"].append(
            {
                **record,
                "type": "Experience",
                "description": " ".join(highlights),
                "highlights": highlights,
            }
        )

    for record in parse_profile_rows(
        projects_text,
        ["name", "domain", "tools", "description"],
    ):
        tools = split_profile_items(record.pop("tools"))
        description = record.pop("description")
        profile["projects"].append(
            {
                **record,
                "tools": tools,
                "description": description,
                "highlights": [description] if description else [],
                "github": profile["github"],
                "grounding_metrics": extract_metrics_from_text(description),
            }
        )

    validate_candidate_profile(profile)
    return profile


def validate_candidate_profile(profile: dict) -> None:
    """Requires enough verified evidence for responsible matching."""
    missing = []
    if len(str(profile.get("name", "")).strip()) < 2:
        missing.append("name")
    if len(str(profile.get("objective", "")).split()) < 8:
        missing.append("professional summary")
    skill_count = sum(
        len(items) for items in profile.get("skills", {}).values()
    )
    if skill_count < 3:
        missing.append("at least three skills")
    if not profile.get("education"):
        missing.append("education")
    if not profile.get("projects") and not profile.get("experience"):
        missing.append("at least one project or experience entry")
    if missing:
        raise ValueError(
            "Complete the tester profile before using it: "
            + ", ".join(missing)
            + "."
        )


def copy_profile(profile: dict) -> dict:
    """Returns an isolated profile copy for session state."""
    return deepcopy(profile)


def get_demo_profile() -> dict:
    """A fictional demo candidate used for the demo account, tests and local trials.

    Every detail here is invented; real users supply their own profile. It is
    deliberately small but covers each section the document generators use.
    """
    return {
        "name": "Amelia Clarke",
        "email": "amelia.clarke@example.com",
        "phone": "+44 7700 900123",
        "linkedin": "linkedin.com/in/amelia-clarke-demo",
        "github": "github.com/amelia-clarke-demo",
        "portfolio": "",
        "location": "Leeds, UK",
        "objective": (
            "Computer Science graduate with practical project experience in "
            "machine learning, natural language processing, computer vision and "
            "data analysis. Built and evaluated a text-classification model and an "
            "image-classification model using Python, scikit-learn and PyTorch. "
            "Comfortable with SQL, Git and technical documentation. Seeking a "
            "graduate role in data science, machine learning or software engineering."
        ),
        "skills": {
            "Programming Languages": ["Python", "SQL", "Java", "C++"],
            "Artificial Intelligence & Machine Learning": [
                "Machine Learning",
                "Natural Language Processing (NLP)",
                "Regression",
                "Classification",
                "Model Evaluation",
                "Cross-Validation",
            ],
            "Deep Learning & Computer Vision": [
                "Deep Learning",
                "Neural Networks",
                "Computer Vision",
                "Image Classification",
                "Transfer Learning",
            ],
            "AI & Application Development": [
                "API Integration",
                "Streamlit Application Development",
            ],
            "Software Fundamentals": [
                "Object-Oriented Programming (OOP)",
                "Data Structures & Algorithms",
                "Software Development Life Cycle (SDLC)",
                "Debugging",
                "Technical Documentation",
            ],
            "Data Analysis": [
                "Data Cleaning",
                "Exploratory Data Analysis (EDA)",
                "Data Visualization",
                "Feature Engineering",
                "Statistical Analysis",
                "TF-IDF",
                "Text Classification",
            ],
            "Libraries & Frameworks": [
                "pandas",
                "NumPy",
                "scikit-learn",
                "NLTK",
                "PyTorch",
                "Torchvision",
                "Matplotlib",
                "Seaborn",
            ],
            "Databases": ["MySQL", "PostgreSQL"],
            "Tools & Platforms": [
                "Jupyter Notebook",
                "VS Code",
                "Git",
                "GitHub",
                "Streamlit",
            ],
            "Soft Skills": [
                "Analytical Thinking",
                "Problem Solving",
                "Team Collaboration",
                "Communication",
                "Attention to Detail",
            ],
        },
        "experience": [
            {
                "title": "Data Analyst Intern",
                "company": "Brightfield Analytics Ltd",
                "duration": "Jun 2024 - Aug 2024",
                "type": "Internship",
                "description": (
                    "Summer internship supporting a retail analytics team with "
                    "reporting and data preparation."
                ),
                "highlights": [
                    "Cleaned and prepared weekly sales datasets in Python and pandas for the reporting team.",
                    "Built SQL queries and Matplotlib charts used in a monthly performance review.",
                ],
            },
            {
                "title": "Software Development Intern",
                "company": "Calder Valley Software",
                "duration": "Jul 2023 - Aug 2023",
                "type": "Internship",
                "description": "Short internship in a small web development team.",
                "highlights": [
                    "Fixed front-end bugs and wrote unit tests for a customer booking web application.",
                ],
            },
        ],
        "projects": [
            {
                "name": "Customer Review Sentiment Classifier",
                "domain": "Data Analytics and NLP",
                "tools": ["Python", "scikit-learn", "NLTK", "TF-IDF", "pandas"],
                "github": "",
                "description": (
                    "Text-classification pipeline that predicts the sentiment of "
                    "customer reviews using TF-IDF features and linear models."
                ),
                "highlights": [
                    "Preprocessed 12,000 customer reviews with tokenisation, stop-word removal and lemmatisation.",
                    "Compared Logistic Regression and Naive Bayes models using cross-validation, reaching 91.2% accuracy.",
                ],
                "grounding_metrics": ["91.2%", "12,000"],
            },
            {
                "name": "Plant Disease Image Classifier",
                "domain": "Deep Learning and Computer Vision",
                "tools": ["Python", "PyTorch", "Torchvision", "Matplotlib"],
                "github": "",
                "description": (
                    "Image classifier for plant leaf diseases built with transfer "
                    "learning and data augmentation."
                ),
                "highlights": [
                    "Fine-tuned a pretrained ResNet model on 8,000 leaf images across 5 disease classes.",
                    "Applied data augmentation and early stopping, reaching 94.5% test accuracy.",
                ],
                "grounding_metrics": ["94.5%", "8,000", "5"],
            },
        ],
        "education": [
            {
                "degree": "BSc Computer Science (Hons)",
                "institution": "University of Leeds",
                "year": "2022 \u2013 2025",
                "grade": "2:1",
                "modules": [
                    "Machine Learning",
                    "Databases",
                    "Algorithms and Data Structures",
                    "Software Engineering",
                ],
            },
            {
                "degree": "A-levels: Mathematics, Further Mathematics, Physics",
                "institution": "Aire Valley Sixth Form College",
                "year": "2020 \u2013 2022",
                "grade": "A*AA",
            },
        ],
        "courses": [
            {
                "name": "Machine Learning Specialisation",
                "provider": "Online course",
                "description": "Self-study course covering supervised learning, model evaluation and neural networks.",
            }
        ],
        "certifications": ["Machine Learning Specialisation (online course)"],
        "publications": [],
        "achievements": [
            "Dean's List for academic performance, 2024",
            "Finalist, university hackathon 2023",
        ],
        "languages": ["English (native)", "French (B1)"],
        "interests": ["Data science", "Machine learning", "Open-source software"],
    }


def get_profile() -> dict:
    """Backwards-compatible alias: the fictional demo profile."""
    return get_demo_profile()


# ───────────────── DISPLAY FUNCTION ───────────────── #

def display_profile(profile: dict):

    print("\n" + "=" * 70)
    print("                    CANDIDATE PROFILE")
    print("=" * 70)

    # Basic Info
    print(f"\n👤 Name       : {profile['name']}")
    print(f"📧 Email      : {profile['email']}")
    print(f"📱 Phone      : {profile['phone']}")
    print(f"🔗 LinkedIn   : {profile['linkedin']}")
    print(f"💻 GitHub     : {profile['github']}")
    print(f"🌐 Portfolio  : {profile.get('portfolio', 'Not provided')}")
    print(f"📍 Location   : {profile['location']}")

    # Objective
    print("\n🎯 CAREER OBJECTIVE:")
    print(f"\n{profile['objective']}")

    # Skills
    print("\n🛠 TECHNICAL SKILLS:")

    for category, items in profile["skills"].items():

        print(f"\n{category}:")

        for item in items:
            print(f"   • {item}")

    # Experience
    print("\n💼 EXPERIENCE / INTERNSHIPS:")

    for exp in profile.get("experience", []):
        print("\n" + "-" * 70)
        print(f"\n📌 {exp['title']} — {exp['company']}")
        print(f"   Duration : {exp['duration']}")
        print(f"   Type     : {exp['type']}")
        print(f"\n   Description:")
        print(f"   {exp['description']}")
        print(f"\n   Highlights:")
        for h in exp.get("highlights", []):
            print(f"   ✓ {h}")

    # Projects
    print("\n🚀 PROJECTS:")

    for proj in profile["projects"]:

        print("\n" + "-" * 70)

        print(f"\n📌 {proj['name']}")

        print(f"   Domain     : {proj['domain']}")

        print(f"   Tools      : {', '.join(proj['tools'])}")

        print(f"   GitHub     : {proj['github']}")

        print(f"\n   Description:")
        print(f"   {proj['description']}")

        print(f"\n   Highlights:")

        for h in proj["highlights"]:
            print(f"   ✓ {h}")

    # Education
    print("\n🎓 EDUCATION:")

    for edu in profile["education"]:

        print(
            f"\n   • {edu['degree']}"
            f"\n     {edu['institution']}"
            f"\n     {edu['year']} | {edu['grade']}"
        )

    # Courses
    print("\n📚 COURSES:")

    for course in profile["courses"]:

        print(f"\n   • {course['name']} — {course['provider']}")
        print(f"     {course['description']}")

    # Certifications
    print("\n📜 CERTIFICATIONS:")

    for cert in profile["certifications"]:
        print(f"   • {cert}")

    # Publications
    print("\n📖 PUBLICATIONS:")

    for pub in profile["publications"]:

        print(f"\n   • {pub['title']}")
        print(f"     Publisher : {pub['publisher']}")
        print(f"     Conference: {pub['conference']}")

    # Achievements
    print("\n🏆 ACHIEVEMENTS:")

    for achievement in profile["achievements"]:
        print(f"   • {achievement}")

    # Languages
    print("\n🗣 LANGUAGES:")

    for lang in profile["languages"]:
        print(f"   • {lang}")

    # Interests
    print("\n💡 AREAS OF INTEREST:")

    for interest in profile["interests"]:
        print(f"   • {interest}")

    print("\n" + "=" * 70)


def get_blank_profile() -> dict:
    """Returns a completely empty candidate profile structure."""
    return {
        "name": "",
        "email": "",
        "phone": "",
        "linkedin": "",
        "github": "",
        "portfolio": "",
        "location": "",
        "objective": "",
        "skills": {
            "Programming Languages": [],
            "Artificial Intelligence & Machine Learning": [],
            "Deep Learning & Computer Vision": [],
            "Software Fundamentals": [],
            "Data Analysis": [],
            "Libraries & Frameworks": [],
            "Databases": [],
            "Tools & Platforms": [],
            "Soft Skills": [],
        },
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "courses": [],
        "achievements": [],
        "publications": [],
        "volunteer_experience": [],
        "languages": [],
        "awards": [],
        "areas_of_interest": [],
    }


# ───────────────── MAIN ───────────────── #

if __name__ == "__main__":

    profile = get_profile()

    display_profile(profile)
