# PathPilot

PathPilot is an intelligent career platform that helps job seekers discover relevant opportunities, analyze fit, generate evidence-backed application materials, prepare outreach, check ATS coverage, and track application progress.

Navigate your career with intelligence.

The long-term objective is not to build a simple resume generator. The objective is to build a trustworthy career intelligence platform that finds relevant jobs, ranks them by fit, generates optimized applications, tracks outcomes, prepares candidates for interviews, and improves career decisions over time.

## Current Status

Current phase: Product Refinement & Demo Readiness.

Generated documents now pass deterministic safety checks for candidate status,
project evidence, application-only familiarity, and cover-letter structure.
Older tracker records may display a review warning when they were generated
before these safeguards were added.

Implemented:

- Candidate master profile
- Session-isolated tester profiles for local and controlled usability testing
- Session-based job preferences covering target roles, locations, experience,
  work mode, job type, preferred skills, exclusions, and freshness
- Evidence-backed role and skill suggestions derived from the active candidate
  profile, while locations and final preferences remain user-confirmed
- Provider-neutral discovery pipeline with default live Greenhouse, Lever, and
  Ashby company feeds, optional Adzuna and Jooble broad-market APIs, a
  developer-only sample catalog, deterministic filtering, cross-source
  deduplication, failure isolation, stale-result invalidation, and a job inbox
- Manual job description input
- Public job URL fetching
- Search/listing-page preflight that prevents misleading fit scores
- Multi-job URL ranking
- Multi-rank shortlisting using inputs such as `1`, `1,2,3`, or `1-3`
- Employer-name inference for common aggregator job pages
- AI job description analysis
- Profile-to-job matching
- Transparent fit scoring
- Explicit seniority penalties for experienced-hire requirements
- Application-only familiarity that never inflates the evidence-based fit score
- Conservative skill alias matching for terms like OOP, NLP, REST API, and SDLC
- Fit verdicts such as Strong Match, Stretch Match, and Not Recommended
- Structured resume generation
- Cover letter generation
- ATS keyword coverage check
- ATS explanation note for noisy/generic keyword coverage
- ATS filtering for obvious job-title, branding, and generic company-language noise
- PDF and text output with a pure-Python PDF fallback when LaTeX is unavailable
- SQLite application draft tracking
- SQLite job ranking session tracking
- Tracker views for approved applications and job-ranking history
- Source URL tracking
- Shared formatting utilities for filenames, display URLs, phone numbers, and LaTeX escaping
- Basic production hardening for AI retries, JD validation, URL failure messaging, and tracker DB initialization
- Deterministic fit-score wording so AI recommendations do not invent conflicting percentages
- Temporary profile-gap confirmation with permanent-evidence separation
- Human review before saving PDFs and tracker records
- Short, collision-safe output filenames that preserve application history
- Regression tests for scoring, ATS matching, profile confirmation, generation safety, job inputs, and tracker behavior
- User-safe Streamlit error messages with technical details retained in logs
- Classified AI-provider failures that stop retrying permanent authentication,
  quota, permission, and model errors
- Multi-source job discovery across curated Greenhouse, Lever, and Ashby
  company feeds plus optional Adzuna and Jooble broad-market APIs

## Product Roadmap & Versions

| Version | Theme | Goal | Key Features |
| :--- | :--- | :--- | :--- |
| **V1.0** | **Application Intelligence** | Help users get more interview calls | Master Profile, Role Recommendations, Discovery feeds, dynamic Scorer & Matcher, Resume/Cover letter Tailoring, and persistent Tracker. (Active/Complete) |
| **V1.5** | **Interview Intelligence** | Help users prepare for interviews | Application status triggers, Resume/JD-based practice questions, Behavioral prep, and Company Dossier briefs. (Target Phase) |
| **V2.0** | **Application Automation** | Reduce repetitive work | Playwright form auto-fillers, Scheduled scans, and Outreach follow-ups. (Future) |

## Core User Workflow (V1.0)

```text
Master Profile
↓
Profile Intelligence & Role Suggestions
↓
Job Discovery (Preferences Scan)
↓
Dynamic Evidence Selection
↓
ATS-Friendly Resume Tailoring
↓
Personalized Cover Letter Compilation
↓
Quality & ATS Validation Check
↓
Tracker Draft & Status Pipeline
```

## Project Structure

