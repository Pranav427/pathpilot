# PathPilot V2 — Comprehensive Engineering Handover Document for Claude

**Generated:** 2026-10-11  
**Repository:** `https://github.com/Pranav427/pathpilot.git`  
**Current Branch:** `main` (commit: `c892089`)  
**Working Directory:** `/Users/pranavobili/Desktop/PathPilot-1`  
**Test Suite Status:** 175 passed in ~8.5s (`pytest`)  
**Candidate Base Profile:** Pranav Obili (B.Tech Computer Science, 8.87 CGPA, Annamacharya Institute of Technology and Sciences, Springer research paper on real-time CNN gesture recognition).

---

## 1. Executive Summary & Purpose

**PathPilot V2** is an AI-powered, ATS-optimized Job Application & Tailoring Copilot specifically designed for freshers, students, and engineers. It automates:
1. **Job Description Extraction & Semantic Analysis**: Deconstructs requirements into core technical skills, required tools, domain concepts, and priority keywords.
2. **Deterministic Match Scoring**: Compares candidate profile facts against job demands without hallucination, scoring suitability based on verified technical evidence.
3. **Application Strategy Generation**: Determines positioning strategy, evidence requirements, company priorities, summary angles, and what topics to de-emphasize before writing application content.
4. **Tailored Resume & Cover Letter Generation**: Produces truthful, role-targeted resumes and 3-paragraph cover letters strictly grounded in candidate facts.
5. **Interactive Live Feedback Loop**: Lets candidates confirm familiarity with missing stack terms and provide academic/self-study context.
6. **Production PDF Compilation**: Generates clean, scannable PDFs (ReportLab fallback compiler) alongside LaTeX outputs.
7. **Application Tracker**: Tracks applications through job stages with full local SQLite and PostgreSQL persistence.

---

## 2. Codebase Architecture & File Structure

```
PathPilot-1/
├── app.py                      # Streamlit frontend UI (~4,700 lines)
├── application_service.py      # Core orchestration service for application lifecycle
├── resume.py                   # Resume strategy, fact selection manifest, generation & PDF compiler
├── cover_letter.py             # Cover letter generation, safety sanitation & PDF compiler
├── matcher.py                  # Deterministic profile-to-job matching & fit score calculations
├── analyzer.py                 # LLM job description extraction & requirement parsing
├── profile.py                  # Fact manifest store, default candidate profile & mutations
├── llm_utils.py                # LLM client abstractions (Anthropic Claude & Google Gemini), retry logic
├── quality.py                  # ATS scanning, pre-apply safety checks, document auditing
├── tracker_service.py          # Application tracking state transitions & metrics
├── job_store.py                # Job discovery store & search engine
├── storage.py                  # SQLite / PostgreSQL persistence abstraction
├── utils.py                    # LaTeX escaping, URL cleaning, candidate normalization
├── tests/                      # 175 unit and integration tests
│   ├── test_ai_contracts.py
│   ├── test_dynamic_grounding.py
│   ├── test_generation_safety.py
│   ├── test_job_discovery.py
│   ├── test_job_inputs.py
│   ├── test_job_preferences.py
│   ├── test_job_store.py
│   ├── test_multi_user.py
│   ├── test_postgresql.py
│   ├── test_profile_confirmation.py
│   ├── test_scoring_quality.py
│   ├── test_service_tracker.py
│   ├── test_session_profile.py
│   └── test_streamlit_app.py
```

---

## 3. Strict Architectural Contracts & Frozen Components

> [!IMPORTANT]
> **THE NARRATIVE GENERATION ENGINE IS STRICTLY FROZEN.**  
> The following four components have undergone rigorous multi-role benchmarking, edge-case evaluation, and recruiter validation. **Do NOT modify their prompts, prompt structure, or core parameters unless external regression tests specifically mandate it**:
> 1. **Resume Formatting** (`resume.py`: ReportLab fallback PDF generator, margins, two-column skills table).
> 2. **Professional Summary** (`resume.py`: 2-3 sentences, B.Tech + 8.87 CGPA + Springer research anchor, no first-person pronouns).
> 3. **Project Bullets** (`resume.py`: Formula: `[Action Verb] + [Specific Implementation] + [Technologies] + [Measurable Outcome]`, 20-35 words per bullet, metric-grounding safety logic).
> 4. **Cover Letter** (`cover_letter.py`: Exactly 3 paragraphs, max 220 words, technical hook opening, project deep dive, company alignment).

### Key Safety and Grounding Rules:
- **No Hallucinated Metrics**: Regex-based metric validation checks that numbers and percentages in bullets exist in the candidate's verified profile highlights. Violations fall back to default profile highlights.
- **Cross-Project Boundary Enforcement**: 15,000+ images and 93.91% accuracy belong ONLY to the face-authenticity project; they must never leak into other projects or NLP/drug review contexts.
- **SkillDzire Internship Boundary**: SkillDzire recorded foundational AI training only; the engine strictly blocks claiming OpenAI, Gemini, Claude API, LLM API, or prompt engineering there.
- **Session-Confirmed Familiarity Rules**: User-confirmed familiarity terms belong under `(familiarity)` in Skills. They can be referenced in narratives ONLY when qualified as `self-study` or `academic coursework`, never as commercial/production experience.

