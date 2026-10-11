from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import cover_letter
import resume
from document_standards import COVER_LETTER_MAX_WORDS, format_uk_date, sign_off_for

LEGACY_FOUNDER_TERMS = ("8.87", "Springer", "CGPA", "B.Tech", "93.91", "SkillDzire")

PROFILE = {
    "name": "Amelia Clarke",
    "email": "amelia@example.com",
    "phone": "+44 7700 900123",
    "location": "Leeds, UK",
    "linkedin": "linkedin.com/in/ameliaclarke",
    "education": [
        {
            "degree": "BSc Economics (Hons)",
            "institution": "University of Leeds",
            "year": "2022 - 2025",
            "grade": "2:1",
            "modules": ["Econometrics", "Microeconomics"],
        }
    ],
    "experience": [
        {
            "title": "Finance Intern",
            "company": "Northern Bank",
            "duration": "Jun 2024 - Aug 2024",
            "highlights": ["Reconciled weekly ledgers for a team of six analysts."],
        }
    ],
    "projects": [
        {
            "name": "Housing Price Study",
            "domain": "Applied econometrics",
            "tools": ["Stata", "Excel"],
            "highlights": ["Modelled regional housing prices using regression analysis."],
            "grounding_metrics": [],
        }
    ],
    "skills": {"Analysis": ["Stata", "Excel"], "Communication": ["Presenting"]},
    "certifications": [],
    "achievements": ["Dean's List 2024"],
}
MATCH = {"matched_skills": ["Excel"], "strongest_points": ["Econometrics"]}
ANALYSIS = {"summary": "Analyst role", "skills": ["Excel"], "tools": [], "keywords": ["finance"]}


def test_uk_date_format():
    assert format_uk_date(date(2026, 10, 1)) == "1 October 2026"


def test_sign_off_matches_salutation():
    assert sign_off_for("Dear Hiring Manager") == "Yours faithfully"
    assert sign_off_for("Dear Ms Patel") == "Yours sincerely"


def test_cover_letter_allows_four_paragraphs_and_uses_uk_format():
    text = "Dear Hiring Manager,\n\n" + "\n\n".join(
        f"Paragraph {i} shows relevant evidence." for i in range(4)
    ) + "\n\nSincerely,\nAmelia Clarke"
    result = cover_letter.enforce_cover_letter_constraints(text, PROFILE)
    assert result.startswith("Dear Hiring Manager,")
    assert result.endswith("Yours faithfully,\nAmelia Clarke")
    assert len(cover_letter.cover_letter_body_paragraphs(result, PROFILE)) == 4


def test_cover_letter_word_cap_is_300():
    long = " ".join(["Relevant evidence sentence here."] * 40)
    text = f"Dear Hiring Manager,\n\n{long}\n\n{long}\n\n{long}\n\nYours faithfully,\nAmelia Clarke"
    result = cover_letter.enforce_cover_letter_constraints(text, PROFILE)
    body = cover_letter.cover_letter_body_paragraphs(result, PROFILE)
    assert len(" ".join(body).split()) <= COVER_LETTER_MAX_WORDS


