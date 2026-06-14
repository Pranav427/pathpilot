# tracker.py

import json
import os
import sqlite3
import webbrowser
from datetime import datetime


DB_PATH = "outputs/applications.db"

# Valid application lifecycle statuses
VALID_STATUSES = [
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
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name        TEXT NOT NULL,
                job_title           TEXT NOT NULL,
                source_url          TEXT,
                status              TEXT NOT NULL DEFAULT 'DRAFT_GENERATED',
                match_score         INTEGER NOT NULL DEFAULT 0,
                ats_score           INTEGER NOT NULL DEFAULT 0,
                resume_path         TEXT,
                cover_letter_path   TEXT,
                notes               TEXT,
                job_analysis_json   TEXT NOT NULL DEFAULT '{}',
                match_json          TEXT NOT NULL DEFAULT '{}',
                ats_report_json     TEXT NOT NULL DEFAULT '{}',
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
        """)

        # Safe migration — add columns if missing
        existing = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(applications)"
            ).fetchall()
        }
        migrations = {
            "source_url": "ALTER TABLE applications ADD COLUMN source_url TEXT",
            "notes":      "ALTER TABLE applications ADD COLUMN notes TEXT",
        }
        for col, sql in migrations.items():
            if col not in existing:
                conn.execute(sql)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_search_runs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                total_urls          INTEGER NOT NULL DEFAULT 0,
                successful_jobs     INTEGER NOT NULL DEFAULT 0,
                failed_jobs         INTEGER NOT NULL DEFAULT 0,
                report_path         TEXT,
                failures_json       TEXT NOT NULL DEFAULT '[]',
                created_at          TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ranked_jobs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                search_run_id       INTEGER NOT NULL,
                rank                INTEGER NOT NULL,
                company_name        TEXT NOT NULL,
                job_title           TEXT NOT NULL,
                source_url          TEXT NOT NULL,
                fit_score           INTEGER NOT NULL DEFAULT 0,
                fit_verdict         TEXT,
                extraction_quality  TEXT,
                missing_skills_json TEXT NOT NULL DEFAULT '[]',
                job_analysis_json   TEXT NOT NULL DEFAULT '{}',
                match_json          TEXT NOT NULL DEFAULT '{}',
                created_at          TEXT NOT NULL,
                FOREIGN KEY(search_run_id)
                    REFERENCES job_search_runs(id)
                    ON DELETE CASCADE
            )
        """)


def record_job_search_run(
    ranked_jobs: list,
    failures: list[str],
    total_urls: int,
    report_path: str = "",
    db_path: str = DB_PATH,
) -> int:
    """Stores one job ranking session and its ranked jobs."""
    init_db(db_path)
    now = datetime.utcnow().isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO job_search_runs (
                total_urls, successful_jobs, failed_jobs,
                report_path, failures_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(total_urls),
                len(ranked_jobs),
                len(failures or []),
                report_path,
                json.dumps(failures or [], ensure_ascii=False),
                now,
            ),
        )
        search_run_id = int(cursor.lastrowid)

        for job in ranked_jobs:
            fetched = job.fetched_job
            match = job.match
            conn.execute(
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
            )

        return search_run_id


def list_job_search_runs(limit: int = 10, db_path: str = DB_PATH) -> list[dict]:
    """Returns recent job ranking sessions."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, total_urls, successful_jobs, failed_jobs,
                   report_path, failures_json, created_at
            FROM job_search_runs
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_ranked_jobs_for_run(
    search_run_id: int,
    db_path: str = DB_PATH
) -> list[dict]:
    """Returns ranked jobs for one search session."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
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
        ).fetchall()
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
    db_path: str = DB_PATH,
) -> int:
    """Saves a new application record. Returns the new row ID."""
    init_db(db_path)
    now = datetime.utcnow().isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO applications (
                company_name, job_title, source_url, status,
                match_score, ats_score,
                resume_path, cover_letter_path, notes,
                job_analysis_json, match_json, ats_report_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        return int(cursor.lastrowid)


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
    now = datetime.utcnow().isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        if notes:
            conn.execute(
                "UPDATE applications SET status=?, notes=?, updated_at=? WHERE id=?",
                (status, notes, now, application_id),
            )
        else:
            conn.execute(
                "UPDATE applications SET status=?, updated_at=? WHERE id=?",
                (status, now, application_id),
            )
    print(f"✅ Application #{application_id} updated to {status}")


def list_applications(
    limit: int = 20,
    status_filter: str = None,
    db_path: str = DB_PATH
) -> list[dict]:
    """Returns applications, optionally filtered by status."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if status_filter:
            rows = conn.execute(
                """
                SELECT id, company_name, job_title, source_url,
                       status, match_score, ats_score,
                       resume_path, cover_letter_path, notes,
                       created_at, updated_at
                FROM applications
                WHERE status = ?
                ORDER BY id DESC LIMIT ?
                """,
                (status_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, company_name, job_title, source_url,
                       status, match_score, ats_score,
                       resume_path, cover_letter_path, notes,
                       created_at, updated_at
                FROM applications
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_application(application_id: int, db_path: str = DB_PATH) -> dict | None:
    """Returns one application record by ID."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, company_name, job_title, source_url,
                   status, match_score, ats_score,
                   resume_path, cover_letter_path, notes,
                   created_at, updated_at
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        ).fetchone()
    return dict(row) if row else None


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


def get_stats(db_path: str = DB_PATH) -> dict:
    """Returns summary statistics across all applications."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM applications"
        ).fetchone()[0]

        avg_match = conn.execute(
            "SELECT AVG(match_score) FROM applications"
        ).fetchone()[0] or 0

        avg_ats = conn.execute(
            "SELECT AVG(ats_score) FROM applications"
        ).fetchone()[0] or 0

        by_status = dict(
            conn.execute(
                "SELECT status, COUNT(*) FROM applications GROUP BY status"
            ).fetchall()
        )

        top_match = conn.execute(
            """SELECT company_name, job_title, match_score
               FROM applications
               ORDER BY match_score DESC LIMIT 3"""
        ).fetchall()

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


if __name__ == "__main__":
    interactive_menu()
