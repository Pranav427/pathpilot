from job_preferences import (
    DEFAULT_LOCATIONS_WHEN_UNSPECIFIED,
    build_job_preferences,
    preference_rejection_reason,
    required_experience_years,
    suggest_job_preferences,
    split_preference_items,
)


def valid_preferences(**overrides):
    values = {
        "target_roles": "Data Scientist, AI/ML Engineer",
        "locations": "Bengaluru, Remote",
        "experience_levels": ["Fresher / Entry level"],
        "work_modes": ["Hybrid", "Remote"],
        "job_types": ["Full-time"],
        "preferred_skills": "Python, Machine Learning",
        "excluded_keywords": "Senior, Sales",
        "maximum_job_age_days": 14,
    }
    values.update(overrides)
    return build_job_preferences(**values)


def test_preference_items_are_clean_and_unique():
    assert split_preference_items("Python, ML\npython, NLP") == [
        "Python",
        "ML",
        "NLP",
    ]


def test_preferences_require_role():
    try:
        valid_preferences(target_roles="")
    except ValueError as exc:
        assert "Complete your job preferences" in str(exc)
    else:
        raise AssertionError("Expected target role validation to fail")


def test_blank_location_defaults_to_india_and_remote():
    preferences = valid_preferences(locations="")

    assert preferences.locations == list(DEFAULT_LOCATIONS_WHEN_UNSPECIFIED)


def test_preferences_reject_invalid_age_window():
    try:
        valid_preferences(maximum_job_age_days=90)
    except ValueError as exc:
        assert "between 1 and 60" in str(exc)
    else:
        raise AssertionError("Expected maximum age validation to fail")


def test_explicit_excluded_keyword_rejects_job():
    preferences = valid_preferences()
    reason = preference_rejection_reason(
        job_title="Senior Data Scientist",
        job_description="Build predictive models.",
        preferences=preferences,
    )
    assert reason == "Excluded keyword matched: Senior"


def test_excluded_title_keyword_does_not_reject_responsibility_text():
    preferences = valid_preferences(job_types=["Full-time", "Internship"])
    reason = preference_rejection_reason(
        job_title="AI/ML Intern",
        job_description="Work with senior engineers on model evaluation.",
        preferences=preferences,
    )

    assert reason == ""


def test_entry_preferences_reject_required_experience_in_description():
    preferences = valid_preferences()
    reason = preference_rejection_reason(
        job_title="Data Scientist",
        job_description=(
            "You have 4+ years of hands-on experience in data science and "
            "analytics roles."
        ),
        preferences=preferences,
    )

    assert reason == "Requires 4+ years of experience"


def test_entry_preferences_reject_year_requirement_in_title():
    preferences = valid_preferences()

    for title, years in (
        ("AI/ML Engineer (6 Yrs)", 6),
        ("Machine Learning Engineer_4 TO 6 YEARS_HYDERABAD", 4),
        ("Data Scientist - 3-5 Years", 3),
    ):
        reason = preference_rejection_reason(
            job_title=title,
            job_description="Build machine learning systems with Python.",
            preferences=preferences,
        )
        assert reason == f"Requires {years}+ years of experience"


def test_experience_parser_handles_common_aggregator_formats():
    assert required_experience_years("AI Engineer", "Experience - 3yr") == 3
    assert required_experience_years(
        "Data Scientist", "Experience: 4 to 12 Years"
    ) == 4
    assert required_experience_years(
        "ML Engineer", "Minimum 2 years of relevant experience"
    ) == 2


def test_entry_preferences_reject_common_aggregator_formats():
    preferences = valid_preferences()
    for description, years in (
        ("Experience - 3yr", 3),
        ("Experience: 4 to 12 Years", 4),
    ):
        reason = preference_rejection_reason(
            job_title="Data Scientist",
            job_description=description,
            preferences=preferences,
        )
        assert reason == f"Requires {years}+ years of experience"


def test_entry_preferences_keep_one_to_two_year_roles_for_review():
    preferences = valid_preferences()
    for description in (
        "0-1 years of data science experience preferred.",
        "Minimum 2 years of relevant experience.",
        "Experience: 1 to 2 Years",
    ):
        reason = preference_rejection_reason(
            job_title="Data Scientist",
            job_description=description,
            preferences=preferences,
        )
        assert reason == ""


def test_entry_preferences_reject_numbered_role_levels():
    preferences = valid_preferences()
    for title in ("Machine Learning Engineer III", "Data Scientist 4"):
        reason = preference_rejection_reason(
            job_title=title,
            job_description="Build machine learning systems.",
            preferences=preferences,
        )
        assert "role level excluded" in reason


def test_entry_preferences_reject_chief_and_architect_roles():
    preferences = valid_preferences()
    for title in ("Chief Data Scientist", "Machine Learning Architect"):
        reason = preference_rejection_reason(
            job_title=title,
            job_description="Build machine learning systems.",
            preferences=preferences,
        )
        assert "Experienced role" in reason


def test_entry_preferences_allow_non_numeric_collaboration_wording():
    preferences = valid_preferences()
    reason = preference_rejection_reason(
        job_title="Data Scientist",
        job_description=(
            "Work with experienced engineers and learn from the team."
        ),
        preferences=preferences,
    )

    assert reason == ""


def test_internship_respects_selected_job_types():
    preferences = valid_preferences()
    reason = preference_rejection_reason(
        job_title="Machine Learning Intern",
        job_description="Support machine learning projects.",
        preferences=preferences,
    )
    assert "Internship roles are excluded" in reason


def test_profile_evidence_suggests_roles_and_verified_skills():
    profile = {
        "location": "India",
        "skills": {
            "Programming Languages": ["Python", "SQL"],
            "AI": [
                "Artificial Intelligence",
                "Machine Learning",
                "Model Training",
                "Natural Language Processing (NLP)",
                "Text Classification",
                "Computer Vision",
                "Deep Learning",
            ],
            "Data": ["Data Analysis", "Statistical Analysis"],
        },
    }

    suggestions = suggest_job_preferences(profile)

    assert "Data Scientist" in suggestions["target_roles"]
    assert "Machine Learning Engineer" in suggestions["target_roles"]
    assert "AI/ML Engineer" in suggestions["target_roles"]
    assert suggestions["target_roles"][:3] == [
        "AI/ML Engineer",
        "Machine Learning Engineer",
        "NLP Engineer",
    ]
    assert suggestions["preferred_skills"][:3] == [
        "Python",
        "Machine Learning",
        "Artificial Intelligence",
    ]
    assert suggestions["locations"] == []


def test_specific_profile_location_is_suggested():
    profile = {
        "location": "Hyderabad",
        "skills": {"Programming Languages": ["Python"]},
    }

    assert suggest_job_preferences(profile)["locations"] == ["Hyderabad"]
