from streamlit.testing.v1 import AppTest

from app import (
    description_fingerprint,
    document_download_name,
    preferred_tracker_apply_url,
    user_facing_error,
)
from llm_utils import LLMServiceError


def test_streamlit_primary_pages_and_short_jd_validation():
    app = AppTest.from_file("app.py", default_timeout=10).run()
    assert not app.exception
    assert app.title[0].value == "Application Workspace"

    app.sidebar.radio[0].set_value("Profile").run()
    assert not app.exception
    assert app.title[0].value == "Candidate Profile"

    app.sidebar.radio[0].set_value("Opportunities").run()
    assert not app.exception
    assert app.title[0].value == "Opportunities Hub"

    app.sidebar.radio[0].set_value("Tracker").run()
    assert not app.exception
    assert app.title[0].value == "Application Tracker"
    app.segmented_control[0].set_value("Ranking history").run()
    assert not app.exception

    app.sidebar.radio[0].set_value("Application").run()
    app.text_input[0].set_value("Example Company")
    app.text_input[1].set_value("Engineer")
    app.text_area[0].set_value("too short")
    app.run()

    assert not app.exception
    assert app.button[0].disabled
    assert any("2/50 words" in caption.value for caption in app.caption)


def test_streamlit_reset_does_not_mutate_instantiated_widget():
    app = AppTest.from_file("app.py", default_timeout=10).run()

    app.text_area[0].set_value("temporary job description")
    app.button[1].click().run()

    assert not app.exception
    assert app.segmented_control[0].value == "Paste description"
    assert app.text_area[0].value == ""


def test_discovered_job_opens_in_application_workspace(monkeypatch):
    monkeypatch.setenv("APPLYSMART_ENABLE_SAMPLE_JOBS", "true")
    app = AppTest.from_file("app.py", default_timeout=10).run()
    app.sidebar.radio[0].set_value("Opportunities").run()

    next(t for t in app.text_area if t.label == "Locations *").set_value("Bengaluru, Hyderabad, Remote")
    next(
        button
        for button in app.button
        if button.label == "Save job preferences"
    ).click().run()
    next(
        control
        for control in app.segmented_control
        if control.key == "discovery_source_control"
    ).set_value("Sample catalog").run()
    next(
        button
        for button in app.button
        if button.label == "Discover sample jobs now"
    ).click().run()
    next(
        button
        for button in app.button
        if button.label == "Prepare Application"
    ).click().run()

    assert not app.exception
    assert app.title[0].value == "Application Workspace"
    assert app.text_input[0].value in {
        "Northstar Analytics",
        "Civic Data Labs",
        "Orbit AI Studio",
    }
    assert app.text_input[1].value
    assert len(app.text_area[0].value.split()) >= 50
    assert any(
        "Loaded from Opportunities" in message.value
        for message in app.success
    )


def test_tracker_apply_url_prefers_direct_apply_link_from_discovery():
    google_jobs_url = "https://www.google.com/search?ibp=htl;jobs&q=AI/ML"
    direct_apply_url = "https://bebee.com/in/jobs/ai-ml-engineer-intern"

    assert (
        preferred_tracker_apply_url(
            current_source_url=google_jobs_url,
            stored_source_url=google_jobs_url,
            direct_apply_url=direct_apply_url,
        )
        == direct_apply_url
    )


def test_tracker_apply_url_respects_manually_edited_url():
    google_jobs_url = "https://www.google.com/search?ibp=htl;jobs&q=AI/ML"
    direct_apply_url = "https://bebee.com/in/jobs/ai-ml-engineer-intern"
    edited_url = "https://company.example/careers/job"

    assert (
        preferred_tracker_apply_url(
            current_source_url=edited_url,
            stored_source_url=google_jobs_url,
            direct_apply_url=direct_apply_url,
        )
        == edited_url
    )


def test_streamlit_multi_job_batch_limit():
    app = AppTest.from_file("app.py", default_timeout=10).run()
    app.sidebar.radio[0].set_value("Opportunities").run()

    urls = "\n".join(
        f"https://example.com/openings/engineer-{index}"
        for index in range(1, 12)
    )
    next(t for t in app.text_area if t.label == "Job URLs").set_value(urls)
    next(b for b in app.button if b.label == "Analyze and rank jobs").click().run()

    assert not app.exception
    assert "10 or fewer" in app.error[0].value


def test_streamlit_rejects_search_pages_before_ranking():
    app = AppTest.from_file("app.py", default_timeout=10).run()
    app.sidebar.radio[0].set_value("Opportunities").run()
    next(t for t in app.text_area if t.label == "Job URLs").set_value(
        "https://www.linkedin.com/jobs/search/?keywords=Data%20Scientist"
    )
    next(b for b in app.button if b.label == "Analyze and rank jobs").click().run()

    assert not app.exception
    assert "No individual job-detail URLs" in app.error[0].value


def test_user_facing_errors_hide_provider_authentication_details():
    raw = RuntimeError(
        "Could not resolve authentication method. Expected api_key or token."
    )

    message = user_facing_error(raw, "Job analysis")

    assert "selected LLM_PROVIDER" in message
    assert "resolve authentication method" not in message


def test_user_facing_errors_explain_provider_quota_limits():
    raw = RuntimeError("RESOURCE_EXHAUSTED: quota exceeded (status code: 429)")

    message = user_facing_error(raw, "Job analysis")

    assert "account limits" in message
    assert "RESOURCE_EXHAUSTED" not in message


def test_normalized_ai_errors_are_actionable_and_safe():
    message = user_facing_error(
        LLMServiceError(
            "authentication",
            "provider diagnostic containing a secret",
        ),
        "Job analysis",
    )

    assert "API key was rejected" in message
    assert "provider diagnostic" not in message


def test_document_download_names_are_short_and_correct():
    profile = {"name": "Obili Pranav"}

    assert document_download_name(
        profile,
        "Domyn SpA",
        "resume",
    ) == "obili_pranav_resume_domyn_spa.pdf"
    assert document_download_name(
        profile,
        "Domyn SpA",
        "cover_letter",
    ) == "obili_pranav_cover_letter_domyn_spa.pdf"


def test_description_fingerprint_ignores_spacing_and_case_only():
    first = description_fingerprint("Python  Engineer\nMachine Learning")
    equivalent = description_fingerprint("python engineer machine learning")
    changed = description_fingerprint("Python Engineer Data Engineering")

    assert first == equivalent
    assert first != changed


def test_tracker_explains_drafts_are_not_submitted_applications():
    app = AppTest.from_file("app.py", default_timeout=10).run()
    app.sidebar.radio[0].set_value("Tracker").run()

    captions = [caption.value for caption in app.caption]

    assert any(
        "Generated drafts are not counted" in caption
        for caption in captions
    )
