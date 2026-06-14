import os
import tempfile
from unittest.mock import patch

from application_service import (
    ApplicationDraft,
    save_application_draft,
    validate_application_identity,
)
from tracker import (
    get_stats,
    init_db,
    list_applications,
    list_job_search_runs,
    record_application,
    record_job_search_run,
    update_application_status,
)


def test_saved_application_paths_are_unique():
    draft = ApplicationDraft(
        company_name="Test Company",
        job_title="Engineer",
        source_url="",
        job_analysis={},
        profile={"skills": {}},
        match={"match_score": 50},
        resume={},
        cover_letter="Cover letter",
        ats_report={"keyword_coverage": 50},
    )

    with tempfile.TemporaryDirectory() as output_dir:
        with (
            patch("application_service.save_resume"),
            patch("application_service.save_cover_letter"),
            patch("application_service.compile_resume", return_value=True),
            patch("application_service.compile_letter", return_value=True),
            patch(
                "application_service.record_application",
                side_effect=[1, 2],
            ),
        ):
            first = save_application_draft(draft, output_dir)
            second = save_application_draft(draft, output_dir)

    assert first.resume_pdf != second.resume_pdf
    assert first.cover_letter_pdf != second.cover_letter_pdf


def test_pdf_failure_does_not_create_tracker_record():
    draft = ApplicationDraft(
        company_name="Test Company",
        job_title="Engineer",
        source_url="",
        job_analysis={},
        profile={"skills": {}},
        match={"match_score": 50},
        resume={},
        cover_letter="Cover letter",
        ats_report={"keyword_coverage": 50},
    )

    with tempfile.TemporaryDirectory() as output_dir:
        with (
            patch("application_service.save_resume"),
            patch("application_service.save_cover_letter"),
            patch("application_service.compile_resume", return_value=False),
            patch("application_service.compile_letter", return_value=True),
            patch("application_service.write_fallback_pdf", return_value=False),
            patch("application_service.record_application") as record,
        ):
            try:
                save_application_draft(draft, output_dir)
            except RuntimeError:
                pass
            else:
                raise AssertionError("Expected PDF failure to stop saving")

    record.assert_not_called()


def test_failed_save_removes_partial_output_files(tmp_path):
    draft = ApplicationDraft(
        company_name="Test Company",
        job_title="Engineer",
        source_url="",
        job_analysis={},
        profile={"name": "Test Candidate", "skills": {}},
        match={"match_score": 50},
        resume={},
        cover_letter="Cover letter",
        ats_report={"keyword_coverage": 50},
    )

    def write_resume(_content, path):
        with open(path, "w", encoding="utf-8") as file:
            file.write("resume")

    def write_cover(_content, path):
        with open(path, "w", encoding="utf-8") as file:
            file.write("cover")

    with (
        patch("application_service.save_resume", side_effect=write_resume),
        patch("application_service.save_cover_letter", side_effect=write_cover),
        patch("application_service.compile_resume", return_value=False),
        patch("application_service.compile_letter", return_value=True),
        patch("application_service.write_fallback_pdf", return_value=False),
    ):
        try:
            save_application_draft(draft, str(tmp_path))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected PDF failure to stop saving")

    assert list(tmp_path.iterdir()) == []


def test_pdf_fallback_allows_cloud_save_without_latex(tmp_path):
    draft = ApplicationDraft(
        company_name="Test Company",
        job_title="Engineer",
        source_url="",
        job_analysis={},
        profile={"name": "Test Candidate", "skills": {}},
        match={"match_score": 50},
        resume={"professional_summary": "Verified Python experience."},
        cover_letter="Dear Hiring Team,\n\nVerified Python experience.",
        ats_report={"keyword_coverage": 50},
    )

    def write_pdf(_text, path):
        with open(path, "wb") as file:
            file.write(b"%PDF-1.4 fallback")
        return True

    with (
        patch("application_service.compile_resume", return_value=False),
        patch("application_service.compile_letter", return_value=False),
        patch("application_service.write_fallback_pdf", side_effect=write_pdf),
        patch("application_service.record_application", return_value=7),
    ):
        saved = save_application_draft(draft, str(tmp_path))

    assert saved.application_id == 7
    assert os.path.exists(saved.resume_pdf)
    assert os.path.exists(saved.cover_letter_pdf)


def test_tracker_crud_with_temporary_database():
    descriptor, db_path = tempfile.mkstemp(suffix=".db")
    os.close(descriptor)
    os.remove(db_path)

    try:
        init_db(db_path)
        application_id = record_application(
            company_name="Test Company",
            job_title="Engineer",
            match={"match_score": 75},
            ats_report={"keyword_coverage": 80},
            resume_path="resume.pdf",
            cover_letter_path="cover.pdf",
            job_analysis={},
            source_url="https://example.com/job",
            notes="Confirmed terms",
            db_path=db_path,
        )

        update_application_status(
            application_id,
            "APPLIED",
            db_path=db_path,
        )
        application = list_applications(db_path=db_path)[0]
        stats = get_stats(db_path)

        assert application["status"] == "APPLIED"
        assert application["source_url"] == "https://example.com/job"
        assert application["notes"] == "Confirmed terms"
        assert stats["total"] == 1
        assert stats["by_status"] == {"APPLIED": 1}
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_ranking_history_returns_failure_details():
    descriptor, db_path = tempfile.mkstemp(suffix=".db")
    os.close(descriptor)
    os.remove(db_path)

    try:
        run_id = record_job_search_run(
            ranked_jobs=[],
            failures=["https://example.com/search -> listing page"],
            total_urls=1,
            db_path=db_path,
        )
        run = list_job_search_runs(db_path=db_path)[0]

        assert run["id"] == run_id
        assert "example.com/search" in run["failures_json"]
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_application_identity_rejects_placeholders():
    for company, title in (
        ("Company", "AI Engineer"),
        ("Honeywell", "Role"),
        ("", "AI Engineer"),
        ("Honeywell", ""),
    ):
        try:
            validate_application_identity(company, title)
        except ValueError as exc:
            assert "actual" in str(exc)
        else:
            raise AssertionError("Placeholder application identity was accepted")


def test_application_identity_accepts_real_values():
    validate_application_identity("Honeywell", "AI Engr I")
