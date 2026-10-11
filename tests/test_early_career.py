import pytest

from early_career import (
    APPRENTICESHIP,
    GRADUATE_ROLE,
    GRADUATE_SCHEME,
    INTERNSHIP,
    PLACEMENT_YEAR,
    SPRING_WEEK,
    classify_programme,
    programme_experience_fields,
)
from job_discovery import (
    has_entry_level_evidence,
    infer_discovery_metadata,
    profile_search_role_queries,
)
from job_preferences import JobPreferences


@pytest.mark.parametrize(
    "title, description, expected",
    [
        ("Spring Week 2027 - Investment Banking", "", SPRING_WEEK),
        ("Insight Week: Technology", "", SPRING_WEEK),
        ("Software Engineer Industrial Placement", "12 month placement from July", PLACEMENT_YEAR),
        ("Data Analyst (Placement Year)", "", PLACEMENT_YEAR),
        ("Data Analyst", "A sandwich year placement in our Leeds team.", PLACEMENT_YEAR),
        ("Technology Graduate Scheme 2027", "", GRADUATE_SCHEME),
        ("Analyst", "Join our two-year graduate programme in London.", GRADUATE_SCHEME),
        ("Degree Apprentice Software Developer", "", APPRENTICESHIP),
        ("Summer Internship - Data Science", "", INTERNSHIP),
        ("Graduate Data Analyst", "", GRADUATE_ROLE),
        ("Senior Data Engineer", "Postgraduate degree preferred. Graduate degree required.", ""),
        ("Data Analyst", "You have graduated recently or have a graduate degree.", ""),
        ("Account Manager", "", ""),
    ],
)
def test_classify_programme(title, description, expected):
    assert classify_programme(title, description) == expected


def test_programme_maps_to_existing_levels():
    assert programme_experience_fields(PLACEMENT_YEAR) == ("Internship", "Internship")
    assert programme_experience_fields(SPRING_WEEK) == ("Internship", "Internship")
    assert programme_experience_fields(GRADUATE_SCHEME) == ("", "Fresher / Entry level")
    assert programme_experience_fields("") == ("", "")


def test_metadata_inference_recognises_uk_programmes():
    scheme = infer_discovery_metadata("Technology Graduate Scheme", "Two-year programme.", "London")
    assert scheme["experience_level"] == "Fresher / Entry level"
    placement = infer_discovery_metadata("Industrial Placement Analyst", "", "Leeds")
    assert placement["experience_level"] == "Internship" and placement["job_type"] == "Internship"
    senior = infer_discovery_metadata("Senior Analyst", "Postgraduate degree preferred.", "Leeds")
    assert senior["experience_level"] == ""


def test_uk_early_career_titles_count_as_entry_level_evidence():
    for title in ("Industrial Placement Analyst", "Spring Week 2027", "Early Careers Analyst", "Graduate Scheme: Tech"):
        assert has_entry_level_evidence(title, "")
    assert not has_entry_level_evidence("Senior Analyst", "Postgraduate degree preferred.")


def _prefs():
    return JobPreferences(
        target_roles=["Data Analyst"], locations=["Leeds"],
        experience_levels=["Internship", "Fresher / Entry level"],
        work_modes=["Hybrid"], job_types=["Full-time", "Internship"],
    )


def test_uk_search_queries_use_uk_terms(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "GB")
    queries = [q.lower() for q in profile_search_role_queries(_prefs())]
    assert "graduate data analyst" in queries
    assert "data analyst graduate scheme" in queries
    assert "data analyst placement year" in queries
    assert not any("fresher" in q for q in queries)


def test_india_search_queries_keep_fresher_terms(monkeypatch):
    monkeypatch.setenv("PATHPILOT_COUNTRY", "IN")
    queries = [q.lower() for q in profile_search_role_queries(_prefs())]
    assert "data analyst fresher" in queries
    assert not any("graduate scheme" in q for q in queries)
