import pytest
from profile import extract_metrics_from_text
from resume import sanitize_resume_facts
from cover_letter import unsupported_profile_claims
from quality import audit_application_documents


def test_extract_metrics_from_text():
    text = "Achieved 95.5% accuracy on 10,000 samples and 200K images in 5 epochs."
    metrics = extract_metrics_from_text(text)
    assert "95.5%" in metrics
    assert "200K" in metrics
    assert "10,000" in metrics
    assert "5" not in metrics  # Should not match single low digit counts without suffix


def test_sanitize_resume_facts_dynamic():
    custom_profile = {
        "skills": {"Languages": ["Python"]},
        "projects": [
            {
                "name": "Speech Ingestion Platform",
                "domain": "Audio NLP",
                "tools": ["Python", "Librosa"],
                "highlights": ["Processed 5,000 files with 98% accuracy."],
                "grounding_metrics": ["98%", "5,000"]
            },
            {
                "name": "Distributed Web Crawler",
                "domain": "Web Scraper",
                "tools": ["Python", "Go"],
                "highlights": ["Indexed 500K pages in 2 hours."],
                "grounding_metrics": ["500K"]
            }
        ]
    }
    
    # Sentence has Speech project keyword but Crawler project metric (500K)
    unsafe_resume = {
        "professional_summary": (
            "Computer Science graduate who built a Speech Ingestion Platform indexing 500K files with 98% accuracy."
        ),
        "skills": {"Languages": ["Python"]},
        "projects": [
            {
                "name": "Speech Ingestion Platform",
                "domain": "Audio NLP",
                "tools": ["Python", "Librosa"],
                "bullets": ["Processed 5,000 files with 98% accuracy."]
            }
        ],
        "certifications": []
    }
    
    sanitized = sanitize_resume_facts(unsafe_resume, custom_profile)
    summary = sanitized["professional_summary"]
    # The sentence with crawler metrics under the speech project keywords should be dropped,
    # falling back to the grounded professional summary text.
    assert "500K" not in summary
    assert "Speech Ingestion Platform" in summary or "Computer Science graduate" in summary


def test_unsupported_profile_claims_dynamic():
    custom_profile = {
        "projects": [
            {
                "name": "Speech Ingestion Platform",
                "domain": "Audio NLP",
                "tools": ["Python"],
                "highlights": [],
                "grounding_metrics": ["98%"]
            },
            {
                "name": "Distributed Web Crawler",
                "domain": "Web Scraper",
                "tools": ["Python"],
                "highlights": [],
                "grounding_metrics": ["500K"]
            }
        ],
        "experience": [
            {
                "company": "TechCorp",
                "title": "Software Intern",
                "description": "Learned standard python software fundamentals."
            }
        ]
    }
    
    # 1. Paragraph mixing Crawler metric (500K) into Speech project context
    text_mix = (
        "Dear Hiring Team,\n\n"
        "I built an Audio NLP Speech Ingestion Platform that crawled 500K sound files.\n\n"
        "Sincerely,\nCandidate"
    )
    violations = unsupported_profile_claims(text_mix, profile=custom_profile)
    assert len(violations) > 0
    assert "Speech Ingestion Platform" in violations[0]
    
    # 2. Paragraph claiming restricted tools under an internship that doesn't document them
    text_internship = (
        "Dear Hiring Team,\n\n"
        "During my internship at TechCorp, I engineered agentic workflows and prompt engineering.\n\n"
        "Sincerely,\nCandidate"
    )
    violations = unsupported_profile_claims(text_internship, profile=custom_profile)
    assert len(violations) > 0
    assert "TechCorp" in violations[0]


def test_audit_application_documents_dynamic(tmp_path):
    custom_profile = {
        "projects": [
            {
                "name": "Speech Ingestion Platform",
                "domain": "Audio NLP",
                "tools": ["Python"],
                "highlights": [],
                "grounding_metrics": ["98%"]
            },
            {
                "name": "Distributed Web Crawler",
                "domain": "Web Scraper",
                "tools": ["Python"],
                "highlights": [],
                "grounding_metrics": ["500K"]
            }
        ]
    }
    
    # Write temporary resume file with leak
    resume_content = (
        "PROFESSIONAL SUMMARY\n"
        "Speech Ingestion Platform: worked on Audio NLP classification with 500K files."
    )
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text(resume_content, encoding="utf-8")
    
    # Run audit
    issues = audit_application_documents(
        resume_path=str(resume_file).replace(".txt", ".pdf"),
        cover_letter_path="",
        profile=custom_profile
    )
    
    assert any("Speech Ingestion Platform" in issue and "metrics" in issue for issue in issues)


def test_generate_application_draft_attaches_confirmed_details():
    from application_service import generate_application_draft
    from profile import get_profile
    from scoring import calculate_fit_score
    from unittest.mock import patch

    profile = get_profile()
    analysis = {
        "skills": ["Python"],
        "tools": [],
        "keywords": ["Software Engineer"],
        "summary": "A Python software role.",
    }
    match = calculate_fit_score(analysis, profile)

    confirmed_terms = ["PyTorch"]
    confirmed_details = {"PyTorch": "Used to train a face detection model for 10 epochs."}

    # We patch the calls to inspect their received arguments
    with (
        patch("application_service.generate_resume") as mock_gen_resume,
        patch("application_service.generate_cover_letter") as mock_gen_letter,
        patch("application_service.build_ats_report") as mock_ats,
        patch("application_service.build_recruiter_message") as mock_recruiter
    ):
        mock_gen_resume.return_value = {
            "professional_summary": "Mock professional summary.",
            "skills": {"Tools": ["PyTorch"]},
            "projects": [],
            "certifications": []
        }
        mock_gen_letter.return_value = "Mock cover letter text."
        mock_ats.return_value = {"score": 80, "keyword_coverage": 70, "recommendations": []}
        mock_recruiter.return_value = "Mock recruiter message."
        
        generate_application_draft(
            company_name="Google",
            job_title="Software Engineer",
            job_description="We need a python engineer who knows PyTorch. " * 30,
            confirmed_terms=confirmed_terms,
            confirmed_details=confirmed_details,
            job_analysis=analysis,
            profile=profile,
            match=match
        )

        called_profile = mock_gen_resume.call_args[0][1]
        assert called_profile["_application_confirmed_details"] == confirmed_details
        assert "PyTorch" in called_profile["_application_confirmed_terms"]

