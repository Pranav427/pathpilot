# main.py
# PathPilot — Master Controller
# One command → full pipeline → resume PDF + cover letter PDF

from analyzer import analyze_job, display_analysis
from profile import get_profile, display_profile
from matcher import match_profile_to_job, display_match
from resume import (
    display_resume,
)
from cover_letter import (
    display_cover_letter
)
from quality import display_ats_report
from job_fetcher import clean_company, fetch_job_from_url, display_fetched_job
from job_search import action_label, run_job_search
from application_service import (
    ApplicationDraft,
    generate_application_draft,
    get_missing_profile_terms,
    prepare_match,
    save_application_draft,
    unique_items,
    validate_job_description as validate_job_description_or_raise,
)


def confirm_missing_profile_terms(match: dict) -> list[str]:
    """
    Asks the user which detected gaps they can honestly claim.
    This does not permanently edit profile.py.
    """
    missing_terms = get_missing_profile_terms(match)
    if not missing_terms:
        return []

    suggested_terms = missing_terms
    print("\n🧩 PROFILE GAP CHECK")
    print("-" * 40)
    print("The job needs these terms that are weak/missing in your current profile:")
    for index, term in enumerate(suggested_terms, 1):
        print(f"   {index}. {term}")

    print("\nIf you honestly know any of these, enter them now.")
    print(
        "Use comma-separated names, numbers, or ranges, "
        "for example: 1, 3-5, Error Handling"
    )
    answer = input("Add to this application only? Press Enter to skip: ").strip()
    if not answer:
        return []

    confirmed = []
    for raw_part in answer.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = [
                value.strip() for value in part.split("-", 1)
            ]
            if start_text.isdigit() and end_text.isdigit():
                start = int(start_text)
                end = int(end_text)
                if start <= end:
                    for index in range(start, end + 1):
                        if 1 <= index <= len(suggested_terms):
                            confirmed.append(suggested_terms[index - 1])
                        else:
                            print(f"⚠️  Ignoring invalid number: {index}")
                    continue
        if part.isdigit():
            index = int(part)
            if 1 <= index <= len(suggested_terms):
                confirmed.append(suggested_terms[index - 1])
            else:
                print(f"⚠️  Ignoring invalid number: {part}")
        else:
            confirmed.append(part)

    confirmed = unique_items(confirmed)
    if confirmed:
        print("\n✅ Confirmed for this application only:")
        for term in confirmed:
            print(f"   • {term}")
        print("   Note: profile.py was not permanently changed.")
    return confirmed


def print_banner():
    print("\n" + "="*60)
    print("        🚀 PATHPILOT — CAREER INTELLIGENCE WORKSPACE")
    print("="*60)
    print("  Powered by IYBUN  |  Built with Python")
    print("="*60 + "\n")


