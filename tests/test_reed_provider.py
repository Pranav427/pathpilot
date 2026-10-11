import base64
import json
from datetime import date
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from job_discovery import JobDiscoveryError, is_broad_market_source
from job_preferences import JobPreferences
from reed_provider import ReedJobProvider, clear_reed_cache, parse_reed_date


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


@pytest.fixture(autouse=True)
def uk_market(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "GB")
    clear_reed_cache()


def prefs(locations=("Leeds",)):
    return JobPreferences(
        target_roles=["Data Analyst"], locations=list(locations),
        experience_levels=["Internship", "Fresher / Entry level"],
        work_modes=["Hybrid", "Onsite", "Remote"], job_types=["Full-time", "Internship"],
    )


SEARCH = {
    "results": [
        {
            "jobId": 111, "employerName": "Northern Data Ltd", "jobTitle": "Graduate Data Analyst",
            "locationName": "Leeds", "date": "09/10/2026", "jobUrl": "https://www.reed.co.uk/jobs/111",
            "jobDescription": "Join our team as a graduate analyst. Short snippet...",
            "minimumSalary": 26000, "maximumSalary": 30000,
        },
        {"jobId": None, "jobTitle": "Broken row"},
        "not a dict",
    ]
}
DETAIL = {
    "jobDescription": "<p>Full advert text. We are unable to offer visa sponsorship.</p>",
    "contractType": "Permanent", "jobType": "Full time",
    "externalUrl": "https://careers.northerndata.example/apply/111",
}


def opener_for(requests, detail=DETAIL):
    def opener(request, **_kwargs):
        requests.append(request)
        if "/search" in request.full_url:
            return FakeResponse(SEARCH)
        if detail is None:
            raise HTTPError(request.full_url, 500, "boom", {}, None)
        return FakeResponse(detail)
    return opener


def test_requires_api_key():
    with pytest.raises(ValueError, match="REED_API_KEY"):
        ReedJobProvider("")


def test_parse_reed_dates():
    assert parse_reed_date("09/10/2026") == (date(2026, 10, 9), True)
    assert parse_reed_date("2026-10-09T10:00:00") == (date(2026, 10, 9), True)
    assert parse_reed_date("")[1] is False
    assert parse_reed_date("garbage")[1] is False


def test_search_request_uses_basic_auth_and_parameters():
    clear_reed_cache()
    requests = []
    provider = ReedJobProvider("my-key", opener=opener_for(requests), max_queries=1)
    provider.discover(prefs())
    search = next(r for r in requests if "/search" in r.full_url)
    query = parse_qs(urlparse(search.full_url).query)
    assert query["keywords"][0].lower().startswith("graduate data analyst")
    assert query["locationName"] == ["Leeds"]
    assert query["resultsToTake"] == ["50"]
    assert "graduate" not in query
    expected = base64.b64encode(b"my-key:").decode()
    assert search.get_header("Authorization") == f"Basic {expected}"


def test_uk_wide_search_omits_location_and_graduate_flag_is_optional():
    requests = []
    provider = ReedJobProvider("k", opener=opener_for(requests), max_queries=1, graduate_only=True)
    provider.discover(prefs(["United Kingdom"]))
    query = parse_qs(urlparse(next(r for r in requests if "/search" in r.full_url).full_url).query)
    assert "locationName" not in query
    assert query["graduate"] == ["true"]


def test_results_are_normalised_and_enriched_with_full_description():
    requests = []
    provider = ReedJobProvider("k", opener=opener_for(requests), max_queries=1)
    jobs = provider.discover(prefs())
    assert len(jobs) == 1
    job = jobs[0]
    assert job.provider_job_id == "reed-111"
    assert job.source == "Reed" and job.company_name == "Northern Data Ltd"
    assert job.posted_date == date(2026, 10, 9) and job.freshness_verified
    assert "unable to offer visa sponsorship" in job.job_description
    assert "<p>" not in job.job_description
    assert job.apply_url == "https://careers.northerndata.example/apply/111"
    assert job.source_url == "https://www.reed.co.uk/jobs/111"
    assert job.experience_level == "Fresher / Entry level"
    assert job.job_type == "Full-time"


def test_detail_failure_keeps_the_snippet_job():
    provider = ReedJobProvider("k", opener=opener_for([], detail=None), max_queries=1)
    jobs = provider.discover(prefs())
    assert len(jobs) == 1 and "Short snippet" in jobs[0].job_description
    assert provider.failures


def test_duplicate_jobs_across_queries_are_merged():
    requests = []
    provider = ReedJobProvider("k", opener=opener_for(requests), max_queries=4)
    jobs = provider.discover(prefs(["Leeds", "York"]))
    assert len([j for j in jobs if j.provider_job_id == "reed-111"]) == 1


def test_all_searches_failing_raises_a_readable_error():
    def opener(request, **_kwargs):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    provider = ReedJobProvider("bad", opener=opener, max_queries=1)
    with pytest.raises(JobDiscoveryError, match="HTTP 401"):
        provider.discover(prefs())


def test_reed_is_a_broad_market_source():
    assert is_broad_market_source("Reed")


def test_reed_full_text_feeds_the_sponsorship_filter():
    from dataclasses import replace
    from job_discovery import job_matches_preferences

    job = ReedJobProvider("k", opener=opener_for([]), max_queries=1).discover(prefs())[0]
    needs = replace(prefs(), needs_sponsorship=True)
    matches, reason = job_matches_preferences(job, needs, today=date(2026, 10, 11))
    assert not matches and reason == "Visa sponsorship not available"
