from dataclasses import replace
from datetime import date, datetime, timedelta
from http.client import IncompleteRead
import json

from job_discovery import (
    AdzunaJobProvider,
    ArbeitnowJobProvider,
    AshbyJobProvider,
    CURATED_ASHBY_BOARDS,
    CURATED_GREENHOUSE_BOARDS,
    CURATED_LEVER_SITES,
    _ADZUNA_CACHE,
    _ASHBY_CACHE,
    _ARBEITNOW_CACHE,
    _GREENHOUSE_CACHE,
    _JOOBLE_CACHE,
    _LEVER_CACHE,
    _REMOTIVE_CACHE,
    _REMOTEOK_CACHE,
    _SERPAPI_CACHE,
    broad_source_company_quality_issue,
    broad_source_title_quality_issue,
    clear_discovery_provider_caches,
    CombinedJobProvider,
    DiscoveredJob,
    EarlyCareerWebJobProvider,
    early_career_sources_enabled,
    discovery_inventory_window_days,
    GreenhouseJobProvider,
    JobDiscoveryError,
    JoobleJobProvider,
    LeverJobProvider,
    LocalSampleJobProvider,
    RemotiveJobProvider,
    RemoteOKJobProvider,
    SearchApiGoogleJobsProvider,
    SerpApiGoogleJobsProvider,
    deduplicate_jobs,
    discover_jobs,
    experience_confidence,
    experience_priority,
    expanded_market_locations,
    expanded_role_queries,
    has_entry_level_evidence,
    has_likely_entry_level_evidence,
    html_to_text,
    infer_discovery_metadata,
    interleaved_role_location_queries,
    is_broad_market_source,
    is_direct_company_source,
    is_india_location,
    job_matches_preferences,
    parse_ashby_boards,
    parse_greenhouse_boards,
    parse_greenhouse_date,
    parse_lever_sites,
    profile_search_role_queries,
    role_relevance,
    source_priority,
    title_matches_target_role,
)
from job_preferences import build_job_preferences


def preferences(**overrides):
    values = {
        "target_roles": "Data Scientist, Machine Learning Engineer, AI/ML",
        "locations": "Bengaluru, Hyderabad, Remote",
        "experience_levels": ["Internship", "Fresher / Entry level"],
        "work_modes": ["Onsite", "Hybrid", "Remote"],
        "job_types": ["Full-time", "Internship"],
        "preferred_skills": "Python, Machine Learning, NLP",
        "excluded_keywords": "Senior, Manager, Sales",
        "maximum_job_age_days": 14,
    }
    values.update(overrides)
    return build_job_preferences(**values)


def test_curated_sources_include_india_oriented_company_feeds():
    assert CURATED_GREENHOUSE_BOARDS["slice"] == "Slice"
    assert CURATED_LEVER_SITES["meesho"] == ("Meesho", "global")
    assert CURATED_LEVER_SITES["mindtickle"] == ("Mindtickle", "global")
    assert CURATED_ASHBY_BOARDS["atlan"] == "Atlan"
    assert CURATED_ASHBY_BOARDS["navi"] == "Navi"


def test_inventory_window_keeps_wider_source_inventory(monkeypatch):
    monkeypatch.delenv("APPLYSMART_JOB_INVENTORY_WINDOW_DAYS", raising=False)

    assert discovery_inventory_window_days(preferences(maximum_job_age_days=7)) == 90

    monkeypatch.setenv("APPLYSMART_JOB_INVENTORY_WINDOW_DAYS", "30")
    assert discovery_inventory_window_days(preferences(maximum_job_age_days=60)) == 60


def test_expanded_role_queries_include_stronger_entry_level_variants():
    queries = expanded_role_queries(["Data Scientist", "Machine Learning Engineer"])

    assert "Data Scientist New Graduate" in queries
    assert "Data Science Trainee" in queries
    assert "Graduate Machine Learning Engineer" in queries
    assert "Associate Machine Learning Engineer" in queries
    assert "AI Engineer" in queries
    assert "Generative AI Engineer" in queries


def test_local_discovery_filters_and_ranks_sample_catalog():
    jobs, rejected = discover_jobs(
        preferences(),
        LocalSampleJobProvider(),
        today=date.today(),
    )

    assert len(jobs) == 3
    assert jobs[0].relevance_score >= jobs[-1].relevance_score
    assert any("Senior Data Science Manager" in item for item in rejected)
    assert any("Junior Data Analyst" in item for item in rejected)


def test_accepted_sample_jobs_have_complete_descriptions():
    jobs, _ = discover_jobs(
        preferences(),
        LocalSampleJobProvider(),
        today=date.today(),
    )

    assert jobs
    assert all(len(job.job_description.split()) >= 50 for job in jobs)


def test_discovery_deduplicates_provider_jobs():
    job = LocalSampleJobProvider().discover(preferences())[0]

    assert deduplicate_jobs([job, job]) == [job]


def test_discovery_deduplicates_aggregator_title_variants():
    job = LocalSampleJobProvider().discover(preferences())[0]
    duplicate = replace(
        job,
        provider_job_id="other-id",
        source_url="https://example.com/another-tracking-url",
        job_title=f"{job.job_title} [T500-26256]",
        company_name="Northstar Analytics Private Limited",
    )

    assert deduplicate_jobs([job, duplicate]) == [job]


def test_discovery_deduplicates_broad_source_company_title_repeats():
    job = DiscoveredJob(
        provider_job_id="adzuna-1",
        source="Adzuna",
        company_name="Honeywell",
        job_title="Data Scientist I",
        location="Bengaluru",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description="Python machine learning data science role.",
        source_url="https://adzuna.example/job/1",
    )
    duplicate = replace(
        job,
        provider_job_id="adzuna-2",
        source_url="https://adzuna.example/job/2",
    )

    assert deduplicate_jobs([job, duplicate]) == [job]