```text
PathPilot/
├── app.py                    Streamlit application
├── main.py                   CLI application
├── application_service.py    Reusable application workflow
├── profile.py                Structured candidate profile
├── job_preferences.py        Discovery preferences and validation
├── job_discovery.py          Provider contract, filtering, and sample catalog
├── job_fetcher.py            Public job-page extraction
├── job_search.py             Multi-URL ranking backend
├── analyzer.py               Job-description analysis
├── matcher.py                Candidate-to-job matching
├── scoring.py                Deterministic fit scoring
├── resume.py                 Resume generation and PDF rendering
├── cover_letter.py           Cover-letter generation and PDF rendering
├── quality.py                ATS and factuality checks
├── tracker.py                SQLite application tracking
├── llm_utils.py              LLM retry and JSON helpers
├── utils.py                  Shared formatting and status helpers
├── tests/                    Automated regression tests
├── DEMO_VALIDATION.md        Repeatable demo-readiness checklist
├── outputs/                  Local generated files, ignored by Git
├── .streamlit/config.toml    Streamlit theme and server settings
├── .env.example              Safe environment template
├── requirements.txt          Runtime dependencies
├── requirements-dev.txt      Test dependencies
└── SYSTEM_DESIGN.md          Architecture and roadmap
```

## Setup

Requirements:

- Python 3.11 recommended
- An Anthropic API key by default, or a Gemini API key when using Gemini
- Optional `pdflatex` for the preferred resume and cover-letter layout. When it
  is unavailable, PathPilot uses its bundled Python PDF fallback.

Clone the repository and create a virtual environment:

