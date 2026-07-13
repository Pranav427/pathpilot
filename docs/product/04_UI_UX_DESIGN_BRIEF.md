# Document 04 - UI/UX Design Brief

## Product Feel

PathPilot should feel like a focused career workspace, not a marketing page and not a raw developer demo. The tone should be calm, trustworthy, and practical.

## Aesthetic Direction

Minimal, clean, professional, and work-focused. Similar spirit to Linear, Notion, Raycast, and modern SaaS dashboards, but lighter and friendlier for students and freshers.

## Visual Priorities

- Make the main workflow obvious: Profile -> Discover -> Review -> Prepare -> Track.
- Reduce long walls of text in job cards.
- Keep action buttons consistent and descriptive.
- Clearly separate recommended jobs from broad/manual-review jobs.
- Show source quality and experience confidence without overwhelming the user.
- Make warnings useful, not scary.

## Primary Color

Deep green for primary actions and trust states. Current Streamlit green is acceptable for alpha, but should be standardized later.

Suggested future palette:

- Primary: `#147A52`
- Primary hover: `#0F6845`
- Background: `#F7FAF9`
- Surface: `#FFFFFF`
- Border: `#DDE5E2`
- Text: `#172026`
- Muted text: `#66757F`
- Warning: `#9A6700`
- Error: `#B42318`

## Typography

Use clean sans-serif UI typography. Current Streamlit typography is acceptable for alpha; future SaaS should use Inter or Geist.

## Component Style

- Border radius: 8px or less.
- Buttons should use clear verbs: Discover, Prepare Application, View Job, Apply on Company Site, Shortlist, Ignore.
- Use compact cards for individual jobs.
- Avoid nested cards.
- Use metrics only when they help decision-making.
- Use expanders for secondary details such as rejection reasons.

## Job Discovery UX Requirements

The user should understand three things immediately:

1. What preferences are being used.
2. How many jobs were found and from which sources.
3. Which jobs are safest to review first.

Job cards should show:

- Score
- Title
- Company
- Location/work mode
- Source
- Experience confidence
- Posting date or active listing status
- View original job link
- Prepare Application action

## Recommended Job UX

The default view should be Recommended, not All Results. All Results can contain weaker roles and should be clearly framed as manual review.

Recommended jobs should require:

- Role relevance
- No obvious seniority conflict
- Entry-level, fresher, internship, junior, associate, graduate, or low-experience evidence when available
- Reasonable location/work-mode match

## Accessibility

- High contrast for text and buttons.
- Avoid relying only on color to communicate status.
- Keep font sizes readable.
- Ensure buttons have clear labels.
- Long job descriptions should be collapsed by default.

## Mobile Direction

Current alpha can prioritize desktop. Future SaaS should support mobile review with a bottom navigation or condensed sidebar, compact job cards, and sticky primary actions.
