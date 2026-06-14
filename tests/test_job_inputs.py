from job_fetcher import (
    clean_company,
    fetch_job_from_url,
    is_likely_job_listing,
    normalize_url,
)
from job_search import extract_urls_from_text, parse_rank_selection


def test_normalize_url_rejects_terminal_commands():
    try:
        normalize_url("source /path/to/.venv/bin/activate")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected invalid URL input to be rejected")

    assert "Paste only" in message


def test_promotional_urls_are_filtered():
    text = """
    https://pdlink.in/4usWTSD
    https://tinyurl.com/abc
    https://freshershunt.in/hp-off-campus-drive-2026/
    """

    assert extract_urls_from_text(text) == [
        "https://freshershunt.in/hp-off-campus-drive-2026/"
    ]


def test_rank_selection_accepts_ranges_and_commas():
    assert parse_rank_selection("1,3-5", 5) == [1, 3, 4, 5]


def test_url_extraction_deduplicates_links():
    text = """
    https://example.com/jobs/1
    Again: https://example.com/jobs/1.
    https://example.com/jobs/2
    """

    assert extract_urls_from_text(text) == [
        "https://example.com/jobs/1",
        "https://example.com/jobs/2",
    ]


def test_company_names_are_normalized():
    assert clean_company("hcltech") == "HCLTech"
    assert clean_company("bnp paribas") == "BNP Paribas"
    assert clean_company("hpe") == "HPE"
    assert clean_company("kpit") == "KPIT"
    assert clean_company("iqvia") == "IQVIA"
    assert clean_company("ntt data") == "NTT DATA"
    assert clean_company("magnit") == "Magnit"
    assert clean_company("domynspa") == "Domyn SpA"


def test_job_listing_urls_are_not_treated_as_individual_jobs():
    assert is_likely_job_listing(
        "https://www.linkedin.com/jobs/search/?keywords=Data%20Scientist",
        "36,000+ Data Scientist jobs in India",
    )
    assert is_likely_job_listing(
        "https://careers.google.com/jobs/results/?location=India",
        "Search Jobs",
    )
    assert is_likely_job_listing(
        "https://internshala.com/jobs/data-science-jobs/",
        "546 Data Science Jobs",
    )
    assert is_likely_job_listing(
        "https://careers.tcs.com/",
        "Step into the kind of work that builds what's next",
    )
    assert is_likely_job_listing(
        "https://www.amazon.jobs/en/locations/india",
        "",
    )
    assert is_likely_job_listing(
        "https://www.microsoft.com/en-in/careers/students/",
        "",
    )
    assert is_likely_job_listing(
        "https://www.infosys.com/careers.html",
        "",
    )
    assert is_likely_job_listing(
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        "",
    )


def test_individual_job_urls_remain_supported():
    assert not is_likely_job_listing(
        "https://group.bnpparibas/en/careers/job-offer/data-science-intern",
        "Data Science Intern",
    )
    assert not is_likely_job_listing(
        "https://kickcharm.com/deloitte-recruitment-2023-hiring-any-graduates/",
        "Deloitte Recruitment Hiring Any Graduates",
    )


def test_fetch_failure_guides_user_to_application_manual_paste(monkeypatch):
    monkeypatch.setattr(
        "job_fetcher.fetch_html",
        lambda _url: "<html><title>Protected job</title><body>Blocked</body></html>",
    )

    try:
        fetch_job_from_url("https://example.com/openings/ai-engineer")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected low-quality extraction to fail")

    assert "Application workspace" in message
    assert "option 1" not in message
