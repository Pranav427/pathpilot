from unittest.mock import patch

from application_service import (
    add_confirmed_skills_to_profile,
    attach_confirmed_familiarity,
    get_missing_profile_terms,
)
from main import confirm_missing_profile_terms
from profile import get_profile


def test_gap_confirmation_accepts_numeric_range():
    match = {
        "missing_skills": ["one", "two", "three"],
        "missing_tools": ["four", "five"],
        "missing_keywords": ["Role Title"],
    }

    with patch("builtins.input", return_value="1-5"):
        confirmed = confirm_missing_profile_terms(match)

    assert confirmed == ["one", "two", "three", "four", "five"]


def test_gap_terms_exclude_keywords_and_job_titles():
    match = {
        "missing_skills": ["Error Handling"],
        "missing_tools": ["PyTorch"],
        "missing_keywords": ["Machine Learning Intern"],
    }

    assert get_missing_profile_terms(match) == ["Error Handling", "PyTorch"]


def test_temporary_enrichment_does_not_mutate_master_profile():
    profile = get_profile()

    enriched = add_confirmed_skills_to_profile(
        profile,
        ["Unit Testing", "Customer Obsession"],
    )

    assert enriched["_application_confirmed_terms"] == [
        "Unit Testing",
        "Customer Obsession",
    ]
    assert "_application_confirmed_terms" not in profile
    assert "Unit Testing" not in profile["skills"]["Software Fundamentals"]


def test_confirmed_familiarity_does_not_inflate_fit_score():
    match = {
        "match_score": 48,
        "fit_verdict": "STRETCH_MATCH",
        "fit_verdict_label": "Stretch Match",
    }

    annotated = attach_confirmed_familiarity(
        match,
        ["System Design", "Complexity Analysis"],
    )

    assert annotated["match_score"] == 48
    assert annotated["base_match_score"] == 48
    assert annotated["familiarity_adjustment"] == 0
    assert annotated["user_confirmed_terms"] == [
        "System Design",
        "Complexity Analysis",
    ]


def test_confirmed_familiarity_is_capped_for_application_wording():
    match = {"match_score": 52}

    annotated = attach_confirmed_familiarity(
        match,
        [f"Term {index}" for index in range(1, 12)],
    )

    assert len(annotated["user_confirmed_terms"]) == 8
    assert annotated["user_confirmed_terms"][-1] == "Term 8"


def test_master_software_skills_stay_concise_and_verified():
    skills = get_profile()["skills"]["Software Fundamentals"]

    assert skills == [
        "Object-Oriented Programming (OOP)",
        "Data Structures & Algorithms",
        "Software Development Life Cycle (SDLC)",
        "Debugging",
        "Error Handling",
        "Technical Documentation",
    ]
