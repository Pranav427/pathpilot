# Document 03 - App Flow

This document details the user journey across PathPilot's version roadmap: Application Intelligence (V1.0), Interview Intelligence (V1.5), and Application Automation (V2.0).

---

## Workspace Navigation

The Streamlit interface exposes a sidebar navigation panel containing the following pages:
1. **Profile**: Input and manage the Master Profile.
2. **Job Discovery**: Scan live feeds and APIs based on profile preferences.
3. **Job Ranking**: Ingest job URLs, rank them, and select shortlists.
4. **Application**: Single-job workspace to match profile details, generate tailored assets, and check ATS coverage.
5. **Tracker**: View application status history and unlock the Interview Prep dashboard.

---

## Core Journey 1 - V1.0 Application Intelligence

### 1. Master Profile Setup
- User creates an account or logs in.
- User sets up their Master Profile (via resume parsing, manual input, or loading sandbox mock data).
- System analyzes the profile data to identify core strengths and suggest matching roles (Data Scientist, SDE, ML Engineer).

### 2. Search & Discovery
- User opens Job Discovery and selects target roles.
- System scans curated company career boards (Greenhouse, Lever, Ashby) and broad market APIs.
- User reviews recommended listings and clicks "Prepare Application" on a selected job to copy it into the active workspace.

### 3. Tailoring & ATS Scoring
- In the active Application workspace, user clicks "Analyze Fit."
- System extracts requirements, compares them to the Master Profile, and outputs a transparent fit score.
- System selects the best evidence (matching projects/skills) from the Master Profile and generates the resume, cover letter, and ATS quality report.
- User reviews and clicks "Approve." The draft and document paths are saved to the Tracker.

---

## Core Journey 2 - V1.5 Interview Intelligence

This workflow is unlocked when an application's status in the Tracker changes to `Applied` or `Interview`.

### 1. Prep Activation
- User navigates to the **Tracker** page.
- User updates the status of a saved application (e.g. Google - Software Engineer) to `Applied`.
- An "Interview Prep" button becomes active next to that application record.

### 2. Contextual Question Generation
- User clicks "Interview Prep" to open the contextual interview dashboard.
- PathPilot sends the matching context (Master Profile + Tailored Resume + Job Description + Company Name) to the AI engine.
- System generates custom practice categories:
  - **Resume Questions**: Focusing on project claims made on the specific tailored PDF.
  - **JD Questions**: Technical drills targeting the job description's required tools.
  - **Behavioral Questions**: Prompts tailored to the role type.
  - **Company Briefs**: Insights on the target company's current technologies.
- User writes preparation notes and practices answering the prompts.

---

## Core Journey 3 - V2.0 Application Automation (Future)

This journey represents future browser-automation features:
- User selects a job and clicks "Auto-Apply."
- PathPilot starts a headless browser, navigates to the application form, auto-fills details from the Master Profile, uploads the tailored resume PDF, and saves the submission status to the Tracker.