def test_discovery_deduplicates_google_jobs_broad_source_repeats():
    job = DiscoveredJob(
        provider_job_id="google-1",
        source="Google Jobs · Shine",
        company_name="MAK",
        job_title="Data Science AI/ML Fresher in Hyderabad",
        location="Hyderabad",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description="Python machine learning data science fresher role.",
        source_url="https://google.example/jobs/1",
    )
    duplicate = replace(
        job,
        provider_job_id="adzuna-1",
        source="Adzuna",
        source_url="https://adzuna.example/jobs/1",
    )

    assert deduplicate_jobs([job, duplicate]) == [job]


def test_discovery_rejects_old_job():
    job = LocalSampleJobProvider().discover(preferences())[0]
    old_job = replace(job, posted_date=date.today() - timedelta(days=30))

    accepted, reason = job_matches_preferences(
        old_job,
        preferences(maximum_job_age_days=7),
    )

    assert not accepted
    assert "freshness window" in reason


def test_broad_source_rejects_deployment_artifact_company_names():
    job = DiscoveredJob(
        provider_job_id="bad-company",
        source="Adzuna",
        company_name="frontendnodeproductionuprailwayapp",
        job_title="Entry Level Java AWS Programmer Junior Data Scientist AI Engineer",
        location="Hyderabad",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python machine learning data science role for freshers.",
    )

    accepted, reason = job_matches_preferences(job, preferences())

    assert not accepted
    assert "deployment artifact" in reason
    assert broad_source_company_quality_issue(
        "frontendnodeproductionrailwayapp"
    ) == "Company name looks like a deployment artifact"


def test_broad_source_rejects_aggregator_artifact_company_names():
    job = DiscoveredJob(
        provider_job_id="artifact-company",
        source="Google Jobs · Example",
        company_name="2.halvolink",
        job_title="Junior Data Scientist",
        location="India",
        work_mode="Remote",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python machine learning data science role for freshers.",
    )

    accepted, reason = job_matches_preferences(job, preferences())

    assert not accepted
    assert "aggregator artifact" in reason


def test_broad_source_rejects_generic_hiring_titles():
    job = DiscoveredJob(
        provider_job_id="generic-title",
        source="Google Jobs · Example",
        company_name="Example AI",
        job_title="junior data scientist/ reputed company",
        location="India",
        work_mode="Remote",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python machine learning data science role for freshers.",
    )

    accepted, reason = job_matches_preferences(job, preferences())

    assert not accepted
    assert "generic hiring advertisement" in reason
    assert (
        broad_source_title_quality_issue("urgent hiring data scientist")
        == "Job title looks like a generic hiring advertisement"
    )


def test_provider_cache_clear_removes_broad_search_cache_entries():
    _GREENHOUSE_CACHE[("test",)] = (1.0, [])
    _LEVER_CACHE[("test",)] = (1.0, [])
    _ASHBY_CACHE[("test",)] = (1.0, [])
    _ADZUNA_CACHE[("test",)] = (1.0, [])
    _JOOBLE_CACHE[("test",)] = (1.0, [])
    _REMOTIVE_CACHE[("test",)] = (1.0, [])
    _ARBEITNOW_CACHE[("test",)] = (1.0, [])
    _REMOTEOK_CACHE[("test",)] = (1.0, [])
    _SERPAPI_CACHE[("test",)] = (1.0, [])

    clear_discovery_provider_caches()

    assert _GREENHOUSE_CACHE == {}
    assert _LEVER_CACHE == {}
    assert _ASHBY_CACHE == {}
    assert _ADZUNA_CACHE == {}
    assert _JOOBLE_CACHE == {}
    assert _REMOTIVE_CACHE == {}
    assert _ARBEITNOW_CACHE == {}
    assert _REMOTEOK_CACHE == {}
    assert _SERPAPI_CACHE == {}


def test_source_family_classification_supports_coverage_reporting():
    assert is_direct_company_source("Greenhouse · Example AI")
    assert is_direct_company_source("Lever · Example AI")
    assert is_direct_company_source("Ashby · Example AI")
    assert not is_direct_company_source("Adzuna")
    assert is_broad_market_source("Adzuna")
    assert is_broad_market_source("Jooble")
    assert is_broad_market_source("RemoteOK")
    assert is_broad_market_source("Google Jobs · LinkedIn")
    assert not is_broad_market_source("Greenhouse · Example AI")


def test_discovery_rejects_unselected_location():
    job = DiscoveredJob(
        provider_job_id="outside-location",
        source="Test",
        company_name="Example",
        job_title="Data Scientist",
        location="Chennai, India",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python data science machine learning.",
    )

    accepted, reason = job_matches_preferences(
        job,
        preferences(locations="Bengaluru, Hyderabad"),
    )

    assert not accepted
    assert "Location excluded" in reason


def test_india_location_expansion_is_opt_in():
    job = DiscoveredJob(
        provider_job_id="india-market-role",
        source="Adzuna",
        company_name="Example",
        job_title="Data Scientist",
        location="Pune, Maharashtra",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python machine learning data science role for graduates.",
    )

    strict_match, strict_reason = job_matches_preferences(
        job,
        preferences(locations="Bengaluru, Hyderabad"),
    )
    expanded_match, expanded_reason = job_matches_preferences(
        job,
        preferences(locations="Bengaluru, Hyderabad"),
        allow_location_expansion=True,
    )

    assert is_india_location(job.location)
    assert not strict_match
    assert "Location excluded" in strict_reason
    assert expanded_match
    assert expanded_reason == ""


