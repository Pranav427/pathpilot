# tracker.py

import json
import os
import webbrowser
import hashlib
from datetime import datetime, timezone
import db_client


DB_PATH = "outputs/applications.db"

# Valid application lifecycle statuses
VALID_STATUSES = [
    "SHORTLISTED",        # Shortlisted from discovery or ranking
    "DRAFT_GENERATED",    # Documents created, not applied yet
    "APPLIED",            # Application submitted
    "ASSESSMENT",         # Online assessment received
    "INTERVIEW",          # Interview scheduled or done
    "OFFER",              # Offer received
    "REJECTED",           # Rejected at any stage
    "WITHDRAWN",          # You withdrew the application
]


def init_db(db_path: str = DB_PATH):
    """Creates the database and table if they don't exist."""
    db_client.init_db_schema(db_path)


def register_user(email: str, password_plain: str, db_path: str = DB_PATH) -> int:
    """Registers a new user and returns their user ID. Raises ValueError if email exists."""
    init_db(db_path)
    email = email.strip().lower()
    pw_hash = hashlib.sha256(password_plain.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    
    try:
        user_id = db_client.execute_write(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, pw_hash, now),
            db_path=db_path
        )
        # Create a default blank profile structure for this user
        db_client.execute_write(
            "INSERT INTO user_profiles (user_id, name, email, raw_profile_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, email.split("@")[0].title(), email, "{}", now),
            db_path=db_path
        )
        return int(user_id)
    except Exception as e:
        err_msg = str(e).lower()
        if "unique" in err_msg or "integrity" in err_msg or "duplicate" in err_msg:
            raise ValueError(f"User with email '{email}' already exists.")
        raise


def authenticate_user(email: str, password_plain: str, db_path: str = DB_PATH) -> int | None:
    """Verifies credentials and returns user ID, or None if invalid."""
    init_db(db_path)
    email = email.strip().lower()
    pw_hash = hashlib.sha256(password_plain.encode("utf-8")).hexdigest()
    
    rows = db_client.execute_query(
        "SELECT id FROM users WHERE email=? AND password_hash=?",
        (email, pw_hash),
        db_path=db_path
    )
    return int(rows[0]["id"]) if rows else None


def get_user_profile(user_id: int, profile_name: str = "Default", db_path: str = DB_PATH) -> dict | None:
    """Fetches user profile details as a candidate profile dict."""
    init_db(db_path)
    rows = db_client.execute_query(
        "SELECT * FROM user_profiles WHERE user_id=? AND profile_name=?",
        (user_id, profile_name),
        db_path=db_path
    )
    if not rows:
        return None
    row = rows[0]
    
    try:
        profile = json.loads(row["raw_profile_json"])
    except (TypeError, json.JSONDecodeError):
        profile = {}
        
    profile.setdefault("name", row["name"])
    profile.setdefault("email", row["email"])
    profile.setdefault("phone", row["phone"] or "")
    profile.setdefault("linkedin", row["linkedin"] or "")
    profile.setdefault("github", row["github"] or "")
    profile.setdefault("portfolio", row["portfolio"] or "")
    profile.setdefault("location", row["location"] or "")
    profile.setdefault("objective", "")
    profile.setdefault("education", [])
    profile.setdefault("experience", [])
    profile.setdefault("projects", [])
    profile.setdefault("skills", {})
    profile.setdefault("certifications", [])
    profile.setdefault("achievements", [])
    return profile


def get_user_email(user_id: int, db_path: str = DB_PATH) -> str | None:
    """Returns the email address for a given user ID."""
    init_db(db_path)
    rows = db_client.execute_query(
        "SELECT email FROM users WHERE id=?",
        (user_id,),
        db_path=db_path
    )
    return rows[0]["email"] if rows else None


