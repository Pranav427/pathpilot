from unittest.mock import patch

from application_service import generate_application_draft
from cover_letter import (
    cover_letter_body_paragraphs,
    enforce_cover_letter_constraints,
    save_cover_letter,
    unsupported_confirmed_claims,
    unsupported_profile_claims,
)
from profile import get_profile
from resume import (
    clean_resume_style,
    grounded_professional_summary,
    sanitize_resume_facts,
    save_resume,
)
from scoring import calculate_fit_score


class FakeMessageResponse:
    def __init__(self, text):
        self.content = [type("Content", (), {"text": text})()]


def test_document_text_writers_create_requested_directories(tmp_path):
    resume_path = tmp_path / "nested" / "resume.txt"
    letter_path = tmp_path / "nested" / "cover_letter.txt"

    save_resume({"professional_summary": "Verified summary."}, str(resume_path))
    save_cover_letter("Dear Hiring Team,", str(letter_path))

    assert resume_path.exists()
    assert "Verified summary." in resume_path.read_text(encoding="utf-8")
    assert letter_path.read_text(encoding="utf-8") == "Dear Hiring Team,"


def test_confirmed_familiarity_cannot_become_internship_experience():
    text = "During my internship, I worked with PyTorch and OpenAI."

    violations = unsupported_confirmed_claims(text, ["PyTorch", "OpenAI"])

    assert violations == [text]


def test_labeled_familiarity_line_does_not_inherit_later_experience_context():
    text = (
        "SKILLS\nRAG (familiarity)\n"
        "EXPERIENCE\nCompleted an Artificial Intelligence internship."
    )

    assert unsupported_confirmed_claims(text, ["RAG"]) == []


def test_grounded_summary_is_substantive_and_multi_sentence():
    summary = grounded_professional_summary(get_profile())

    assert len(summary.split()) >= 28
    assert summary.count(".") >= 2


def test_resume_summary_removes_recent_graduate_label():
    cleaned = clean_resume_style(
        "Recent Computer Science graduate with practical Python experience."
    )

    assert cleaned == (
        "Computer Science graduate with practical Python experience."
    )


def test_cross_project_metrics_are_detected():
    text = (
        "My Medical Condition Classification project processed 15,000 drug "
        "reviews and achieved 93.91% accuracy using Logistic Regression."
    )

    assert unsupported_profile_claims(text) == [text]


def test_resume_removes_face_metrics_from_medical_project():
    profile = {
        "projects": [
            {
                "name": "Medical Condition Classification from Drug Reviews",
                "domain": "Data Analytics and NLP",
                "tools": ["Python", "TF-IDF"],
                "highlights": [
                    "Built an NLP classification pipeline",
                    "Used TF-IDF feature extraction",
                ],
            }
        ]
    }
    resume = {
        "projects": [
            {
                "name": "Medical Condition Classification from Drug Reviews",
                "bullets": [
                    "Achieved 93.91% accuracy",
                    "Processed 15,000 reviews",
                    "Used TF-IDF",
                ],
            }
        ]
    }

    sanitized = sanitize_resume_facts(resume, profile)
    bullets = sanitized["projects"][0]["bullets"]

    assert all("93.91%" not in bullet for bullet in bullets)
    assert all("15,000" not in bullet for bullet in bullets)
    assert "Used TF-IDF feature extraction" in bullets


def test_cover_letter_constraints_fix_status_and_word_limit():
    profile = get_profile()
    long_paragraph = " ".join(["Relevant project evidence."] * 60)
    text = (
        "Dear Hiring Team,\n\n"
        "As a final year B.Tech student, I am interested in this role. "
        "My Python foundation matches the position.\n\n"
        f"{long_paragraph}\n\n"
        "The company interests me. I welcome the opportunity to discuss the role.\n\n"
        "Sincerely,\nObili Pranav"
    )

    constrained = enforce_cover_letter_constraints(text, profile)
    paragraphs = cover_letter_body_paragraphs(constrained, profile)

    assert len(paragraphs) == 3
    assert len(" ".join(paragraphs).split()) <= 220
    assert "student" not in constrained.lower()
    assert "graduate" in constrained.lower()


def test_application_service_sanitizes_generated_documents_end_to_end():
    profile = get_profile()
    analysis = {
        "skills": ["Python"],
        "tools": [],
        "keywords": ["Software Engineer"],
        "summary": "A Python software role.",
    }
    match = calculate_fit_score(analysis, profile)
    match.update(
        {
            "strongest_points": ["Verified Python evidence."],
            "recommendation": "Apply with verified evidence.",
        }
    )
    unsafe_resume = {
        "professional_summary": (
            "Final year Computer Science student with production RAG experience."
        ),
        "skills": {"AI": ["RAG", "Python", "Imaginary Tool"]},
        "projects": [
            {
                "name": profile["projects"][0]["name"],
                "domain": "Invented domain",
                "tools": ["Imaginary Tool"],
                "bullets": ["Processed 15,000 reviews with 93.91% accuracy"],
            }
        ],
        "certifications": ["Invented Certificate"],
        "ats_notes": [],
    }
    unsafe_cover = (
        "Dear Hiring Team,\n\n"
        "As a final year Computer Science student, I am interested in this role.\n\n"
        "I built a verified machine learning project using Python.\n\n"
        "I welcome the opportunity to discuss my application.\n\n"
        "Sincerely,\nObili Pranav"
    )

    with (
        patch("resume.create_json_with_retry", return_value=unsafe_resume),
        patch(
            "cover_letter.create_message_with_retry",
            return_value=FakeMessageResponse(unsafe_cover),
        ),
    ):
        draft = generate_application_draft(
            company_name="Example",
            job_title="Software Engineer",
            job_description=" ".join(["software"] * 50),
            job_analysis=analysis,
            profile=profile,
            match=match,
        )

    cover_paragraphs = cover_letter_body_paragraphs(
        draft.cover_letter,
        profile,
    )
    assert "student" not in draft.cover_letter.lower()
    assert len(cover_paragraphs) == 3
    assert len(" ".join(cover_paragraphs).split()) <= 220
    assert "Imaginary Tool" not in str(draft.resume)
    assert "Invented Certificate" not in draft.resume["certifications"]
    assert draft.resume["projects"][0]["tools"] == profile["projects"][0]["tools"]