def test_discovery_uses_india_expansion_when_exact_coverage_is_low():
    exact = DiscoveredJob(
        provider_job_id="exact-role",
        source="Test",
        company_name="Example",
        job_title="Data Scientist",
        location="Hyderabad, India",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python machine learning data science role for graduates.",
        source_url="https://example.com/exact",
    )
    expanded = replace(
        exact,
        provider_job_id="expanded-role",
        location="Pune, Maharashtra",
        source_url="https://example.com/expanded",
    )
    foreign = replace(
        exact,
        provider_job_id="foreign-role",
        location="Singapore",
        source_url="https://example.com/foreign",
    )

    class Provider:
        def discover(self, _preferences):
            return [foreign, expanded, exact]

    jobs, rejected = discover_jobs(
        preferences(locations="Hyderabad"),
        Provider(),
    )

    assert [job.provider_job_id for job in jobs] == [
        "exact-role",
        "expanded-role",
    ]
    assert any("Singapore" in item for item in rejected)


def test_role_title_matching_supports_ai_variants():
    assert title_matches_target_role(
        "AI Engineering Intern",
        ["AI/ML Engineer"],
    )
    assert title_matches_target_role(
        "AI Engineer, Enterprise AI Development",
        ["AI/ML Engineer"],
    )
    assert title_matches_target_role(
        "AI Engineer - Generative AI and Machine Learning",
        ["AI/ML Engineer"],
    )
    assert title_matches_target_role(
        "Machine Learning Engineer I",
        ["AI/ML Engineer"],
    )
    assert title_matches_target_role(
        "Data Science Intern",
        ["Data Scientist"],
    )
    assert title_matches_target_role(
        "Graduate Software Engineer, Open Source",
        ["Associate Software"],
    )


def test_entry_level_metadata_uses_positive_description_evidence():
    metadata = infer_discovery_metadata(
        "Data Scientist",
        "This fresher opportunity welcomes recent graduates with 0-2 years.",
        "Bengaluru",
    )

    assert metadata["experience_level"] == "Fresher / Entry level"

    associate = infer_discovery_metadata(
        "Associate Software Engineer",
        "Build and test product features with guidance from the team.",
        "Bengaluru",
    )
    assert associate["experience_level"] == ""
    assert has_likely_entry_level_evidence(
        "Associate Software Engineer",
        "Build and test product features with guidance from the team.",
    )


def test_unstated_experience_is_not_claimed_as_verified():
    job = DiscoveredJob(
        provider_job_id="unknown-experience",
        source="Adzuna",
        company_name="Example",
        job_title="Data Scientist",
        location="Bengaluru",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description="Analyze data using Python and machine learning.",
    )

    assert experience_confidence(job) == "Experience not stated"


def test_broad_source_level_metadata_requires_text_evidence():
    job = DiscoveredJob(
        provider_job_id="broad-internship-metadata",
        source="Google Jobs · Example",
        company_name="Example",
        job_title="Data Scientist, Analytics Operations",
        location="Hyderabad",
        work_mode="Onsite",
        job_type="Internship",
        experience_level="Internship",
        posted_date=date.today(),
        job_description="Analyze operations data using Python and machine learning.",
    )

    assert experience_confidence(job) == "Experience not stated"


def test_direct_source_level_metadata_can_be_verified():
    job = DiscoveredJob(
        provider_job_id="direct-internship-metadata",
        source="Greenhouse · Example",
        company_name="Example",
        job_title="Data Scientist, Analytics Operations",
        location="Hyderabad",
        work_mode="Onsite",
        job_type="Internship",
        experience_level="Internship",
        posted_date=date.today(),
        job_description="Analyze operations data using Python and machine learning.",
    )

    assert experience_confidence(job) == "Verified selected level"


def test_broad_source_legal_entity_artifacts_are_manual_review():
    job = DiscoveredJob(
        provider_job_id="legal-entity-artifact",
        source="Google Jobs · Workday",
        company_name="1074 Amgen Technology Pvt Ltd.",
        job_title="Associate Data Scientist - Investment Analytics",
        location="Hyderabad",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description="Build analytics models with Python and machine learning.",
    )

    assert experience_confidence(job) == "Experience not stated"


def test_broad_source_mixed_role_titles_are_manual_review():
    job = DiscoveredJob(
        provider_job_id="mixed-role",
        source="Google Jobs · Example",
        company_name="Example AI",
        job_title="Junior Data scientist/Jr Java Developer-remote",
        location="Remote, India",
        work_mode="Remote",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description="Junior role using Python, data science, and ML.",
    )

    assert experience_confidence(job) == "Experience not stated"


def test_entry_level_evidence_marks_unstructured_jobs_verified():
    job = DiscoveredJob(
        provider_job_id="freshers-role",
        source="Adzuna",
        company_name="Example",
        job_title="AI Engineer",
        location="Bengaluru",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description=(
            "Open to 2026 batch freshers. Work on Python, machine learning, "
            "model evaluation, documentation, and collaboration."
        ),
    )

    assert has_entry_level_evidence(job.job_title, job.job_description)
    assert experience_confidence(job) == "Verified selected level"


def test_likely_entry_level_evidence_is_separate_from_verified():
    job = DiscoveredJob(
        provider_job_id="associate-role",
        source="Adzuna",
        company_name="Example",
        job_title="Associate Machine Learning Engineer",
        location="Bengaluru",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description="Build models with Python and collaborate with the team.",
    )

    assert has_likely_entry_level_evidence(job.job_title, job.job_description)
    assert experience_confidence(job) == "Likely entry-level"
    assert experience_priority(job) == 2