def save_user_profile(user_id: int, profile: dict, profile_name: str = "Default", db_path: str = DB_PATH, bypass_demo_lock: bool = False) -> None:
    """Saves candidate profile dict back to the database user_profiles table."""
    init_db(db_path)
    if not bypass_demo_lock and get_user_email(user_id, db_path) == "demo@pathpilot.ai":
        existing = db_client.execute_query(
            "SELECT user_id FROM user_profiles WHERE user_id = ? AND profile_name = ?",
            (user_id, profile_name),
            db_path=db_path
        )
        if existing:
            return
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    
    name = profile.get("name", "").strip()
    email = profile.get("email", "").strip()
    phone = profile.get("phone", "").strip()
    linkedin = profile.get("linkedin", "").strip()
    github = profile.get("github", "").strip()
    portfolio = profile.get("portfolio", "").strip()
    location = profile.get("location", "").strip()
    
    raw_profile_json = json.dumps(profile, ensure_ascii=False)
    
    db_client.execute_write(
        """
        INSERT INTO user_profiles (
            user_id, profile_name, name, email, phone, linkedin, github, portfolio, location, raw_profile_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, profile_name) DO UPDATE SET
            name=excluded.name,
            email=excluded.email,
            phone=excluded.phone,
            linkedin=excluded.linkedin,
            github=excluded.github,
            portfolio=excluded.portfolio,
            location=excluded.location,
            raw_profile_json=excluded.raw_profile_json,
            updated_at=excluded.updated_at
        """,
        (user_id, profile_name, name, email, phone, linkedin, github, portfolio, location, raw_profile_json, now),
        db_path=db_path
    )


def list_user_profiles(user_id: int, db_path: str = DB_PATH) -> list[str]:
    """Returns a list of profile/persona names for the given user."""
    init_db(db_path)
    rows = db_client.execute_query(
        "SELECT profile_name FROM user_profiles WHERE user_id=? ORDER BY profile_name ASC",
        (user_id,),
        db_path=db_path
    )
    return [row["profile_name"] for row in rows]


def delete_user_profile(user_id: int, profile_name: str, db_path: str = DB_PATH) -> None:
    """Deletes a career persona for a user."""
    init_db(db_path)
    db_client.execute_write(
        "DELETE FROM user_profiles WHERE user_id=? AND profile_name=?",
        (user_id, profile_name),
        db_path=db_path
    )


def record_job_search_run(
    ranked_jobs: list,
    failures: list[str],
    total_urls: int,
    report_path: str = "",
    user_id: int = 1,
    db_path: str = DB_PATH,
) -> int:
    """Stores one job ranking session and its ranked jobs."""
    init_db(db_path)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    search_run_id = db_client.execute_write(
        """
        INSERT INTO job_search_runs (
            total_urls, successful_jobs, failed_jobs,
            report_path, failures_json, created_at, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(total_urls),
            len(ranked_jobs),
            len(failures or []),
            report_path,
            json.dumps(failures or [], ensure_ascii=False),
            now,
            user_id,
        ),
        db_path=db_path
    )

    for job in ranked_jobs:
        fetched = job.fetched_job
        match = job.match
        db_client.execute_write(
            """
            INSERT INTO ranked_jobs (
                search_run_id, rank, company_name, job_title, source_url,
                fit_score, fit_verdict, extraction_quality,
                missing_skills_json, job_analysis_json, match_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                search_run_id,
                int(job.rank),
                fetched.company_name,
                fetched.job_title,
                fetched.source_url,
                int(match.get("match_score", 0)),
                match.get("fit_verdict_label", ""),
                fetched.extraction_quality,
                json.dumps(match.get("missing_skills", []), ensure_ascii=False),
                json.dumps(job.job_analysis, ensure_ascii=False),
                json.dumps(match, ensure_ascii=False),
                now,
            ),
            db_path=db_path
        )

    return search_run_id


def list_job_search_runs(limit: int = 10, db_path: str = DB_PATH, user_id: int = 1) -> list[dict]:
    """Returns recent job ranking sessions for a user."""
    init_db(db_path)
    rows = db_client.execute_query(
        """
        SELECT id, total_urls, successful_jobs, failed_jobs,
               report_path, failures_json, created_at
        FROM job_search_runs
        WHERE user_id = ?
        ORDER BY id DESC LIMIT ?
        """,
        (user_id, limit),
        db_path=db_path
    )
    return [dict(row) for row in rows]


