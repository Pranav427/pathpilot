from datetime import date

from job_discovery import DiscoveredJob, discover_jobs
from job_preferences import build_job_preferences
from job_store import (
    StoredJobProvider,
    ingest_provider_jobs,
    job_store_stats,
    list_stored_jobs,
    upsert_discovered_jobs,
)


def preferences():
    return build_job_preferences(
        target_roles="Data Scientist",
        locations="Hyderabad",
        experience_levels=["Internship", "Fresher / Entry level"],
        work_modes=["Onsite", "Hybrid", "Remote"],
        job_types=["Full-time", "Internship"],
        preferred_skills="Python, SQL, Machine Learning",
        excluded_keywords="Senior, Manager",
        maximum_job_age_days=14,
    )


def sample_job(**overrides):
    values = {
        "provider_job_id": "source-123",
        "source": "Greenhouse · Example AI",
        "company_name": "Example AI",
        "job_title": "Junior Data Scientist",
        "location": "Hyderabad, India",
        "work_mode": "Onsite",
        "job_type": "Full-time",
        "experience_level": "Fresher / Entry level",
        "posted_date": date.today(),
        "job_description": (
            "Use Python, SQL, machine learning, data analysis, model "
            "evaluation, documentation, dashboards, and stakeholder "
            "communication to support product decisions."
        ),
        "date_label": "Active listing",
        "freshness_verified": False,
        "source_url": "https://example.com/jobs/source-123",
        "apply_url": "https://example.com/jobs/source-123/apply",
    }
    values.update(overrides)
    return DiscoveredJob(**values)


def test_job_store_upserts_and_lists_normalized_jobs(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    job = sample_job()

    assert upsert_discovered_jobs([job], db_path=db_path) == 1
    assert upsert_discovered_jobs(
        [sample_job(job_title="Junior Data Scientist - Updated")],
        db_path=db_path,
    ) == 1

    jobs = list_stored_jobs(db_path=db_path)

    assert len(jobs) == 1
    assert jobs[0].job_title == "Junior Data Scientist - Updated"
    assert jobs[0].apply_url.endswith("/apply")


def test_stored_job_provider_uses_existing_discovery_filters(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    upsert_discovered_jobs(
        [
            sample_job(),
            sample_job(
                provider_job_id="outside-location",
                location="Mumbai, India",
                source_url="https://example.com/jobs/outside-location",
            ),
        ],
        db_path=db_path,
    )

    jobs, rejected = discover_jobs(
        preferences(),
        StoredJobProvider(db_path=db_path),
    )

    assert [job.provider_job_id for job in jobs] == [
        "source-123",
        "outside-location",
    ]
    assert not any("Location excluded" in item for item in rejected)


def test_ingest_provider_jobs_persists_provider_output(tmp_path):
    db_path = str(tmp_path / "jobs.db")

    class Provider:
        def discover(self, _preferences):
            return [sample_job()]

    assert ingest_provider_jobs(
        Provider(),
        preferences(),
        db_path=db_path,
    ) == 1

    stats = job_store_stats(db_path=db_path)
    assert stats["total"] == 1
    assert stats["by_source"] == {"Greenhouse · Example AI": 1}