def test_above_entry_title_markers_are_manual_review_only():
    for title in (
        "Advanced Data Scientist",
        "Data Scientist, Specialist",
        "Machine Learning Engineer - L3",
        "Data Scientist 4A",
    ):
        job = DiscoveredJob(
            provider_job_id=title,
            source="Greenhouse",
            company_name="Example",
            job_title=title,
            location="Bengaluru",
            work_mode="Onsite",
            job_type="Full-time",
            experience_level="Fresher / Entry level",
            posted_date=date.today(),
            job_description="Build models with Python and machine learning.",
        )

        assert experience_confidence(job) == "Experience requirement detected"
        assert experience_priority(job) == 0


def test_entry_level_relevance_scores_above_generic_match():
    junior = DiscoveredJob(
        provider_job_id="junior-role",
        source="Adzuna",
        company_name="Example",
        job_title="Junior Data Scientist",
        location="Bengaluru",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="",
        posted_date=date.today(),
        job_description=(
            "Use Python, SQL, machine learning, data cleaning, model "
            "evaluation, and documentation."
        ),
    )
    generic = replace(
        junior,
        provider_job_id="generic-role",
        job_title="Data Scientist",
    )

    assert role_relevance(junior, preferences()) > role_relevance(
        generic,
        preferences(),
    )


def test_ai_interest_demotes_bi_analyst_hybrid_roles_from_recommended_lane():
    analyst = DiscoveredJob(
        provider_job_id="analyst-hybrid",
        source="Google Jobs · Shine",
        company_name="SA",
        job_title="Data Analyst & Data Scientist (Required Fresher)",
        location="India",
        work_mode="Remote",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description=(
            "Fresher data analyst role focused on Power BI, Azure Data Factory, "
            "Azure Databricks, data warehousing, dashboards, reports, Excel, "
            "business intelligence, SQL, Python, machine learning, deep learning, "
            "NLP, computer vision, TensorFlow, and stakeholder reporting."
        ),
    )
    ai_role = replace(
        analyst,
        provider_job_id="ai-role",
        company_name="Example AI",
        job_title="AI Engineer Fresher",
        job_description=(
            "Fresher AI engineer role using Python, machine learning, "
            "deep learning, NLP, model evaluation, and Git."
        ),
    )

    assert role_relevance(analyst, preferences()) < 75
    assert role_relevance(ai_role, preferences()) > role_relevance(
        analyst,
        preferences(),
    )


def test_profile_search_queries_prioritize_early_career_intent():
    queries = profile_search_role_queries(
        preferences(
            target_roles="Data Scientist, Machine Learning Engineer, AI/ML Engineer",
            preferred_skills="Python, TensorFlow, Communication",
        )
    )

    assert queries[:5] == [
        "Data Scientist fresher",
        "Machine Learning Engineer fresher",
        "AI/ML Engineer fresher",
        "AI Engineer fresher",
        "Artificial Intelligence Engineer fresher",
    ]
    assert "Data Scientist Python" in queries
    assert "Data Scientist TensorFlow" in queries
    assert "AI Engineer fresher" in queries
    assert "Generative AI Engineer fresher" in queries


def test_interleaved_queries_use_profile_search_plan_when_available():
    queries = interleaved_role_location_queries(
        ["Data Scientist"],
        ["Bengaluru", "Hyderabad"],
        limit=4,
        preferences=preferences(
            target_roles="Data Scientist",
            locations="Bengaluru, Hyderabad",
            preferred_skills="Python",
        ),
    )

    assert queries == [
        ("Data Scientist fresher", "Bengaluru"),
        ("Data Scientist fresher", "Hyderabad"),
        ("Data Scientist fresher", "India"),
        ("Data Scientist fresher", ""),
    ]


def test_google_jobs_query_budget_reaches_ai_engineer_fresher_searches():
    prefs = preferences(
        target_roles=(
            "Data Scientist, Machine Learning Engineer, AI/ML Engineer, "
            "NLP Engineer, Computer Vision Engineer"
        ),
        locations="Bengaluru, Hyderabad, Chennai",
        preferred_skills="Python, Machine Learning, NLP",
    )
    queries = interleaved_role_location_queries(
        prefs.target_roles,
        prefs.locations,
        limit=32,
        preferences=prefs,
    )

    assert ("AI Engineer fresher", "Chennai") in queries
    assert ("Artificial Intelligence Engineer fresher", "India") in queries
    assert ("Generative AI Engineer fresher", "Bengaluru") in queries


def test_location_aliases_match_bangalore_and_bengaluru():
    job = DiscoveredJob(
        provider_job_id="bangalore-role",
        source="Test",
        company_name="Example",
        job_title="Data Scientist",
        location="Bangalore, Karnataka",
        work_mode="Onsite",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python machine learning data science role for graduates.",
    )

    accepted, reason = job_matches_preferences(job, preferences())

    assert accepted
    assert reason == ""


def test_worldwide_remote_matches_selected_remote_work_mode():
    job = DiscoveredJob(
        provider_job_id="remote-role",
        source="Test",
        company_name="Example",
        job_title="Machine Learning Engineer",
        location="Remote - Worldwide",
        work_mode="Remote",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Python machine learning model evaluation and deployment.",
    )
    local_preferences = preferences(
        locations="Bengaluru, Hyderabad",
        work_modes=["Remote"],
    )

    accepted, reason = job_matches_preferences(job, local_preferences)

    assert accepted
    assert reason == ""


