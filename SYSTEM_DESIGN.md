# PathPilot System Design Documentation

## 1. Executive Summary

PathPilot is an AI-powered Career Intelligence Platform that helps job seekers increase interview opportunities by improving every major step of the job search process: job discovery, job selection, job fit analysis, resume tailoring, cover letter generation, ATS optimization, application tracking, interview preparation, and career analytics.

The product is not intended to be a simple resume generator. Its purpose is to become an AI Career Copilot that helps users decide which jobs are worth applying to, how to position themselves, what gaps they need to close, and which application strategies produce the best outcomes.

The primary input is a candidate profile. The primary output is more interview opportunities. The long-term vision is a scalable SaaS platform used by thousands of students, freshers, job switchers, software engineers, data scientists, AI engineers, and career changers.

## 2. Problem Statement

Job seekers face a fragmented, inefficient, and low-feedback job search process. Jobs are spread across LinkedIn, Naukri, Indeed, company career pages, referrals, and niche platforms. Many listings are irrelevant, duplicated, expired, or unrealistic for the candidate's profile. Candidates often apply with generic resumes, fail ATS keyword screening, do not know which roles are worth prioritizing, and rarely track outcomes in a structured way.

PathPilot solves this by turning job search into a data-driven workflow. It can analyze jobs, compare them with a candidate's profile, rank opportunities, generate tailored materials, track application status, and later learn which roles and resume strategies produce interviews.

## 3. Project Goals

Business goals: create a differentiated AI career product, increase user interview conversion, support future SaaS monetization, and build a defensible career intelligence dataset.

Technical goals: build modular Python services, support AI-driven structured outputs, add job fetching/search, introduce persistence, and evolve toward API-driven SaaS architecture.

User goals: find better jobs faster, apply with stronger materials, reduce wasted applications, and understand personal skill gaps.

Career goals: help users improve positioning, learn missing skills, and increase interview opportunities.

SaaS goals: support multi-user profiles, subscriptions, dashboards, analytics, document storage, and secure user data.

Startup goals: validate demand, acquire job seekers, improve interview outcomes, and eventually build a scalable career intelligence platform.

## 4. System Objectives

Primary objectives:

- Convert a candidate profile and job description into a fit score, tailored resume, cover letter, ATS report, and tracked draft.
- Help users decide whether a job is a strong match, moderate match, stretch role, or poor fit.
- Reduce manual tailoring time.

Secondary objectives:

- Fetch job descriptions from URLs.
- Search jobs from multiple sources.
- Rank multiple jobs by fit.
- Track application outcomes.

Future objectives:

- Learn from outcomes.
- Recommend better roles.
- Suggest skill-development plans.
- Support multi-user SaaS workflows.

Success metrics:

- Interview callback rate.
- Applications generated per user.
- Applications submitted per week.
- Average fit score of applied jobs.
- ATS keyword coverage.
- Resume approval/edit rate.
- Time saved per application.
- Offer/interview conversion rate.

## 5. Product Vision

Current vision: a single-user AI assistant that analyzes one job at a time and generates application materials.

One-year vision: a web-based Career Copilot where users create profiles, paste job URLs, receive ranked job recommendations, generate applications, and track outcomes.

Three-year vision: a SaaS platform with multi-source job aggregation, resume intelligence, interview analytics, skill-gap planning, and personalized career strategy.

Five-year vision: a full Career Intelligence Platform that helps users navigate the entire job market using AI agents, outcome analytics, and personalized labor-market insights.

## 6. Target Users

Students: need internships, fresher roles, resume guidance, and ATS-ready applications. Expected outcome: clearer profile positioning and more internship interviews.

Freshers: lack work experience and need project-based positioning. Expected outcome: better role selection and stronger project storytelling.

Job switchers: need to map existing experience to target roles. Expected outcome: faster identification of realistic opportunities.

Data scientists: need project/skill alignment with analytics, ML, Python, SQL, and model-building roles. Expected outcome: better technical keyword targeting.

Software engineers: need code, stack, system, and project alignment. Expected outcome: stronger engineering resumes for specific stacks.

AI engineers: need positioning around LLMs, ML, evaluation, prompting, pipelines, and AI systems. Expected outcome: clearer AI-focused applications.

Career changers: need transferability analysis and gap identification. Expected outcome: realistic transition roadmap.

## 7. End-to-End User Workflow

Candidate registration: the user creates an account or local profile.

Profile creation: the user adds education, skills, projects, certifications, experience, links, achievements, preferences, and target roles.

Job discovery: the system searches or receives job URLs.

