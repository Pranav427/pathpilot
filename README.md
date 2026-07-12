# PathPilot
> Navigate your career with intelligence.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pathpilot-01.streamlit.app)
[![Portfolio](https://img.shields.io/badge/Portfolio-Creator-blue?style=flat&logo=vercel)](https://portfolio-self-one-10.vercel.app/)

---

PathPilot is an intelligent career platform that helps job seekers discover relevant opportunities, analyze fit, generate evidence-backed application materials, prepare outreach, check ATS coverage, and track application progress.

## Current Status
PathPilot is currently in the **Product Refinement & Demo Readiness** phase. 

### 🚀 Key Core Features
- **Candidate Master Profile**: Maintain a single, structured source of truth for your background.
- **Preferences Scan**: Filter opportunities dynamically by roles, locations, work modes, and job types.
- **Multi-Source Discovery**: Search Greenhouse, Lever, Ashby company feeds, and broad-market API aggregators.
- **Centralized Tracker**: Keep historical records of job-ranking history, application states, and approved PDFs.

### 🧠 Intelligent Scorer & Matcher
- **Transparent Scoring**: Understand exact match scores with detailed breakdowns.
- **Evidence Verification**: Strictly match qualifications to actual profile details (preventing AI hallucinations).
- **Seniority Analysis**: Apply realistic seniority scoring based on required years of experience.
- **ATS Keyword Coverage**: Scan for missing terms and filter generic company noise dynamically.

### 🛡️ Safety & Production Hardening
- **LaTeX Fallback**: Clean PDF generation using pure-Python fallbacks when LaTeX is missing.
- **Deterministic AI Scoring**: Enforce consistency so AI providers don't output random percentages.
- **Authentication Safety**: Gracefully isolate auth/quota errors instead of continuous failed retries.
- **Human-in-the-Loop Review**: Review every detail before saving PDFs or tracker records.

---

## Product Roadmap & Versions

| Version | Theme | Goal | Key Features |
| :--- | :--- | :--- | :--- |
| **V1.0** | **Application Intelligence** | Help users get more interview calls | Master Profile, Role Recommendations, Discovery feeds, dynamic Scorer & Matcher, Resume/Cover letter Tailoring, and persistent Tracker. (Active/Complete) |
| **V1.5** | **Interview Intelligence** | Help users prepare for interviews | Application status triggers, Resume/JD-based practice questions, Behavioral prep, and Company Dossier briefs. (Target Phase) |
| **V2.0** | **Application Automation** | Reduce repetitive work | Playwright form auto-fillers, Scheduled scans, and Outreach follow-ups. (Future) |

---

## Core User Workflow (V1.0)

> **Master Profile**  
> ➔ **Profile Intelligence & Role Suggestions**  
> ➔ **Job Discovery (Preferences Scan)**  
> ➔ **Dynamic Evidence Selection**  
> ➔ **ATS-Friendly Resume Tailoring**  
> ➔ **Personalized Cover Letter Compilation**  
> ➔ **Quality & ATS Validation Check**  
> ➔ **Tracker Draft & Status Pipeline**

---

## Project Structure

```text
PathPilot/
├── app.py                    Streamlit application
├── main.py                   CLI application
├── application_service.py    Reusable application workflow
├── job_discovery.py          Multi-source job discovery providers & filters
├── job_preferences.py        Search parameters and user profile suggestions
├── profile.py                Candidate default master profile
├── tracker.py                Database applications and ranking history store
├── db_client.py              SQLite client wrapper
└── tests/                    Automated testing suite
```

---

## Multi-Source Discovery Setup

When multiple providers are configured, **All live sources** combines and deduplicates their results. Direct company feeds are ranked ahead of broad aggregator feeds when relevance and experience confidence are otherwise close.

### Broad Market Aggregators

For broader market coverage, register an Adzuna API application and configure:
```env
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
ADZUNA_COUNTRY=in
```

For a second broad-market source, configure Jooble:
```env
JOOBLE_API_KEY=your_api_key
JOOBLE_COUNTRY=in
```

### Google Jobs search (Unified)
PathPilot supports a unified Google Jobs search option using SearchApi.io (preferred) or SerpAPI:
```env
# Optional SearchApi.io (preferred)
SEARCHAPI_API_KEY=your_searchapi_key

# Optional SerpAPI
SERPAPI_API_KEY=your_serpapi_key
```

### Local Testing Catalog
The fictional sample catalog is hidden from normal users. Developers may enable it explicitly for offline workflow testing:
```env
APPLYSMART_ENABLE_SAMPLE_JOBS=true
```

---

## Getting Started

### Local Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/Pranav427/pathpilot.git
   cd pathpilot
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the Streamlit UI:
   ```bash
   streamlit run app.py
   ```
4. Run the CLI version:
   ```bash
   python main.py
   ```

### Running Tests
Execute unit and regression tests cleanly with:
```bash
python -m pytest -q
```

---

## Tracked Fields & Verdicts

### Tracker Database Schema
* **Applications**: Company, Job title, Source URL, Status, Fit score, ATS score, Resume path, Cover letter path, Created date.
* **Job Ranking Runs**: Total URLs, Successful jobs, Failed jobs, Ranking report path, Ranked jobs list.

### Fit Verdicts
PathPilot uses a transparent scoring layer and produces verdicts:
* `Strong Match` (High odds)
* `Moderate Match` (Good odds)
* `Stretch Match` (Low/stretch odds)
* `Not Recommended` (Significant skill/seniority gap)

---

## Important Limitations

- **Aggregator Pages**: LinkedIn, Naukri, Indeed, Glassdoor, login-protected pages, and JavaScript-heavy pages may block extraction. Use manual job-description pasting instead.
- **Evidence Separation**: The system should not claim unsupported experience.
- **Local Storage**: SQLite tracker data and generated files are stored locally. Streamlit Cloud may reset local files when the app container restarts.

---

## Phase-wise Roadmap

- **Phase 1-3**: Core application engine, URL fetching, multi-job URL ranking, SQLite history, and regression tests. *(Completed)*
- **Phase 4**: Streamlit application UI, failure isolation, and document review. *(Completed)*
- **Phase 5**: SaaS beta foundation, campaign manager, and analytics. *(In Progress)*
- **Phase 6-8**: Outcome tracking, persistent hosted DB, and agent-based Career Copilot. *(Planned)*
