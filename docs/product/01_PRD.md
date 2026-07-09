# Document 01 - Product Requirements Document

## App Name

PathPilot

## Tagline

Navigate your career with intelligence.

The intelligent platform for modern careers.

## Problem

Job seekers waste time across fragmented job boards, duplicated listings, expired roles, unclear eligibility, and generic applications. Early-career candidates struggle to match their projects and skills to realistic roles, extract relevant evidence to pass ATS checks, and prepare effectively for interviews once they do get called.

---

## Product Philosophy & Core Journey

PathPilot is built around a single, comprehensive **Master Profile** (representing the user's complete capabilities, experiences, and projects). The system dynamically extracts the most relevant evidence to tailor resumes and cover letters for specific jobs, rather than forcing the user to maintain separate manual personas.

```text
Master Profile
      │
      ▼
Profile Intelligence (Candidate analysis)
      │
      ▼
Career Role Recommendations (Suggest target paths)
      │
      ▼
User selects role
      │
      ▼
Job Discovery (Aggregated, filtered listings)
      │
      ▼
User selects job
      │
      ▼
Job Description Intelligence (Analyze requirements)
      │
      ▼
Evidence Selection (AI selects matching items from Master Profile)
      │
      ▼
ATS-Friendly Resume (Tailored layout)
      │
      ▼
Personalized Cover Letter (Targeted tone)
      │
      ▼
Quality Validation (ATS & factuality checks)
      │
      ▼
Ready to Apply
```

---

## Feature Matrix by Version

### V1.0 - Application Intelligence (Goal: Get Interview Calls)
* **Master Profile**: Comprehensive portfolio of skills, education, experience, projects, and target roles.
* **Profile Intelligence**: Automated parsing and capabilities assessment.
* **Role Recommendation**: Suggests aligned titles (e.g. Data Scientist, AI Engineer) based on profile evidence.
* **Job Discovery**: Aggregated, deduplicated direct feeds (Greenhouse, Lever, Ashby) and API fallbacks.
* **Job Matching & Scorer**: Strict, transparent fit scores with alias mapping and seniority checks.
* **Dynamic Evidence Selection**: Automatically extracts matching projects and skills from the Master Profile.
* **Resume & Cover Letter Generation**: Dynamic tailoring with LaTeX or a pure-Python fallback.
* **ATS & Quality Validation**: Validates keyword coverage and prevents factuality hallucination.
* **Application Tracker**: Pipeline tracker logs generated drafts, status, and metadata.

### V1.5 - Interview Intelligence (Goal: Pass the Interview)
* **Status Unlock**: Triggered when an application status updates to `Applied` or `Interview` in the Tracker.
* **Resume-based Questions**: Practice questions targeting the specific tailored resume version submitted.
* **JD-based Questions**: Technical queries aligned with the target job description requirements.
* **Project & Skill Gap Questions**: Drills down into the candidate's projects and points out gap solutions.
* **Company-focused Preparation**: Summarizes company culture, tech stack, and strategic goals.
* **Behavioral & Mock Prep**: Framework-aligned behavioral questions and mock interview simulation.

### V2.0 - Application Automation (Goal: Reduce Repetitive Work - Future Roadmap)
* **Browser Automation**: Automated form fills for application pipelines (e.g. Playwright integration).
* **Auto-Apply**: Automatic submission workflows where authorized.
* **Smart Follow-ups**: Automated outreach emails and follow-ups.
* **System Notifications**: Email/desktop alerts for new high-fit jobs.

---

## Out Of Scope For Current Build (V1.0 & V1.5)

- Automatic application form-submission.
- Scraping LinkedIn, Indeed, or Naukri pages without approved API credentials.
- Paid subscription billing.
- Recruiter/employer-facing dashboards.

---

## Success Metrics

- Users can go from Master Profile creation to discovery and generating a tailored draft in under 10 minutes.
- Resume and cover-letter generation compiles cleanly without inventing any candidate qualifications.
- Less than 10% senior/unqualified roles are recommended in the user's role dashboard.
- Tracker correctly preserves document assets and transitions them into the Interview Prep workspace upon status update.