Job aggregation: jobs from multiple sources are normalized into one structure.

Job filtering: jobs are filtered by location, role, experience level, salary, work mode, and eligibility.

Job ranking: jobs are scored using profile fit, required skills, tools, keywords, seniority, and user preferences.

Job selection: the user selects jobs worth applying to.

JD analysis: the analyzer extracts skills, tools, keywords, responsibilities, qualifications, and summary.

Profile matching: the matcher compares candidate evidence with job requirements.

Fit score: scoring produces transparent component scores.

Resume tailoring: resume generation selects relevant skills and projects.

Cover letter generation: the system creates a company/role-specific letter.

ATS optimization: quality checks keyword coverage, sections, length, and missing terms.

Application tracking: tracker stores status, scores, document paths, and timestamps.

Interview tracking: future versions store interview dates, rounds, feedback, and outcomes.

Analytics: insights show which roles and materials perform best.

Continuous improvement: the system learns from application outcomes and improves recommendations.

## 8. Current System Architecture

`profile.py`: stores the repository demo profile and validates session-created
tester profiles. Input: optional tester identity, skills, education,
experience, projects, and certifications. Output: a normalized profile
dictionary. The Streamlit UI keeps tester data in browser session state, so
testers can use their own evidence without modifying the repository profile.

`job_fetcher.py`: fetches one public job URL and extracts readable job description text. Input: URL. Output: company, title, JD text, source URL, extraction quality. Responsibility: public/static job page ingestion, early rejection of search/listing/career-hub pages, employer-name inference for common aggregator pages, and manual fallback when blocked.

`job_search.py`: accepts multiple public job URLs, fetches each job, analyzes each JD, calculates fit, ranks jobs, labels each job as Recommended/Review Carefully/Skip, saves a ranking report, records the ranking session in SQLite, and returns shortlisted jobs for document generation. Input: list of URLs and profile. Output: ranked jobs, persisted search run, and selected shortlisted jobs.

`job_preferences.py`: validates session-based discovery intent including target
roles, locations, experience levels, work modes, job types, preferred skills,
excluded keywords, and freshness. It also derives conservative role and skill
suggestions from verified profile evidence. Explicit exclusions can filter
supplied jobs without changing the evidence-based fit score.

`job_discovery.py`: defines the provider-neutral discovered-job contract,
deterministic freshness/preference filtering, deduplication, discovery
relevance, default curated connectors for public Greenhouse boards and Lever
posting sites, and a developer-only local sample provider.
Sample results are labeled and never represented as active vacancies. Live
Greenhouse jobs retain their public apply URL and source identity. Changing
confirmed preferences or the selected provider invalidates prior discovery
results so stale matches and rejection reasons are never presented as current.
The connector labels Greenhouse timestamps as updated dates, because the public
API does not guarantee an original posting timestamp, and caps each normalized
inbox at the top 50 matching records.
Lever records are sourced only from its published public Postings API. Because
that feed does not expose a reliable original publication date, the system
labels them as active with date unavailable and does not manufacture freshness.
The combined provider isolates individual source failures and runs shared
cross-source deduplication before filtering and ranking.
Normal discovery defaults to a small vetted catalog of India-relevant public
company feeds and supports environment-based overrides. The fictional sample
catalog is available only behind an explicit developer flag, preventing test
vacancies from being mistaken for live opportunities.

`analyzer.py`: analyzes raw job descriptions using AI. Input: job description text. Output: skills, tools, keywords, summary. Dependencies: the provider-neutral client in `llm_utils.py`.

`matcher.py`: compares job analysis against candidate profile. Input: job analysis and profile. Output: matches, gaps, score, recommendation. Dependencies: `scoring.py`, AI JSON utility. The deterministic score is the source of truth, and AI recommendation wording is sanitized to avoid conflicting percentages.

`scoring.py`: calculates deterministic fit score. Input: job analysis and profile. Output: match score, score components, matched/missing terms. Responsibility: transparent scoring with conservative alias matching for terms such as OOP, NLP, REST API, and SDLC.

Application-only familiarity is excluded from the evidence-based fit score.
Explicit experienced-hire requirements can apply a visible seniority penalty.

`resume.py`: generates structured tailored resume content and renders the
preferred LaTeX PDF. Input: job analysis, profile, match. Output: resume dict,
text file, PDF. If LaTeX is unavailable on the host, `application_service.py`
uses a pure-Python ReportLab fallback so saving and downloading can continue.

`cover_letter.py`: generates a cover letter and renders the preferred LaTeX
PDF. Input: job analysis, profile, match, company, role, tone. Output: letter
text and PDF. The same cloud-safe PDF fallback applies when LaTeX is missing.