def list_ranked_jobs_for_run(
    search_run_id: int,
    db_path: str = DB_PATH
) -> list[dict]:
    """Returns ranked jobs for one search session."""
    init_db(db_path)
    rows = db_client.execute_query(
        """
        SELECT rank, company_name, job_title, source_url,
               fit_score, fit_verdict, extraction_quality,
               missing_skills_json, job_analysis_json,
               match_json, created_at
        FROM ranked_jobs
        WHERE search_run_id = ?
        ORDER BY rank ASC
        """,
        (search_run_id,),
        db_path=db_path
    )
    return [dict(row) for row in rows]


def display_job_search_runs(limit: int = 10):
    """Prints recent job ranking sessions."""
    runs = list_job_search_runs(limit)

    print("\n" + "=" * 70)
    print("                    JOB SEARCH RUNS")
    print("=" * 70)

    if not runs:
        print("\nNo job ranking sessions tracked yet.")
        return

    for run in runs:
        print(
            f"\n#{run['id']} | {run['successful_jobs']}/{run['total_urls']} processed"
            f" | Failed: {run['failed_jobs']}"
            f"\n   Report : {run.get('report_path') or 'Not saved'}"
            f"\n   Date   : {run['created_at']}"
        )


def display_ranked_jobs_for_run(search_run_id: int):
    """Prints ranked jobs from one stored search session."""
    jobs = list_ranked_jobs_for_run(search_run_id)

    print("\n" + "=" * 70)
    print(f"                  RANKED JOBS FOR RUN #{search_run_id}")
    print("=" * 70)

    if not jobs:
        print("\nNo ranked jobs found for this run.")
        return

    for job in jobs:
        try:
            missing = json.loads(job.get("missing_skills_json") or "[]")[:4]
        except json.JSONDecodeError:
            missing = []

        print(
            f"\n#{job['rank']} | {job['fit_score']}/100 | {job['fit_verdict']}"
            f"\n   Company : {job['company_name']}"
            f"\n   Role    : {job['job_title']}"
            f"\n   Quality : {job['extraction_quality']}"
            f"\n   Apply Link : {job['source_url']}"
        )
        if missing:
            print(f"   Gaps    : {', '.join(missing)}")


def record_application(
    company_name: str,
    job_title: str,
    match: dict,
    ats_report: dict,
    resume_path: str,
    cover_letter_path: str,
    job_analysis: dict,
    status: str = "DRAFT_GENERATED",
    source_url: str = "",
    notes: str = "",
    user_id: int = 1,
    db_path: str = DB_PATH,
) -> int:
    """Saves a new application record. Returns the new row ID."""
    init_db(db_path)
    if get_user_email(user_id, db_path) == "demo@pathpilot.ai":
        existing = db_client.execute_query(
            "SELECT COUNT(id) FROM applications WHERE user_id = ?",
            (user_id,),
            db_path=db_path
        )
        if existing and existing[0][0] >= 2:
            return 999999
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    if source_url:
        existing = db_client.execute_query(
            "SELECT id FROM applications WHERE user_id = ? AND source_url = ? AND status = 'SHORTLISTED' LIMIT 1",
            (user_id, source_url),
            db_path=db_path
        )
        if existing:
            row_id = existing[0]["id"]
            db_client.execute_write(
                """
                UPDATE applications SET
                    company_name = ?, job_title = ?, status = ?,
                    match_score = ?, ats_score = ?,
                    resume_path = ?, cover_letter_path = ?, notes = ?,
                    job_analysis_json = ?, match_json = ?, ats_report_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    company_name,
                    job_title,
                    status,
                    int(match.get("match_score", 0)),
                    int(ats_report.get("keyword_coverage", 0)),
                    resume_path,
                    cover_letter_path,
                    notes,
                    json.dumps(job_analysis, ensure_ascii=False),
                    json.dumps(match, ensure_ascii=False),
                    json.dumps(ats_report, ensure_ascii=False),
                    now,
                    row_id
                ),
                db_path=db_path
            )
            return row_id

    val = db_client.execute_write(
        """
        INSERT INTO applications (
            company_name, job_title, source_url, status,
            match_score, ats_score,
            resume_path, cover_letter_path, notes,
            job_analysis_json, match_json, ats_report_json,
            created_at, updated_at, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_name,
            job_title,
            source_url,
            status,
            int(match.get("match_score", 0)),
            int(ats_report.get("keyword_coverage", 0)),
            resume_path,
            cover_letter_path,
            notes,
            json.dumps(job_analysis, ensure_ascii=False),
            json.dumps(match, ensure_ascii=False),
            json.dumps(ats_report, ensure_ascii=False),
            now,
            now,
            user_id,
        ),
        db_path=db_path
    )
    return int(val)


