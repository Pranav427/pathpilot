import os
import sys
import tempfile
import pytest

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tracker import (
    init_db,
    register_user,
    authenticate_user,
    get_user_profile,
    save_user_profile,
    record_application,
    list_applications,
    record_job_search_run,
    list_job_search_runs,
)
from job_store import (
    init_job_store,
    upsert_discovered_jobs,
    list_stored_jobs,
)
from job_discovery import DiscoveredJob


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    yield path
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)


def test_user_registration_and_auth(temp_db):
    init_db(temp_db)
    
    # 1. Register a new user
    uid = register_user("test@example.com", "securepassword123", db_path=temp_db)
    assert uid > 0

    # 2. Try to register same email - should raise ValueError
    with pytest.raises(ValueError):
        register_user("test@example.com", "password", db_path=temp_db)

    # 3. Authenticate correct credentials
    auth_uid = authenticate_user("test@example.com", "securepassword123", db_path=temp_db)
    assert auth_uid == uid

    # 4. Authenticate incorrect credentials
    bad_uid = authenticate_user("test@example.com", "wrongpassword", db_path=temp_db)
    assert bad_uid is None


def test_user_profiles_isolation(temp_db):
    init_db(temp_db)
    uid_a = register_user("a@example.com", "password", db_path=temp_db)
    uid_b = register_user("b@example.com", "password", db_path=temp_db)

    # Fetch default pre-filled profiles
    prof_a = get_user_profile(uid_a, db_path=temp_db)
    prof_b = get_user_profile(uid_b, db_path=temp_db)
    assert prof_a["name"] == "A"
    assert prof_b["name"] == "B"

    # Modify and save profile A
    prof_a["name"] = "Alice Peterson"
    prof_a["location"] = "Seattle, WA"
    save_user_profile(uid_a, prof_a, db_path=temp_db)

    # Modify and save profile B
    prof_b["name"] = "Bob Builder"
    prof_b["location"] = "Austin, TX"
    save_user_profile(uid_b, prof_b, db_path=temp_db)

    # Verify isolation
    loaded_a = get_user_profile(uid_a, db_path=temp_db)
    loaded_b = get_user_profile(uid_b, db_path=temp_db)

    assert loaded_a["name"] == "Alice Peterson"
    assert loaded_a["location"] == "Seattle, WA"
    assert loaded_b["name"] == "Bob Builder"
    assert loaded_b["location"] == "Austin, TX"


def test_applications_isolation(temp_db):
    init_db(temp_db)
    uid_a = register_user("a@example.com", "password", db_path=temp_db)
    uid_b = register_user("b@example.com", "password", db_path=temp_db)

    # Create application for user A
    record_application(
        company_name="Google",
        job_title="Software Engineer",
        match={"match_score": 85},
        ats_report={"keyword_coverage": 70},
        resume_path="/path/a.pdf",
        cover_letter_path="/path/a_letter.pdf",
        job_analysis={},
        status="DRAFT_GENERATED",
        user_id=uid_a,
        db_path=temp_db,
    )

    # Create application for user B
    record_application(
        company_name="Meta",
        job_title="Production Engineer",
        match={"match_score": 90},
        ats_report={"keyword_coverage": 80},
        resume_path="/path/b.pdf",
        cover_letter_path="/path/b_letter.pdf",
        job_analysis={},
        status="APPLIED",
        user_id=uid_b,
        db_path=temp_db,
    )

    # Verify lists are isolated
    apps_a = list_applications(user_id=uid_a, db_path=temp_db)
    apps_b = list_applications(user_id=uid_b, db_path=temp_db)

    assert len(apps_a) == 1
    assert apps_a[0]["company_name"] == "Google"
    assert apps_a[0]["job_title"] == "Software Engineer"

    assert len(apps_b) == 1
    assert apps_b[0]["company_name"] == "Meta"
    assert apps_b[0]["job_title"] == "Production Engineer"


