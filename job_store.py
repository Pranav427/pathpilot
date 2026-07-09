"""SQLite/PostgreSQL-backed normalized job store for discovery ingestion."""

import json
import os
from datetime import date, datetime, timedelta, timezone

from job_discovery import DiscoveredJob, JobDiscoveryProvider
from job_preferences import JobPreferences
import db_client

JOB_STORE_DB_PATH = "outputs/applications.db"
JOB_STORE_TABLE = "discovered_jobs"


def init_job_store(db_path: str = JOB_STORE_DB_PATH) -> None:
    """Creates the normalized job store if it does not exist."""
    db_client.init_db_schema(db_path)


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
    user_id: int = 1,
    db_path: str = JOB_STORE_DB_PATH,
) -> int:
    """Upserts normalized jobs for a user and returns the number of rows processed."""
    init_job_store(db_path)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    live_jobs = [
        job for job in jobs if job.source != "Local sample catalog"
    ]
    for job in live_jobs:
        row = _job_to_row(job)
        db_client.execute_write(
            f"""
            INSERT INTO {JOB_STORE_TABLE} (
                provider_job_id, source, company_name, job_title, location,
                work_mode, job_type, experience_level, posted_date,
                job_description, date_label, freshness_verified, source_url,
                apply_url, raw_json, first_seen_at, last_seen_at, user_id
            ) VALUES (
                :provider_job_id, :source, :company_name, :job_title,
                :location, :work_mode, :job_type, :experience_level,
                :posted_date, :job_description, :date_label,
                :freshness_verified, :source_url, :apply_url, :raw_json,
                :first_seen_at, :last_seen_at, :user_id
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
                "first_seen_at": now,
                "last_seen_at": now,
                "user_id": user_id,
            },
            db_path=db_path,
        )
    return len(live_jobs)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return date.today()


def list_stored_jobs(
    *,
    user_id: int = 1,
    db_path: str = JOB_STORE_DB_PATH,
    seen_within_days: int = 7,
) -> list[DiscoveredJob]:
    """Returns recently ingested normalized jobs for a user."""
    init_job_store(db_path)
    cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max(1, int(seen_within_days)))
    ).isoformat(timespec="seconds")
    
    rows = db_client.execute_query(
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
        db_path=db_path,
    )
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
    total_rows = db_client.execute_query(
        f"SELECT COUNT(*) AS count FROM {JOB_STORE_TABLE}",
        db_path=db_path
    )
    total = total_rows[0]["count"] if total_rows else 0
    
    by_source = db_client.execute_query(
        f"""
        SELECT source, COUNT(*) AS count
        FROM {JOB_STORE_TABLE}
        GROUP BY source
        ORDER BY count DESC
        LIMIT 8
        """,
        db_path=db_path
    )
    
    latest_rows = db_client.execute_query(
        f"SELECT MAX(last_seen_at) AS latest FROM {JOB_STORE_TABLE}",
        db_path=db_path
    )
    latest = latest_rows[0]["latest"] if latest_rows else ""
    
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
        db_path: str = JOB_STORE_DB_PATH,
        seen_within_days: int = 7,
    ):
        self.db_path = db_path
        self.seen_within_days = seen_within_days

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        del preferences
        return list_stored_jobs(
            db_path=self.db_path,
            seen_within_days=self.seen_within_days,
        )


def ingest_provider_jobs(
    provider: JobDiscoveryProvider,
    preferences: JobPreferences,
    *,
    db_path: str = JOB_STORE_DB_PATH,
) -> int:
    """Fetches provider jobs once and stores their normalized representation."""
    jobs = provider.discover(preferences)
    return upsert_discovered_jobs(jobs, db_path=db_path)