def get_manual_job_input() -> tuple:
    print("📋 STEP 1 — JOB DETAILS")
    print("-"*40)

    company_name = input("Enter company name: ").strip()
    job_title    = input("Enter job title: ").strip()

    print("\nPaste the job description below.")
    print("When done, type 'DONE' on a new line and press Enter:\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "DONE":
            break
        lines.append(line)

    job_description = "\n".join(lines)
    return company_name, job_title, job_description, ""


def confirm_or_edit_detected_job(company_name: str, job_title: str) -> tuple:
    print("\nDetected job details:")
    print(f"Company : {company_name}")
    print(f"Role    : {job_title}")
    choice = input("\nUse these details? (y/n): ").strip().lower()
    if choice == "y":
        return company_name, job_title

    corrected_company = input("Enter correct company name: ").strip()
    corrected_title = input("Enter correct job title: ").strip()
    return (
        corrected_company or company_name or "Company",
        corrected_title or job_title or "Role",
    )


def get_url_job_input() -> tuple:
    print("📋 STEP 1 — JOB URL")
    print("-"*40)
    url = input("Enter job URL: ").strip()

    print("\n🌐 Fetching job page...")
    fetched_job = fetch_job_from_url(url)
    display_fetched_job(fetched_job)

    company_name, job_title = confirm_or_edit_detected_job(
        fetched_job.company_name,
        fetched_job.job_title,
    )

    preview_choice = input("\nPreview extracted JD before continuing? (y/n): ").strip().lower()
    if preview_choice == "y":
        print("\n" + "=" * 60)
        print("              EXTRACTED JOB DESCRIPTION PREVIEW")
        print("=" * 60)
        print(fetched_job.job_description[:3000])
        if len(fetched_job.job_description) > 3000:
            print("\n... preview truncated ...")
        print("=" * 60)

    return company_name, job_title, fetched_job.job_description, fetched_job.source_url


def job_input_from_ranked_job(selected_job, profile: dict) -> tuple:
    """Converts a RankedJob into the pipeline input tuple."""
    return (
        selected_job.fetched_job.company_name,
        selected_job.fetched_job.job_title,
        selected_job.fetched_job.job_description,
        selected_job.fetched_job.source_url,
        selected_job.job_analysis,
        profile,
        selected_job.match,
    )


def job_input_from_basic_input(basic_input: tuple) -> tuple:
    """Converts manual or single-URL input into the pipeline input tuple."""
    company_name, job_title, job_description, source_url = basic_input
    return company_name, job_title, job_description, source_url, None, None, None


def get_job_input() -> list[tuple]:
    print("📋 CHOOSE JOB INPUT METHOD")
    print("-"*40)
    print("1. Paste job description manually")
    print("2. Extract from job URL")
    print("3. Rank multiple job URLs")

    choice = input("\nChoose input method (1/2/3): ").strip()
    if choice == "2":
        try:
            return [job_input_from_basic_input(get_url_job_input())]
        except Exception as exc:
            print(f"\n❌ URL extraction failed: {exc}")
            print("Falling back to manual job description input.\n")
            return [job_input_from_basic_input(get_manual_job_input())]

    if choice == "3":
        profile = get_profile()
        selected_jobs = run_job_search(profile)
        if selected_jobs:
            return [
                job_input_from_ranked_job(selected_job, profile)
                for selected_job in selected_jobs
            ]
        print("Falling back to manual job description input.\n")

    company_name, job_title, job_description, source_url = get_manual_job_input()
    return [(company_name, job_title, job_description, source_url, None, None, None)]


def get_tone_preference() -> str:
    print("\n🎨 COVER LETTER TONE")
    print("-"*40)
    print("1. Professional")
    print("2. Enthusiastic")
    print("3. Friendly")

    choice = input("\nChoose tone (1/2/3): ").strip()
    tones  = {"1": "professional", "2": "enthusiastic", "3": "friendly"}
    return tones.get(choice, "professional")


def run_pipeline(
    company_name: str,
    job_title: str,
    job_description: str,
    tone: str,
    job_analysis: dict = None,
    profile: dict = None,
    match: dict = None,
):
    print("\n" + "="*60)
    print("           ⚙️  RUNNING PIPELINE")
    print("="*60)

    had_analysis = job_analysis is not None
    had_profile = profile is not None
    had_match = match is not None

    if not had_analysis:
        print("\n📊 Step 1/6 — Analyzing job description...")
    else:
        print("\n📊 Step 1/6 — Using existing job analysis from ranking")

    if not had_profile:
        print("\n👤 Step 2/6 — Loading candidate profile...")
    else:
        print("\n👤 Step 2/6 — Using existing candidate profile")

    if not had_match:
        print("\n🎯 Step 3/6 — Matching profile to job requirements...")
    else:
        print("\n🎯 Step 3/6 — Using existing match result from ranking")

    job_analysis, profile, match = prepare_match(
        job_description=job_description,
        job_analysis=job_analysis,
        profile=profile,
        match=match,
    )
    if not had_analysis:
        print("✅ Job analyzed successfully")
    if not had_profile:
        print("✅ Profile loaded successfully")

    score = match["match_score"]
    verdict_label = match.get("fit_verdict_label", "Fit scored")
    print(
        f"✅ Match complete — Score: {score}/100 "
        f"{verdict_label} ({action_label(score)})"
    )

    confirmed_terms = confirm_missing_profile_terms(match)
    if confirmed_terms:
        print("\n🔁 Updating temporary profile and recalculating fit...")

    # ── Step 4: Generate Resume ───────────────────────────────
    print("\n📄 Step 4/6 — Generating tailored resume...")
    draft = generate_application_draft(
        company_name=company_name,
        job_title=job_title,
        job_description=job_description,
        tone=tone,
        confirmed_terms=confirmed_terms,
        job_analysis=job_analysis,
        profile=profile,
        match=match,
    )
    if confirmed_terms:
        score = draft.match["match_score"]
        verdict_label = draft.match.get("fit_verdict_label", "Fit scored")
        print(
            f"✅ Updated match — Score: {score}/100 "
            f"{verdict_label} ({action_label(score)})"
        )
    if draft.match.get("fit_verdict") in {"STRETCH_MATCH", "NOT_RECOMMENDED"}:
        print("\n⚠️  FIT WARNING")
        print(
            f"   {draft.match.get('fit_guidance', 'This role has important gaps.')}"
        )
        print(
            "   The system will generate drafts, but review them carefully "
            "before applying."
        )
    print("✅ Resume generated successfully")

    # ── Step 5: Generate Cover Letter ─────────────────────────
    print("\n✉️  Step 5/6 — Generating cover letter...")
    print("✅ Cover letter generated successfully")

    # ── Step 6: ATS Quality Check ─────────────────────────────
    print("\n🔎 Step 6/6 — Checking ATS quality...")
    print(
        "✅ ATS check complete — "
        f"Keyword Coverage: {draft.ats_report['keyword_coverage']}/100"
    )

    return (
        draft.job_analysis,
        draft.profile,
        draft.match,
        draft.resume,
        draft.cover_letter,
        draft.ats_report,
    )


def validate_job_description(job_description: str) -> bool:
    """Returns True when the JD has enough text for reliable analysis."""
    try:
        validate_job_description_or_raise(job_description)
    except ValueError as exc:
        print(f"❌ {exc}")
        return False
    return True


def save_all_outputs(
    resume: str,
    cover_letter: str,
    profile: dict,
    job_analysis: dict,
    match: dict,
    ats_report: dict,
    company_name: str,
    job_title: str,
    source_url: str = ""
):
    print("\n" + "="*60)
    print("           💾 SAVING OUTPUTS")
    print("="*60)

    draft = ApplicationDraft(
        company_name=company_name,
        job_title=job_title,
        source_url=source_url,
        job_analysis=job_analysis,
        profile=profile,
        match=match,
        resume=resume,
        cover_letter=cover_letter,
        ats_report=ats_report,
    )
    saved = save_application_draft(draft)
    print(f"\n🗂  Application tracked with ID #{saved.application_id}")
    return saved.resume_pdf, saved.cover_letter_pdf, saved.application_id


def print_summary(
    match: dict,
    ats_report: dict,
    resume_pdf: str,
    letter_pdf: str,
    application_id: int,
    company_name: str,
    job_title: str,
    source_url: str = ""
):
    print("\n" + "="*60)
    print("           ✅ APPLICATION READY!")
    print("="*60)

    print(f"\n🏢 Company      : {company_name}")
    print(f"💼 Role         : {job_title}")
    if source_url:
        print(f"🔗 Apply Link   : {source_url}")
    print(f"🗂  Tracker ID   : {application_id}")
    print(f"🎯 Match Score  : {match['match_score']}/100")
    if match.get("fit_verdict_label"):
        print(f"🧭 Fit Verdict  : {match['fit_verdict_label']}")
    print(f"🔎 ATS Coverage : {ats_report['keyword_coverage']}/100")

    if match.get("score_components"):
        print("\n📊 FIT SCORE BREAKDOWN:")
        for label, value in match["score_components"].items():
            print(f"   • {label.replace('_', ' ').title()}: {value}")

    if match.get("user_confirmed_terms"):
        print("\n🧩 CONFIRMED FOR THIS APPLICATION ONLY:")
        for term in match["user_confirmed_terms"]:
            print(f"   • {term}")

    print(f"\n📄 Resume PDF       → {resume_pdf}")
    print(f"✉️  Cover Letter PDF → {letter_pdf}")

    print("\n⭐ TOP THINGS TO HIGHLIGHT IN YOUR INTERVIEW:")
    for i, point in enumerate(match["strongest_points"], 1):
        print(f"   {i}. {point}")

    print("\n💡 QUICK TIP:")
    print(f"   {match['recommendation']}")

    if match["missing_skills"]:
        print("\n📚 SKILLS TO LEARN NEXT:")
        for skill in match["missing_skills"]:
            print(f"   • {skill}")

    if ats_report["missing_terms"]:
        print("\n🔎 ATS TERMS TO CONSIDER ADDING IF TRUE:")
        for term in ats_report["missing_terms"][:8]:
            print(f"   • {term}")

    print("\n🔍 TO OPEN YOUR FILES:")
    print(f"   open \"{resume_pdf}\"")
    print(f"   open \"{letter_pdf}\"")
    if source_url:
        print(f"   open \"{source_url}\"")

    print("\n" + "="*60)
    print("  Good luck with your application! 🍀")
    print("="*60 + "\n")


def ask_show_details() -> bool:
    choice = input("\nWould you like to see the full output? (y/n): ").strip().lower()
    return choice == "y"


def ask_save_generated_outputs() -> bool:
    """Final human approval before writing PDFs and tracker records."""
    choice = input(
        "\nSave these materials as PDFs and add to tracker? (y/n): "
    ).strip().lower()
    return choice in {"y", "yes"}


def process_job_input(job_input: tuple, tone: str, show_details: bool):
    """Runs the full application generation flow for one job input."""
    (
        company_name,
        job_title,
        job_description,
        source_url,
        precomputed_analysis,
        precomputed_profile,
        precomputed_match,
    ) = job_input

    if not job_description.strip():
        print("❌ No job description entered. Skipping.")
        return

    if not validate_job_description(job_description):
        return

    if not company_name.strip():
        company_name = "Company"
    else:
        company_name = clean_company(company_name)

    if not job_title.strip():
        job_title = "Role"

    job_analysis, profile, match, resume, cover_letter, ats_report = run_pipeline(
        company_name=company_name,
        job_title=job_title,
        job_description=job_description,
        tone=tone,
        job_analysis=precomputed_analysis,
        profile=precomputed_profile,
        match=precomputed_match,
    )

    if show_details:
        display_analysis(job_analysis)
        display_match(match)
        display_resume(resume)
        display_cover_letter(cover_letter)
        display_ats_report(ats_report)

    if not ask_save_generated_outputs():
        print("\nSkipped saving. Review the generated content and rerun when ready.")
        return

    resume_pdf, letter_pdf, application_id = save_all_outputs(
        resume=resume,
        cover_letter=cover_letter,
        profile=profile,
        job_analysis=job_analysis,
        match=match,
        ats_report=ats_report,
        company_name=company_name,
        job_title=job_title,
        source_url=source_url,
    )

    print_summary(
        match=match,
        ats_report=ats_report,
        resume_pdf=resume_pdf,
        letter_pdf=letter_pdf,
        application_id=application_id,
        company_name=company_name,
        job_title=job_title,
        source_url=source_url,
    )


# ── MAIN ENTRY POINT ──────────────────────────────────────────
if __name__ == "__main__":

    # Welcome
    print_banner()

    # Get inputs
    job_inputs = get_job_input()
    if not job_inputs:
        print("No jobs selected. Exiting.")
        exit()

    # Get tone
    tone = get_tone_preference()

    show_details = ask_show_details()
    for index, job_input in enumerate(job_inputs, 1):
        if len(job_inputs) > 1:
            print("\n" + "=" * 60)
            print(f"      GENERATING APPLICATION {index}/{len(job_inputs)}")
            print("=" * 60)
        process_job_input(job_input, tone, show_details)