def test_job_search_runs_isolation(temp_db):
    init_db(temp_db)
    uid_a = register_user("a@example.com", "password", db_path=temp_db)
    uid_b = register_user("b@example.com", "password", db_path=temp_db)

    # Record search run for user A
    record_job_search_run(
        ranked_jobs=[],
        failures=[],
        total_urls=5,
        report_path="/reports/a.txt",
        user_id=uid_a,
        db_path=temp_db,
    )

    # Verify search run list
    runs_a = list_job_search_runs(user_id=uid_a, db_path=temp_db)
    runs_b = list_job_search_runs(user_id=uid_b, db_path=temp_db)

    assert len(runs_a) == 1
    assert len(runs_b) == 0


def test_job_store_isolation(temp_db):
    init_job_store(temp_db)
    uid_a = 100
    uid_b = 200

    from datetime import date
    job_a = DiscoveredJob(
        provider_job_id="job_123",
        source="LinkedIn",
        company_name="Amazon",
        job_title="SDE I",
        job_description="Description...",
        location="Seattle",
        work_mode="Hybrid",
        job_type="Full-time",
        experience_level="Entry",
        posted_date=date.today(),
    )
    job_b = DiscoveredJob(
        provider_job_id="job_123",  # Same job ID but for user B
        source="LinkedIn",
        company_name="Amazon",
        job_title="SDE I - Different",
        job_description="Description...",
        location="Seattle",
        work_mode="Hybrid",
        job_type="Full-time",
        experience_level="Entry",
        posted_date=date.today(),
    )

    # Upsert Amazon SDE I for user A
    upsert_discovered_jobs([job_a], user_id=uid_a, db_path=temp_db)
    # Upsert Amazon SDE I for user B
    upsert_discovered_jobs([job_b], user_id=uid_b, db_path=temp_db)

    # Verify lists are partitioned
    jobs_a = list_stored_jobs(user_id=uid_a, db_path=temp_db)
    jobs_b = list_stored_jobs(user_id=uid_b, db_path=temp_db)

    assert len(jobs_a) == 1
    assert jobs_a[0].company_name == "Amazon"
    assert jobs_a[0].job_title == "SDE I"

    assert len(jobs_b) == 1
    assert jobs_b[0].company_name == "Amazon"
    assert jobs_b[0].job_title == "SDE I - Different"


def test_multiple_personas_per_user(temp_db):
    from tracker import (
        get_user_profile,
        save_user_profile,
        list_user_profiles,
        delete_user_profile,
    )
    uid = 42
    
    prof_default = {"name": "User Default", "email": "d@x.com"}
    prof_ds = {"name": "User Data Scientist", "email": "ds@x.com"}
    prof_swe = {"name": "User Software Engineer", "email": "swe@x.com"}
    
    # Save three different personas
    save_user_profile(uid, prof_default, "Default", db_path=temp_db)
    save_user_profile(uid, prof_ds, "Data Scientist", db_path=temp_db)
    save_user_profile(uid, prof_swe, "Software Engineer", db_path=temp_db)
    
    # List and check
    personas = list_user_profiles(uid, db_path=temp_db)
    assert len(personas) == 3
    assert "Default" in personas
    assert "Data Scientist" in personas
    assert "Software Engineer" in personas
    
    # Get and check content
    res_ds = get_user_profile(uid, "Data Scientist", db_path=temp_db)
    assert res_ds["name"] == "User Data Scientist"
    
    res_swe = get_user_profile(uid, "Software Engineer", db_path=temp_db)
    assert res_swe["name"] == "User Software Engineer"
    
    # Delete one
    delete_user_profile(uid, "Data Scientist", db_path=temp_db)
    personas_after = list_user_profiles(uid, db_path=temp_db)
    assert len(personas_after) == 2
    assert "Data Scientist" not in personas_after
    assert "Software Engineer" in personas_after
