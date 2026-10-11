from datetime import date

import pytest

from job_discovery import DiscoveredJob, job_matches_preferences
from job_preferences import JobPreferences
from sponsorship import (
    NO_SPONSORSHIP,
    RIGHT_TO_WORK_NEEDED,
    SPONSORSHIP_OFFERED,
    UNKNOWN,
    classify_sponsorship,
)

NO = [
    "Unfortunately we are unable to offer visa sponsorship for this role.",
    "We cannot sponsor visas at this time.",
    "No sponsorship is available.",
    "Applicants must have the right to work in the UK without sponsorship.",
    "Candidates must not require sponsorship now or in the future.",
    "We do not provide visa sponsorship.",
    "Sorry, we are not able to sponsor candidates for this position.",
    "Visa sponsorship is not available for this vacancy.",
    "This role does not offer sponsorship.",
    "We're unable to support work visas.",
    "You must be eligible to work in the UK without the need for sponsorship.",
    "We're not currently able to provide sponsorship but may in future.",
    "We are unable to consider applicants requiring visa sponsorship.",
    "Please note we do not accept applications from candidates who require sponsorship.",
    "Applicants requiring sponsorship will not be considered.",
    "The company will not sponsor.",
]
YES = [
    "Visa sponsorship is available for the right candidate.",
    "We are a licensed sponsor and can support Skilled Worker visas.",
    "We offer visa sponsorship to international graduates.",
    "We can sponsor your visa.",
    "Sponsorship is available.",
    "Visa sponsorship may be considered for exceptional candidates.",
]
RTW = [
    "You must have the right to work in the UK.",
    "Candidates should be eligible to work in the United Kingdom.",
]
NONE = [
    "Join our growing analytics team in Leeds. 2:1 degree required.",
    "We sponsor the local football club and a charity run.",
    "You will work with sponsors of the programme to report progress.",
    "This role is sponsored by our corporate partner programme.",
    "Graduate Route and Student visa holders are welcome to apply.",
    "",
]


@pytest.mark.parametrize("text", NO)
def test_no_sponsorship(text):
    assert classify_sponsorship(text) == NO_SPONSORSHIP


@pytest.mark.parametrize("text", YES)
def test_sponsorship_offered(text):
    assert classify_sponsorship(text) == SPONSORSHIP_OFFERED


@pytest.mark.parametrize("text", RTW)
def test_right_to_work_needed(text):
    assert classify_sponsorship(text) == RIGHT_TO_WORK_NEEDED


@pytest.mark.parametrize("text", NONE)
def test_unknown(text):
    assert classify_sponsorship(text) == UNKNOWN


def test_negative_wins_over_positive():
    text = "We are a licensed sponsor, but unable to sponsor this particular role."
    assert classify_sponsorship(text) == NO_SPONSORSHIP


def _job(description: str) -> DiscoveredJob:
    return DiscoveredJob(
        provider_job_id="1", source="Test Feed", company_name="Acme Ltd",
        job_title="Graduate Data Analyst", location="Leeds, UK", work_mode="Hybrid",
        job_type="Full-time", experience_level="Fresher / Entry level",
        posted_date=date(2026, 10, 10), job_description=description,
    )


def _prefs(needs: bool) -> JobPreferences:
    return JobPreferences(
        target_roles=["Data Analyst"], locations=["Leeds"],
        experience_levels=["Fresher / Entry level"], work_modes=["Hybrid"],
        job_types=["Full-time"], needs_sponsorship=needs,
    )


TODAY = date(2026, 10, 11)


def test_filter_hides_no_sponsorship_jobs_only_when_user_needs_sponsorship(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "GB")
    job = _job("Graduate analyst role. We are unable to offer visa sponsorship.")
    hidden, reason = job_matches_preferences(job, _prefs(True), today=TODAY)
    assert not hidden and reason == "Visa sponsorship not available"
    shown, _ = job_matches_preferences(job, _prefs(False), today=TODAY)
    assert shown


def test_filter_keeps_unclear_and_sponsoring_jobs(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "GB")
    for text in (
        "Graduate analyst role in our Leeds office.",
        "Right to work in the UK is required.",
        "Visa sponsorship is available for the right candidate.",
    ):
        ok, reason = job_matches_preferences(_job(text), _prefs(True), today=TODAY)
        assert ok, reason