---

## 4. Work Accomplished in Recent Milestones

### Milestone 1: Visual Layout & Formatting (Approved & Frozen)
- Rebuilt the ReportLab fallback compiler to achieve parity with MVP LaTeX designs.
- Replaced loose bulleted skills with a compact, structured two-column grid.
- Enforced 0.5-inch margins, scannable contact header, clean section dividers, and strict 1-page visual density.

### Milestone 2: Professional Summary (Approved & Frozen)
- Validated across 10 distinct technical roles (AI Engineer, ML Engineer, Data Scientist, Backend Python, Backend Java, Data Analyst, Software Engineer, Full Stack, Computer Vision, MLOps).
- Established the Summary Diversity Score and verified graceful handling of academic credentials and publication records.

### Milestone 3: Project Bullets (Approved & Frozen)
- Resolved a bug in `sanitize_resume_facts` where LLM-tailored bullets were being discarded and replaced with static defaults.
- Implemented dynamic metric-grounding validation (regex pattern matching for unsupported numbers/percentages).
- Locked word count strictly between 20 and 35 words.

### Milestone 4: Cover Letter (Approved & Frozen)
- Enforced a 3-paragraph structure with an academic/technical hook opening, technical project narrative, and company alignment closing.
- Validated across 10 roles with 100% factual adherence.

### Milestone A: Application Strategy Engine Upgrades (Completed)
- Extended `generate_application_strategy` schema in `resume.py` to output `evidence_requirements` alongside `positioning_strategy`, `company_priorities`, `interviewer_takeaway`, `summary_focus`, `project_focus`, `skills_focus`, and `what_to_deemphasize`.
- Precomputed the strategy dictionary in `application_service.py` once per application and passed it downstream to both `generate_resume(..., strategy=strategy)` and `generate_cover_letter(..., strategy=strategy)` to ensure unified strategic alignment.

### Milestone B: Live Session Feedback Loop (Completed)
- Refined `unsupported_confirmed_claims` in `cover_letter.py` to permit academic/self-study qualifiers (`self-study`, `coursework`, `academic`, `university`).
- Updated prompt instructions to weave session-confirmed terms and details (e.g. university PostgreSQL project) into summaries and letters without claiming commercial experience.
- Added a strict project enforcement rule in `resume.py` so the engine always describes candidate projects (highlighting transferable engineering architecture) even when applying for divergent roles (e.g., CV project for a Java Backend role).

---

## 5. Next Steps on the Engineering Roadmap

The user approved prioritizing **Milestone C**, followed by **Milestone D**:

### 🎯 Next Milestone: Milestone C — Multi-User Architecture & Session Isolation
* **Problem:** In multi-tenant environments, temporary session variables, profile mutations, and application drafts must be strictly isolated per user/session to prevent cross-user state collisions.
* **Scope:**
  1. Audit `session_profile.py`, `storage.py`, and `application_service.py` for user/session ID propagation.
  2. Ensure all temporary profile overlays (`_application_confirmed_terms`, `_application_confirmed_details`) are scoped strictly to the active session ID.
  3. Validate multi-user test coverage in `tests/test_multi_user.py` and `tests/test_session_profile.py`.
  4. Ensure PostgreSQL and SQLite stores enforce tenant partition boundaries.

### 🎯 Subsequent Milestone: Milestone D — Streamlit UI Refinements & Polish
* **Scope:** Polish navigation flow, responsive layouts, clear visual status indicators, and streamlined multi-step application workflow in `app.py`.

---

## 6. How to Run & Verify

```bash
# 1. Activate virtual environment
source /Users/pranavobili/Desktop/PathPilot-1/.venv/bin/activate

# 2. Run the complete test suite (all 175 tests must pass)
python3 -m pytest

# 3. Environment Configuration (.env)
# LLM_PROVIDER can be set to 'anthropic' or 'gemini'
# Required keys: ANTHROPIC_API_KEY and/or GEMINI_API_KEY
```

---

## 7. Crucial Guidelines for Claude

1. **Maintain Test Integrity**: Always run `python3 -m pytest` after making changes. Never leave tests failing.
2. **Preserve Frozen Narrative Components**: Do not alter prompts in `resume.py` or `cover_letter.py` for summary, bullets, or cover letter without explicit user instruction and batch evaluation.
3. **Follow the Evidence-Based Methodology**:
   - Implement change.
   - Run unit tests (`pytest`).
   - Run batch evaluation / generate real outputs.
   - Critically inspect before vs. after.
   - Commit cleanly to git.