def update_application_status(
    application_id: int,
    status: str,
    notes: str = "",
    db_path: str = DB_PATH
):
    """Updates status and optionally adds notes to an application."""
    if status not in VALID_STATUSES:
        print(f"⚠️  Invalid status '{status}'. Valid: {VALID_STATUSES}")
        return

    init_db(db_path)
    res = db_client.execute_query(
        "SELECT user_id FROM applications WHERE id = ?",
        (application_id,),
        db_path=db_path
    )
    if res and get_user_email(res[0][0], db_path) == "demo@pathpilot.ai":
        return
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    if notes:
        db_client.execute_write(
            "UPDATE applications SET status=?, notes=?, updated_at=? WHERE id=?",
            (status, notes, now, application_id),
            db_path=db_path
        )
    else:
        db_client.execute_write(
            "UPDATE applications SET status=?, updated_at=? WHERE id=?",
            (status, now, application_id),
            db_path=db_path
        )
    print(f"✅ Application #{application_id} updated to {status}")


def list_applications(
    limit: int = 20,
    status_filter: str = None,
    db_path: str = DB_PATH,
    user_id: int = 1
) -> list[dict]:
    """Returns applications for a user, optionally filtered by status."""
    init_db(db_path)
    if status_filter:
        rows = db_client.execute_query(
            """
            SELECT id, company_name, job_title, source_url,
                   status, match_score, ats_score,
                   resume_path, cover_letter_path, notes,
                   created_at, updated_at
            FROM applications
            WHERE status = ? AND user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (status_filter, user_id, limit),
            db_path=db_path
        )
    else:
        rows = db_client.execute_query(
            """
            SELECT id, company_name, job_title, source_url,
                   status, match_score, ats_score,
                   resume_path, cover_letter_path, notes,
                   created_at, updated_at
            FROM applications
            WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
            db_path=db_path
        )
    return [dict(row) for row in rows]


def get_application(application_id: int, db_path: str = DB_PATH, user_id: int = 1) -> dict | None:
    """Returns one application record by ID for a user."""
    init_db(db_path)
    rows = db_client.execute_query(
        """
        SELECT id, company_name, job_title, source_url,
               status, match_score, ats_score,
               resume_path, cover_letter_path, notes,
               created_at, updated_at, user_id
        FROM applications
        WHERE id = ? AND user_id = ?
        """,
        (application_id, user_id),
        db_path=db_path
    )
    return dict(rows[0]) if rows else None


def open_application_asset(application_id: int, asset: str):
    """Opens an application link or generated document."""
    app = get_application(application_id)
    if not app:
        print(f"❌ Application #{application_id} not found")
        return

    asset_map = {
        "link": app.get("source_url"),
        "resume": app.get("resume_path"),
        "cover": app.get("cover_letter_path"),
    }
    target = asset_map.get(asset)
    if not target:
        print(f"❌ No {asset} available for application #{application_id}")
        return

    if asset in {"resume", "cover"}:
        target = os.path.abspath(target)
        if not os.path.exists(target):
            print(f"❌ File not found: {target}")
            return

    opened = webbrowser.open(target)
    if opened:
        print(f"✅ Opened {asset}: {target}")
    else:
        print(f"⚠️  Could not open automatically. Open manually: {target}")


