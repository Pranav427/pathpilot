# Document 02 - Technical Requirements Document

## Architecture Overview

PathPilot is designed as a modular, local-first Python application that operates under a single client runtime (Streamlit) and database interface (`db_client.py`). The services are structured to transition into a cloud-native SaaS backend.

---

## Technical Stack & Version Alignment

### V1.0 - Application Intelligence (Core Engine)
- **Frontend**: Streamlit. Focuses on rapid iteration and local validation.
- **Backend Services**:
  - `application_service.py`: Orchestrates the matching and generation flow.
  - `db_client.py`: Abstraction layer routing to SQLite locally or PostgreSQL in production.
  - `job_discovery.py` & `job_store.py`: Aggregation and normalization of company feeds.
  - `analyzer.py` & `matcher.py`: Structured AI parsing and profile evaluation.
  - `scoring.py`: Deterministic scoring rules (alias handling, seniority penalties).
  - `resume.py` & `cover_letter.py`: Tailored asset generation using LaTeX (with ReportLab PDF fallback).
  - `quality.py`: ATS validation and factuality constraints check.
- **Persistence**: SQLite (local) / PostgreSQL (production).
- **Authentication**: Centralized local alpha validation, prepared for production providers (e.g. Supabase Auth).

### V1.5 - Interview Intelligence (Interview Workspace)
- **AI Service**: Prompt orchestration targeting contextual interview drills.
- **Prompt Inputs**: Combines the Master Profile, generated resume, job description, target role, and company name.
- **Structured JSON outputs**: Evaluates skill gaps and generates:
  - Technical Questions
  - Behavioral Questions
  - Resume-specific Project Questions
  - Company Culture Briefs
- **Database Schema Extensions**:
  - `interview_preps`: id, application_id, prep_questions_json (structured categories), user_notes, created_at.

### V2.0 - Application Automation (Orchestration - Future)
- **Execution Engines**: Playwright integration for headless form completion on simple career pages.
- **Scheduler**: Cron-based background routines for automated preferences scans.

---

## Production DB Schema (PostgreSQL)

- **`users`**: id, email, password_hash, created_at.
- **`user_profiles`**: user_id, profile_name, name, email, phone, linkedin, github, portfolio, location, raw_profile_json, updated_at.
- **`applications`**: id, company_name, job_title, source_url, status, match_score, ats_score, resume_path, cover_letter_path, notes, job_analysis_json, match_json, ats_report_json, created_at, updated_at, user_id.
- **`job_search_runs`**: id, total_urls, successful_jobs, failed_jobs, report_path, failures_json, created_at, user_id.
- **`ranked_jobs`**: id, search_run_id, rank, company_name, job_title, source_url, fit_score, fit_verdict, extraction_quality, missing_skills_json, job_analysis_json, match_json, created_at.
- **`discovered_jobs`**: id, provider_job_id, source, company_name, job_title, location, work_mode, job_type, experience_level, posted_date, job_description, date_label, freshness_verified, source_url, apply_url, raw_json, first_seen_at, last_seen_at, user_id.
- **`interview_preps` [NEW - V1.5]**: id, application_id, prep_questions_json, user_notes, created_at.

---

## Constants & Constraints
- **Hallucination Prevention**: Tailored documents must only use claims, skills, and projects present in the Master Profile.
- **Keyword Filtering**: Obvious boilerplates, company names, and title banners are excluded from ATS match ratios to prevent score inflation.
- **Error Propagation**: Low-level provider errors are isolated in the aggregation layer, enabling partial discovery results without system crash.
