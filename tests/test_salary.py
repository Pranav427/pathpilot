from dataclasses import replace
from datetime import date

import pytest

from job_discovery import DiscoveredJob, job_matches_preferences
from job_preferences import JobPreferences, build_job_preferences
from reed_provider import reed_salary_line
from salary import (
    NEW_ENTRANT_SALARY_THRESHOLD,
    below_sponsorship_threshold,
    format_salary,
    parse_salary,
)


@pytest.mark.parametrize(
    "text, low, high, period",
    [
        ("Salary: £28,000 - £32,000 per annum plus benefits", 28000, 32000, "year"),
        ("£30k-£35k DOE", 30000, 35000, "year"),
        ("£28-32k", 28000, 32000, "year"),
        ("From £13.50 per hour", 13.5, 13.5, "hour"),
        ("£250 per day rate", 250, 250, "day"),
        ("£4,500 per month", 4500, 4500, "month"),
        ("Up to £35,000 a year", 35000, 35000, "year"),
        ("£45,000", 45000, 45000, "year"),
        ("£12.60 an hour (£24,570 per annum)", 12.6, 12.6, "hour"),
    ],
)
def test_parse_salary(text, low, high, period):
    info = parse_salary(text)
    assert info and (info.low, info.high, info.period) == (low, high, period)


@pytest.mark.parametrize(
    "text",
    [
        "Competitive salary",
        "We turned over £50m last year",
        "£1,500 bonus after 6 months",
        "A £10,000 signing bonus is offered",
        "£100 gift voucher",
        "",
    ],
)
def test_non_salaries_are_ignored(text):
    assert parse_salary(text) is None


def test_annualising_and_formatting():
    hourly = parse_salary("£13.50 per hour")
    assert hourly.annual_low == pytest.approx(13.5 * 1950)
    assert format_salary(parse_salary("£28,000 - £32,000 per annum")) == "£28,000–£32,000 a year"
    assert "about" in format_salary(hourly)


def test_sponsorship_threshold_warning_only_when_clearly_below():
    assert below_sponsorship_threshold(parse_salary("£28,000 - £32,000 per annum"))
    assert not below_sponsorship_threshold(parse_salary("£28,000 - £40,000 per annum"))
    assert not below_sponsorship_threshold(None)
    assert NEW_ENTRANT_SALARY_THRESHOLD == 33_400


def test_reed_structured_salary_becomes_parseable_text():
    line = reed_salary_line({"minimumSalary": 26000, "maximumSalary": 30000, "currency": "GBP"})
    assert parse_salary(line).annual_low == 26000
    hourly = reed_salary_line({"minimumSalary": 13.5, "maximumSalary": 13.5})
    assert parse_salary(hourly).period == "hour"
    assert reed_salary_line({"minimumSalary": 100000, "currency": "USD"}) == ""
    assert reed_salary_line({}) == ""


def _job(description):
    return DiscoveredJob(
        provider_job_id="1", source="Test Feed", company_name="Acme Ltd",
        job_title="Graduate Data Analyst", location="Leeds, UK", work_mode="Hybrid",
        job_type="Full-time", experience_level="Fresher / Entry level",
        posted_date=date(2026, 10, 10), job_description=description,
    )


def _prefs(minimum):
    return JobPreferences(
        target_roles=["Data Analyst"], locations=["Leeds"],
        experience_levels=["Fresher / Entry level"], work_modes=["Hybrid"],
        job_types=["Full-time"], minimum_salary=minimum,
    )


def test_minimum_salary_filter(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "GB")
    today = date(2026, 10, 11)
    low = _job("Graduate analyst. Salary £24,000 - £26,000 per annum.")
    ok, reason = job_matches_preferences(low, _prefs(30000), today=today)
    assert not ok and reason == "Salary below minimum"
    assert job_matches_preferences(low, _prefs(0), today=today)[0]
    high = _job("Graduate analyst. Salary £28,000 - £34,000 per annum.")
    assert job_matches_preferences(high, _prefs(30000), today=today)[0]
    unstated = _job("Graduate analyst role with a competitive salary.")
    assert job_matches_preferences(unstated, _prefs(30000), today=today)[0]


def test_build_job_preferences_accepts_minimum_salary():
    prefs = build_job_preferences(
        target_roles="Data Analyst", locations="Leeds",
        experience_levels=["Fresher / Entry level"], work_modes=["Hybrid"],
        job_types=["Full-time"], minimum_salary=28000,
    )
    assert prefs.minimum_salary == 28000
    assert replace(prefs, minimum_salary=-5).minimum_salary == -5  # dataclass only; builder clamps
    assert build_job_preferences(
        target_roles="x", locations="", experience_levels=["Internship"],
        work_modes=["Remote"], job_types=["Internship"], minimum_salary=-10,
    ).minimum_salary == 0