def get_stats(db_path: str = DB_PATH, user_id: int = 1) -> dict:
    """Returns summary statistics across all applications for a user."""
    init_db(db_path)
    
    total_rows = db_client.execute_query(
        "SELECT COUNT(*) AS count FROM applications WHERE user_id = ?",
        (user_id,),
        db_path=db_path
    )
    total = total_rows[0]["count"] if total_rows else 0

    avg_match_rows = db_client.execute_query(
        "SELECT AVG(match_score) AS avg_match FROM applications WHERE user_id = ?",
        (user_id,),
        db_path=db_path
    )
    avg_match = avg_match_rows[0]["avg_match"] if avg_match_rows else 0
    if avg_match is None:
        avg_match = 0

    avg_ats_rows = db_client.execute_query(
        "SELECT AVG(ats_score) AS avg_ats FROM applications WHERE user_id = ?",
        (user_id,),
        db_path=db_path
    )
    avg_ats = avg_ats_rows[0]["avg_ats"] if avg_ats_rows else 0
    if avg_ats is None:
        avg_ats = 0

    by_status_rows = db_client.execute_query(
        "SELECT status, COUNT(*) AS count FROM applications WHERE user_id = ? GROUP BY status",
        (user_id,),
        db_path=db_path
    )
    by_status = {row["status"]: row["count"] for row in by_status_rows}

    top_match = db_client.execute_query(
        """SELECT company_name, job_title, match_score
           FROM applications
           WHERE user_id = ?
           ORDER BY match_score DESC LIMIT 3""",
        (user_id,),
        db_path=db_path
    )

    return {
        "total":      total,
        "avg_match":  round(avg_match, 1),
        "avg_ats":    round(avg_ats, 1),
        "by_status":  by_status,
        "top_matches": [dict(zip(
            ["company", "role", "score"], row
        )) for row in top_match],
    }


def display_applications(limit: int = 20, status_filter: str = None):
    """Prints application history in a readable format."""
    applications = list_applications(limit, status_filter)

    print("\n" + "=" * 70)
    title = "APPLICATION HISTORY"
    if status_filter:
        title += f" — {status_filter}"
    print(f"{'':^10}{title}")
    print("=" * 70)

    if not applications:
        msg = f"No applications with status '{status_filter}'." if status_filter \
              else "No applications tracked yet."
        print(f"\n{msg}")
        return

    status_icons = {
        "DRAFT_GENERATED": "📝",
        "APPLIED":         "📤",
        "ASSESSMENT":      "📋",
        "INTERVIEW":       "🎤",
        "OFFER":           "🎉",
        "REJECTED":        "❌",
        "WITHDRAWN":       "↩️",
    }

    for app in applications:
        icon = status_icons.get(app["status"], "•")
        print(
            f"\n#{app['id']} {icon} {app['company_name']} | {app['job_title']}"
            f"\n   Status : {app['status']}"
            f" | Fit: {app['match_score']}/100"
            f" | ATS: {app['ats_score']}/100"
            f"\n   Resume : {app['resume_path']}"
            f"\n   Cover  : {app['cover_letter_path']}"
            f"\n   Apply Link : {app.get('source_url') or 'Manual input'}"
            f"\n   Notes  : {app.get('notes') or '—'}"
            f"\n   Date   : {app['created_at']}"
        )


def display_stats():
    """Prints summary statistics."""
    stats = get_stats()
    print("\n" + "=" * 50)
    print("         APPLICATION STATISTICS")
    print("=" * 50)
    print(f"\n  Total Applications : {stats['total']}")
    print(f"  Avg Match Score    : {stats['avg_match']}/100")
    print(f"  Avg ATS Score      : {stats['avg_ats']}/100")

    print("\n  By Status:")
    status_icons = {
        "DRAFT_GENERATED": "📝", "APPLIED": "📤",
        "ASSESSMENT": "📋",  "INTERVIEW": "🎤",
        "OFFER": "🎉",       "REJECTED": "❌",
        "WITHDRAWN": "↩️",
    }
    for status, count in stats["by_status"].items():
        icon = status_icons.get(status, "•")
        print(f"    {icon}  {status}: {count}")

    if stats["top_matches"]:
        print("\n  Top Matches:")
        for app in stats["top_matches"]:
            print(f"    • {app['company']} | {app['role']} → {app['score']}/100")
    print("\n" + "=" * 50)