def test_us_remote_friendly_role_does_not_match_india_locations():
    job = DiscoveredJob(
        provider_job_id="us-remote-role",
        source="Greenhouse · Example",
        company_name="Example",
        job_title="Machine Learning Engineer I",
        location="Remote-Friendly | San Francisco, CA | New York, NY",
        work_mode="Remote",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description="Build machine learning systems using Python.",
        freshness_verified=False,
    )

    accepted, reason = job_matches_preferences(
        job,
        preferences(locations="Bengaluru, Hyderabad"),
    )

    assert not accepted
    assert "Location excluded" in reason


def test_skill_mentions_do_not_admit_unselected_job_title():
    job = DiscoveredJob(
        provider_job_id="product-analyst",
        source="Test",
        company_name="Example",
        job_title="Product Analyst",
        location="Bengaluru, India",
        work_mode="Hybrid",
        job_type="Full-time",
        experience_level="Fresher / Entry level",
        posted_date=date.today(),
        job_description=(
            "Partner with data scientists and use Python, SQL, machine "
            "learning, and NLP to analyze product performance."
        ),
    )

    accepted, reason = job_matches_preferences(job, preferences())

    assert not accepted
    assert reason == "Job title is outside the selected target roles"


def test_training_roles_are_not_treated_as_practitioner_roles():
    assert not title_matches_target_role(
        "Data Science Trainer",
        ["Data Scientist"],
    )


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class IncompleteReadResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        raise IncompleteRead(b"{", 20)


def test_greenhouse_provider_normalizes_public_jobs():
    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Machine Learning Intern",
                "location": {"name": "Remote, India"},
                "updated_at": date.today().isoformat() + "T10:30:00Z",
                "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
                "content": (
                    "<p>Build and evaluate machine learning models using "
                    "Python, pandas, NumPy, and scikit-learn.</p>"
                    "<p>Prepare datasets, document experiments, collaborate "
                    "with engineers, review errors, communicate findings, "
                    "and improve model quality through careful testing.</p>"
                ),
            }
        ]
    }

    provider = GreenhouseJobProvider(
        {"example": "Example AI"},
        opener=lambda *_args, **_kwargs: FakeResponse(payload),
    )
    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].company_name == "Example AI"
    assert jobs[0].work_mode == "Remote"
    assert jobs[0].job_type == "Internship"
    assert jobs[0].date_label == "Active listing"
    assert not jobs[0].freshness_verified
    assert jobs[0].source_url.endswith("/123")
    assert jobs[0].apply_url.endswith("/123")
    assert "<p>" not in jobs[0].job_description


def test_greenhouse_board_configuration_is_explicit():
    assert parse_greenhouse_boards(
        "acme|Acme AI,\nexample-board|Example Labs"
    ) == {
        "acme": "Acme AI",
        "example-board": "Example Labs",
    }


def test_curated_live_sources_are_defaults(monkeypatch):
    monkeypatch.delenv("GREENHOUSE_BOARDS", raising=False)
    monkeypatch.delenv("LEVER_SITES", raising=False)
    monkeypatch.delenv("APPLYSMART_USE_CURATED_LIVE_SOURCES", raising=False)

    assert parse_greenhouse_boards() == CURATED_GREENHOUSE_BOARDS
    assert parse_lever_sites() == CURATED_LEVER_SITES


def test_curated_live_sources_can_be_disabled(monkeypatch):
    monkeypatch.delenv("GREENHOUSE_BOARDS", raising=False)
    monkeypatch.delenv("LEVER_SITES", raising=False)
    monkeypatch.setenv("APPLYSMART_USE_CURATED_LIVE_SOURCES", "false")

    assert parse_greenhouse_boards() == {}
    assert parse_lever_sites() == {}


def test_html_to_text_normalizes_greenhouse_content():
    assert html_to_text("<p>Python &amp; SQL</p><ul><li>Testing</li></ul>") == (
        "Python & SQL Testing"
    )


def test_greenhouse_date_parser_never_returns_none():
    assert parse_greenhouse_date("2026-06-20T10:30:00Z") == date(2026, 6, 20)
    assert isinstance(parse_greenhouse_date("invalid"), date)


def test_discovery_caps_large_provider_results():
    sample = LocalSampleJobProvider().discover(preferences())[0]

    class LargeProvider:
        def discover(self, _preferences):
            return [
                replace(
                    sample,
                    provider_job_id=f"job-{index}",
                    source_url=f"https://example.com/jobs/{index}",
                )
                for index in range(75)
            ]

    jobs, _ = discover_jobs(preferences(), LargeProvider(), limit=50)

    assert len(jobs) == 50


def test_lever_provider_normalizes_public_postings():
    payload = [
        {
            "id": "lever-123",
            "text": "Data Science Intern",
            "categories": {
                "location": "Bengaluru, India",
                "commitment": "Intern",
            },
            "descriptionPlain": (
                "Support data science experiments using Python, SQL, machine "
                "learning, data cleaning, exploratory analysis, and model "
                "evaluation. Work with engineers to document results and "
                "communicate findings clearly."
            ),
            "lists": [
                {
                    "text": "Requirements",
                    "content": (
                        "<li>Experience with pandas and scikit-learn</li>"
                        "<li>Strong analytical and problem-solving skills</li>"
                    ),
                }
            ],
            "additionalPlain": "Applications are reviewed on a rolling basis.",
            "hostedUrl": "https://jobs.lever.co/example/lever-123",
            "applyUrl": "https://jobs.lever.co/example/lever-123/apply",
            "workplaceType": "hybrid",
        }
    ]
    provider = LeverJobProvider(
        {"example": ("Example Labs", "global")},
        opener=lambda *_args, **_kwargs: FakeResponse(payload),
    )

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].company_name == "Example Labs"
    assert jobs[0].work_mode == "Hybrid"
    assert jobs[0].job_type == "Internship"
    assert jobs[0].experience_level == "Internship"
    assert jobs[0].date_label == "Active listing"
    assert not jobs[0].freshness_verified
    assert jobs[0].source_url.endswith("lever-123")
    assert jobs[0].apply_url.endswith("lever-123/apply")
    assert "pandas and scikit-learn" in jobs[0].job_description