`quality.py`: checks ATS quality. Input: resume content and job analysis. Output: keyword coverage, missing terms, quality issues, and a note explaining that low keyword coverage can come from noisy or generic job-page terms. Obvious job-title, branding, and generic company-language terms are excluded from the coverage calculation.

`tracker.py`: stores generated application drafts and job ranking sessions in SQLite. Input: company, role, scores, document paths, ranking results, and reports. Output: application ID, search run ID, application history, and ranking history. The Streamlit tracker presents applications and ranking experiments as separate views so ranked links are not mistaken for submitted applications.

`llm_utils.py`: shared AI request retry, JSON extraction, required-key
validation, and normalized provider-error classification. Permanent
authentication, permission, quota, and model errors fail immediately;
temporary service and timeout errors use bounded retries.

`utils.py`: shared formatting helpers for filenames, display URLs, phone numbers, and LaTeX escaping.

`application_service.py`: Reusable application workflow. Input: job details, tone, optional confirmed profile terms, and optional precomputed analysis/match. Output: structured application draft and saved application result.

`main.py`: CLI prompts and terminal presentation. It delegates generation and persistence to `application_service.py`.

## 9. Future System Architecture

Frontend: web app for profile editing, job search, ranking, resume preview, tracking, and analytics.

Backend: API service that coordinates profile, jobs, matching, document generation, tracking, and analytics.

AI layer: structured LLM calls, prompt versions, retry logic, evaluation, and guardrails.

Database layer: users, profiles, jobs, applications, documents, outcomes, analytics, and model logs.

Analytics layer: dashboards, conversion metrics, missing skills, best-performing roles, and interview predictors.

Job discovery layer: connectors for APIs, career pages, job boards, saved alerts, and URL fetching.

Application layer: resume generation, cover letters, ATS reports, tracking, and future form-fill assistance.

## 10. Data Flow Architecture

```text
Candidate Profile
↓
Job Discovery / Manual Job Input
↓
Job Fetching / JD Extraction
↓
Job Analysis
↓
Profile Matching
↓
Fit Scoring
↓
Resume + Cover Letter Generation
↓
ATS Quality Check
↓
Application Tracker
↓
Outcome Analytics
↓
Recommendation Improvement
```

The candidate profile acts as the source of truth. Job discovery provides raw jobs. Job fetching extracts the JD. Analyzer turns unstructured text into structured requirements. Matcher and scorer evaluate fit. Resume and cover letter modules generate materials. Quality checks validate ATS coverage. Tracker stores drafts and outcomes. Analytics converts history into insights.

## 11. Database Design

Recommended production database: PostgreSQL.

Core tables:

- `users`: id, name, email, auth_provider, created_at.
- `profiles`: id, user_id, headline, summary, location, target_roles, raw_profile_json, updated_at.
- `skills`: id, profile_id, name, category, proficiency, evidence_level.
- `projects`: id, profile_id, name, domain, tools_json, description, highlights_json, links_json.
- `jobs`: id, source, source_url, company, title, location, work_mode, raw_description, normalized_json, discovered_at.
- `job_requirements`: id, job_id, type, name, importance, confidence.
- `applications`: id, user_id, job_id, status, fit_score, ats_score, applied_at, created_at.
- `resumes`: id, application_id, version, content_json, file_url, created_at.
- `cover_letters`: id, application_id, version, content_text, file_url, created_at.
- `ats_reports`: id, application_id, keyword_coverage, missing_terms_json, issues_json.
- `interviews`: id, application_id, round_name, scheduled_at, status, notes.
- `analytics_events`: id, user_id, event_type, payload_json, created_at.

## 12. AI Architecture

Job Analysis Engine: extracts skills, tools, responsibilities, qualifications, ATS keywords, seniority, and summary.

Matching Engine: maps candidate evidence to job requirements and identifies gaps.

Fit Score Engine: combines deterministic scoring with AI explanation.

Resume Engine: generates structured resume sections using only profile evidence.

Cover Letter Engine: creates role-specific letters without inventing experience.

ATS Engine: checks keyword coverage, formatting, sections, and length.

Analytics Engine: evaluates application history and conversion patterns.

Future Learning Engine: recommends role strategy, resume improvements, and skill development based on outcomes.

## 13. Job Discovery Engine

Jobs can be gathered from manual JD paste, job URL fetching, job search APIs, company career pages, RSS feeds, email alerts, or curated job boards.

