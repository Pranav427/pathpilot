import resume
from wording_checks import strip_unsupported_intensifiers, unsupported_intensifiers

PROFILE = {
    "education": [{"degree": "BSc Economics", "institution": "University of Leeds", "grade": "2:1"}],
    "projects": [{
        "name": "Housing Price Study", "domain": "Econometrics", "tools": ["Stata", "Excel"],
        "highlights": ["Modelled regional housing prices using regression analysis."],
    }],
    "skills": {"Analysis": ["Excel", "Stata"]},
    "achievements": ["Won an outstanding student award"],
}


def test_unsupported_strength_words_are_found():
    text = "Used advanced Excel on extensive datasets with proven ability."
    assert set(unsupported_intensifiers(text, PROFILE)) == {"advanced", "extensive", "proven"}


def test_words_the_candidate_wrote_themselves_are_kept():
    text = "Earned an outstanding student award."
    assert unsupported_intensifiers(text, PROFILE) == []
    assert strip_unsupported_intensifiers(text, PROFILE) == text


def test_stripping_keeps_sentences_readable():
    text = "Highly analytical graduate. Used advanced Excel on extensive datasets, demonstrating strong skills."
    out = strip_unsupported_intensifiers(text, PROFILE)
    assert out == "Analytical graduate. Used Excel on datasets, demonstrating skills."


def test_text_without_intensifiers_is_unchanged():
    text = "Modelled regional housing prices in Stata."
    assert strip_unsupported_intensifiers(text, PROFILE) == text


def test_resume_bullets_and_summary_are_cleaned():
    content = {
        "professional_summary": (
            "Highly motivated BSc Economics graduate from the University of Leeds with a 2:1. "
            "Proven Excel and Stata skills for economic analysis tasks. "
            "Keen to support analyst teams."
        ),
        "skills": {},
        "projects": [{
            "name": "Housing Price Study",
            "bullets": ["Applied advanced regression analysis to model regional housing prices in Stata."],
        }],
    }
    out = resume.sanitize_resume_facts(content, PROFILE)
    joined = out["professional_summary"] + " " + " ".join(out["projects"][0]["bullets"])
    assert not any(w in joined.lower() for w in ("advanced", "proven", "highly"))
    assert "regression analysis" in joined
