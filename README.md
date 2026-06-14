# ApplySmart AI

ApplySmart AI is an AI Career Copilot prototype that helps job seekers analyze jobs, measure profile fit, generate tailored application materials, check ATS coverage, and track application drafts.

The long-term objective is not to build a simple resume generator. The objective is to build a career intelligence platform that finds relevant jobs, ranks them by fit, generates optimized applications, tracks outcomes, and improves interview chances over time.

## Current Status

Current phase: Product Refinement & Demo Readiness.

Generated documents now pass deterministic safety checks for candidate status,
project evidence, application-only familiarity, and cover-letter structure.
Older tracker records may display a review warning when they were generated
before these safeguards were added.

Implemented:

- Candidate master profile
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
- PDF and text output
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

Not yet implemented:

- Broad job-board discovery beyond user-provided URLs
- Multi-user SaaS backend
- Outcome analytics
- Auto-apply workflow

## Workflow

```text
Profile
↓
Manual JD or Job URL or Multiple Job URLs
↓
Analyze Job
↓
Match Profile
↓
Calculate Fit Score
↓
Generate Resume
↓
Generate Cover Letter
↓
Check ATS Quality
↓
Track Draft
```

## Project Structure

```text
SmartApply/
├── app.py                    Streamlit application
├── main.py                   CLI application
├── application_service.py    Reusable application workflow
├── profile.py                Structured candidate profile
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
- `pdflatex` for PDF generation

Clone the repository and create a virtual environment:

```bash
git clone <your-repository-url>
cd SmartApply
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

Edit `.env`, choose `LLM_PROVIDER=gemini` or `LLM_PROVIDER=anthropic`, and
provide the corresponding API key plus candidate contact details. Claude
Sonnet is the default model.
Never commit `.env`; it is intentionally excluded by `.gitignore`.

The remaining education, skills, projects, experience, and certifications are
stored in `profile.py` and should be customized for the candidate.

### Private Alpha Configuration

The private testing build supports three deployment controls:

```env
APPLYSMART_ALPHA_MODE=true
APP_PASSWORD=replace_with_a_strong_shared_password
MAX_AI_ACTIONS_PER_SESSION=20
```

- `APP_PASSWORD` enables the shared-password gate. If it is empty, the gate is
  disabled for local development.
- `MAX_AI_ACTIONS_PER_SESSION` limits analysis, generation, and ranking usage
  in each browser session.
- Alpha mode displays a persistent warning that generated documents require
  human review and that automated submission is disabled.

For Streamlit Community Cloud, copy the safe structure from
`.streamlit/secrets.toml.example` into the deployment's **Secrets** editor.
Do not create or commit a real `.streamlit/secrets.toml`.

The Feedback page stores invited-tester comments in the same local SQLite
database as the tracker. Streamlit Community Cloud's filesystem can reset
during restarts or redeployments, so export important feedback manually during
the alpha. Persistent multi-user storage belongs in a later phase.

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

Private-alpha feedback:

- Optional tester name
- Category
- One-to-five rating
- Detailed comments
- Submission date

In the Streamlit Tracker, switch from `Applications` to `Ranking history` to
inspect earlier URL batches and rejected links. Ranking history is intentionally
separate from applications because a ranked job is not considered an
application until its documents are reviewed, approved, and saved.

## Fit Verdicts

ApplySmart AI uses a transparent scoring layer and produces verdicts:

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