# ── INTERACTIVE MENU ──────────────────────────────────────────────────────────
def interactive_menu():
    """Simple CLI menu for managing applications."""
    while True:
        print("\n" + "="*50)
        print("     APPLICATION TRACKER MENU")
        print("="*50)
        print("1. View all applications")
        print("2. View by status")
        print("3. Update application status")
        print("4. View statistics")
        print("5. View job search runs")
        print("6. View ranked jobs for a run")
        print("7. Open application link or files")
        print("8. Exit")

        choice = input("\nChoose option (1-8): ").strip()

        if choice == "1":
            display_applications()

        elif choice == "2":
            print("\nStatuses:", ", ".join(VALID_STATUSES))
            status = input("Enter status to filter: ").strip().upper()
            display_applications(status_filter=status)

        elif choice == "3":
            display_applications()
            try:
                app_id = int(input("\nEnter application ID to update: ").strip())
                print("Statuses:", ", ".join(VALID_STATUSES))
                new_status = input("Enter new status: ").strip().upper()
                notes = input("Add notes (optional, press Enter to skip): ").strip()
                update_application_status(app_id, new_status, notes)
            except ValueError:
                print("❌ Invalid ID entered")

        elif choice == "4":
            display_stats()

        elif choice == "5":
            display_job_search_runs()

        elif choice == "6":
            display_job_search_runs()
            try:
                run_id = int(input("\nEnter search run ID: ").strip())
                display_ranked_jobs_for_run(run_id)
            except ValueError:
                print("❌ Invalid run ID entered")

        elif choice == "7":
            display_applications()
            try:
                app_id = int(input("\nEnter application ID: ").strip())
                print("\nWhat do you want to open?")
                print("1. Apply link")
                print("2. Resume PDF")
                print("3. Cover letter PDF")
                asset_choice = input("Choose option (1/2/3): ").strip()
                asset_map = {"1": "link", "2": "resume", "3": "cover"}
                asset = asset_map.get(asset_choice)
                if asset:
                    open_application_asset(app_id, asset)
                else:
                    print("❌ Invalid option")
            except ValueError:
                print("❌ Invalid application ID entered")

        elif choice == "8":
            print("Goodbye!")
            break

        else:
            print("❌ Invalid choice")


def seed_demo_data(user_id: int, db_path: str = DB_PATH) -> None:
    """Seeds the database with mock jobs, runs, and applications for Demo Mode (clearing any old data)."""
    init_db(db_path)
    
    # Always clear existing demo data to ensure a clean refresh
    db_client.execute_write(
        "DELETE FROM ranked_jobs WHERE search_run_id IN (SELECT id FROM job_search_runs WHERE user_id = ?)",
        (user_id,),
        db_path=db_path
    )
    db_client.execute_write(
        "DELETE FROM job_search_runs WHERE user_id = ?",
        (user_id,),
        db_path=db_path
    )
    db_client.execute_write(
        "DELETE FROM applications WHERE user_id = ?",
        (user_id,),
        db_path=db_path
    )
    db_client.execute_write(
        "DELETE FROM discovered_jobs WHERE user_id = ?",
        (user_id,),
        db_path=db_path
    )


def get_discovered_job_description(url: str, db_path: str = DB_PATH) -> str:
    """Retrieves the full job description from the local discovered_jobs catalog by its source URL or provider_job_id."""
    if not url:
        return ""
    provider_job_id = ""
    if "pathpilot.ai/jobs/" in url:
        provider_job_id = url.split("pathpilot.ai/jobs/")[-1]

    if provider_job_id:
        rows = db_client.execute_query(
            "SELECT job_description FROM discovered_jobs WHERE provider_job_id = ? LIMIT 1",
            (provider_job_id,),
            db_path=db_path
        )
    else:
        rows = db_client.execute_query(
            "SELECT job_description FROM discovered_jobs WHERE source_url = ? OR apply_url = ? LIMIT 1",
            (url, url),
            db_path=db_path
        )
    return rows[0]["job_description"] if rows else ""


def delete_application(application_id: int, db_path: str = DB_PATH) -> None:
    """Deletes an application by ID from the applications table."""
    init_db(db_path)
    db_client.execute_write(
        "DELETE FROM applications WHERE id = ?",
        (application_id,),
        db_path=db_path
    )


if __name__ == "__main__":
    interactive_menu()
