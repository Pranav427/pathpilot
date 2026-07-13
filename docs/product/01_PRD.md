# Document 01 - Product Requirements Document

## App Name

PathPilot

## Tagline

Navigate your career with intelligence.

The intelligent platform for modern careers.

## Problem

Job seekers waste time across fragmented job boards, duplicated listings, expired roles, unclear eligibility, and generic applications. Freshers and early-career candidates especially struggle to identify roles that match their actual profile, convert project experience into job-ready evidence, and understand why a role is or is not worth applying to.

## Target User

The primary user is an early-career job seeker, fresher, student, or career switcher targeting data science, AI/ML, software engineering, analytics, or related technology roles. They have projects and skills but need help finding realistic jobs, tailoring documents, and tracking applications in one workflow.

## Core Value Proposition

PathPilot is not just a resume generator. It connects profile intelligence, job discovery, fit scoring, document generation, preparation, and tracking so users can apply to better-fit roles with stronger evidence-backed materials and better career decisions.

## Must-Have Features

- Profile-based job preferences derived from verified user skills, roles, and experience.
- Multi-source job discovery from reliable APIs and company career feeds.
- Job filtering by role, location, experience level, work mode, job type, freshness, and exclusions.
- Job ranking with transparent relevance and experience-confidence signals.
- Manual job description input and public job URL ingestion.
- JD analysis for skills, tools, responsibilities, keywords, and requirements.
- Candidate-to-job matching with evidence-backed fit scoring.
- Resume generation tailored to selected job requirements.
- Cover letter generation tailored to selected company and role.
- ATS keyword coverage and quality checks.
- Application tracker for generated drafts and user review.
- Explicit user approval before saving or using generated materials.

## Nice-To-Have Features

- Daily job alerts based on saved profile preferences.
- Outcome analytics showing which roles and resumes produce interviews.
- Skill-gap learning recommendations.
- Saved job collections and shortlist workflows.
- Browser extension for capturing roles from job boards.
- Multi-profile support for different target career paths.
- Team/admin dashboard for colleges or placement support.

## Out Of Scope For Current Build

- Automatic application submission on behalf of the user.
- Scraping LinkedIn, Naukri, or Indeed without approved/licensed access.
- Paid subscription billing.
- Full multi-user SaaS database and auth.
- Interview scheduling automation.
- Employer/recruiter-facing dashboard.

## User Stories

- As a fresher, I want PathPilot to discover entry-level roles based on my profile so that I do not waste time on senior roles.
- As a job seeker, I want to review the original job posting before preparing an application so that I can verify the role is real.
- As a candidate, I want a fit score with matched and missing skills so that I understand whether to apply.
- As a user, I want tailored resume and cover-letter drafts so that I can apply faster with stronger materials.
- As a tester, I want to use my own profile without editing the repository profile so that feedback reflects my real career situation.
- As a future SaaS user, I want my saved profile to drive job recommendations automatically so that the product feels personalized.

## Success Metrics

- At least 10 relevant jobs returned for common broad searches such as AI/ML fresher roles across major Indian tech cities.
- At least 3-5 recommended jobs returned for narrow city searches when supply exists.
- Less than 10% obviously senior/unqualified jobs in the recommended view.
- Resume and cover-letter generation succeeds for selected jobs without manual recovery.
- Users can complete profile to job discovery to application preparation in under 10 minutes.
- Testers can understand why jobs were accepted or filtered without developer explanation.
- Application drafts are tracked with clear status and source URL.