def test_ashby_provider_normalizes_public_postings():
    payload = {
        "jobs": [
            {
                "id": "ashby-123",
                "title": "AI/ML Intern",
                "location": {"name": "Remote, India"},
                "descriptionHtml": (
                    "<p>Support machine learning and NLP experiments using "
                    "Python, TensorFlow, PyTorch, pandas, and NumPy.</p>"
                    "<p>Prepare datasets, train models, evaluate results, "
                    "document findings, and collaborate with engineers.</p>"
                ),
                "jobUrl": "https://jobs.ashbyhq.com/example/ashby-123",
                "applyUrl": "https://jobs.ashbyhq.com/example/ashby-123/application",
                "isListed": True,
            }
        ]
    }
    provider = AshbyJobProvider(
        {"example": "Example AI"},
        opener=lambda *_args, **_kwargs: FakeResponse(payload),
    )

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "Ashby · Example AI"
    assert jobs[0].work_mode == "Remote"
    assert jobs[0].job_type == "Internship"
    assert jobs[0].experience_level == "Internship"
    assert jobs[0].date_label == "Active listing"
    assert not jobs[0].freshness_verified
    assert jobs[0].source_url.endswith("ashby-123")
    assert jobs[0].apply_url.endswith("application")


def test_ashby_incomplete_http_reads_are_isolated_as_provider_failures():
    provider = AshbyJobProvider(
        {"example": "Example AI"},
        opener=lambda *_args, **_kwargs: IncompleteReadResponse(),
    )

    try:
        provider.discover(preferences())
    except JobDiscoveryError as exc:
        assert "No configured Ashby boards could be loaded" in str(exc)
        assert "could not be reached" in str(exc)
    else:
        raise AssertionError("Expected incomplete read to become provider error")


def test_ashby_configuration_is_explicit():
    assert parse_ashby_boards("example|Example AI,orb|Orb") == {
        "example": "Example AI",
        "orb": "Orb",
    }


def test_adzuna_provider_searches_roles_and_normalizes_results():
    payload = {
        "results": [
            {
                "id": "adzuna-123",
                "title": "Junior Data Scientist",
                "company": {"display_name": "Example Analytics"},
                "location": {"display_name": "Bengaluru, Karnataka"},
                "description": (
                    "Build data science solutions using Python, SQL, machine "
                    "learning, data cleaning, feature engineering, model "
                    "evaluation, documentation, communication, collaboration, "
                    "and reproducible analytical workflows for product teams."
                ),
                "created": date.today().isoformat() + "T10:30:00Z",
                "redirect_url": "https://www.adzuna.in/jobs/details/123",
                "contract_type": "permanent",
            }
        ]
    }
    requested_urls = []

    def opener(request, **_kwargs):
        requested_urls.append(request.full_url)
        return FakeResponse(payload)

    provider = AdzunaJobProvider(
        "app-id",
        "app-key",
        opener=opener,
        max_queries=1,
    )
    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "Adzuna"
    assert jobs[0].company_name == "Example Analytics"
    assert jobs[0].job_type == "Full-time"
    assert jobs[0].source_url == jobs[0].apply_url
    assert "what=Data+Scientist+fresher" in requested_urls[0]
    assert "where=Bengaluru" in requested_urls[0]
    assert "max_days_old=14" in requested_urls[0]


def test_jooble_provider_searches_role_locations_and_normalizes_results():
    payload = {
        "jobs": [
            {
                "id": "jooble-123",
                "title": "Junior Machine Learning Engineer",
                "company": "Example ML",
                "location": "Hyderabad",
                "snippet": (
                    "Build machine learning models using Python, pandas, "
                    "NumPy, scikit-learn, TensorFlow, model evaluation, "
                    "documentation, and collaboration in an entry-level "
                    "engineering role for recent graduates."
                ),
                "updated": date.today().isoformat() + "T10:30:00Z",
                "link": "https://jooble.org/job/123",
            }
        ]
    }
    requested = []

    def opener(request, **_kwargs):
        requested.append(request)
        return FakeResponse(payload)

    provider = JoobleJobProvider("api-key", opener=opener, max_queries=1)

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "Jooble"
    assert jobs[0].company_name == "Example ML"
    assert jobs[0].experience_level == "Fresher / Entry level"
    assert jobs[0].source_url == jobs[0].apply_url
    body = json.loads(requested[0].data.decode("utf-8"))
    assert body["keywords"] == "Data Scientist fresher"
    assert body["location"] == "Bengaluru"


def test_remotive_provider_searches_and_normalizes_remote_jobs():
    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Data Science Intern",
                "company_name": "Remote Analytics",
                "candidate_required_location": "Worldwide",
                "job_type": "full_time",
                "publication_date": date.today().isoformat() + "T09:00:00",
                "url": "https://remotive.com/remote-jobs/data/123",
                "description": (
                    "<p>Build data science projects using Python, SQL, "
                    "machine learning, model evaluation, documentation, "
                    "collaboration, dashboards, experiments, and practical "
                    "analytics workflows for remote product teams.</p>"
                ),
            }
        ]
    }
    requested_urls = []

    def opener(request, **_kwargs):
        requested_urls.append(request.full_url)
        return FakeResponse(payload)

    provider = RemotiveJobProvider(opener=opener, max_queries=1)

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "Remotive"
    assert jobs[0].company_name == "Remote Analytics"
    assert jobs[0].work_mode == "Remote"
    assert jobs[0].job_type == "Internship"
    assert jobs[0].experience_level == "Internship"
    assert jobs[0].source_url == jobs[0].apply_url
    assert "search=Data+Scientist+fresher" in requested_urls[0]


