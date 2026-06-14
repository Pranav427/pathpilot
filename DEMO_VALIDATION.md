# ApplySmart AI Demo Validation

Use this checklist before a portfolio demonstration or milestone review.

## Automated Gate

Run:

```bash
python -m pytest -q
python -m compileall -q .
```

Both commands must complete without errors.

## Required Demo Scenarios

### 1. Entry-Level Match

- Use an individual public job-detail URL or a complete pasted description.
- Confirm the extracted company, title, and description.
- Verify that fit evidence comes from the permanent profile.
- Generate and review the resume, cover letter, and ATS report.
- Save the draft and confirm the tracker record and PDF previews.

### 2. Stretch Match

- Use a role with several realistic gaps.
- Confirm that the verdict and guidance explain those gaps.
- Select one or more genuine familiarity terms.
- Verify that the fit score does not increase after confirmation.
- Verify that familiarity is not presented as project or work experience.

### 3. Senior or Ineligible Role

- Use a role that explicitly requires multiple years of experience.
- Verify that a seniority adjustment appears in the score explanation.
- Confirm that the final verdict does not overstate candidate suitability.

## Failure Scenarios

- Empty or very short job description shows an actionable validation message.
- Search, listing, and career-homepage URLs are rejected before scoring.
- Blocked job pages explain how to use manual paste.
- Editing a job description after analysis blocks generation until it is
  analyzed again.
- Editing a failed job URL does not keep showing an error from the previous
  URL.
- Missing API configuration produces a safe setup message.
- A text or PDF save failure removes partial files and does not create a
  tracker record.
- Invalid or expired historical links do not crash the tracker.

## Output Review

- Candidate status is "graduate", not "student".
- Dates, education, certifications, links, and contact details are correct.
- Project metrics remain attached to the correct project.
- No confirmed familiarity is described as employment or production evidence.
- Resume summary is substantive and role-relevant.
- Cover letter is natural, specific, and within the expected length.
- ATS coverage is described as a keyword heuristic, not a hiring guarantee.

## Demo Approval

The project is demo-ready only when:

- automated tests pass;
- all three required scenarios complete successfully;
- no unsupported claim appears in either document;
- PDFs open and download correctly;
- the tracker clearly distinguishes drafts, submitted applications, and ranking history;
- known URL-fetching limitations are explained honestly.
