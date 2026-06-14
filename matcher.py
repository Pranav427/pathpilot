# matcher.py

from analyzer import analyze_job
from profile import get_profile
from scoring import calculate_fit_score


def build_grounded_strongest_points(
    job_analysis: dict,
    profile: dict,
    deterministic: dict,
) -> list[str]:
    """Build interview evidence from verified profile records only."""
    confirmed = {
        str(term).strip().lower()
        for term in profile.get("_application_confirmed_terms", [])
    }
    matched = [
        term
        for term in (
            deterministic.get("matched_skills", [])
            + deterministic.get("matched_tools", [])
        )
        if str(term).strip().lower() not in confirmed
    ]

    points = []
    if matched:
        points.append(
            "Verified profile skills relevant to this role: "
            + ", ".join(matched[:5])
            + "."
        )

    projects = profile.get("projects", [])
    if projects:
        requirement_text = " ".join(
            str(item)
            for key in ("skills", "tools", "keywords", "summary")
            for item in (
                job_analysis.get(key, [])
                if isinstance(job_analysis.get(key), list)
                else [job_analysis.get(key, "")]
            )
        ).lower()

        def relevance(project: dict) -> int:
            project_text = " ".join(
                [
                    str(project.get("name", "")),
                    str(project.get("domain", "")),
                    str(project.get("description", "")),
                    " ".join(project.get("tools", [])),
                    " ".join(project.get("highlights", [])),
                ]
            ).lower()
            terms = {
                term
                for term in requirement_text.replace("/", " ").split()
                if len(term) >= 4
            }
            return sum(1 for term in terms if term in project_text)

        project = max(projects, key=relevance)
        tools = ", ".join(project.get("tools", [])[:5])
        detail = f" using {tools}" if tools else ""
        points.append(
            f"Project evidence: {project.get('name', 'Relevant project')}{detail}."
        )

    evidence = []
    education = profile.get("education", [])
    certifications = profile.get("certifications", [])
    if education:
        evidence.append(education[0].get("degree", ""))
    if certifications:
        evidence.append(certifications[0])
    if evidence:
        points.append(
            "Education and certification evidence: "
            + "; ".join(item for item in evidence if item)
            + "."
        )

    return points[:3]


def match_profile_to_job(job_analysis: dict, profile: dict) -> dict:
    """
    Compares job requirements with candidate profile.
    Returns matches, gaps, score and recommendation.
    """

    deterministic = calculate_fit_score(job_analysis, profile)
    grounded_points = build_grounded_strongest_points(
        job_analysis,
        profile,
        deterministic,
    )
    return {
        **deterministic,
        "strongest_points": grounded_points,
        "recommendation": deterministic["fit_guidance"],
    }


def display_match(match: dict):
    """
    Prints the match result in a readable format.
    """
    print("\n" + "="*50)
    print("         PROFILE MATCH ANALYSIS")
    print("="*50)

    score = match["match_score"]
    if score >= 75:
        grade = "🟢 Strong Match"
    elif score >= 50:
        grade = "🟡 Moderate Match"
    else:
        grade = "🔴 Needs Improvement"

    verdict = match.get("fit_verdict_label", grade)
    print(f"\n🎯 MATCH SCORE: {score}/100  —  {verdict}")

    if match.get("fit_guidance"):
        print("\n🧭 FIT GUIDANCE:")
        print(f"   {match['fit_guidance']}")

    if match.get("score_components"):
        print("\n📊 SCORE BREAKDOWN:")
        for label, value in match["score_components"].items():
            clean_label = label.replace("_", " ").title()
            print(f"   • {clean_label}: {value}")

    print("\n✅ MATCHED SKILLS:")
    for skill in match["matched_skills"]:
        print(f"   • {skill}")

    print("\n❌ MISSING SKILLS:")
    for skill in match["missing_skills"]:
        print(f"   • {skill}")

    print("\n✅ MATCHED TOOLS:")
    for tool in match["matched_tools"]:
        print(f"   • {tool}")

    print("\n❌ MISSING TOOLS:")
    for tool in match["missing_tools"]:
        print(f"   • {tool}")

    print("\n⭐ STRONGEST POINTS TO HIGHLIGHT:")
    for point in match["strongest_points"]:
        print(f"   • {point}")

    print("\n💡 RECOMMENDATION:")
    print(f"   {match['recommendation']}")

    print("\n" + "="*50)


if __name__ == "__main__":

    sample_job = """
    We are looking for a Data Science Intern who is passionate
    about analyzing data, building models, and deriving actionable insights.

    Requirements:
    - Strong knowledge of Python programming
    - Basic understanding of machine learning algorithms
    - Familiarity with data visualization tools
    - Understanding of statistics and probability concepts
    - Experience with pandas, NumPy, scikit-learn
    - Familiarity with TensorFlow or PyTorch is a plus
    - Basic knowledge of SQL
    """

    print("Step 1: Analyzing job description...")
    job_analysis = analyze_job(sample_job)
    print("✅ Job analyzed")

    print("\nStep 2: Loading candidate profile...")
    profile = get_profile()
    print("✅ Profile loaded")

    print("\nStep 3: Matching profile to job...")
    match = match_profile_to_job(job_analysis, profile)
    display_match(match)