def test_arbeitnow_provider_normalizes_public_jobs():
    payload = {
        "data": [
            {
                "slug": "junior-data-scientist-123",
                "company_name": "Berlin Data Lab",
                "title": "Junior Data Scientist",
                "description": (
                    "<p>Analyze product data using Python, SQL, machine "
                    "learning, data cleaning, feature engineering, model "
                    "evaluation, communication, documentation, and teamwork "
                    "with senior data scientists.</p>"
                ),
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/junior-data-scientist-123",
                "tags": ["Python", "Machine Learning"],
                "job_types": ["Full-time"],
                "location": "Berlin",
                "created_at": int(datetime.now().timestamp()),
            }
        ]
    }

    def opener(_request, **_kwargs):
        return FakeResponse(payload)

    provider = ArbeitnowJobProvider(opener=opener, max_pages=1)

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "Arbeitnow"
    assert jobs[0].company_name == "Berlin Data Lab"
    assert jobs[0].location == "Remote · Berlin"
    assert jobs[0].work_mode == "Remote"
    assert jobs[0].job_type == "Full-time"
    assert experience_confidence(jobs[0]) == "Likely entry-level"
    assert jobs[0].source_url == jobs[0].apply_url


def test_remoteok_provider_searches_tags_and_normalizes_jobs():
    payload = [
        {"legal": "metadata"},
        {
            "slug": "remote-junior-data-scientist",
            "id": "remoteok-123",
            "epoch": int(datetime.now().timestamp()),
            "date": date.today().isoformat() + "T09:00:00+00:00",
            "company": "Remote Data Co",
            "position": "Junior Data Scientist",
            "tags": ["python", "data science", "machine learning"],
            "description": (
                "<p>Build data science tools using Python, SQL, machine "
                "learning, data cleaning, model evaluation, dashboards, "
                "documentation, collaboration, and product analytics for "
                "distributed teams.</p>"
            ),
            "location": "Worldwide",
            "apply_url": "https://remoteok.com/apply/123",
            "url": "https://remoteok.com/remote-jobs/123",
        },
    ]
    requested_urls = []

    def opener(request, **_kwargs):
        requested_urls.append(request.full_url)
        return FakeResponse(payload)

    provider = RemoteOKJobProvider(opener=opener, max_tags=1)

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "RemoteOK"
    assert jobs[0].company_name == "Remote Data Co"
    assert jobs[0].work_mode == "Remote"
    assert experience_confidence(jobs[0]) == "Likely entry-level"
    assert jobs[0].source_url == "https://remoteok.com/remote-jobs/123"
    assert jobs[0].apply_url == "https://remoteok.com/apply/123"
    assert "tags=data-science" in requested_urls[0]


def test_serpapi_google_jobs_provider_normalizes_platform_results():
    payload = {
        "jobs_results": [
            {
                "job_id": "google-job-123",
                "title": "Data Science Intern",
                "company_name": "Example India AI",
                "location": "Hyderabad, Telangana, India",
                "via": "via LinkedIn",
                "description": (
                    "Build data science workflows with Python, SQL, machine "
                    "learning, data cleaning, model evaluation, dashboards, "
                    "documentation, communication, collaboration, and product "
                    "analytics for customer-facing AI features."
                ),
                "detected_extensions": {
                    "posted_at": "2 days ago",
                    "schedule_type": "Full-time",
                },
                "extensions": ["2 days ago", "Full-time"],
                "share_link": "https://www.google.com/search?q=job",
                "apply_options": [
                    {
                        "title": "LinkedIn",
                        "link": "https://www.linkedin.com/jobs/view/123",
                    }
                ],
            }
        ]
    }
    requested_urls = []

    def opener(request, **_kwargs):
        requested_urls.append(request.full_url)
        return FakeResponse(payload)

    provider = SerpApiGoogleJobsProvider(
        "api-key",
        opener=opener,
        max_queries=1,
    )

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "Google Jobs · LinkedIn"
    assert jobs[0].company_name == "Example India AI"
    assert jobs[0].job_type == "Internship"
    assert jobs[0].experience_level == "Internship"
    assert jobs[0].freshness_verified
    assert jobs[0].apply_url == "https://www.linkedin.com/jobs/view/123"
    assert "engine=google_jobs" in requested_urls[0]
    assert "location=Bengaluru" in requested_urls[0]


def test_serpapi_provider_requires_credentials():
    try:
        SerpApiGoogleJobsProvider("")
    except ValueError as exc:
        assert "SERPAPI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing SerpAPI credentials to fail")


def test_searchapi_provider_fetches_and_parses_results():
    payload = {
        "jobs": [
            {
                "job_id": "test-job-123",
                "title": "Data Science Intern",
                "company_name": "Example India AI",
                "location": "Bengaluru",
                "via": "LinkedIn",
                "description": "This is a detailed job description that is long enough to pass length checks. Requires Python and machine learning knowledge.",
                "detected_extensions": {
                    "posted_at": "2 days ago",
                    "work_from_home": True,
                    "schedule": "Full-time",
                },
                "sharing_link": "https://google.com/jobs/sharing",
                "apply_link": "https://www.linkedin.com/jobs/view/123",
            }
        ]
    }
    requested_urls = []

    def opener(request, **_kwargs):
        requested_urls.append(request.full_url)
        return FakeResponse(payload)

    provider = SearchApiGoogleJobsProvider(
        "api-key",
        opener=opener,
        max_queries=1,
    )

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert jobs[0].source == "Google Jobs · LinkedIn"
    assert jobs[0].company_name == "Example India AI"
    assert jobs[0].job_type == "Internship"  # lever_job_type or fallback
    assert jobs[0].experience_level == "Internship"
    assert jobs[0].freshness_verified
    assert jobs[0].apply_url == "https://www.linkedin.com/jobs/view/123"
    assert "engine=google_jobs" in requested_urls[0]
    assert "location=Bengaluru" in requested_urls[0]


