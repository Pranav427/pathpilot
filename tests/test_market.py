import pytest

import job_discovery
from job_discovery import (
    AdzunaJobProvider,
    JoobleJobProvider,
    expanded_market_locations,
    is_market_location,
    normalized_location_variants,
)
from job_preferences import suggest_job_preferences
from market import INDIA, UK, get_market


@pytest.fixture
def uk(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "GB")


def test_default_market_is_uk(monkeypatch):
    monkeypatch.delenv("PATHPILOT_COUNTRY", raising=False)
    assert get_market() is UK


def test_country_setting_and_aliases(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "in")
    assert get_market() is INDIA
    monkeypatch.setenv("PATHPILOT_COUNTRY", "uk")
    assert get_market() is UK
    monkeypatch.setenv("PATHPILOT_COUNTRY", "nonsense")
    assert get_market() is UK


def test_uk_market_locations(uk):
    assert is_market_location("Leeds, West Yorkshire, England")
    assert is_market_location("London (Hybrid)")
    assert not is_market_location("Bengaluru, India")
    assert expanded_market_locations(["Leeds"])[-2:] == ["United Kingdom", ""]
    assert {"london", "greater london"} <= normalized_location_variants(["London"])


def test_broad_providers_default_to_gb(uk):
    assert AdzunaJobProvider("id", "key").country == "gb"
    assert JoobleJobProvider("key").country == "gb"
    assert AdzunaJobProvider("id", "key", country="us").country == "us"


def test_uk_defaults_in_job_preferences(uk):
    profile = {"name": "A", "location": "United Kingdom", "skills": {}, "projects": []}
    prefs = suggest_job_preferences(profile)
    assert prefs["locations"] == []


def test_google_jobs_requests_are_scoped_to_the_uk(uk):
    source = open(job_discovery.__file__, encoding="utf-8").read()
    assert source.count('"gl": get_market().google_gl') == 2
    assert 'or "India"' not in source
