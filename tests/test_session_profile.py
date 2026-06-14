import pytest

from profile import build_session_profile, split_profile_items


def valid_profile(**overrides):
    values = {
        "name": "Test Candidate",
        "email": "candidate@example.com",
        "phone": "",
        "location": "India",
        "linkedin": "",
        "github": "",
        "portfolio": "",
        "objective": (
            "Computer Science graduate with verified Python and machine "
            "learning project experience."
        ),
        "skills": {
            "Programming Languages": "Python, SQL",
            "Artificial Intelligence & Machine Learning": "Machine Learning",
        },
        "education_text": (
            "B.Tech Computer Science | Example Institute | 2021-2025 | 8.5 CGPA"
        ),
        "experience_text": "",
        "projects_text": (
            "Prediction Project | Machine Learning | Python, scikit-learn | "
            "Built and evaluated a classification model."
        ),
        "certifications_text": "Python Certificate",
    }
    values.update(overrides)
    return build_session_profile(**values)


def test_session_profile_builds_structured_evidence():
    profile = valid_profile()

    assert profile["name"] == "Test Candidate"
    assert profile["skills"]["Programming Languages"] == ["Python", "SQL"]
    assert profile["projects"][0]["tools"] == ["Python", "scikit-learn"]
    assert profile["education"][0]["degree"] == "B.Tech Computer Science"


def test_session_profile_rejects_missing_evidence():
    with pytest.raises(ValueError, match="at least one project or experience"):
        valid_profile(projects_text="", experience_text="")


def test_session_profile_rows_require_expected_columns():
    with pytest.raises(ValueError, match=r"separated by \|"):
        valid_profile(education_text="B.Tech | Example Institute")


def test_profile_item_split_is_deduplicated():
    assert split_profile_items("Python, SQL\npython") == ["Python", "SQL"]