def test_searchapi_provider_requires_credentials():
    try:
        SearchApiGoogleJobsProvider("")
    except ValueError as exc:
        assert "SEARCHAPI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing SearchAPI credentials to fail")


def test_early_career_provider_combines_sources_and_failures():
    sample = LocalSampleJobProvider().discover(preferences())[0]

    class WorkingProvider:
        name = "Working"
        failures = ["minor warning"]

        def discover(self, _preferences):
            return [replace(sample, provider_job_id="early-career-sample")]

    class FailedProvider:
        name = "Failed"

        def discover(self, _preferences):
            raise JobDiscoveryError("Source unavailable.")

    provider = EarlyCareerWebJobProvider([FailedProvider(), WorkingProvider()])

    jobs = provider.discover(preferences())

    assert len(jobs) == 1
    assert provider.failures == ["Source unavailable.", "minor warning"]


def test_jooble_query_planner_balances_roles_and_locations():
    queries = interleaved_role_location_queries(
        ["Data Scientist", "Machine Learning Engineer"],
        ["Bengaluru", "Hyderabad", "Chennai"],
        limit=8,
    )

    roles = {role for role, _location in queries}
    locations = {location for _role, location in queries}

    assert "Data Scientist" in roles
    assert "Machine Learning Engineer" in roles
    assert "Bengaluru" in locations
    assert "Hyderabad" in locations


def test_broad_market_query_expansion_adds_entry_level_variants():
    roles = expanded_role_queries(["Data Scientist", "AI/ML Engineer"])
    locations = expanded_market_locations(["Bengaluru"])

    assert "Junior Data Scientist" in roles
    assert "AI ML Intern" in roles
    assert "India" in locations
    assert "" in locations


def test_adzuna_provider_requires_credentials():
    try:
        AdzunaJobProvider("", "")
    except ValueError as exc:
        assert "ADZUNA_APP_ID" in str(exc)
    else:
        raise AssertionError("Expected missing Adzuna credentials to fail")


def test_adzuna_missing_date_is_active_but_not_freshness_verified():
    payload = {
        "results": [
            {
                "id": "missing-date",
                "title": "Data Scientist",
                "company": {"display_name": "Example"},
                "location": {"display_name": "Hyderabad"},
                "description": " ".join(["Python machine learning analysis"] * 20),
                "redirect_url": "https://www.adzuna.in/jobs/details/missing",
                "contract_type": "permanent",
            }
        ]
    }
    provider = AdzunaJobProvider(
        "app-id",
        "app-key",
        opener=lambda *_args, **_kwargs: FakeResponse(payload),
        max_queries=1,
    )

    job = provider.discover(preferences())[0]

    assert isinstance(job.posted_date, date)
    assert not job.freshness_verified
    assert job.date_label == "Active listing"


def test_lever_configuration_supports_global_and_eu_sites():
    assert parse_lever_sites(
        "example|Example Labs,eu-site|EU Labs|eu"
    ) == {
        "example": ("Example Labs", "global"),
        "eu-site": ("EU Labs", "eu"),
    }


def test_unknown_lever_date_does_not_claim_freshness():
    job = replace(
        LocalSampleJobProvider().discover(preferences())[0],
        posted_date=date.today() - timedelta(days=365),
        freshness_verified=False,
        date_label="Active listing",
    )

    accepted, reason = job_matches_preferences(
        job,
        preferences(maximum_job_age_days=1),
    )

    assert accepted
    assert reason == ""


def test_combined_provider_isolates_one_provider_failure():
    sample_provider = LocalSampleJobProvider()

    class FailedProvider:
        name = "Failed"

        def discover(self, _preferences):
            raise JobDiscoveryError("Failed provider unavailable.")

    provider = CombinedJobProvider([FailedProvider(), sample_provider])
    jobs = provider.discover(preferences())

    assert jobs
    assert provider.failures == ["Failed provider unavailable."]


def test_direct_company_feed_ranks_ahead_of_broad_source_when_equal():
    sample = LocalSampleJobProvider().discover(preferences())[0]
    broad = replace(
        sample,
        provider_job_id="broad",
        source="Adzuna",
        source_url="https://adzuna.example/job",
    )
    direct = replace(
        sample,
        provider_job_id="direct",
        source="Ashby · Example",
        source_url="https://company.example/job",
    )

    assert source_priority(direct) > source_priority(broad)


def test_entry_preferences_reject_principal_roles():
    job = replace(
        LocalSampleJobProvider().discover(preferences())[0],
        job_title="Principal Machine Learning Engineer",
    )

    accepted, reason = job_matches_preferences(job, preferences())

    assert not accepted
    assert "Experienced role" in reason


def test_entry_preferences_reject_year_requirement_from_description():
    job = replace(
        LocalSampleJobProvider().discover(preferences())[0],
        job_title="Data Scientist",
        job_description=(
            "Applicants must have 10+ years of experience building machine "
            "learning systems with Python."
        ),
    )

    accepted, reason = job_matches_preferences(job, preferences())

    assert not accepted
    assert reason == "Requires 10+ years of experience"
