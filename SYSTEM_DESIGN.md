# PathPilot System Design & Architecture Documentation

## 1. Executive Summary

PathPilot is an AI-powered Career Intelligence Platform designed to turn the job search process into a structured, data-driven workflow. It is built around a single source of truth: a comprehensive **Master Profile**. The system dynamically extracts relevant experiences and projects to evaluate fit, compile tailored resumes and cover letters, run ATS quality validation checks, and log status histories.

The product's version roadmap is organized into three progressive, thematic phases:
* **V1.0: Application Intelligence** (Goal: Help users get more interview calls)
* **V1.5: Interview Intelligence** (Goal: Help users prepare for interviews)
* **V2.0: Application Automation** (Goal: Reduce repetitive work through automation)

---

## 2. Product Philosophy

We do not build multiple manual career personas. Instead, we capture a single, comprehensive Master Profile representing everything the candidate is capable of. 

When a candidate targets a specific role, PathPilot performs **Dynamic Evidence Selection**—extracting only the relevant achievements and skills from the Master Profile to tailor application materials on-the-fly, without hallucinating details or inventing experience.

```text
Master Profile (Unified data source)
      │
      ▼
Profile Intelligence (Capabilities analysis)
      │
      ▼
Career Role Recommendations (Suggest target paths)
      │
      ▼
User selects role
      │
      ▼
Job Discovery (Curated ATS feeds & API aggregation)
      │
      ▼
User selects job
      │
      ▼
Job Description Intelligence (Analyze requirements)
      │
      ▼
Evidence Selection (Extract matching items from Master Profile)
      │
      ▼
ATS-Friendly Resume (LaTeX/ReportLab compilation)
      │
      ▼
Personalized Cover Letter (Tone & company context alignment)
      │
      ▼
Quality Validation (ATS keyword coverage & factuality checks)
      │
      ▼
Ready to Apply
```

---

## 3. Version Roadmap & Build Order

| Version | Theme | Objective / Goal | Feature Matrix |
| :--- | :--- | :--- | :--- |
| **V1.0** | **Application Intelligence** | Help users get more interview calls | Master Profile, Role Recommendations, Multi-source Discovery, Scoring & Matcher, Dynamic Evidence Selector, Resume & Cover Letter PDF compilers, ATS Quality Checks, Application Tracker. |
| **V1.5** | **Interview Intelligence** | Help users prepare for interviews | Status triggers (Applied/Interview status unlock), Resume-based practice questions, JD-based technical drills, Behavioral and project gap prep, Company brief compiler, Preparation Dashboard. |
| **V2.0** | **Application Automation** | Reduce repetitive work | Headless form auto-fillers (Playwright), Scheduled background discovery scans, Automated outreach follow-ups. |

---

## 4. Current System Architecture (V1.0 Core)

* **`profile.py`**: Handles Master Profile schemas.
* **`job_fetcher.py`**: Fetches job postings from public URLs.
* **`job_search.py`**: Orchestrates multi-URL ingestion, fit-scoring, and ranking.
* **`job_preferences.py`**: Manages search filters (roles, locations, work modes, exclusions).
* **`job_discovery.py` & `job_store.py`**: Connectors for ATS feeds (Greenhouse, Lever, Ashby) and fallback search APIs.
* **`analyzer.py`**: Parses raw job text using structured AI models.
* **`matcher.py` & `scoring.py`**: Measures candidate-to-job fit and calculates deterministic scores with keyword alias matching and seniority penalties.
* **`resume.py` & `cover_letter.py`**: Tailors documents using LaTeX (with a pure-Python ReportLab fallback).
* **`quality.py`**: Verifies ATS keyword coverage and checks factuality constraints.
* **`db_client.py`**: Centralized database controller routing queries to SQLite locally or PostgreSQL in production.
* **`app.py`**: Streamlit web client hosting user login, registration, and onboarding.

---

## 5. Database Schema (PostgreSQL)

* **`users`**: id, email, password_hash, created_at.
* **`user_profiles`**: user_id, profile_name, name, email, phone, linkedin, github, portfolio, location, raw_profile_json, updated_at.
* **`applications`**: id, company_name, job_title, source_url, status, match_score, ats_score, resume_path, cover_letter_path, notes, job_analysis_json, match_json, ats_report_json, created_at, updated_at, user_id.
* **`job_search_runs`**: id, total_urls, successful_jobs, failed_jobs, report_path, failures_json, created_at, user_id.
* **`ranked_jobs`**: id, search_run_id, rank, company_name, job_title, source_url, fit_score, fit_verdict, extraction_quality, missing_skills_json, job_analysis_json, match_json, created_at.
* **`discovered_jobs`**: id, provider_job_id, source, company_name, job_title, location, work_mode, job_type, experience_level, posted_date, job_description, date_label, freshness_verified, source_url, apply_url, raw_json, first_seen_at, last_seen_at, user_id.
* **`interview_preps` [NEW - V1.5]**: id, application_id, prep_questions_json (structured categories), user_notes, created_at.

---

## 6. Constraints & Safety Checks
* **Grounded Claims Only**: Generators are strictly constrained to details present in the Master Profile, preventing AI from inventing job history.
- **ATS Noise Filtering**: Excludes obvious boilerplate company copy and title headers from fit scores to avoid keyword stuffing and scoring anomalies.
- **Fail-Safe Fallbacks**: If LaTeX or external API services fail, the system falls back to ReportLab or local SQLite without halting the application.
