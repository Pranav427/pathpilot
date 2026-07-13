# Document 05 - Backend Schema

## Current Local Persistence

The current app uses SQLite through `tracker.py` for application drafts and job-ranking sessions. Session profile and discovery preferences currently live in Streamlit session state.

## Future SaaS Database

Use PostgreSQL with user-owned rows. Each table should include `id`, `user_id` where applicable, `created_at`, and `updated_at`.

## Table: users

- `id` uuid primary key
- `email` text unique not null
- `name` text
- `role` text default `user`
- `created_at` timestamp
- `updated_at` timestamp

## Table: profiles

- `id` uuid primary key
- `user_id` uuid foreign key to users.id
- `name` text
- `email` text
- `phone` text encrypted or private
- `location` text
- `linkedin_url` text
- `github_url` text
- `portfolio_url` text
- `target_roles` jsonb
- `summary` text
- `is_active` boolean
- `created_at` timestamp
- `updated_at` timestamp

## Table: profile_skills

- `id` uuid primary key
- `profile_id` uuid foreign key to profiles.id
- `skill_name` text
- `category` text
- `confidence` text
- `is_verified` boolean
- `created_at` timestamp

## Table: profile_projects

- `id` uuid primary key
- `profile_id` uuid foreign key to profiles.id
- `title` text
- `description` text
- `tools` jsonb
- `evidence_points` jsonb
- `url` text
- `created_at` timestamp

## Table: job_preferences

- `id` uuid primary key
- `user_id` uuid foreign key to users.id
- `profile_id` uuid foreign key to profiles.id
- `target_roles` jsonb
- `locations` jsonb
- `experience_levels` jsonb
- `work_modes` jsonb
- `job_types` jsonb
- `preferred_skills` jsonb
- `excluded_keywords` jsonb
- `max_job_age_days` integer
- `created_at` timestamp
- `updated_at` timestamp

## Table: discovered_jobs

- `id` uuid primary key
- `source` text
- `source_job_id` text
- `company` text
- `title` text
- `location` text
- `work_mode` text
- `job_type` text
- `experience_level` text
- `posted_date` date nullable
- `description` text
- `job_url` text
- `apply_url` text
- `raw_payload` jsonb
- `created_at` timestamp
- `last_seen_at` timestamp

Indexes:

- `(source, source_job_id)`
- `(company, title, location)`
- `posted_date`
- full-text index on title and description

## Table: job_discovery_runs

- `id` uuid primary key
- `user_id` uuid foreign key to users.id
- `profile_id` uuid foreign key to profiles.id
- `preferences_id` uuid foreign key to job_preferences.id
- `source_mode` text
- `matched_count` integer
- `recommended_count` integer
- `filtered_count` integer
- `source_coverage` jsonb
- `created_at` timestamp

## Table: job_recommendations

- `id` uuid primary key
- `run_id` uuid foreign key to job_discovery_runs.id
- `job_id` uuid foreign key to discovered_jobs.id
- `relevance_score` integer
- `experience_confidence` text
- `status` text default `new`
- `filter_reason` text nullable
- `created_at` timestamp

## Table: applications

- `id` uuid primary key
- `user_id` uuid foreign key to users.id
- `profile_id` uuid foreign key to profiles.id
- `job_id` uuid foreign key to discovered_jobs.id nullable
- `company` text
- `role` text
- `job_url` text
- `fit_score` integer
- `verdict` text
- `status` text
- `created_at` timestamp
- `updated_at` timestamp

## Table: generated_documents

- `id` uuid primary key
- `application_id` uuid foreign key to applications.id
- `document_type` text
- `content_text` text
- `storage_path` text
- `version` integer
- `created_at` timestamp

## Table: application_outcomes

- `id` uuid primary key
- `application_id` uuid foreign key to applications.id
- `outcome_status` text
- `notes` text
- `event_date` date
- `created_at` timestamp

## Table: ai_runs

- `id` uuid primary key
- `user_id` uuid foreign key to users.id
- `application_id` uuid nullable
- `task_type` text
- `provider` text
- `model` text
- `prompt_version` text
- `status` text
- `error_class` text nullable
- `created_at` timestamp

## Auth And Security

- Users can read and write only their own profiles, preferences, recommendations, applications, and documents.
- Admins can view aggregate metrics, not private generated documents unless explicitly authorized.
- API keys must never be stored in client code.
- Generated PDFs and private contact data should be stored behind authenticated access.
- Sensitive contact fields should be treated as private user data.

## Row-Level Security Direction

- `profiles.user_id = auth.uid()`
- `job_preferences.user_id = auth.uid()`
- `job_discovery_runs.user_id = auth.uid()`
- `applications.user_id = auth.uid()`
- `generated_documents` accessible through owned applications only.
- `discovered_jobs` may be shared globally if no user-private data is stored in the row.