def test_cover_letter_prompt_has_no_founder_specific_content():
    captured = {}

    def fake_create(client, **kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        body = "Dear Hiring Manager,\n\nOne.\n\nTwo.\n\nThree.\n\nYours faithfully,\nAmelia Clarke"
        return SimpleNamespace(content=[SimpleNamespace(text=body)])

    strategy = {"positioning_strategy": "x", "interviewer_takeaway": "y", "summary_focus": "z", "what_to_deemphasize": []}
    with patch.object(cover_letter, "llm_runtime", return_value=(object(), "m")), \
         patch.object(cover_letter, "create_message_with_retry", side_effect=fake_create):
        cover_letter.generate_cover_letter(ANALYSIS, PROFILE, MATCH, "Acme", "Analyst", strategy=strategy)

    prompt = captured["prompt"]
    assert not any(term in prompt for term in LEGACY_FOUNDER_TERMS)
    assert "British English" in prompt
    assert "Dear Hiring Manager" in prompt


def test_resume_prompt_has_no_founder_specific_content():
    captured = {}

    def fake_json(client, **kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return {"professional_summary": "", "skills": {}, "projects": [], "certifications": [], "ats_notes": []}

    strategy = {
        "positioning_strategy": "x", "interviewer_takeaway": "y", "summary_focus": "z",
        "what_to_deemphasize": [], "project_focus": [], "skills_focus": [],
    }
    with patch.object(resume, "llm_runtime", return_value=(object(), "m")), \
         patch.object(resume, "create_json_with_retry", side_effect=fake_json):
        resume.generate_resume(ANALYSIS, PROFILE, MATCH, strategy=strategy)

    prompt = captured["prompt"]
    assert not any(term in prompt for term in LEGACY_FOUNDER_TERMS)
    assert "British English" in prompt


def test_grounded_summary_uses_the_users_own_profile():
    summary = resume.grounded_professional_summary(PROFILE)
    assert "BSc Economics" in summary and "University of Leeds" in summary
    assert not any(term in summary for term in LEGACY_FOUNDER_TERMS)
    assert len(summary.split()) >= 20


def test_latex_cv_is_uk_style_and_profile_driven():
    content = {"professional_summary": resume.grounded_professional_summary(PROFILE),
               "skills": PROFILE["skills"], "projects": [], "certifications": []}
    tex = resume.build_latex_resume(PROFILE, ANALYSIS, MATCH, content)
    assert "a4paper" in tex
    assert tex.index("Personal Profile") < tex.index("Education") < tex.index("Experience")
    assert tex.index("Experience") < tex.index("Projects") < tex.index("Skills")
    assert "Leeds, UK" in tex and "Dean's List 2024" in tex
    assert "Languages" not in tex  # none on the profile
    assert not any(term in tex for term in LEGACY_FOUNDER_TERMS)


def test_languages_and_right_to_work_are_opt_in():
    profile = {**PROFILE, "languages": ["English", "Hindi"], "right_to_work": "Graduate Route visa holder"}
    content = {"professional_summary": "x " * 30, "skills": {}, "projects": [], "certifications": []}
    off = resume.build_latex_resume(profile, ANALYSIS, MATCH, content)
    assert "Hindi" in off and "Graduate Route" not in off
    on = resume.build_latex_resume({**profile, "show_right_to_work": True}, ANALYSIS, MATCH, content)
    assert "Graduate Route visa holder" in on
    assert "Graduate Route visa holder" in resume.resume_to_text(content, {**profile, "show_right_to_work": True})


def test_two_page_length_is_not_flagged():
    from quality import build_ats_report
    text = "Education Skills Projects " + " ".join(["analysis"] * 900)
    report = build_ats_report(text, ANALYSIS)
    assert "length" not in " ".join(report.get("issues", [])).lower()


def test_resume_summary_drops_invented_right_to_work_claims():
    content = {
        "professional_summary": (
            "BSc Economics graduate from the University of Leeds with a 2:1 and Excel skills. "
            "Possesses the right to work in the UK without sponsorship. "
            "Ready to support the pricing team."
        ),
        "skills": {}, "projects": [], "certifications": [],
    }
    safe = resume.sanitize_resume_facts(content, PROFILE)
    summary = safe["professional_summary"].lower()
    assert "right to work" not in summary and "sponsorship" not in summary


def test_cover_letter_right_to_work_sentences_are_detected_and_removed():
    from document_standards import strip_right_to_work_claims
    text = "I studied economics. I am eligible to work in the UK without a visa. I enjoy analysis."
    assert cover_letter._right_to_work_sentences(text)
    assert strip_right_to_work_claims(text) == "I studied economics. I enjoy analysis."
