"""SQLite-backed normalized job store for discovery ingestion."""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta

from job_discovery import DiscoveredJob, JobDiscoveryProvider
from job_preferences import JobPreferences


JOB_STORE_DB_PATH = "outputs/applications.db"
JOB_STORE_TABLE = "discovered_jobs"


def init_job_store(db_path: str = JOB_STORE_DB_PATH) -> None:
    """Creates the normalized job store if it does not exist."""
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {JOB_STORE_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                provider_job_id TEXT NOT NULL,
                source TEXT NOT NULL,
                company_name TEXT NOT NULL,
                job_title TEXT NOT NULL,
                location TEXT,
                work_mode TEXT,
                job_type TEXT,
                experience_level TEXT,
                posted_date TEXT NOT NULL,
                job_description TEXT NOT NULL,
                date_label TEXT NOT NULL DEFAULT 'Posted',
                freshness_verified INTEGER NOT NULL DEFAULT 1,
                source_url TEXT,
                apply_url TEXT,
                raw_json TEXT NOT NULL DEFAULT '{{}}',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        # Migrate: add user_id column if it was missing (old schema)
        existing_cols = {
            row[1]
            for row in conn.execute(
                f"PRAGMA table_info({JOB_STORE_TABLE})"
            ).fetchall()
        }
        if "user_id" not in existing_cols:
            conn.execute(
                f"ALTER TABLE {JOB_STORE_TABLE} ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_jobs_identity
            ON {JOB_STORE_TABLE} (user_id, source, provider_job_id)
            """
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_discovered_jobs_seen
            ON {JOB_STORE_TABLE} (last_seen_at)
            """
        )


def _job_to_row(job: DiscoveredJob) -> dict:
    return {
        "provider_job_id": str(job.provider_job_id or job.source_url),
        "source": job.source,
        "company_name": job.company_name,
        "job_title": job.job_title,
        "location": job.location,
        "work_mode": job.work_mode,
        "job_type": job.job_type,
        "experience_level": job.experience_level,
        "posted_date": job.posted_date.isoformat(),
        "job_description": job.job_description,
        "date_label": job.date_label,
        "freshness_verified": 1 if job.freshness_verified else 0,
        "source_url": job.source_url,
        "apply_url": job.apply_url,
        "raw_json": json.dumps(
            {
                "relevance_score": job.relevance_score,
            },
            ensure_ascii=False,
        ),
    }


def upsert_discovered_jobs(
    jobs: list[DiscoveredJob],
    *,
    user_id: int = 0,
    db_path: str = JOB_STORE_DB_PATH,
) -> int:
    """Upserts normalized jobs for a specific user and returns the number of rows processed."""
    init_job_store(db_path)
    now = datetime.utcnow().isoformat(timespec="seconds")
    live_jobs = [
        job for job in jobs if job.source != "Local sample catalog"
    ]
    with sqlite3.connect(db_path) as conn:
        for job in live_jobs:
            row = _job_to_row(job)
            conn.execute(
                f"""
                INSERT INTO {JOB_STORE_TABLE} (
                    user_id, provider_job_id, source, company_name, job_title,
                    location, work_mode, job_type, experience_level, posted_date,
                    job_description, date_label, freshness_verified, source_url,
                    apply_url, raw_json, first_seen_at, last_seen_at
                ) VALUES (
                    :user_id, :provider_job_id, :source, :company_name, :job_title,
                    :location, :work_mode, :job_type, :experience_level,
                    :posted_date, :job_description, :date_label,
                    :freshness_verified, :source_url, :apply_url, :raw_json,
                    :first_seen_at, :last_seen_at
                )
                ON CONFLICT(user_id, source, provider_job_id) DO UPDATE SET
                    company_name = excluded.company_name,
                    job_title = excluded.job_title,
                    location = excluded.location,
                    work_mode = excluded.work_mode,
                    job_type = excluded.job_type,
                    experience_level = excluded.experience_level,
                    posted_date = excluded.posted_date,
                    job_description = excluded.job_description,
                    date_label = excluded.date_label,
                    freshness_verified = excluded.freshness_verified,
                    source_url = excluded.source_url,
                    apply_url = excluded.apply_url,
                    raw_json = excluded.raw_json,
                    last_seen_at = excluded.last_seen_at
                """,
                {
                    **row,
                    "user_id": user_id,
                    "first_seen_at": now,
                    "last_seen_at": now,
                },
            )
    return len(live_jobs)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return date.today()


def list_stored_jobs(
    *,
    user_id: int = 0,
    db_path: str = JOB_STORE_DB_PATH,
    seen_within_days: int = 7,
) -> list[DiscoveredJob]:
    """Returns recently ingested normalized jobs for the given user."""
    init_job_store(db_path)
    cutoff = (
        datetime.utcnow() - timedelta(days=max(1, int(seen_within_days)))
    ).isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT provider_job_id, source, company_name, job_title, location,
                   work_mode, job_type, experience_level, posted_date,
                   job_description, date_label, freshness_verified, source_url,
                   apply_url
            FROM {JOB_STORE_TABLE}
            WHERE last_seen_at >= ?
              AND user_id = ?
              AND source != 'Local sample catalog'
            ORDER BY last_seen_at DESC, id DESC
            """,
            (cutoff, user_id),
        ).fetchall()
    return [
        DiscoveredJob(
            provider_job_id=row["provider_job_id"],
            source=row["source"],
            company_name=row["company_name"],
            job_title=row["job_title"],
            location=row["location"] or "",
            work_mode=row["work_mode"] or "",
            job_type=row["job_type"] or "",
            experience_level=row["experience_level"] or "",
            posted_date=_parse_date(row["posted_date"]),
            job_description=row["job_description"],
            date_label=row["date_label"] or "Posted",
            freshness_verified=bool(row["freshness_verified"]),
            source_url=row["source_url"] or "",
            apply_url=row["apply_url"] or "",
        )
        for row in rows
    ]


def job_store_stats(db_path: str = JOB_STORE_DB_PATH) -> dict:
    """Returns small diagnostics for the local discovery database."""
    init_job_store(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM {JOB_STORE_TABLE}"
        ).fetchone()["count"]
        by_source = conn.execute(
            f"""
            SELECT source, COUNT(*) AS count
            FROM {JOB_STORE_TABLE}
            GROUP BY source
            ORDER BY count DESC
            LIMIT 8
            """
        ).fetchall()
        latest = conn.execute(
            f"SELECT MAX(last_seen_at) AS latest FROM {JOB_STORE_TABLE}"
        ).fetchone()["latest"]
    return {
        "total": int(total or 0),
        "latest": latest or "",
        "by_source": {row["source"]: int(row["count"]) for row in by_source},
    }


class StoredJobProvider:
    """Discovery provider backed by the normalized local job database."""

    name = "Normalized job database"

    def __init__(
        self,
        *,
        user_id: int = 0,
        db_path: str = JOB_STORE_DB_PATH,
        seen_within_days: int = 7,
    ):
        self.user_id = user_id
        self.db_path = db_path
        self.seen_within_days = seen_within_days

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        del preferences
        return list_stored_jobs(
            user_id=self.user_id,
            db_path=self.db_path,
            seen_within_days=self.seen_within_days,
        )


def ingest_provider_jobs(
    provider: JobDiscoveryProvider,
    preferences: JobPreferences,
    *,
    user_id: int = 0,
    db_path: str = JOB_STORE_DB_PATH,
) -> int:
    """Fetches provider jobs once and stores their normalized representation."""
    jobs = provider.discover(preferences)
    return upsert_discovered_jobs(jobs, user_id=user_id, db_path=db_path)