```bash
git clone <your-repository-url>
cd PathPilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For development and testing:

```bash
pip install -r requirements-dev.txt
```

Create local configuration from the safe template:

```bash
cp .env.example .env
```

Normal Job Discovery uses a curated set of public Greenhouse, Lever, and
Ashby company feeds without provider API keys. The default pack now includes a
broader set of India-present technology companies, but these direct feeds are
still not a complete job market. For narrow fresher data/AI searches,
broad-market or licensed partner search is still required to consistently
reach the 10-job coverage target. Custom Greenhouse boards can replace the
curated Greenhouse defaults through `.env`:

```env
GREENHOUSE_BOARDS=companytoken|Company Name,anotherboard|Another Company
```

This connector does not require a Greenhouse API key. It searches only the
companies explicitly configured by the app owner; it is not a global job-board
search. Greenhouse provides an update timestamp rather than a guaranteed
original publication date. Its feed contains currently published jobs, so
PathPilot labels those records as **Active listing · date unavailable** and
does not reject a role merely because its content was not recently edited.
PathPilot keeps only the top 50 matching results per discovery run.

Custom Lever sites can replace the curated Lever defaults by company site name:

```env
LEVER_SITES=companysite|Company Name|global,eucompany|EU Company|eu
```

Lever does not require an API key for published public postings. Its public
feed does not provide a reliable original posting date, so PathPilot labels
those records as **Active listing · date unavailable** and does not claim they
were posted inside the user's freshness window.

Custom Ashby boards can be added by public job-board name:

```env
ASHBY_BOARDS=companyboard|Company Name,anotherboard|Another Company
```

Ashby public postings are active company-career listings. PathPilot labels
them as **Active listing · date unavailable** unless the provider exposes a
reliable posting date.

When multiple providers are configured, **All live sources** combines and
deduplicates their results. Direct company feeds are ranked ahead of broad
aggregator feeds when relevance and experience confidence are otherwise close.

LinkedIn, Indeed, and Naukri are not scraped by discovery. They do not expose
an unrestricted public job-search API suitable for this workflow, and their
pages commonly block automated extraction. Jobs from those platforms can be
reviewed through a user-supplied public detail URL or manual job-description
paste. Broader automated coverage must use an approved API or licensed data
partner rather than fragile browser scraping.

Each live result exposes **View Job** for verification and **Apply on Company
Site** when the provider publishes a direct application URL. **Prepare
Application** transfers only that selected job into PathPilot's application
workspace. Discovery never applies automatically.

For broader market coverage, register an Adzuna API application and configure:

```env
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
ADZUNA_COUNTRY=in
```

PathPilot performs one bounded query per target role, combines those results
with configured company feeds, and then applies the same deterministic
freshness, location, title, and experience filters. Adzuna usage is subject to
its API limits, attribution requirements, and commercial licensing terms.
Successful broad searches are cached briefly to protect provider quotas.

For a second broad-market source, configure Jooble:

```env
JOOBLE_API_KEY=your_api_key
JOOBLE_COUNTRY=in
```

Jooble is queried with bounded role/location combinations, then passed through
the same title, location, experience, and exclusion filters as all other
providers. This improves coverage when Adzuna or direct company feeds are thin,
but every listing should still be opened and verified before preparing an
application.

The fictional sample catalog is hidden from normal users. Developers may
enable it explicitly for offline workflow testing:

```env
APPLYSMART_ENABLE_SAMPLE_JOBS=true
```

The `APPLYSMART_*` environment variable prefix is retained for compatibility
during the PathPilot rebrand. Product-facing UI and documentation now use
PathPilot.

Edit `.env`, choose `LLM_PROVIDER=gemini` or `LLM_PROVIDER=anthropic`, and
provide the corresponding API key plus candidate contact details. Claude
Sonnet is the default model.
Never commit `.env`; it is intentionally excluded by `.gitignore`.

The repository demo profile is stored in `profile.py`. In Streamlit, testers
can instead select `Tester profile` and enter their own verified evidence.
Tester-profile data remains in that browser session and does not modify
`profile.py`.

## Run The App

Streamlit UI:

```bash
streamlit run app.py
```

CLI:

```bash
python main.py
```

The app will ask:

```text
1. Paste job description manually
2. Extract from job URL
3. Rank multiple job URLs
```

If URL extraction fails, the app falls back to manual JD input.

## Run Tests

```bash
python -m pytest -q
```

## View Application History

```bash
python tracker.py
```

Tracked fields include:

Applications:

- Company
- Job title
- Source URL
- Status
- Fit score
- ATS score
- Resume path
- Cover letter path
- Created date

Job ranking runs:

- Total URLs
- Successful jobs
- Failed jobs
- Ranking report path
- Ranked jobs with score, verdict, URL, and gaps

In the Streamlit Tracker, switch from `Applications` to `Ranking history` to
inspect earlier URL batches and rejected links. Ranking history is intentionally
separate from applications because a ranked job is not considered an
application until its documents are reviewed, approved, and saved.

## Fit Verdicts

PathPilot uses a transparent scoring layer and produces verdicts:

```text
Strong Match
Moderate Match
Stretch Match
Not Recommended
```

For low-fit jobs, the system still generates drafts but warns the user to review the application carefully.

## Important Limitations

- URL fetching works best on public/static job pages.
- Job search results, career homepages, location hubs, and multi-job listings
  are identified before analysis; open a specific role and use its detail URL.
- LinkedIn, Naukri, Indeed, Glassdoor, login-protected pages, and JavaScript-heavy pages may fail.
- The system should not claim unsupported experience.
- Historical documents generated before the current factuality safeguards must
  be reviewed when the Tracker displays a legacy warning.
- Current tracker records generated drafts, not confirmed job submissions.
- Tester profiles are session-only. Refreshing or restarting the browser can
  remove them until persistent multi-user storage is implemented.
- SQLite tracker data and generated files are appropriate for local use, but
  Streamlit Cloud may reset them when the app restarts. Persistent hosted
  storage belongs to the later multi-user database phase.
- Matching is transparent and conservative, but still not as strong as embeddings, semantic search, or outcome-trained ranking.
- ATS coverage is an internal keyword-coverage heuristic, not an official score
  from a hiring platform or commercial ATS.
- The CLI validates very short job descriptions, but users should still review extracted URL text before generating documents.

## Roadmap

Phase 1: Single-job application engine.

Phase 2: Job URL fetching and production-hardening fixes. Complete for prototype use.

Phase 3: Multi-job URL ranking, normalization, shortlisting, report saving, SQLite ranking history, reusable application service, and regression testing. Complete for backend prototype use.

Phase 4: Streamlit application-management UI. Complete for local MVP use.

Phase 4.1: Controlled multi-job Streamlit ranking, failure isolation,
shortlisting, and one-at-a-time application review. Complete for local use.

Current refinement milestone: stabilize scoring, output grounding, error
handling, tracker terminology, responsive UI behavior, tests, and
documentation before public demonstration work.

Phase 4.2: Professional UI hierarchy, guided application steps, improved fit
and ATS presentation, document review, responsive layouts, and tracker
dashboard polish. Complete for local use.

Phase 5: SaaS beta foundation, application campaign manager, and analytics.

Phase 6: Outcome tracking and interview insights.

Phase 7: Production SaaS MVP.

Phase 8: Agent-based Career Copilot.

## Current Recommended Next Step

Complete the demo-readiness validation checklist with representative public
job pages and manual descriptions. Begin public user testing only after the
single-job workflow, ranking workflow, generated documents, PDF saving, and
Tracker have passed the documented regression scenarios.
