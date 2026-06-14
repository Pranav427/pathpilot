import os

from dotenv import load_dotenv


load_dotenv()

def get_profile() -> dict:
    """
    Candidate master resume stored as structured data.

    Contact details come from environment variables so the repository can be
    shared publicly without exposing private information.
    """

    profile = {

        # ───────────────── BASIC DETAILS ───────────────── #

        "name": os.getenv("CANDIDATE_NAME", "Your Name"),
        "email": os.getenv("CANDIDATE_EMAIL", "your.email@example.com"),
        "phone": os.getenv("CANDIDATE_PHONE", "+91 00000 00000"),
        "linkedin": os.getenv(
            "CANDIDATE_LINKEDIN",
            "https://linkedin.com/in/your-profile",
        ),
        "github": os.getenv(
            "CANDIDATE_GITHUB",
            "https://github.com/your-username",
        ),
        "portfolio": os.getenv(
            "CANDIDATE_PORTFOLIO",
            "https://your-portfolio.example.com",
        ),
        "location": os.getenv(
            "CANDIDATE_LOCATION",
            "Your City, State, Country",
        ),

        # ───────────────── CAREER OBJECTIVE ───────────────── #

        "objective": (
            "Computer Science graduate with practical project experience in machine "
            "learning, deep learning, natural language processing, computer vision, "
            "data analysis, and AI application development. Built and evaluated "
            "multiclass text-classification and face-authenticity systems using "
            "Python, scikit-learn, PyTorch, TensorFlow, transfer learning, and "
            "Streamlit. Also experienced with software fundamentals, API integration, "
            "prompt engineering, SQL, Git, and technical "
            "documentation. Seeking an entry-level AI, machine learning, data "
            "science, or software engineering role."
        ),

        # ───────────────── TECHNICAL SKILLS ───────────────── #

        "skills": {

            "Programming Languages": [
                "Python",
                "SQL",
                "Java",
                "C++"
            ],

            "Artificial Intelligence & Machine Learning": [
                "Artificial Intelligence",
                "Machine Learning",
                "Natural Language Processing (NLP)",
                "Large Language Models (LLMs)",
                "Prompt Engineering",
                "Regression",
                "Classification",
                "Clustering",
                "Model Training",
                "Model Evaluation",
                "Model Validation",
                "Predictive Modeling",
                "Hyperparameter Tuning",
                "Cross-Validation"
            ],

            "Deep Learning & Computer Vision": [
                "Deep Learning",
                "Neural Networks",
                "Convolutional Neural Networks (CNNs)",
                "Computer Vision",
                "Image Classification",
                "Transfer Learning",
                "Image Preprocessing",
                "Data Augmentation",
                "Model Training and Evaluation",
                "ResNet50",
                "EfficientNetV2-B0"
            ],

            "AI & Application Development": [
                "LLM API Integration",
                "API Integration",
                "Machine Learning Pipelines",
                "AI Application Development",
                "Streamlit Application Development"
            ],

            "Software Fundamentals": [
                "Object-Oriented Programming (OOP)",
                "Data Structures & Algorithms",
                "Software Development Life Cycle (SDLC)",
                "Debugging",
                "Error Handling",
                "Technical Documentation"
            ],

            "Data Analysis": [
                "Data Cleaning",
                "Data Preprocessing",
                "Exploratory Data Analysis (EDA)",
                "Data Visualization",
                "Feature Engineering",
                "Statistical Analysis",
                "TF-IDF",
                "Text Classification",
                "Sentiment Analysis",
                "Text Preprocessing",
                "Stop-word Removal",
                "Lemmatization",
                "N-grams",
                "ETL Concepts"
            ],

            "Libraries & Frameworks": [
                "pandas",
                "NumPy",
                "scikit-learn",
                "NLTK",
                "PyTorch",
                "Torchvision",
                "TensorFlow",
                "Keras",
                "Matplotlib",
                "Seaborn"
            ],

            "Databases": [
                "MySQL",
                "Relational Databases"
            ],

            "Tools & Platforms": [
                "Jupyter Notebook",
                "Google Colab",
                "VS Code",
                "Git",
                "GitHub",
                "Streamlit"
            ],

            "Soft Skills": [
                "Analytical Thinking",
                "Critical Thinking",
                "Problem Solving",
                "Team Collaboration",
                "Communication",
                "Self-Learning",
                "Innovation",
                "Attention to Detail",
                "Adaptability"
            ]
        },

        # ───────────────── EXPERIENCE ───────────────── #

        "experience": [
            {
                "title": "Artificial Intelligence Intern",
                "company": "SkillDzire",
                "duration": "Apr 2024",
                "type": "Internship / Training",
                "description": (
                    "Completed a 240-hour Artificial Intelligence internship "
                    "program organized by SkillDzire in collaboration with the "
                    "Andhra Pradesh State Council of Higher Education."
                ),
                "highlights": [
                    "Completed long-term AI internship training",
                    "Built foundational understanding of artificial intelligence concepts",
                    "Strengthened AI-focused project and application readiness"
                ],
                "certificate": "AI certificate.pdf"
            },
            {
                "title": "Data Science Intern",
                "company": "Aivariant",
                "duration": "Nov 2025 - Feb 2026",
                "type": "Internship",
                "description": (
                    "Completed a Data Science internship project at Aivariant, "
                    "focused on applying data science concepts in a project-based "
                    "internship environment."
                ),
                "highlights": [
                    "Completed Data Science internship project",
                    "Applied data science concepts in a structured internship program",
                    "Received internship certificate issued on February 11, 2026"
                ],
                "certificate": "DS Intern .pdf"
            },
            {
                "title": "Data Science Intern",
                "company": "SkillDzire",
                "duration": "Oct 2024 - Mar 2025",
                "type": "Internship / Training",
                "description": (
                    "Completed a long-term Data Science internship program "
                    "organized by SkillDzire in collaboration with the Andhra "
                    "Pradesh State Council of Higher Education."
                ),
                "highlights": [
                    "Completed long-term Data Science internship program",
                    "Strengthened data science, analysis, and ML foundations",
                    "Completed program from October 2024 to March 2025"
                ],
                "certificate": "DS certificate .pdf"
            },
            {
                "title": "Full Stack Development Intern",
                "company": "Pantech e Learning",
                "duration": "Mar 2023 - May 2023",
                "type": "Internship",
                "description": (
                    "Completed a two-month internship in Full Stack Development "
                    "covering Web, Java, and Python."
                ),
                "highlights": [
                    "Completed internship in Full Stack Development",
                    "Worked with Web, Java, and Python fundamentals",
                    "Strengthened software development and coding foundations"
                ],
                "certificate": "FSJ certificate.pdf"
            }
        ],

        # ───────────────── PROJECTS ───────────────── #

        "projects": [

            {
                "name": "Medical Condition Classification from Drug Reviews",

                "domain": "Data Analytics and NLP",

                "tools": [
                    "Python",
                    "scikit-learn",
                    "TF-IDF",
                    "pandas",
                    "NumPy",
                    "NLTK",
                    "Streamlit"
                ],

                "github": os.getenv(
                    "CANDIDATE_GITHUB",
                    "https://github.com/your-username",
                ),

                "description": (
                    "Developed an NLP-based multiclass text classification "
                    "system to predict medical conditions from user drug reviews. "
                    "Applied text preprocessing, lemmatization, TF-IDF vectorization, "
                    "and machine learning algorithms including Logistic Regression, "
                    "Naive Bayes, Linear SVM, and SGD Classifier. Tuned the final "
                    "Linear SVM using five-fold GridSearchCV and achieved 96.16% "
                    "test accuracy with a 94.60% macro F1 score."
                ),

                "highlights": [
                    "Built a multiclass NLP pipeline to classify three patient conditions from drug reviews",
                    "Compared four classifiers using accuracy, precision, recall, and macro F1",
                    "Tuned Linear SVM with five-fold GridSearchCV, achieving 96.16% test accuracy",
                    "Implemented TF-IDF, lemmatization, VADER sentiment analysis, and Streamlit inference",
                    "Saved the trained model, vectorizer, and label encoder for reproducible deployment"
                ]
            },

            {
                "name": "Modern Security System for Detection of Real and Fake Human Faces",

                "domain": "Deep Learning and Computer Vision",

                "tools": [
                    "Python",
                    "PyTorch",
                    "Torchvision",
                    "TensorFlow",
                    "Keras",
                    "ResNet50",
                    "EfficientNetV2-B0",
                    "NumPy",
                    "Matplotlib",
                    "Streamlit"
                ],

                "github": os.getenv(
                    "CANDIDATE_GITHUB",
                    "https://github.com/your-username",
                ),

                "description": (
                    "Developed a deep-learning face-authenticity classification "
                    "system using the 140K Real and Fake Faces dataset. Applied "
                    "transfer learning with a pretrained ResNet50, custom classifier "
                    "layers, image preprocessing, and PyTorch training and evaluation "
                    "loops. Achieved 93.91% final test accuracy and deployed image "
                    "inference through Streamlit using a TensorFlow/Keras "
                    "EfficientNetV2-B0 model."
                ),

                "highlights": [
                    "Built a real-versus-fake face classifier using PyTorch and ResNet50 transfer learning",
                    "Implemented custom classifier layers, training, evaluation, and image inference workflows",
                    "Achieved 93.91% final test accuracy after 10 training epochs",
                    "Deployed inference with Streamlit and a TensorFlow/Keras EfficientNetV2-B0 model",
                    "Presented and published the research at ICETCI-2025 in Springer proceedings"
                ]
            }
        ],

        # ───────────────── EDUCATION ───────────────── #

        "education": [

            {
                "degree": "B.Tech in Computer Science and Engineering",
                "institution": "Annamacharya Institute of Technology and Sciences",
                "year": "2021 – 2025",
                "grade": "8.66 CGPA"
            },

            {
                "degree": "Intermediate",
                "institution": "Narayana Junior College",
                "year": "2019 – 2021",
                "grade": "868/1000"
            },

            {
                "degree": "SSC",
                "institution": "Ravindra Bharathi School",
                "year": "2018 – 2019",
                "grade": "9.3 GPA"
            }
        ],

        # ───────────────── COURSES ───────────────── #

        "courses": [

            {
                "name": "Data Science",
                "provider": "ExcelR",

                "description": (
                    "Completed Data Science programme with distinction. Learned "
                    "Python for data analysis, statistics, EDA, machine learning, "
                    "and predictive modeling. Worked on real-world datasets using "
                    "pandas, NumPy, and scikit-learn."
                )
            },

            {
                "name": "Artificial Intelligence Internship",
                "provider": "SkillDzire / APSCHE",

                "description": (
                    "Completed a 240-hour Artificial Intelligence internship "
                    "program organized by SkillDzire in collaboration with "
                    "Andhra Pradesh State Council of Higher Education. Strengthened "
                    "foundations in AI concepts, agentic AI workflows, prompt "
                    "engineering, and practical AI application thinking."
                )
            },

            {
                "name": "Full Stack Development Internship",
                "provider": "Pantech e Learning",

                "description": (
                    "Completed a two-month Full Stack Development internship "
                    "covering Web, Java, and Python, with exposure to backend "
                    "development, RESTful API concepts, authentication concepts, "
                    "database management, and the software development life cycle."
                )
            },

            {
                "name": "Crash Course on Python",
                "provider": "Coursera",

                "description": (
                    "Learned Python fundamentals including variables, loops, "
                    "functions, conditionals, and data structures."
                )
            }
        ],

        # ───────────────── CERTIFICATIONS ───────────────── #

        "certifications": [
            "Masters Program in Data Science -- FutureSkills Prime / NASSCOM -- Gold Category (96%)",
            "Data Science Programme with Distinction -- ExcelR",
            "Problem Solving (Intermediate) -- HackerRank -- Verified",
            "Artificial Intelligence -- SkillDzire / APSCHE",
        ],
        # ───────────────── PUBLICATIONS ───────────────── #

        "publications": [

            {
                "title": (
                    "A Modern Security Advance System for Detection "
                    "of Real and Fake Human Faces"
                ),

                "publisher": "Springer",

                "conference": "ICETCI-2025",

                "event": (
                    "First International Conference on Emerging Technologies "
                    "and Computing Innovations"
                ),

                "date": "February 22-23, 2025",

                "location": "Hotel Grand Rio, Nashik, India"
            }
        ],

        # ───────────────── ACHIEVEMENTS ───────────────── #

        "achievements": [

            "Earned Gold category with 96% in the FutureSkills Prime / NASSCOM Masters Program in Data Science assessment",

            "Research paper accepted and published in Springer conference proceedings (ICETCI-2025)",

            "Presented paper titled 'A Modern Security Advance System for Detection of Real and Fake Human Faces' at ICETCI-2025",

            "Achieved 93.91% accuracy in face authenticity detection project",

            "Completed 240-hour Artificial Intelligence internship through SkillDzire / APSCHE",

            "Completed Data Science programme with distinction from ExcelR",

            "Completed Full Stack Development internship covering Web, Java, and Python",

            "Earned Logical Reasoning Recognition from Lara Technologies with 38/45 marks",

            #"Selected for TCS Prime hiring program",

            "Completed multiple ML and NLP academic projects"
        ],

        # ───────────────── LANGUAGES ───────────────── #

        "languages": [
            "English",
            "Telugu",
            "Hindi"
        ],

        # ───────────────── INTERESTS ───────────────── #

        "interests": [

            "Data Science and Machine Learning",

            "Natural Language Processing (NLP)",

            "Applied Statistics and Data Analysis",

            "Data Engineering and ETL Pipelines",

            "Mathematics Driven Problem Solving"
        ]
    }

    return profile


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


# ───────────────── MAIN ───────────────── #

if __name__ == "__main__":

    profile = get_profile()

    display_profile(profile)
