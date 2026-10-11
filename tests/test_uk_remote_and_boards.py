from dataclasses import replace
from datetime import date

import pytest

from job_discovery import (
    DiscoveredJob,
    job_matches_preferences,
    parse_ashby_boards,
    parse_greenhouse_boards,
    parse_lever_sites,
)
from job_preferences import JobPreferences
from market import remote_location_is_compatible


@pytest.fixture
def uk(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "GB")
    monkeypatch.delenv("GREENHOUSE_BOARDS", raising=False)
    monkeypatch.delenv("LEVER_SITES", raising=False)
    monkeypatch.delenv("ASHBY_BOARDS", raising=False)


@pytest.mark.parametrize(
    "location, ok",
    [
        ("Remote", True),
        ("Remote - UK", True),
        ("Home based - Worldwide", True),
        ("Anywhere", True),
        ("Remote, EMEA", True),
        ("Home Based - Americas; Home based - EMEA", True),
        ("Remote, India", False),
        ("Bengaluru, India (Remote)", False),
        ("Home Based - Americas", False),
        ("Remote - United States", False),
        ("Remote, Canada", False),
        ("APAC", False),
    ],
)
def test_remote_location_compatibility_for_uk(uk, location, ok):
    assert remote_location_is_compatible(location) is ok


def test_india_market_keeps_indian_remote_jobs(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "IN")
    assert remote_location_is_compatible("Remote, India")
    assert not remote_location_is_compatible("Remote, United States")


def _job(location, mode="Remote"):
    return DiscoveredJob(
        provider_job_id="x", source="Greenhouse · Example", company_name="Example Ltd",
        job_title="Graduate Data Analyst", location=location, work_mode=mode,
        job_type="Full-time", experience_level="Fresher / Entry level",
        posted_date=date(2026, 10, 10), job_description="Graduate analyst role. " * 10,
    )


def _prefs(locations):
    return JobPreferences(
        target_roles=["Data Analyst"], locations=locations,
        experience_levels=["Fresher / Entry level"],
        work_modes=["Onsite", "Hybrid", "Remote"], job_types=["Full-time"],
    )


def test_remote_preference_no_longer_admits_other_regions(uk):
    today = date(2026, 10, 11)
    prefs = _prefs(["Leicester, UK", "Remote"])
    assert job_matches_preferences(_job("Remote"), prefs, today=today)[0]
    assert job_matches_preferences(_job("Home based - Worldwide"), prefs, today=today)[0]
    ok, reason = job_matches_preferences(_job("Remote, India"), prefs, today=today)
    assert not ok and reason.startswith("Location excluded")
    assert not job_matches_preferences(_job("Home Based - Americas"), prefs, today=today)[0]
    assert not job_matches_preferences(_job("Bangalore, Karnataka", "Hybrid"), prefs, today=today)[0]


def test_uk_curated_defaults_skip_india_focused_boards(uk):
    greenhouse, lever, ashby = parse_greenhouse_boards(), parse_lever_sites(), parse_ashby_boards()
    for token in ("phonepe", "groww", "slice", "sigmoid"):
        assert token not in greenhouse
    for token in ("paytm", "cred", "meesho"):
        assert token not in lever
    assert "navi" not in ashby and "atlan" not in ashby
    assert "anthropic" in greenhouse and "levelai" in lever  # global boards stay


def test_india_market_keeps_its_curated_boards(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "IN")
    monkeypatch.delenv("GREENHOUSE_BOARDS", raising=False)
    monkeypatch.delenv("LEVER_SITES", raising=False)
    assert "phonepe" in parse_greenhouse_boards()
    assert "paytm" in parse_lever_sites()
