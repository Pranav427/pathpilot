import os
import re
from dataclasses import dataclass
from datetime import datetime

from analyzer import analyze_job
from job_fetcher import FetchedJob, fetch_job_from_url
from matcher import match_profile_to_job
from tracker import record_job_search_run


URL_PATTERN = re.compile(r"https?://[^\s]+")
NON_JOB_URL_MARKERS = (
    "freshershunt.in/pro",
    "freshershunt.in/whatsapp",
    "fhlinks.in/freshershunt-app",
    "youtu.be/",
    "youtube.com/",
    "yt.openinapp.co/",
    "instagram.com/",
    "t.me/",
    "telegram.me/",
    "tinyurl.com/",
    "bit.ly/",
    "rebrand.ly/",
    "pdlink.in/",
    "wa.me/",
    "whatsapp",
)


@dataclass
class RankedJob:
    """A fetched job with analysis, match details, and ranking metadata."""

    rank: int
    fetched_job: FetchedJob
    job_analysis: dict
    match: dict
    error: str = ""


def extract_urls_from_text(text: str) -> list[str]:
    """Extracts clean URLs from pasted text that may include labels or icons."""
    urls = []
    seen = set()
    for match in URL_PATTERN.findall(str(text)):
        url = match.strip().rstrip(".,);]")
        if any(marker in url.lower() for marker in NON_JOB_URL_MARKERS):
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def action_label(score: int) -> str:
    """Returns a user-facing action label for a fit score."""
    if score >= 65:
        return "Recommended"
    if score >= 45:
        return "Review Carefully"
    return "Skip"


def collect_job_urls() -> list[str]:
    """Reads multiple job URLs from the terminal."""
    print("📋 STEP 1 — MULTIPLE JOB URLS")
    print("-" * 40)
    print("Paste one job URL per line, or paste a full job list.")
    print("The system will automatically extract https:// links.")
    print("When done, type 'DONE' on a new line and press Enter:\n")

    pasted_lines = []
    while True:
        line = input().strip()
        if line.upper() == "DONE":
            break
        if line:
            pasted_lines.append(line)

    urls = extract_urls_from_text("\n".join(pasted_lines))
    print(f"\n🔗 Found {len(urls)} job URL(s).")
    return urls


def rank_jobs_from_urls(
    urls: list[str],
    profile: dict,
    progress_callback=None,
) -> tuple[list[RankedJob], list[str]]:
    """
    Fetches, analyzes, matches, and ranks multiple job URLs.

    Returns:
        ranked_jobs: successfully processed jobs sorted by fit score.
        failures: readable error messages for URLs that could not be processed.
    """
    ranked_jobs = []
    failures = []

    for index, url in enumerate(urls, 1):
        if progress_callback:
            progress_callback(index, len(urls), url, "processing", "")
        print("\n" + "=" * 60)
        print(f"Processing job {index}/{len(urls)}")
        print("=" * 60)
        print(f"URL: {url}")

        try:
            print("🌐 Fetching job page...")
            fetched_job = fetch_job_from_url(url)
            print(
                "✅ Fetched: "
                f"{fetched_job.company_name} | {fetched_job.job_title}"
            )

            print("📊 Analyzing job description...")
            job_analysis = analyze_job(fetched_job.job_description)
            print("✅ Job analyzed")

            print("🎯 Calculating profile fit...")
            match = match_profile_to_job(job_analysis, profile)
            print(
                "✅ Fit calculated: "
                f"{match['match_score']}/100 "
                f"({match.get('fit_verdict_label', 'Fit scored')}, "
                f"{action_label(match['match_score'])})"
            )

            ranked_jobs.append(
                RankedJob(
                    rank=0,
                    fetched_job=fetched_job,
                    job_analysis=job_analysis,
                    match=match,
                )
            )
            if progress_callback:
                progress_callback(
                    index,
                    len(urls),
                    url,
                    "success",
                    (
                        f"{fetched_job.company_name} · "
                        f"{fetched_job.job_title}"
                    ),
                )

        except Exception as exc:
            message = f"{url} -> {exc}"
            failures.append(message)
            print(f"❌ Skipped: {exc}")
            if progress_callback:
                progress_callback(
                    index,
                    len(urls),
                    url,
                    "failed",
                    str(exc),
                )

    ranked_jobs.sort(
        key=lambda item: (
            item.match.get("match_score", 0),
            item.fetched_job.extraction_quality == "high",
        ),
        reverse=True,
    )

    for rank, job in enumerate(ranked_jobs, 1):
        job.rank = rank

    return ranked_jobs, failures


def display_ranked_jobs(ranked_jobs: list[RankedJob], failures: list[str] = None):
    """Prints ranked jobs in a compact terminal view."""
    print("\n" + "=" * 70)
    print("                  RANKED JOB MATCHES")
    print("=" * 70)

    if not ranked_jobs:
        print("\nNo jobs could be processed successfully.")
    else:
        for job in ranked_jobs:
            fetched = job.fetched_job
            match = job.match
            print(
                f"\n#{job.rank} | {match['match_score']}/100 "
                f"| {match.get('fit_verdict_label', 'Fit scored')}"
                f" | {action_label(match['match_score'])}"
                f"\n   Company : {fetched.company_name}"
                f"\n   Role    : {fetched.job_title}"
                f"\n   Quality : {fetched.extraction_quality}"
                f"\n   Apply Link : {fetched.source_url}"
            )

            missing = match.get("missing_skills", [])[:4]
            if missing:
                print(f"   Gaps    : {', '.join(missing)}")

    if failures:
        print("\n" + "-" * 70)
        print("Skipped URLs:")
        for failure in failures:
            print(f"   - {failure}")

    print("=" * 70)