The engine normalizes provider results from company ATS feeds and broad licensed search APIs into a common schema: title, company, location, work mode, source URL, direct apply URL, raw JD, extracted requirements, and metadata.

The user remains in control of the handoff. **View Job** verifies the original listing, **Apply on Company Site** opens the provider's direct application page, and **Prepare Application** transfers only the selected job into the document workflow. No discovery result is submitted automatically.

Filtering should include role, seniority, location, remote/hybrid/on-site, salary, company type, required skills, and eligibility.

Ranking should consider fit score, skill coverage, missing critical skills, profile evidence, salary, user preference, freshness, and probability of interview.

Success probability should start rule-based and later become outcome-trained.

## 14. AI Agent Architecture

The best architecture is workflow automation first, multi-agent later.

Current stage: deterministic workflow with AI calls.

Future agents:

- Job Discovery Agent: finds relevant roles.
- Job Fetching Agent: extracts JD from URLs.
- Matching Agent: evaluates fit and gaps.
- Resume Agent: creates evidence-based resumes.
- Cover Letter Agent: writes personalized letters.
- QA Agent: checks ATS and factuality.
- Tracking Agent: manages application state.
- Analytics Agent: learns from outcomes.

The orchestrator should control the workflow and prevent agents from acting independently without user approval.

## 15. Feature Roadmap

Phase 1 - MVP: single-job engine. Features: profile, manual JD, analyzer, matcher, scoring, resume, cover letter, ATS check, tracker. Success: one complete application draft generated reliably. Status: complete for prototype use.

Phase 2 - URL Ingestion and Hardening: add `job_fetcher.py`, source URL tracking, JD validation, conservative scoring aliases, safe LaTeX escaping, AI retry fixes, tracker DB safety, and shared utilities. Success: user can paste a public job URL and run the pipeline, with fallback to manual paste. Status: complete for prototype use.

Phase 3 - Multi-Job Application Backend: add `job_search.py`, multi-job URL normalization, fit ranking, shortlisting, report saving, SQLite ranking history, reusable `application_service.py`, temporary profile-gap confirmation, factuality safeguards, and regression tests. Success: user can rank several supplied job URLs, shortlist opportunities, and generate reviewed application drafts. Status: complete for backend prototype use.

Phase 4 - Application Management UI: add a focused Streamlit interface for job input, fit review, profile-gap confirmation, document preview/download, tracker history, deterministic factuality checks, and legacy-document warnings. Success: one user can complete the current workflow without the terminal. Status: complete for local MVP use.

Phase 4.1 - Multi-Job UI: expose the existing multi-URL ranking and shortlisting backend through Streamlit with small batch limits, per-job errors, progress feedback, and approval before generation. Status: complete for local use.

Phase 4.2 - UI/UX Polish: improve visual hierarchy, guided workflow progress, fit and ATS presentation, document review, tracker scanning, empty states, and responsive behavior without changing backend logic. Status: complete for local use.

Phase 5 - SaaS Beta: add backend API, production database, login, saved profiles, document storage, and application dashboard. Success: multiple users can use the system safely.

Phase 6 - Public Launch and Career Intelligence: add subscriptions, outcome analytics, document versions, monitoring, recommendations, skill plans, and interview strategy. Success: measurable improvement in interview conversion.

## 16. Scalability Design

100 users: Streamlit or simple web app, SQLite/Postgres, direct AI calls.

1,000 users: FastAPI backend, PostgreSQL, object storage, background workers, auth, logging.

10,000 users: queue-based generation, Redis, rate limits, model gateway, cost tracking, analytics pipeline.

100,000 users: microservices or modular monolith, horizontal scaling, event bus, caching, distributed workers, advanced observability, enterprise security.

## 17. Security Design

Authentication: email/password, OAuth, or managed auth provider.

Authorization: users can only access their own profile, jobs, documents, and applications.

API security: rate limits, input validation, secrets management, request logging, abuse prevention.

Data privacy: resumes and profiles contain sensitive personal information and must be encrypted at rest and in transit.

Resume security: document URLs should be private, expiring, or permission-controlled.

Compliance: prepare for GDPR-style deletion, data export, consent, and retention policies.

## 18. Monetization Strategy

Free tier: limited profile, manual JD analysis, few applications per month.

Premium tier: unlimited applications, URL fetching, resume versions, ATS reports, tracking dashboard.

Subscription plans: student plan, professional plan, pro job-search plan.

Revenue opportunities: premium templates, interview prep, skill-gap plans, career coaching marketplace.

Enterprise opportunities: universities, bootcamps, placement cells, career services, training institutes.

## 19. Competitive Analysis

