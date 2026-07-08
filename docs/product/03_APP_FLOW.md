# Document 03 - App Flow

## Navigation Type

Current app uses a left sidebar with main workspace sections:

- Application
- Job Discovery
- Job Ranking
- Profile
- Tracker

Future SaaS should keep this workspace model but make the flow clearer with a top-level dashboard and guided steps.

## First Screen

Current private alpha:

1. User opens PathPilot.
2. User enters the private alpha password if enabled.
3. User lands in the main workspace.

Future SaaS:

1. Visitor lands on marketing/auth entry.
2. User signs up or logs in.
3. New user completes onboarding profile.
4. User lands on dashboard with next recommended action.

## Core Journey 1 - Profile To Job Discovery

1. User opens Profile.
2. User reviews or updates skills, projects, education, certifications, and target roles.
3. System derives conservative target roles and preferred skills from verified evidence.
4. User opens Job Discovery.
5. User reviews target roles, locations, work mode, job type, freshness, and exclusions.
6. User saves preferences.
7. User chooses discovery source or all live sources.
8. System fetches jobs, normalizes them, filters them, deduplicates them, and ranks them.
9. User sees recommended jobs, verified-level jobs, and all results.
10. User opens a job, verifies original source, and decides whether to prepare an application.

## Core Journey 2 - Selected Job To Application

1. User clicks Prepare Application on one selected job.
2. App loads that job into the Application workspace.
3. User reviews company, role, source URL, and job description.
4. User clicks Analyze fit.
5. System analyzes the JD, matches the profile, and calculates fit.
6. User reviews matched skills, missing skills, score, and recommendation.
7. User confirms whether temporary profile gaps should be included.
8. System generates resume, cover letter, and ATS quality report.
9. User reviews generated materials.
10. User approves saving PDFs/text and tracker record.
11. App stores the application draft and source metadata.

## Core Journey 3 - Manual Job Input

1. User opens Application.
2. User pastes a job description or enters a public job URL.
3. App validates whether the input is a complete job detail page.
4. User runs fit analysis.
5. App follows the same match, generate, review, and track flow.

## Core Journey 4 - Tracker Review

1. User opens Tracker.
2. User sees approved application drafts and job-ranking history.
3. User filters or reviews applications.
4. User checks generated document paths, scores, source URL, and status.
5. Future: user updates outcome such as applied, interview, rejected, offer.

## Empty States

- No profile: prompt user to create or confirm a profile before discovery.
- No job preferences: show suggested preferences from profile and ask user to save.
- No discovery results: explain which filters were too strict and suggest broadening location, freshness, or source.
- No tracker records: tell user to prepare and approve an application first.

## Error States

- LLM auth/quota error: stop retrying and show user-safe provider message.
- Job URL blocked or incomplete: ask user to paste the job description.
- Provider timeout: isolate failed provider and show partial results.
- No source configured: explain which environment variables enable providers.
- PDF generation issue: use fallback renderer when possible.

## Redirect Logic

- Prepare Application: Job Discovery to Application with selected job loaded.
- Generate and approve: Application remains visible and tracker record is created.
- View tracker: user manually opens Tracker after approval.
- Reset job: clears current application workspace but does not delete tracker history.
