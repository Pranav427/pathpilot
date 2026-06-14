from profile import get_profile
from quality import audit_application_documents, build_ats_report
from scoring import calculate_fit_score, flatten_profile_terms, has_term


def test_profile_aliases_cover_known_equivalent_terms():
    terms = flatten_profile_terms(get_profile())
    requirements = [
        "Python coding",
        "Data handling",
        "Machine learning development",
        "Communication",
        "Collaboration",
        "Supervised learning",
        "Unsupervised learning",
        "Teamwork",
        "Eagerness to learn",
        "Database knowledge",
        "Model training and evaluation",
        "Bachelor's degree",
        "Linear programming",
        "Index and query systems",
        "Innovation",
    ]

    assert all(has_term(terms, requirement) for requirement in requirements)


def test_ats_report_uses_alias_evidence():
    resume_text = """
    PROFESSIONAL SUMMARY
    Computer Science graduate.
    SKILLS
    Python, Coding, Data Cleaning, Data Preprocessing, Machine Learning,
    Model Evaluation, Communication, Team Collaboration, scikit-learn
    PROJECTS
    Classification project
    EDUCATION
    B.Tech Computer Science
    """
    job_analysis = {
        "skills": [
            "Python coding",
            "Data handling",
            "Machine learning development",
            "Communication",
            "Collaboration",
        ],
        "tools": ["scikit-learn"],
        "keywords": [],
    }

    report = build_ats_report(resume_text, job_analysis)

    assert report["keyword_coverage"] == 100
    assert report["missing_terms"] == []


def test_ats_report_excludes_generic_title_and_brand_language():
    report = build_ats_report(
        "SKILLS\nPython\nEDUCATION\nB.Tech Computer Science",
        {
            "skills": ["Python"],
            "tools": [],
            "keywords": [
                "Software Development Engineer",
                "Customer obsession",
                "Bachelor's degree",
            ],
        },
    )

    assert report["keyword_coverage"] == 100
    assert report["context_terms"] == ["Bachelor's degree"]
    assert report["excluded_terms"] == [
        "Software Development Engineer",
        "Customer obsession",
    ]


def test_explicit_experience_requirement_reduces_fit_score():
    profile = get_profile()
    base_analysis = {
        "skills": ["Python"],
        "tools": [],
        "keywords": ["Python"],
    }
    senior_analysis = {
        **base_analysis,
        "keywords": ["Python", "5+ years experience"],
    }

    base = calculate_fit_score(base_analysis, profile)
    senior = calculate_fit_score(senior_analysis, profile)

    assert senior["seniority_penalty"] == 20
    assert senior["match_score"] < base["match_score"]


def test_legacy_document_audit_flags_outdated_and_unsupported_claims(tmp_path):
    resume_pdf = tmp_path / "resume_example.pdf"
    cover_pdf = tmp_path / "cover_example.pdf"
    resume_pdf.write_bytes(b"%PDF-1.4")
    cover_pdf.write_bytes(b"%PDF-1.4")
    resume_pdf.with_suffix(".txt").write_text(
        "Final year Computer Science student with production-ready software.",
        encoding="utf-8",
    )
    cover_pdf.with_suffix(".txt").write_text(
        "Dear Hiring Team,\n\n"
        "During my internship at SkillDzire, I worked with OpenAI.\n\n"
        "I built useful projects.\n\n"
        "I welcome a discussion.\n\n"
        "Sincerely,\nObili Pranav",
        encoding="utf-8",
    )

    issues = audit_application_documents(
        str(resume_pdf),
        str(cover_pdf),
        get_profile(),
        "User-confirmed for this application only: OpenAI",
    )

    assert any("outdated" in issue.lower() for issue in issues)
    assert any("familiarity" in issue.lower() for issue in issues)
    assert any("production" in issue.lower() for issue in issues)