LinkedIn: strong job network, weak personalized application intelligence.

Naukri: strong Indian job marketplace, limited AI tailoring and analytics.

Indeed: broad job search, weak profile-to-job strategy.

Resume builders: good formatting, weak job ranking and tracking.

AI resume tools: generate documents, but often lack discovery, fit scoring, tracking, and outcome learning.

Career platforms: broad guidance, but not end-to-end AI application workflow.

Differentiator: PathPilot combines job discovery, fit ranking, tailored application generation, ATS checks, tracking, preparation, automation, and learning.

## 20. Risk Analysis

Technical risks: unreliable scraping, malformed AI outputs, PDF failures, high model costs.

Product risks: users may expect auto-apply too early, resumes may overfit keywords, low-fit jobs may still be applied to.

Market risks: crowded AI resume space, platform restrictions, user trust.

Business risks: monetization may be difficult if outcomes are not proven.

AI risks: hallucinated experience, biased recommendations, inconsistent scoring.

Mitigation: evidence mapping, user review, retry logic, transparent scoring, outcome tracking, conservative automation.

## 21. Implementation Roadmap

7-day plan: polish current pipeline, add `requirements.txt`, add README, test real JDs, improve scoring honesty. Status: complete.

30-day plan: complete the multi-job Streamlit workspace, preserve CLI compatibility, test real user workflows, and add basic outcome analytics only after the batch workflow is stable.

90-day plan: build web MVP, database, authentication, document storage, multiple applications, job ranking.

6-month plan: SaaS beta, analytics, subscriptions, saved searches, user feedback, stronger AI agents.

12-month plan: full career copilot with discovery, ranking, generation, tracking, insights, and outcome learning.

## 22. Project Status Assessment

Current progress: approximately 55% of the full Career Copilot vision.

Current stage: Product Refinement & Demo Readiness; the single-job Streamlit workflow, controlled multi-job ranking and shortlisting, guided application progress, improved document review, tracker management, SQLite history, reusable workflow services, deterministic factuality safeguards, legacy-document review warnings, and regression tests are available.

Strengths: clear modular structure, working URL/manual JD intake, AI analysis, matching, deterministic scoring, grounded evidence summaries, fact-safe resume projects, constrained cover letters, ATS checking, source tracking, application tracking, document preview/download, and SQLite ranking history.

Weaknesses: no broad job-board discovery, no production database, tester
profiles are session-only, SQLite and local document paths are not durable on
ephemeral cloud hosts, there is no authenticated multi-user isolation, semantic
matching remains limited, and there is no outcome analytics.

Missing components: broader search connectors, `insights.py`, production
database implementation, authentication, durable document storage, and
production deployment.

Next priority: validate the multi-job workspace against varied public job pages while keeping the CLI available.

## 23. Final CTO Review

Brutally honest assessment: PathPilot is a promising prototype with the right product direction, but it is not yet a full Career Intelligence Platform. It currently proves the discovery-to-application workflow, not the full long-term career-intelligence platform.

Top opportunities:

- Help users avoid wasting time on poor-fit jobs.
- Turn resume generation into a measurable interview-improvement system.
- Build a differentiated product around fit ranking and outcome learning.

Top risks:

- Becoming just another resume generator.
- Overpromising auto-apply.
- Weak matching leading to bad recommendations.
- Scraping limitations on major platforms.

Top 10 improvements:

1. Complete alpha stabilization and test the current workflow with session
   tester profiles.
2. Add small batch limits and per-job failure isolation.
3. Add user approval before batch document generation.
4. Add basic outcome analytics after batch UI stability.
5. Expand job discovery beyond supplied URLs later.
6. Improve semantic matching only after collecting outcome data.
7. Add PostgreSQL when multi-user SaaS work begins.
8. Add document version browsing.
9. Add production logging and cost tracking.
10. Add skill-gap learning recommendations.

Fastest path to the next milestone: finish alpha stabilization, validate the
session-profile workflow with trusted testers, then introduce persistent
multi-user profiles and tracker storage.

Fastest path to SaaS: add Streamlit/FastAPI UI, user profiles, PostgreSQL, document storage, and subscriptions.

Fastest path to revenue: target students/freshers with premium ATS reports, tailored applications, and interview tracking.

Fastest path to interview success: rank jobs by realistic fit, generate evidence-based resumes, and track outcomes.

Final recommendation: continue building in phases. Do not jump directly to
automatic applications, public SaaS, or autonomous agents. The local MVP and
controlled multi-job workspace are complete; finish alpha stabilization before
adding daily job discovery or persistent multi-user infrastructure.