def ranked_jobs_report(ranked_jobs: list[RankedJob], failures: list[str] = None) -> str:
    """Builds a plain-text report of ranked jobs."""
    lines = [
        "APPLYSMART AI - RANKED JOB REPORT",
        "=" * 70,
        f"Generated At: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    if not ranked_jobs:
        lines.append("No jobs were processed successfully.")
    else:
        for job in ranked_jobs:
            fetched = job.fetched_job
            match = job.match
            lines.extend(
                [
                    f"Rank: #{job.rank}",
                    f"Company: {fetched.company_name}",
                    f"Role: {fetched.job_title}",
                    f"Fit Score: {match['match_score']}/100",
                    f"Fit Verdict: {match.get('fit_verdict_label', 'Fit scored')}",
                    f"Action Label: {action_label(match['match_score'])}",
                    f"Extraction Quality: {fetched.extraction_quality}",
                    f"Apply Link: {fetched.source_url}",
                ]
            )

            missing = match.get("missing_skills", [])[:6]
            if missing:
                lines.append(f"Top Gaps: {', '.join(missing)}")

            strengths = match.get("strongest_points", [])[:3]
            if strengths:
                lines.append("Strongest Points:")
                lines.extend(f"- {point}" for point in strengths)

            lines.append("-" * 70)

    if failures:
        lines.extend(["", "SKIPPED URLS", "-" * 70])
        lines.extend(f"- {failure}" for failure in failures)

    return "\n".join(lines).strip() + "\n"


def save_ranked_jobs_report(
    ranked_jobs: list[RankedJob],
    failures: list[str] = None,
    output_dir: str = "outputs",
) -> str:
    """Saves ranked job results to a timestamped text file."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"job_rankings_{timestamp}.txt")
    with open(path, "w", encoding="utf-8") as file:
        file.write(ranked_jobs_report(ranked_jobs, failures))
    print(f"\n🧾 Ranked job report saved → {path}")
    print(f"   To open after the app exits: open \"{path}\"")
    return path


def parse_rank_selection(selection: str, max_rank: int) -> list[int]:
    """Parses rank input like '1', '1,2,3', or '1-3'."""
    selection = selection.strip()
    if not selection:
        return []

    ranks = set()
    parts = [part.strip() for part in selection.split(",") if part.strip()]
    for part in parts:
        if "-" in part:
            start_text, end_text = [item.strip() for item in part.split("-", 1)]
            if not start_text.isdigit() or not end_text.isdigit():
                raise ValueError("Ranges must look like 1-3.")
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError("Range start must be smaller than range end.")
            ranks.update(range(start, end + 1))
        else:
            if not part.isdigit():
                raise ValueError("Use rank numbers only, like 1,2,3.")
            ranks.add(int(part))

    invalid = [rank for rank in ranks if rank < 1 or rank > max_rank]
    if invalid:
        raise ValueError(f"Rank out of range: {invalid[0]}")

    return sorted(ranks)


def confirm_selected_jobs(selected_jobs: list[RankedJob]) -> bool:
    """Shows selected jobs and asks for confirmation before generation."""
    print("\n" + "=" * 70)
    print("               SHORTLIST CONFIRMATION")
    print("=" * 70)
    for job in selected_jobs:
        match = job.match
        fetched = job.fetched_job
        print(
            f"\n#{job.rank} | {match['match_score']}/100 "
            f"| {action_label(match['match_score'])}"
            f"\n   Company : {fetched.company_name}"
            f"\n   Role    : {fetched.job_title}"
        )
    print(
        f"\nThis will generate {len(selected_jobs)} resume(s) "
        f"and {len(selected_jobs)} cover letter(s) using AI."
    )
    choice = input("Continue? (y/n): ").strip().lower()
    return choice == "y"


def select_ranked_jobs(ranked_jobs: list[RankedJob]) -> list[RankedJob]:
    """Asks which ranked jobs should continue to document generation."""
    while True:
        choice = input(
            "\nEnter ranks to shortlist for application generation "
            "(examples: 1 or 1,2,3 or 1-3). "
            "Press Enter to stop: "
        ).strip()
        if not choice:
            print("No jobs selected. Stopping after ranking.")
            return []
        if choice.lower().startswith("open "):
            print(
                "That is a terminal command. Enter only rank numbers here. "
                "You can open the report after exiting the app."
            )
            continue

        try:
            selected_ranks = parse_rank_selection(choice, len(ranked_jobs))
        except ValueError as exc:
            print(f"Please enter valid ranks: {exc}")
            continue

        selected_jobs = [job for job in ranked_jobs if job.rank in selected_ranks]
        if confirm_selected_jobs(selected_jobs):
            return selected_jobs

        print("Selection cancelled. You can choose different ranks.")


def run_job_search(profile: dict) -> list[RankedJob]:
    """Runs the complete multi-URL job ranking workflow."""
    urls = collect_job_urls()
    if not urls:
        print("❌ No job URLs entered.")
        return []

    ranked_jobs, failures = rank_jobs_from_urls(urls, profile)
    display_ranked_jobs(ranked_jobs, failures)
    report_path = save_ranked_jobs_report(ranked_jobs, failures)
    search_run_id = record_job_search_run(
        ranked_jobs=ranked_jobs,
        failures=failures,
        total_urls=len(urls),
        report_path=report_path,
    )
    print(f"🗄️  Job ranking saved to database with run ID #{search_run_id}")

    if not ranked_jobs:
        return []

    return select_ranked_jobs(ranked_jobs)


if __name__ == "__main__":
    from profile import get_profile

    selected_jobs = run_job_search(get_profile())
    for selected in selected_jobs:
        print(
            "\nSelected: "
            f"{selected.fetched_job.company_name} | {selected.fetched_job.job_title}"
        )
