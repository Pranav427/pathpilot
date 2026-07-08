"""Streamlit interface for the PathPilot application workflow."""

import json
import hashlib
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(path: str = ".env") -> None:
        """Small fallback for environments missing python-dotenv."""
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

load_dotenv()

JOB_STORE_REFRESH_TTL_MINUTES = 30
DEFAULT_DISCOVERY_INVENTORY_WINDOW_DAYS = 90
DISCOVERY_QUALITY_POLICY_VERSION = "2026-07-04-top-recommended-v3"
RECOMMENDED_DISCOVERY_LIMIT = 20
RECOMMENDED_DISCOVERY_MIN_SCORE = 75
PRODUCT_NAME = "PathPilot"
PRODUCT_TAGLINE = "Navigate your career with intelligence."
PRODUCT_DESCRIPTION = "The intelligent platform for modern careers."

from application_service import (
    MIN_JD_WORDS,
    generate_application_draft,
    get_missing_profile_terms,
    prepare_match,
    save_application_draft,
    validate_application_identity,
)
from job_fetcher import (
    FetchedJob,
    clean_company,
    fetch_job_from_url,
    is_likely_job_listing,
)
from job_discovery import (
    AdzunaJobProvider,
    AshbyJobProvider,
    CombinedJobProvider,
    EarlyCareerWebJobProvider,
    GreenhouseJobProvider,
    JobDiscoveryError,
    JoobleJobProvider,
    LeverJobProvider,
    LocalSampleJobProvider,
    SerpApiGoogleJobsProvider,
    TARGET_DISCOVERY_RESULTS,
    clear_discovery_provider_caches,
    discover_jobs,
    early_career_sources_enabled,
    experience_confidence,
    is_direct_company_source,
    is_broad_market_source,
    jooble_is_configured,
    parse_ashby_boards,
    parse_greenhouse_boards,
    parse_lever_sites,
    serpapi_is_configured,
)
from job_search import (
    action_label,
    extract_urls_from_text,
    rank_jobs_from_urls,
    save_ranked_jobs_report,
)
from job_preferences import (
    EXPERIENCE_LEVELS,
    JOB_TYPES,
    WORK_MODES,
    build_job_preferences,
    suggest_job_preferences,
)
from job_store import (
    StoredJobProvider,
    ingest_provider_jobs,
    job_store_stats,
)
from llm_utils import LLMServiceError
from profile import build_session_profile, copy_profile, get_profile
from quality import audit_application_documents
from resume import resume_to_text
from tracker import (
    VALID_STATUSES,
    get_stats,
    list_applications,
    list_job_search_runs,
    list_ranked_jobs_for_run,
    record_job_search_run,
    update_application_status,
)
from utils import clean_filename

MAX_BATCH_URLS = 10
LOGGER = logging.getLogger(__name__)

st.set_page_config(
    page_title=PRODUCT_NAME,
    page_icon="PP",
    layout="wide",
    initial_sidebar_state="auto",
)


def user_facing_error(exc: Exception, action: str) -> str:
    """Returns useful UI feedback without exposing provider internals."""
    message = str(exc).strip()
    lower = message.lower()

    if isinstance(exc, LLMServiceError):
        messages = {
            "authentication": (
                "The AI API key was rejected. The app owner must update the "
                "deployment secret before analysis can continue."
            ),
            "permission": (
                "The AI account does not have access to the configured model. "
                "The app owner must review the provider permissions."
            ),
            "model_unavailable": (
                "The configured AI model is unavailable. The app owner must "
                "select a model enabled for this API account."
            ),
            "account_limit": (
                "The AI account has reached its usage limit. Please try again "
                "after the app owner restores API capacity."
            ),
            "temporary_unavailable": (
                "The AI service is temporarily unavailable. Please try again "
                "in a few minutes."
            ),
            "timeout": (
                f"{action} timed out. Check the connection and try again."
            ),
        }
        return messages.get(
            exc.code,
            f"{action} could not be completed. Please try again.",
        )

    if "api key is not configured" in lower or "authentication method" in lower:
        return (
            "AI authentication is not configured. Add the API key for your "
            f"selected LLM_PROVIDER to .env and restart {PRODUCT_NAME}."
        )
    if any(
        term in lower
        for term in (
            "credit balance",
            "rate limit",
            "quota exceeded",
            "resource_exhausted",
            "status code: 429",
        )
    ):
        return (
            "The AI service is temporarily unavailable because of account "
            "limits. Check the API account and try again."
        )
    if "timed out" in lower or "timeout" in lower:
        return f"{action} timed out. Check the connection and try again."
    if isinstance(exc, (ValueError, RuntimeError)) and not message.startswith(
        ("AI request failed", "Job analysis failed", "Profile match failed")
    ):
        return message
    return f"{action} could not be completed. Please try again."


def show_action_error(exc: Exception, action: str) -> None:
    """Logs diagnostic details and displays a safe, actionable message."""
    LOGGER.exception("%s failed", action, exc_info=exc)
    st.error(user_facing_error(exc, action))


def document_download_name(
    profile: dict,
    company_name: str,
    document_type: str,
) -> str:
    """Builds a short professional filename for a generated PDF."""
    candidate = clean_filename(profile.get("name", "candidate"))
    company = clean_filename(company_name) or "company"
    kind = "resume" if document_type == "resume" else "cover_letter"
    return f"{candidate}_{kind}_{company}.pdf"


def description_fingerprint(job_description: str) -> str:
    """Returns a stable fingerprint used to detect stale fit analysis."""
    normalized = " ".join(str(job_description).split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def apply_styles():
    st.markdown(
        """
        <style>
        :root {
            --ink: #18212a;
            --muted: #66727d;
            --line: #dfe4e8;
            --surface: #ffffff;
            --soft: #f4f6f7;
            --green: #126447;
            --green-soft: #e9f4ef;
            --amber: #986b14;
            --amber-soft: #fff6dd;
            --red: #a13c35;
            --red-soft: #fff0ee;
            --blue: #245b8a;
            --blue-soft: #edf4fa;
        }

        .stApp {
            background: #f6f8f9;
            color: var(--ink);
        }

        [data-testid="stSidebar"] {
            background: #f0f3f4;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {
            font-size: 1.2rem;
            margin-bottom: 0;
        }

        [data-testid="stSidebar"] [role="radiogroup"] {
            gap: 0.25rem;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            padding: 0.45rem 0.55rem;
            border-radius: 4px;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.75rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 {
            color: var(--ink);
            letter-spacing: 0;
        }

        h1 {
            font-size: 1.85rem;
            margin-bottom: 0.1rem;
        }

        h2 {
            font-size: 1.25rem;
            margin-top: 1.4rem;
        }

        h3 {
            font-size: 1.02rem;
        }

        .app-subtitle {
            color: var(--muted);
            margin: 0.1rem 0 1.4rem 0;
            max-width: 760px;
            line-height: 1.55;
        }

        .section-label {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            margin: 1.25rem 0 0.4rem;
        }

        .workflow {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            border: 1px solid var(--line);
            background: var(--surface);
            margin: 0 0 1.5rem;
        }

        .workflow-step {
            padding: 0.7rem 0.8rem;
            border-right: 1px solid var(--line);
            color: var(--muted);
            font-size: 0.8rem;
            font-weight: 650;
        }

        .workflow-step:last-child {
            border-right: none;
        }

        .workflow-step.active {
            color: var(--green);
            background: var(--green-soft);
        }

        .workflow-number {
            display: block;
            font-size: 0.7rem;
            color: var(--muted);
            margin-bottom: 0.12rem;
        }

        .metric-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            border: 1px solid var(--line);
            background: var(--surface);
            margin: 0.75rem 0 1.1rem;
            border-radius: 6px;
            overflow: hidden;
        }

        .metric-cell {
            padding: 1rem 1.1rem;
            border-right: 1px solid var(--line);
            min-width: 0;
        }

        .metric-cell:last-child {
            border-right: none;
        }

        .metric-value {
            font-size: 1.45rem;
            font-weight: 700;
            color: var(--ink);
            line-height: 1.25;
            overflow-wrap: anywhere;
        }

        .metric-name {
            color: var(--muted);
            font-size: 0.82rem;
        }

        .notice {
            padding: 0.8rem 0.95rem;
            border-left: 4px solid var(--blue);
            background: var(--blue-soft);
            margin: 0.8rem 0 1rem;
            color: #29475f;
            line-height: 1.5;
        }

        .notice.warning {
            border-left-color: var(--amber);
            background: var(--amber-soft);
        }

        .notice.danger {
            border-left-color: var(--red);
            background: var(--red-soft);
        }

        .detail-panel {
            border: 1px solid var(--line);
            background: var(--surface);
            padding: 0.95rem 1rem;
            border-radius: 6px;
            min-height: 100%;
        }

        .detail-panel h4 {
            margin: 0 0 0.6rem;
            font-size: 0.92rem;
        }

        .detail-list {
            color: var(--ink);
            font-size: 0.9rem;
            line-height: 1.65;
        }

        .status-pill {
            display: inline-block;
            padding: 0.22rem 0.48rem;
            border: 1px solid #c9d3d9;
            background: var(--soft);
            color: #43515d;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }

        .status-pill.positive {
            border-color: #b6d8c9;
            background: var(--green-soft);
            color: var(--green);
        }

        .status-pill.warning {
            border-color: #e1c77f;
            background: var(--amber-soft);
            color: var(--amber);
        }

        .document-shell {
            border: 1px solid var(--line);
            background: var(--surface);
            padding: 0.8rem;
            border-radius: 6px;
        }

        .empty-state {
            border: 1px dashed #cbd3d8;
            background: var(--surface);
            color: var(--muted);
            padding: 1.4rem;
            text-align: center;
            border-radius: 6px;
        }

        div[data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            padding: 0.85rem 0.95rem;
            border-radius: 6px;
            min-height: 108px;
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--line);
            border-radius: 6px;
            background: var(--surface);
            overflow: hidden;
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: 4px;
            min-height: 2.45rem;
            font-weight: 650;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .stTextInput input, .stTextArea textarea,
        .stSelectbox [data-baseweb="select"] > div {
            border-radius: 4px;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--line);
        }

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 0.2rem;
            border-bottom: 1px solid var(--line);
        }

        [data-testid="stTabs"] [data-baseweb="tab"] {
            padding-left: 0.9rem;
            padding-right: 0.9rem;
        }

        @media (max-width: 720px) {
            .block-container {
                padding: 1rem 0.75rem 2.5rem;
            }

            .metric-strip {
                grid-template-columns: 1fr;
            }

            .metric-cell {
                border-right: none;
                border-bottom: 1px solid var(--line);
            }

            .metric-cell:last-child {
                border-bottom: none;
            }

            .workflow {
                display: flex;
                overflow-x: auto;
                scroll-snap-type: x proximity;
            }

            .workflow-step {
                flex: 0 0 112px;
                min-height: 58px;
                border-bottom: none;
                scroll-snap-align: start;
            }

            h1 {
                font-size: 1.55rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str):
    """Renders a consistent page title and supporting description."""
    st.title(title)
    st.markdown(
        f'<p class="app-subtitle">{escape(subtitle)}</p>',
        unsafe_allow_html=True,
    )


def render_section_label(label: str):
    st.markdown(
        f'<div class="section-label">{escape(label)}</div>',
        unsafe_allow_html=True,
    )


def render_workflow(active_step: int):
    steps = ["Add job", "Review fit", "Confirm", "Generate", "Save"]
    cells = []
    for index, step in enumerate(steps, 1):
        active = " active" if index <= active_step else ""
        cells.append(
            f'<div class="workflow-step{active}">'
            f'<span class="workflow-number">STEP {index}</span>'
            f"{step}</div>"
        )
    st.markdown(
        '<div class="workflow">' + "".join(cells) + "</div>",
        unsafe_allow_html=True,
    )


def render_list_panel(title: str, items: list, tone: str = ""):
    panel_items = items or ["None identified"]
    list_html = "<br>".join(
        f"&#8226;&nbsp; {escape(str(item))}" for item in panel_items
    )
    pill = (
        f'<span class="status-pill {tone}">{len(items)} items</span>'
        if items
        else '<span class="status-pill">No items</span>'
    )
    st.markdown(
        f'<div class="detail-panel">{pill}<h4>{escape(title)}</h4>'
        f'<div class="detail-list">{list_html}</div></div>',
        unsafe_allow_html=True,
    )


def init_state():
    defaults = {
        "job_analysis": None,
        "base_profile": None,
        "base_match": None,
        "draft": None,
        "saved": None,
        "source_url": "",
        "application_apply_url": "",
        "company_name": "",
        "job_title": "",
        "job_description": "",
        "analyzed_description_fingerprint": "",
        "fetch_error": "",
        "fetch_error_url": "",
        "input_method": "Paste description",
        "job_form_revision": 0,
        "ranked_jobs": [],
        "ranking_failures": [],
        "ranking_urls": [],
        "ranking_run_id": None,
        "shortlist": [],
        "history_load_error": "",
        "profile_mode": "Demo profile",
        "session_profile": copy_profile(get_profile()),
        "profile_saved": False,
        "job_preferences": None,
        "preferences_saved": False,
        "discovered_jobs": [],
        "discovery_rejections": [],
        "job_inbox_status": {},
        "discovery_preferences_snapshot": None,
        "discovery_source": "All live sources",
        "pending_discovered_job": None,
        "loaded_job_notice": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_workflow():
    for key in (
        "job_analysis",
        "base_profile",
        "base_match",
        "draft",
        "saved",
        "source_url",
        "application_apply_url",
        "company_name",
        "job_title",
        "job_description",
        "analyzed_description_fingerprint",
        "fetch_error",
        "fetch_error_url",
        "input_method",
        "loaded_job_notice",
    ):
        if key in {"job_analysis", "base_profile", "base_match", "draft", "saved"}:
            st.session_state[key] = None
        elif key == "input_method":
            st.session_state[key] = "Paste description"
        else:
            st.session_state[key] = ""
    st.session_state.job_form_revision += 1


def invalidate_application_results():
    """Clears analysis and generated artifacts when the job input changes."""
    for key in ("job_analysis", "base_profile", "base_match", "draft", "saved"):
        st.session_state[key] = None
    st.session_state.analyzed_description_fingerprint = ""


def reset_ranking():
    """Clears only the multi-job ranking workspace."""
    st.session_state.ranked_jobs = []
    st.session_state.ranking_failures = []
    st.session_state.ranking_urls = []
    st.session_state.ranking_run_id = None
    st.session_state.shortlist = []


def reset_discovery():
    """Clears profile-dependent discovery preferences and inbox results."""
    clear_discovery_provider_caches()
    st.session_state.job_preferences = None
    st.session_state.preferences_saved = False
    st.session_state.discovered_jobs = []
    st.session_state.discovery_rejections = []
    st.session_state.job_inbox_status = {}
    st.session_state.discovery_preferences_snapshot = None
    st.session_state.discovery_source = "All live sources"


def clear_discovery_results():
    """Invalidates inbox results without removing saved preferences."""
    clear_discovery_provider_caches()
    st.session_state.discovered_jobs = []
    st.session_state.discovery_rejections = []
    st.session_state.job_inbox_status = {}
    st.session_state.discovery_preferences_snapshot = None


def discovery_inventory_window_days(preferences) -> int:
    """Returns how far back the local source inventory should be ranked."""
    configured = os.getenv("APPLYSMART_JOB_INVENTORY_WINDOW_DAYS", "").strip()
    try:
        window = (
            int(configured)
            if configured
            else DEFAULT_DISCOVERY_INVENTORY_WINDOW_DAYS
        )
    except ValueError:
        window = DEFAULT_DISCOVERY_INVENTORY_WINDOW_DAYS
    if preferences is not None:
        window = max(window, int(preferences.maximum_job_age_days))
    return max(1, min(window, 365))


def is_recommended_discovery_job(job) -> bool:
    """Returns true for high-signal jobs shown in the default inbox view."""
    if experience_confidence(job) not in {
        "Verified selected level",
        "Likely entry-level",
    }:
        return False
    return job.relevance_score >= RECOMMENDED_DISCOVERY_MIN_SCORE


def active_profile() -> dict:
    """Returns an isolated copy of the profile selected for this session."""
    if st.session_state.get("profile_mode") == "Tester profile":
        return copy_profile(st.session_state.session_profile)
    return copy_profile(get_profile())


def activate_demo_profile():
    """Restores the repository profile and clears profile-dependent results."""
    st.session_state.profile_mode = "Demo profile"
    st.session_state.session_profile = copy_profile(get_profile())
    st.session_state.profile_saved = False
    invalidate_application_results()
    reset_ranking()
    reset_discovery()


def activate_tester_profile(profile: dict):
    """Uses a validated tester profile only for the current browser session."""
    st.session_state.profile_mode = "Tester profile"
    st.session_state.session_profile = copy_profile(profile)
    st.session_state.profile_saved = True
    invalidate_application_results()
    reset_ranking()
    reset_discovery()


def load_ranked_job(job):
    """Loads a ranked job into the existing single-job review workflow."""
    fetched = job.fetched_job
    st.session_state.job_analysis = job.job_analysis
    st.session_state.base_profile = active_profile()
    st.session_state.base_match = job.match
    st.session_state.draft = None
    st.session_state.saved = None
    st.session_state.source_url = fetched.source_url
    st.session_state.application_apply_url = fetched.source_url
    st.session_state.company_name = fetched.company_name
    st.session_state.job_title = fetched.job_title
    st.session_state.job_description = fetched.job_description
    st.session_state.analyzed_description_fingerprint = description_fingerprint(
        fetched.job_description
    )
    st.session_state.fetch_error = ""
    st.session_state.fetch_error_url = ""
    st.session_state.input_method = "Job URL"
    st.session_state.navigation = "Application"


def queue_discovered_job(job):
    """Queues a discovery selection for the next Streamlit render cycle."""
    st.session_state.pending_discovered_job = job
    st.session_state.job_inbox_status[job.provider_job_id] = "Prepared"


def apply_pending_discovered_job():
    """Applies queued navigation before the sidebar widget is instantiated."""
    job = st.session_state.pop("pending_discovered_job", None)
    if job is None:
        return
    reset_workflow()
    st.session_state.company_name = job.company_name
    st.session_state.job_title = job.job_title
    st.session_state.job_description = job.job_description
    st.session_state.source_url = job.source_url
    st.session_state.application_apply_url = job.apply_url or job.source_url
    st.session_state.input_method = "Paste description"
    st.session_state.loaded_job_notice = (
        f"Loaded from Job Discovery: {job.company_name} · {job.job_title}"
    )
    st.session_state.navigation = "Application"


def preferred_tracker_apply_url(
    current_source_url: str,
    stored_source_url: str,
    direct_apply_url: str,
) -> str:
    """Prefers direct apply links unless the visible source URL was edited."""
    current_url = str(current_source_url or "").strip()
    stored_source_url = str(stored_source_url or "").strip()
    direct_apply_url = str(direct_apply_url or "").strip()
    if direct_apply_url and (not current_url or current_url == stored_source_url):
        return direct_apply_url
    return current_url or direct_apply_url


def tracker_apply_url(current_source_url: str) -> str:
    """Returns the best user-facing apply link for the tracker record."""
    return preferred_tracker_apply_url(
        current_source_url,
        st.session_state.get("source_url", ""),
        st.session_state.get("application_apply_url", ""),
    )


def update_inbox_status(job_id: str, status: str):
    """Updates a discovery result within the current browser session."""
    st.session_state.job_inbox_status[job_id] = status


def load_historical_job(job: dict):
    """Refreshes a historical URL and loads it into the application workspace."""
    try:
        fetched = fetch_job_from_url(job["source_url"])
        analysis = json.loads(job.get("job_analysis_json") or "{}")
        profile = active_profile()
        _, _, match = prepare_match(
            fetched.job_description,
            job_analysis=analysis,
            profile=profile,
        )
        historical_job = type(
            "HistoricalRankedJob",
            (),
            {
                "fetched_job": FetchedJob(
                    company_name=clean_company(job["company_name"]),
                    job_title=job["job_title"],
                    job_description=fetched.job_description,
                    source_url=job["source_url"],
                    extraction_quality=fetched.extraction_quality,
                ),
                "job_analysis": analysis,
                "match": match,
            },
        )()
        st.session_state.history_load_error = ""
        load_ranked_job(historical_job)
    except Exception as exc:
        LOGGER.exception("Historical job reload failed", exc_info=exc)
        st.session_state.history_load_error = (
            "Could not reopen this historical job. The page may have expired, "
            "changed, or become blocked."
        )


def format_history_time(value: str) -> str:
    """Converts stored UTC timestamps into a readable India-local time."""
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local = parsed.astimezone(ZoneInfo("Asia/Kolkata"))
        return local.strftime("%d %b %Y, %I:%M %p IST")
    except (TypeError, ValueError):
        return str(value).replace("T", " ")


def verdict_tone(verdict: str) -> str:
    if verdict == "Strong Match":
        return "positive"
    if verdict in {"Stretch Match", "Not Recommended"}:
        return "warning"
    return ""


def verdict_color(verdict: str) -> str:
    return {
        "Strong Match": "#176b4d",
        "Moderate Match": "#245b8a",
        "Stretch Match": "#986b14",
        "Not Recommended": "#a13c35",
    }.get(verdict, "#5f6b76")


def render_profile():
    profile = active_profile()
    render_page_header(
        "Candidate Profile",
        "Choose the evidence used for matching and document generation.",
    )

    mode_col, status_col = st.columns([1, 2])
    with mode_col:
        profile_mode = st.selectbox(
            "Active profile",
            ["Demo profile", "Tester profile"],
            index=0 if st.session_state.profile_mode == "Demo profile" else 1,
            help=(
                "Tester profiles remain only in this browser session and do "
                "not modify profile.py."
            ),
        )
    with status_col:
        if profile_mode == "Demo profile":
            st.info("Using the repository demo profile.")
            if st.session_state.profile_mode != "Demo profile":
                activate_demo_profile()
                st.rerun()
        elif not st.session_state.profile_saved:
            st.warning("Complete and save the tester profile below.")
        else:
            st.success("Using a session-only tester profile.")

    if profile_mode == "Tester profile":
        current = (
            st.session_state.session_profile
            if st.session_state.profile_mode == "Tester profile"
            else {}
        )
        current_skills = current.get("skills", {})
        with st.form("tester_profile_form"):
            st.subheader("Tester profile")
            st.caption(
                "Personal data stays in this browser session. Use only facts "
                "you can explain and verify."
            )
            identity_left, identity_right = st.columns(2)
            with identity_left:
                name = st.text_input("Full name *", value=current.get("name", ""))
                email = st.text_input("Email", value=current.get("email", ""))
                phone = st.text_input("Phone", value=current.get("phone", ""))
                location = st.text_input(
                    "Location",
                    value=current.get("location", ""),
                )
            with identity_right:
                linkedin = st.text_input(
                    "LinkedIn",
                    value=current.get("linkedin", ""),
                )
                github = st.text_input(
                    "GitHub",
                    value=current.get("github", ""),
                )
                portfolio = st.text_input(
                    "Portfolio",
                    value=current.get("portfolio", ""),
                )
            objective = st.text_area(
                "Professional summary *",
                value=current.get("objective", ""),
                height=120,
                placeholder=(
                    "Summarize your education, verified strengths, projects, "
                    "experience, and target roles."
                ),
            )

            st.markdown("**Skills**")
            skill_columns = st.columns(2)
            skill_fields = {}
            skill_categories = [
                "Programming Languages",
                "Artificial Intelligence & Machine Learning",
                "Deep Learning & Computer Vision",
                "Software Fundamentals",
                "Data Analysis",
                "Libraries & Frameworks",
                "Databases",
                "Tools & Platforms",
                "Soft Skills",
            ]
            for index, category in enumerate(skill_categories):
                with skill_columns[index % 2]:
                    skill_fields[category] = st.text_area(
                        category,
                        value=", ".join(current_skills.get(category, [])),
                        height=90,
                        placeholder="Comma-separated verified skills",
                    )

            st.markdown("**Evidence**")
            education_text = st.text_area(
                "Education *",
                value="\n".join(
                    " | ".join(
                        [
                            item.get("degree", ""),
                            item.get("institution", ""),
                            item.get("year", ""),
                            item.get("grade", ""),
                        ]
                    )
                    for item in current.get("education", [])
                ),
                placeholder=(
                    "One per line: Degree | Institution | Year | Grade"
                ),
            )
            experience_text = st.text_area(
                "Experience",
                value="\n".join(
                    " | ".join(
                        [
                            item.get("title", ""),
                            item.get("company", ""),
                            item.get("duration", ""),
                            ", ".join(item.get("highlights", [])),
                        ]
                    )
                    for item in current.get("experience", [])
                ),
                placeholder=(
                    "One per line: Role | Company | Duration | "
                    "Achievement one, Achievement two"
                ),
            )
            projects_text = st.text_area(
                "Projects",
                value="\n".join(
                    " | ".join(
                        [
                            item.get("name", ""),
                            item.get("domain", ""),
                            ", ".join(item.get("tools", [])),
                            item.get("description", ""),
                        ]
                    )
                    for item in current.get("projects", [])
                ),
                placeholder=(
                    "One per line: Project | Domain | Tool one, Tool two | "
                    "What you built and measured"
                ),
            )
            certifications_text = st.text_area(
                "Certifications",
                value="\n".join(current.get("certifications", [])),
                placeholder="One verified certification per line",
            )
            save_profile = st.form_submit_button(
                "Use this tester profile",
                type="primary",
                use_container_width=True,
            )
            if save_profile:
                try:
                    tester_profile = build_session_profile(
                        name=name,
                        email=email,
                        phone=phone,
                        location=location,
                        linkedin=linkedin,
                        github=github,
                        portfolio=portfolio,
                        objective=objective,
                        skills=skill_fields,
                        education_text=education_text,
                        experience_text=experience_text,
                        projects_text=projects_text,
                        certifications_text=certifications_text,
                    )
                    activate_tester_profile(tester_profile)
                    st.success(
                        "Tester profile activated for this browser session."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        if st.session_state.profile_mode != "Tester profile":
            return
        profile = active_profile()

    identity, links = st.columns([1.4, 1])
    with identity:
        st.subheader(profile["name"])
        st.caption("Candidate identity")
        for label, value in (
            ("Location", profile.get("location")),
            ("Email", profile.get("email")),
            ("Phone", profile.get("phone")),
        ):
            if value:
                st.write(f"{label}: {value}")
    with links:
        render_section_label("Professional links")
        available_links = [
            (label, profile.get(key))
            for label, key in (
                ("LinkedIn", "linkedin"),
                ("GitHub", "github"),
                ("Portfolio", "portfolio"),
            )
            if profile.get(key)
        ]
        if available_links:
            for label, url in available_links:
                st.link_button(label, url, use_container_width=True)
        else:
            st.caption("No professional links provided.")

    render_section_label("Profile evidence")
    skills_tab, experience_tab, education_tab, certification_tab = st.tabs(
        ["Skills", "Experience", "Education", "Certifications"]
    )
    with skills_tab:
        for category, skills in profile["skills"].items():
            with st.expander(category):
                st.write(", ".join(skills))

    with experience_tab:
        for item in profile.get("experience", []):
            st.markdown(f"**{item['title']} · {item['company']}**")
            st.caption(item["duration"])
            for highlight in item.get("highlights", [])[:3]:
                st.write(f"- {highlight}")

    with education_tab:
        for item in profile.get("education", []):
            st.markdown(f"**{item['degree']}**")
            st.write(item["institution"])
            st.caption(f"{item['year']} · {item['grade']}")

    with certification_tab:
        for certification in profile.get("certifications", []):
            st.write(f"- {certification}")


def render_job_discovery():
    """Collects validated search intent before source discovery is enabled."""
    render_page_header(
        "Job Discovery",
        f"Set the roles and constraints {PRODUCT_NAME} should use for job discovery.",
    )
    preferences = st.session_state.job_preferences
    profile_suggestions = suggest_job_preferences(active_profile())
    current = preferences.to_dict() if preferences else profile_suggestions

    with st.form("job_preferences_form"):
        st.subheader("Search preferences")
        st.caption(
            "Roles and skills are suggested from your active verified profile. "
            "Review them, add your preferred locations, and confirm before "
            "discovery."
        )
        role_col, location_col = st.columns(2)
        with role_col:
            target_roles = st.text_area(
                "Target roles *",
                value=", ".join(current.get("target_roles", [])),
                height=100,
                placeholder=(
                    "Data Scientist, AI/ML Engineer, AI Engineer, "
                    "Machine Learning Engineer"
                ),
            )
        with location_col:
            locations = st.text_area(
                "Locations *",
                value=", ".join(current.get("locations", [])),
                height=100,
                placeholder="Bengaluru, Hyderabad, Remote, India",
            )

        level_col, mode_col, type_col = st.columns(3)
        with level_col:
            experience_levels = st.multiselect(
                "Experience level *",
                EXPERIENCE_LEVELS,
                default=current.get(
                    "experience_levels",
                    ["Internship", "Fresher / Entry level"],
                ),
            )
        with mode_col:
            work_modes = st.multiselect(
                "Work mode *",
                WORK_MODES,
                default=current.get("work_modes", list(WORK_MODES)),
            )
        with type_col:
            job_types = st.multiselect(
                "Job type *",
                JOB_TYPES,
                default=current.get(
                    "job_types",
                    ["Full-time", "Internship"],
                ),
            )

        skills_col, exclude_col = st.columns(2)
        with skills_col:
            preferred_skills = st.text_area(
                "Preferred skills",
                value=", ".join(current.get("preferred_skills", [])),
                height=100,
                placeholder="Python, Machine Learning, NLP, Deep Learning",
                help=(
                    "These guide discovery relevance. They do not become "
                    "candidate skills or inflate fit scores."
                ),
            )
        with exclude_col:
            excluded_keywords = st.text_area(
                "Excluded roles or keywords",
                value=", ".join(current.get("excluded_keywords", [])),
                height=100,
                placeholder="Senior, Manager, Sales, 5+ years",
            )

        maximum_job_age_days = st.slider(
            "Maximum job age",
            min_value=1,
            max_value=60,
            value=current.get("maximum_job_age_days", 14),
            format="%d days",
        )
        save_preferences = st.form_submit_button(
            "Save job preferences",
            type="primary",
            use_container_width=True,
        )

    if save_preferences:
        try:
            updated_preferences = build_job_preferences(
                target_roles=target_roles,
                locations=locations,
                experience_levels=experience_levels,
                work_modes=work_modes,
                job_types=job_types,
                preferred_skills=preferred_skills,
                excluded_keywords=excluded_keywords,
                maximum_job_age_days=maximum_job_age_days,
            )
            if updated_preferences != st.session_state.job_preferences:
                clear_discovery_results()
            st.session_state.job_preferences = updated_preferences
            st.session_state.preferences_saved = True
            st.success(
                "Job preferences saved. Previous discovery results were "
                "cleared because they may no longer match."
            )
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    if not st.session_state.preferences_saved:
        st.markdown(
            '<div class="empty-state">Save your preferences to prepare the '
            "job-discovery pipeline.</div>",
            unsafe_allow_html=True,
        )
        return

    preferences = st.session_state.job_preferences
    render_section_label("Active discovery profile")
    st.markdown(
        f"**{', '.join(preferences.target_roles)}**  \n"
        f"{', '.join(preferences.locations)} · "
        f"{', '.join(preferences.experience_levels)}"
    )
    st.caption(
        f"{', '.join(preferences.work_modes)} · "
        f"{', '.join(preferences.job_types)} · "
        f"Posted within {preferences.maximum_job_age_days} days"
    )

    if preferences.excluded_keywords:
        st.caption(
            "Excluded keywords: "
            + ", ".join(preferences.excluded_keywords)
        )
    try:
        configured_boards = parse_greenhouse_boards()
        greenhouse_configuration_error = ""
    except ValueError as exc:
        configured_boards = {}
        greenhouse_configuration_error = str(exc)
    try:
        configured_lever_sites = parse_lever_sites()
        lever_configuration_error = ""
    except ValueError as exc:
        configured_lever_sites = {}
        lever_configuration_error = str(exc)
    try:
        configured_ashby_boards = parse_ashby_boards()
        ashby_configuration_error = ""
    except ValueError as exc:
        configured_ashby_boards = {}
        ashby_configuration_error = str(exc)
    adzuna_app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    adzuna_app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    adzuna_country = os.getenv("ADZUNA_COUNTRY", "in").strip().lower()
    adzuna_configured = bool(adzuna_app_id and adzuna_app_key)
    jooble_api_key = os.getenv("JOOBLE_API_KEY", "").strip()
    jooble_country = os.getenv("JOOBLE_COUNTRY", "in").strip().lower()
    jooble_configured = jooble_is_configured()
    serpapi_api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    serpapi_configured = serpapi_is_configured()
    early_career_sources_configured = early_career_sources_enabled()
    sample_jobs_enabled = os.getenv(
        "APPLYSMART_ENABLE_SAMPLE_JOBS",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    source_options = []
    if configured_boards:
        source_options.append("Live Greenhouse boards")
    if configured_lever_sites:
        source_options.append("Live Lever sites")
    if configured_ashby_boards:
        source_options.append("Live Ashby boards")
    if early_career_sources_configured:
        source_options.append("Early-career web sources")
    if adzuna_configured:
        source_options.append("Broad Adzuna search")
    if jooble_configured:
        source_options.append("Broad Jooble search")
    if serpapi_configured:
        source_options.append("Google Jobs search")
    live_source_count = sum(
        bool(value)
        for value in (
            configured_boards,
            configured_lever_sites,
            configured_ashby_boards,
            early_career_sources_configured,
            adzuna_configured,
            jooble_configured,
            serpapi_configured,
        )
    )
    if live_source_count > 1:
        source_options.insert(0, "All live sources")
    if sample_jobs_enabled:
        source_options.append("Sample catalog")
    if not source_options:
        st.error(
            "No live discovery sources are configured. Enable curated live "
            "sources, configure GREENHOUSE_BOARDS / LEVER_SITES / "
            "ASHBY_BOARDS, or add Adzuna/Jooble credentials."
        )
        return
    preferred_source = (
        "All live sources"
        if "All live sources" in source_options
        else source_options[0]
    )
    source = st.segmented_control(
        "Discovery source",
        source_options,
        default=(
            st.session_state.discovery_source
            if st.session_state.discovery_source in source_options
            else preferred_source
        ),
        key="discovery_source_control",
    )
    if source != st.session_state.discovery_source:
        clear_discovery_results()
        st.session_state.discovery_source = source

    if source == "Live Greenhouse boards":
        st.success(
            f"Live discovery is configured for {len(configured_boards)} "
            "public Greenhouse board(s). Jobs are filtered using your saved "
            "preferences before appearing in the inbox."
        )
        provider = GreenhouseJobProvider(configured_boards)
        discover_label = "Discover live jobs now"
        spinner_label = "Loading configured Greenhouse job boards..."
    elif source == "Live Lever sites":
        st.success(
            f"Live discovery is configured for {len(configured_lever_sites)} "
            "public Lever site(s). Lever confirms these listings are public "
            "and active, but does not expose their original posting dates."
        )
        provider = LeverJobProvider(configured_lever_sites)
        discover_label = "Discover live jobs now"
        spinner_label = "Loading configured Lever posting sites..."
    elif source == "Live Ashby boards":
        st.success(
            f"Live discovery is configured for {len(configured_ashby_boards)} "
            "public Ashby board(s). These are active company career listings "
            "filtered through your saved preferences."
        )
        provider = AshbyJobProvider(configured_ashby_boards)
        discover_label = "Discover live jobs now"
        spinner_label = "Loading configured Ashby job boards..."
    elif source == "Early-career web sources":
        st.success(
            "Early-career web sources are enabled through no-key public job "
            f"APIs. {PRODUCT_NAME} searches remote and public tech feeds, then "
            "applies your saved role, skill, experience, location, and "
            "freshness filters before ranking."
        )
        provider = EarlyCareerWebJobProvider()
        discover_label = "Search early-career web sources"
        spinner_label = "Searching early-career web job sources..."
    elif source == "Broad Adzuna search":
        st.success(
            f"Broad search is enabled through Adzuna. {PRODUCT_NAME} searches each "
            "saved target role, then applies the same experience, location, "
            "freshness, and title filters used for company feeds."
        )
        provider = AdzunaJobProvider(
            adzuna_app_id,
            adzuna_app_key,
            country=adzuna_country,
        )
        discover_label = "Search broad job market"
        spinner_label = "Searching Adzuna for target roles..."
    elif source == "Broad Jooble search":
        st.success(
            f"Broad search is enabled through Jooble. {PRODUCT_NAME} searches "
            "bounded role and location combinations, then applies the same "
            "title, experience, and preference filters used for every source."
        )
        provider = JoobleJobProvider(
            jooble_api_key,
            country=jooble_country,
        )
        discover_label = "Search broad job market"
        spinner_label = "Searching Jooble for target roles..."
    elif source == "Google Jobs search":
        st.success(
            f"Google Jobs search is enabled through SerpAPI. {PRODUCT_NAME} "
            "queries role and location combinations, then normalizes postings "
            "from major platforms and company pages into the same ranking "
            "pipeline."
        )
        provider = SerpApiGoogleJobsProvider(serpapi_api_key)
        discover_label = "Search Google Jobs"
        spinner_label = "Searching Google Jobs for target roles..."
    elif source == "All live sources":
        st.success(
            "Live discovery will combine every configured provider, "
            "deduplicate the results, and isolate source failures."
        )
        live_providers = []
        if configured_boards:
            live_providers.append(GreenhouseJobProvider(configured_boards))
        if configured_lever_sites:
            live_providers.append(LeverJobProvider(configured_lever_sites))
        if configured_ashby_boards:
            live_providers.append(AshbyJobProvider(configured_ashby_boards))
        if early_career_sources_configured:
            live_providers.append(EarlyCareerWebJobProvider())
        if adzuna_configured:
            live_providers.append(
                AdzunaJobProvider(
                    adzuna_app_id,
                    adzuna_app_key,
                    country=adzuna_country,
                )
            )
        if jooble_configured:
            live_providers.append(
                JoobleJobProvider(
                    jooble_api_key,
                    country=jooble_country,
                )
            )
        if serpapi_configured:
            live_providers.append(SerpApiGoogleJobsProvider(serpapi_api_key))
        provider = CombinedJobProvider(live_providers)
        discover_label = "Discover from all live sources"
        spinner_label = "Loading configured live job sources..."
    else:  # Developer-only sample catalog.
        st.info(
            "Developer sample mode is enabled. These vacancies validate the "
            "workflow and are not active external job postings."
        )
        if greenhouse_configuration_error:
            st.warning(greenhouse_configuration_error)
        if lever_configuration_error:
            st.warning(lever_configuration_error)
        if ashby_configuration_error:
            st.warning(ashby_configuration_error)
        provider = LocalSampleJobProvider()
        discover_label = "Discover sample jobs now"
        spinner_label = "Filtering the local sample catalog..."

    if (
        source in {"Broad Adzuna search", "All live sources"}
        and adzuna_configured
    ):
        st.caption(
            "Broad-market listings are provided by "
            "[Adzuna](https://www.adzuna.co.in/)."
        )
    if (
        source in {"Broad Jooble search", "All live sources"}
        and jooble_configured
    ):
        st.caption(
            "Additional broad-market listings are provided by "
            "[Jooble](https://jooble.org/)."
        )
    if (
        source in {"Early-career web sources", "All live sources"}
        and early_career_sources_configured
    ):
        st.caption(
            "Early-career web coverage includes public no-key feeds from "
            "[Remotive](https://remotive.com/) and "
            "[Arbeitnow](https://www.arbeitnow.com/), plus tagged remote-tech "
            "listings from [RemoteOK](https://remoteok.com/)."
        )
    if (
        source in {"Google Jobs search", "All live sources"}
        and serpapi_configured
    ):
        st.caption(
            "Google Jobs results are provided through "
            "[SerpAPI](https://serpapi.com/google-jobs-api) and may include "
            "listings from LinkedIn, Naukri, Indeed, and company career pages "
            "when Google exposes them for the query."
        )
    if source == "All live sources" and not serpapi_configured:
        st.info(
            "High-coverage Google Jobs search is not configured yet. Add "
            "SERPAPI_API_KEY to enable discovery from Google Jobs results, "
            "including listings Google exposes from LinkedIn, Naukri, Indeed, "
            "and company career pages."
        )
    stats = job_store_stats()
    source_database_fresh = False
    if stats["total"]:
        latest = stats.get("latest") or "not available"
        st.caption(
            f"Local job database: {stats['total']} normalized listing(s). "
            f"Last refresh: {latest} UTC."
        )
        try:
            latest_refresh = datetime.fromisoformat(stats["latest"])
            age_seconds = (datetime.utcnow() - latest_refresh).total_seconds()
            source_database_fresh = (
                age_seconds < JOB_STORE_REFRESH_TTL_MINUTES * 60
            )
        except (TypeError, ValueError):
            source_database_fresh = False
    refresh_sources = False
    if source != "Sample catalog":
        refresh_sources = st.checkbox(
            "Refresh source database before search",
            value=not source_database_fresh,
            help=(
                "Turn this on when you want to call the live providers again. "
                "Leave it off to rank the local normalized job database "
                "quickly."
            ),
        )

    discover_col, clear_col = st.columns([2, 1])
    with discover_col:
        discover_clicked = st.button(
            discover_label,
            type="primary",
            use_container_width=True,
        )
    with clear_col:
        if st.button(
            "Clear job inbox",
            use_container_width=True,
        ):
            clear_discovery_results()
            st.rerun()

    if discover_clicked:
        try:
            with st.spinner(spinner_label):
                if source == "Sample catalog":
                    stored_count = 0
                    jobs, rejections = discover_jobs(preferences, provider)
                else:
                    stored_count = None
                    if refresh_sources or not stats["total"]:
                        stored_count = ingest_provider_jobs(
                            provider,
                            preferences,
                        )
                    jobs, rejections = discover_jobs(
                        preferences,
                        StoredJobProvider(
                            seen_within_days=discovery_inventory_window_days(
                                preferences
                            )
                        ),
                    )
        except (JobDiscoveryError, ValueError) as exc:
            st.error(str(exc))
            return
        st.session_state.discovered_jobs = jobs
        st.session_state.discovery_rejections = rejections
        st.session_state.discovery_preferences_snapshot = {
            "preferences": preferences.to_dict(),
            "source": source,
            "quality_policy": DISCOVERY_QUALITY_POLICY_VERSION,
        }
        st.session_state.job_inbox_status = {
            job.provider_job_id: "New" for job in jobs
        }
        provider_failures = list(getattr(provider, "failures", []))
        if provider_failures:
            affected_sources = sorted(
                {
                    failure.split(":", 1)[0].split(" / ", 1)[0].strip()
                    for failure in provider_failures
                    if str(failure).strip()
                }
            )
            rate_limited_count = sum(
                "429" in failure or "rate" in failure.lower()
                for failure in provider_failures
            )
            unreachable_count = sum(
                "could not be reached" in failure.lower()
                for failure in provider_failures
            )
            details = []
            if rate_limited_count:
                details.append(f"{rate_limited_count} rate-limited request(s)")
            if unreachable_count:
                details.append(f"{unreachable_count} unreachable feed(s)")
            other_count = max(
                0,
                len(provider_failures) - rate_limited_count - unreachable_count,
            )
            if other_count:
                details.append(f"{other_count} other provider issue(s)")
            st.warning(
                f"Some live sources could not be refreshed. {PRODUCT_NAME} ranked "
                "the available local job database instead"
                + (f" ({', '.join(details)})." if details else ".")
            )
            if affected_sources:
                visible_sources = ", ".join(affected_sources[:4])
                overflow = len(affected_sources) - 4
                st.caption(
                    "Affected source/query groups: "
                    + visible_sources
                    + (f", +{overflow} more" if overflow > 0 else "")
                    + "."
                )
            with st.expander(
                f"Source refresh details ({len(provider_failures)})",
                expanded=False,
            ):
                for failure in provider_failures:
                    st.caption(failure)
        if source != "Sample catalog" and stored_count is not None:
            st.caption(
                f"Refreshed {stored_count} normalized listing(s) into the "
                "local job database before ranking this search."
            )
        elif source != "Sample catalog":
            st.caption(
                "Ranked from the local normalized job database. Enable "
                "refresh above when you want to fetch new provider data."
            )
        if jobs:
            message = (
                f"Found {len(jobs)} matching job(s). "
                f"Filtered {len(rejections)} result(s)."
            )
            if len(jobs) >= TARGET_DISCOVERY_RESULTS:
                st.success(message)
            else:
                st.warning(
                    message
                    + f" The current sources did not reach the "
                    f"{TARGET_DISCOVERY_RESULTS}-job coverage target."
                )
        else:
            st.warning(
                "No jobs matched these preferences. Broaden one or "
                "more filters and try again."
            )

    results_are_current = (
        st.session_state.discovery_preferences_snapshot
        == {
            "preferences": preferences.to_dict(),
            "source": source,
            "quality_policy": DISCOVERY_QUALITY_POLICY_VERSION,
        }
    )
    jobs = st.session_state.discovered_jobs if results_are_current else []
    rejections = (
        st.session_state.discovery_rejections if results_are_current else []
    )
    if rejections:
        source_rejection_counts = Counter(
            (
                rejection.split(" · ", 1)[0]
                if " · " in rejection
                else "Unknown source"
            )
            for rejection in rejections
        )
        reason_counts = Counter(
            (
                rejection.split(": ", 1)[1]
                if ": " in rejection
                else rejection
            )
            for rejection in rejections
        )
        with st.expander(f"Why {len(rejections)} jobs were filtered"):
            st.caption(
                f"{PRODUCT_NAME} removes jobs that conflict with your saved "
                "preferences before showing the inbox."
            )
            for reason, count in reason_counts.most_common(6):
                st.write(f"**{count}** · {reason}")
            if source_rejection_counts:
                st.caption(
                    "Filtered by source: "
                    + " · ".join(
                        f"{source} {count}"
                        for source, count in source_rejection_counts.most_common()
                    )
                )
            if len(reason_counts) > 6:
                st.caption(
                    f"{len(reason_counts) - 6} less common reason(s) are not "
                    "shown."
                )
    if not jobs:
        return

    render_section_label("Job inbox")
    verified_count = sum(
        experience_confidence(job) == "Verified selected level" for job in jobs
    )
    likely_count = sum(
        experience_confidence(job) == "Likely entry-level" for job in jobs
    )
    unstated_count = sum(
        experience_confidence(job) == "Experience not stated" for job in jobs
    )
    recommended_jobs = [
        job for job in jobs if is_recommended_discovery_job(job)
    ]
    recommended_count = min(
        len(recommended_jobs),
        RECOMMENDED_DISCOVERY_LIMIT,
    )
    source_counts = Counter(job.source.split(" · ", 1)[0] for job in jobs)
    direct_source_count = sum(
        1 for job in jobs if is_direct_company_source(job.source)
    )
    broad_source_count = sum(
        1 for job in jobs if is_broad_market_source(job.source)
    )
    title_col, recommended_col, count_col, verified_col = st.columns(
        [2, 1, 1, 1]
    )
    with title_col:
        st.subheader("Discovered opportunities")
    with recommended_col:
        st.metric("Recommended", recommended_count)
    with count_col:
        st.metric("Total found", len(jobs))
    with verified_col:
        st.metric("Verified level", verified_count)
    st.caption(
        "Source coverage: "
        + " · ".join(
            f"{provider} {count}"
            for provider, count in source_counts.most_common()
        )
    )
    if direct_source_count < min(TARGET_DISCOVERY_RESULTS, len(jobs)):
        st.info(
            f"{direct_source_count} result(s) came directly from company "
            "career feeds. The remaining jobs are broad-market listings and "
            "should be opened before preparing an application."
        )
    if len(jobs) >= TARGET_DISCOVERY_RESULTS:
        selected_locations = [
            location.lower() for location in preferences.locations
        ]
        expanded_count = sum(
            not any(
                selected in job.location.lower()
                or job.location.lower() in selected
                for selected in selected_locations
            )
            for job in jobs
        )
        if expanded_count:
            st.caption(
                f"{expanded_count} result(s) are India-market coverage "
                "expansions because exact-location matches were below the "
                f"{TARGET_DISCOVERY_RESULTS}-job target."
            )
    if len(source_counts) == 1 and "Adzuna" in source_counts:
        st.warning(
            "No configured company career feed produced a matching role for "
            "this search. These results come from Adzuna; open the original "
            "listing before preparing an application."
        )
    st.caption(
        "Open the original listing to verify details. Prepare Application "
        "loads only the selected job into your private application workspace; "
        "it never submits an application automatically."
    )
    status_filter = st.segmented_control(
        "Inbox view",
        ["All", "New", "Shortlisted", "Prepared", "Ignored"],
        default="All",
        key="discovery_status_filter",
    )
    experience_options = ["Recommended", "Verified only", "All results"]
    experience_view = st.segmented_control(
        "Experience confidence",
        experience_options,
        default="Recommended",
        key="discovery_experience_filter_v4",
        help=(
            "Recommended shows verified and likely early-career roles. "
            "Verified only shows roles that explicitly mention internship, "
            "fresher, graduate, or 0-2 years. All results includes broad "
            "search matches whose experience level must be checked manually."
        ),
    )
    st.caption(
        f"{recommended_count} top recommended result(s). "
        f"{broad_source_count} "
        "broad-market result(s) need source verification before applying."
    )
    filtered_jobs = [
        job
        for job in jobs
        if (
            status_filter == "All"
            or st.session_state.job_inbox_status.get(
                job.provider_job_id,
                "New",
            )
            == status_filter
        )
        and (
            experience_view == "All results"
            or (
                experience_view == "Recommended"
                and is_recommended_discovery_job(job)
            )
            or (
                experience_view == "Verified only"
                and experience_confidence(job) == "Verified selected level"
            )
        )
    ]
    visible_jobs = (
        filtered_jobs[:RECOMMENDED_DISCOVERY_LIMIT]
        if experience_view == "Recommended"
        else filtered_jobs
    )
    if not visible_jobs:
        st.markdown(
            '<div class="empty-state">No jobs match this inbox view.</div>',
            unsafe_allow_html=True,
        )
        return

    for job in visible_jobs:
        status = st.session_state.job_inbox_status.get(
            job.provider_job_id,
            "New",
        )
        with st.expander(
            f"{job.relevance_score}/100 · {job.job_title} · {job.company_name}",
            expanded=False,
        ):
            st.markdown(
                f'<span class="status-pill">{escape(status)}</span>',
                unsafe_allow_html=True,
            )
            date_text = (
                f"{job.date_label} "
                f"{job.posted_date.strftime('%d %b %Y')}"
                if job.freshness_verified
                else f"{job.date_label} · date unavailable"
            )
            metadata = [
                f"Relevance {job.relevance_score}/100",
                experience_confidence(job),
                date_text,
                job.work_mode,
                job.location,
                job.job_type,
                job.source,
            ]
            st.caption(
                " · ".join(item for item in metadata if str(item).strip())
            )
            description = " ".join(job.job_description.split())
            preview = (
                description
                if len(description) <= 700
                else description[:697].rsplit(" ", 1)[0] + "..."
            )
            st.write(preview)
            if len(description) > len(preview):
                st.caption(
                    "Preview shortened for readability. View the original "
                    "listing for complete responsibilities and requirements."
                )

            prepare_col, view_col, apply_col = st.columns([2, 1, 1])
            with prepare_col:
                st.button(
                    "Prepare Application",
                    key=f"review_discovered_{job.provider_job_id}",
                    type="primary",
                    use_container_width=True,
                    on_click=queue_discovered_job,
                    args=(job,),
                )
            with view_col:
                if job.source_url:
                    st.link_button(
                        "View Job",
                        job.source_url,
                        use_container_width=True,
                    )
            with apply_col:
                if job.apply_url:
                    st.link_button(
                        "Apply on Company Site",
                        job.apply_url,
                        use_container_width=True,
                    )

            shortlist_col, ignore_col, _ = st.columns([1, 1, 2])
            with shortlist_col:
                st.button(
                    "Shortlist",
                    key=f"shortlist_discovered_{job.provider_job_id}",
                    use_container_width=True,
                    on_click=update_inbox_status,
                    args=(job.provider_job_id, "Shortlisted"),
                )
            with ignore_col:
                st.button(
                    "Ignore",
                    key=f"ignore_discovered_{job.provider_job_id}",
                    use_container_width=True,
                    on_click=update_inbox_status,
                    args=(job.provider_job_id, "Ignored"),
                )


def render_fit(match: dict):
    score = int(match.get("match_score", 0))
    verdict = match.get("fit_verdict_label", "Fit scored")
    recommendation = match.get("application_recommendation", "")
    color = verdict_color(verdict)
    st.markdown(
        f"""
        <div class="metric-strip">
            <div class="metric-cell">
                <div class="metric-value">{score}/100</div>
                <div class="metric-name">Fit score</div>
            </div>
            <div class="metric-cell">
                <div class="metric-value" style="color:{color}">{verdict}</div>
                <div class="metric-name">Fit verdict</div>
            </div>
            <div class="metric-cell">
                <div class="metric-value">{len(match.get("missing_skills", [])) + len(match.get("missing_tools", []))}</div>
                <div class="metric-name">Open gaps</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if recommendation:
        st.caption(f"Suggested action: {recommendation}")
    guidance = match.get("fit_guidance", "")
    if guidance:
        notice_class = "warning" if score < 65 else ""
        st.markdown(
            f'<div class="notice {notice_class}">{guidance}</div>',
            unsafe_allow_html=True,
        )
    confirmed_terms = list(match.get("user_confirmed_terms", []))[:8]
    if confirmed_terms:
        st.caption(
            "Fit remains based on permanent profile evidence. "
            f"{len(confirmed_terms)} application-only familiarity term(s) "
            "may improve wording and ATS coverage, but do not raise the fit score."
        )
    if match.get("seniority_penalty"):
        st.caption(
            f"Seniority adjustment: -{match['seniority_penalty']} points. "
            + match.get("seniority_reason", "")
        )
    components = match.get("score_components", {})
    if components:
        with st.expander("How this fit score was calculated"):
            labels = {
                "skills": "Skill coverage",
                "tools": "Tool coverage",
                "ats_keywords": "Role-keyword coverage",
                "project_evidence_bonus": "Project evidence bonus",
                "education_bonus": "Education evidence bonus",
                "seniority_penalty": "Seniority adjustment",
            }
            for key, label in labels.items():
                if key in components:
                    value = components[key]
                    suffix = (
                        " points"
                        if "bonus" in key or "penalty" in key
                        else "/100"
                    )
                    st.write(f"**{label}:** {value}{suffix}")


def render_analysis(analysis: dict, match: dict):
    render_fit(match)
    tab_summary, tab_requirements, tab_match = st.tabs(
        ["Summary", "Requirements", "Match details"]
    )
    with tab_summary:
        st.write(analysis.get("summary", ""))
        points = match.get("strongest_points", [])
        if points:
            st.markdown("**Evidence to highlight**")
            for point in points:
                st.write(f"- {point}")
    with tab_requirements:
        col1, col2, col3 = st.columns(3)
        with col1:
            render_list_panel("Required skills", analysis.get("skills", []))
        with col2:
            render_list_panel("Tools and platforms", analysis.get("tools", []))
        with col3:
            render_list_panel("ATS keywords", analysis.get("keywords", []))
    with tab_match:
        col1, col2 = st.columns(2)
        with col1:
            matched = (
                match.get("matched_skills", [])
                + match.get("matched_tools", [])
            )
            render_list_panel("Matched evidence", matched, "positive")
        with col2:
            missing = (
                match.get("missing_skills", [])
                + match.get("missing_tools", [])
            )
            render_list_panel("Missing or unverified", missing)


def render_workspace():
    render_page_header(
        "Application Workspace",
        "Build one evidence-based application from job input to reviewed documents.",
    )
    if st.session_state.loaded_job_notice:
        st.success(
            st.session_state.loaded_job_notice
            + ". Review the details below, then select Analyze fit."
        )
    active_step = 1
    if st.session_state.base_match:
        active_step = 2
    if st.session_state.draft:
        active_step = 4
    if st.session_state.saved:
        active_step = 5
    render_workflow(active_step)

    render_section_label("Job details")
    form_revision = st.session_state.job_form_revision
    input_method = st.segmented_control(
        "Job input",
        ["Paste description", "Job URL"],
        key="input_method",
    )

    company_col, role_col = st.columns(2)
    with company_col:
        company = st.text_input(
            "Company *",
            value=st.session_state.company_name,
            placeholder="Example: Magnit",
            key=f"company_input_{form_revision}",
        )
    with role_col:
        role = st.text_input(
            "Job title *",
            value=st.session_state.job_title,
            placeholder="Example: Associate Software Engineer",
            key=f"job_title_input_{form_revision}",
        )

    source_url = ""
    job_description = ""
    if input_method == "Job URL":
        source_url_key = f"source_url_input_{form_revision}"
        source_url = st.text_input(
            "Public job URL",
            value=st.session_state.source_url,
            placeholder="https://company.com/careers/job",
            key=source_url_key,
        )
        fetch_col, _ = st.columns([1, 3])
        with fetch_col:
            if st.button("Fetch job", use_container_width=True):
                entered_url = st.session_state.get(
                    source_url_key,
                    source_url,
                )
                try:
                    with st.spinner("Fetching the public job page..."):
                        fetched = fetch_job_from_url(entered_url)
                    invalidate_application_results()
                    st.session_state.company_name = fetched.company_name
                    st.session_state.job_title = fetched.job_title
                    st.session_state.job_description = fetched.job_description
                    st.session_state.source_url = fetched.source_url
                    st.session_state.application_apply_url = fetched.source_url
                    st.session_state.fetch_error = ""
                    st.session_state.fetch_error_url = ""
                    st.session_state.job_form_revision += 1
                    st.success("Job description extracted. Review it before analysis.")
                    st.rerun()
                except Exception as exc:
                    LOGGER.exception("Job fetching failed", exc_info=exc)
                    invalidate_application_results()
                    st.session_state.source_url = str(entered_url).strip()
                    st.session_state.application_apply_url = str(entered_url).strip()
                    st.session_state.fetch_error = user_facing_error(
                        exc,
                        "Job fetching",
                    )
                    st.session_state.fetch_error_url = str(entered_url).strip()
        current_url = str(source_url).strip()
        fetch_error_matches_url = (
            st.session_state.fetch_error
            and st.session_state.fetch_error_url == current_url
        )
        if fetch_error_matches_url:
            st.markdown(
                '<div class="notice warning"><strong>Automatic extraction did '
                "not work.</strong> The job URL is preserved. Copy the complete "
                "job description from the posting and paste it below, then "
                "continue with Analyze fit.</div>",
                unsafe_allow_html=True,
            )
            st.caption(st.session_state.fetch_error)
        job_description = st.text_area(
            (
                "Paste job description manually"
                if fetch_error_matches_url
                else "Extracted job description"
            ),
            value=st.session_state.job_description,
            height=260,
            placeholder="If extraction fails, paste the full description here.",
            key=f"url_description_input_{form_revision}",
        )
    else:
        source_url = st.text_input(
            "Job posting URL (optional)",
            value=st.session_state.source_url,
            placeholder="https://company.com/careers/job",
            key=f"manual_source_url_input_{form_revision}",
            help="Saved with the tracker so you can return to the original job.",
        )
        job_description = st.text_area(
            "Job description",
            value=st.session_state.job_description,
            height=300,
            placeholder="Paste the complete responsibilities, requirements, and qualifications.",
            key=f"pasted_description_input_{form_revision}",
        )

    action_col, reset_col = st.columns([1, 1])
    description_word_count = len(str(job_description).split())
    description_ready = description_word_count >= MIN_JD_WORDS
    with action_col:
        analyze_clicked = st.button(
            "Analyze fit",
            type="primary",
            use_container_width=True,
            disabled=not description_ready,
        )
    with reset_col:
        st.button(
            "Reset",
            use_container_width=True,
            on_click=reset_workflow,
        )

    if job_description and not description_ready:
        st.caption(
            f"Add the complete job description before analysis "
            f"({description_word_count}/{MIN_JD_WORDS} words)."
        )
    elif description_ready:
        st.caption(
            f"Job description ready for analysis · {description_word_count} words"
        )

    if analyze_clicked:
        try:
            with st.spinner("Analyzing the role and calculating fit..."):
                analysis, profile, match = prepare_match(
                    job_description,
                    profile=active_profile(),
                )
            st.session_state.job_analysis = analysis
            st.session_state.base_profile = profile
            st.session_state.base_match = match
            st.session_state.company_name = company
            st.session_state.job_title = role
            st.session_state.job_description = job_description
            st.session_state.source_url = source_url
            if not st.session_state.application_apply_url:
                st.session_state.application_apply_url = source_url
            st.session_state.analyzed_description_fingerprint = (
                description_fingerprint(job_description)
            )
            st.session_state.draft = None
            st.session_state.saved = None
        except Exception as exc:
            show_action_error(exc, "Job analysis")

    if not st.session_state.base_match:
        st.markdown(
            '<div class="empty-state">Add a complete job description and select '
            '<strong>Analyze fit</strong> to begin.</div>',
            unsafe_allow_html=True,
        )
        return

    analysis_is_current = (
        description_fingerprint(job_description)
        == st.session_state.analyzed_description_fingerprint
    )
    if not analysis_is_current:
        st.markdown(
            '<div class="notice warning"><strong>The job description changed '
            "after the last analysis.</strong> Select Analyze fit again before "
            "generating documents so the score and application stay aligned.</div>",
            unsafe_allow_html=True,
        )
        return

    render_section_label("Decision support")
    st.subheader("Fit review")
    render_analysis(
        st.session_state.job_analysis,
        st.session_state.base_match,
    )

    gaps = get_missing_profile_terms(st.session_state.base_match)
    confirmed = []
    if gaps:
        render_section_label("Candidate verification")
        st.subheader("Confirm familiarity")
        st.markdown(
            '<div class="notice warning">Select only terms you can honestly '
            "discuss in an interview. They may be shown as familiarity, but "
            "they do not increase your fit score and are not saved to your "
            "master profile.</div>",
            unsafe_allow_html=True,
        )
        confirmed = st.multiselect(
            "Terms you genuinely know",
            gaps,
            default=[],
        )

    generation_left, generation_right = st.columns([1, 2])
    with generation_left:
        tone = st.selectbox(
            "Cover letter tone",
            ["professional", "enthusiastic", "friendly"],
        )
    with generation_right:
        st.markdown(
            '<div class="notice">The generator uses your verified profile, the '
            "job analysis, and only the familiarity terms you select.</div>",
            unsafe_allow_html=True,
        )
    identity_error = ""
    try:
        validate_application_identity(company, role)
    except ValueError as exc:
        identity_error = str(exc)
        st.caption(identity_error)
    else:
        st.markdown(
            '<div class="notice">Application details are complete. Generate the '
            "draft, review every claim, then approve the PDFs for Tracker.</div>",
            unsafe_allow_html=True,
        )
    if st.button(
        "Generate application draft",
        type="primary",
        use_container_width=True,
        disabled=bool(identity_error),
    ):
        try:
            with st.spinner("Generating grounded application materials..."):
                draft = generate_application_draft(
                    company_name=company,
                    job_title=role,
                    job_description=job_description,
                    tone=tone,
                    source_url=tracker_apply_url(source_url),
                    confirmed_terms=confirmed,
                    job_analysis=st.session_state.job_analysis,
                    profile=st.session_state.base_profile,
                    match=st.session_state.base_match,
                )
            st.session_state.draft = draft
            st.session_state.saved = None
        except Exception as exc:
            show_action_error(exc, "Application generation")

    if st.session_state.draft:
        render_draft(st.session_state.draft)


def render_job_ranking():
    render_page_header(
        "Job Ranking",
        "Compare public job links, shortlist strong matches, and review each application individually.",
    )

    st.markdown(
        f'<div class="notice">Paste up to {MAX_BATCH_URLS} public job URLs. '
        "Blocked or script-heavy pages may fail, but other links will continue processing.</div>",
        unsafe_allow_html=True,
    )
    raw_urls = st.text_area(
        "Job URLs",
        height=220,
        placeholder=(
            "Paste one URL per line, or paste text containing several "
            "https:// links."
        ),
        key="ranking_url_input",
    )
    detected_urls = extract_urls_from_text(raw_urls)
    obvious_listings = [
        url for url in detected_urls if is_likely_job_listing(url, "")
    ]
    candidate_urls = [
        url for url in detected_urls if url not in set(obvious_listings)
    ]
    st.caption(
        f"{len(detected_urls)} link(s) detected · "
        f"{len(candidate_urls)} possible job detail page(s) · "
        f"{len(obvious_listings)} search/listing page(s)"
    )
    if obvious_listings:
        with st.expander(
            f"Search or listing pages detected ({len(obvious_listings)})"
        ):
            st.write(
                "These pages contain many jobs and cannot produce one reliable "
                "fit score. Open a specific role and paste its job-detail URL."
            )
            for url in obvious_listings:
                st.write(f"- {url}")

    rank_col, clear_col = st.columns([2, 1])
    with rank_col:
        rank_clicked = st.button(
            "Analyze and rank jobs",
            type="primary",
            use_container_width=True,
        )
    with clear_col:
        if st.button("Clear results", use_container_width=True):
            reset_ranking()
            st.rerun()

    if rank_clicked:
        if not detected_urls:
            st.error("Add at least one valid public job URL.")
        elif len(candidate_urls) > MAX_BATCH_URLS:
            st.error(
                f"This run contains {len(candidate_urls)} possible job-detail "
                f"links. Use {MAX_BATCH_URLS} or fewer so results remain reviewable."
            )
        elif not candidate_urls:
            st.error(
                "No individual job-detail URLs were found. Open a specific job "
                "from one of these search pages, then paste that job's URL."
            )
        else:
            progress = st.progress(0, text="Preparing job analysis...")
            activity = st.empty()

            def update_progress(index, total, url, state, detail):
                percent = int(((index - 1) / total) * 100)
                if state in {"success", "failed"}:
                    percent = int((index / total) * 100)
                label = {
                    "processing": f"Analyzing job {index} of {total}",
                    "success": f"Completed job {index} of {total}",
                    "failed": f"Skipped job {index} of {total}",
                }[state]
                progress.progress(percent, text=label)
                if state == "failed":
                    activity.warning(f"{url}: {detail}")
                elif detail:
                    activity.caption(detail)

            try:
                ranked_jobs, failures = rank_jobs_from_urls(
                    candidate_urls,
                    active_profile(),
                    progress_callback=update_progress,
                    preferences=st.session_state.job_preferences,
                )
                listing_failures = [
                    f"{url} -> Search/listing page; use an individual job URL"
                    for url in obvious_listings
                ]
                failures = listing_failures + failures
                report_path = save_ranked_jobs_report(ranked_jobs, failures)
                run_id = record_job_search_run(
                    ranked_jobs=ranked_jobs,
                    failures=failures,
                    total_urls=len(detected_urls),
                    report_path=report_path,
                )
                st.session_state.ranked_jobs = ranked_jobs
                st.session_state.ranking_failures = failures
                st.session_state.ranking_urls = detected_urls
                st.session_state.ranking_run_id = run_id
                st.session_state.shortlist = []
                progress.progress(100, text="Ranking complete")
                if ranked_jobs:
                    st.success(
                        f"Ranked {len(ranked_jobs)} job(s). "
                        f"Search run #{run_id} was saved."
                    )
                else:
                    st.error("None of the supplied job pages could be processed.")
            except Exception as exc:
                show_action_error(exc, "Job ranking")

    ranked_jobs = st.session_state.ranked_jobs
    failures = st.session_state.ranking_failures
    if not ranked_jobs and not failures:
        return

    if failures:
        with st.expander(f"Skipped links ({len(failures)})"):
            for failure in failures:
                st.write(f"- {failure}")

    if not ranked_jobs:
        return

    render_section_label("Ranking results")
    st.subheader("Ranked opportunities")
    options = {job.rank: job for job in ranked_jobs}
    labels = {
        job.rank: (
            f"#{job.rank} · {job.match.get('match_score', 0)}/100 · "
            f"{job.fetched_job.company_name} · {job.fetched_job.job_title}"
        )
        for job in ranked_jobs
    }
    selected_ranks = st.multiselect(
        "Shortlist jobs to review",
        options=list(options),
        format_func=lambda rank: labels[rank],
        key="shortlist",
    )

    for job in ranked_jobs:
        fetched = job.fetched_job
        match = job.match
        with st.expander(labels[job.rank], expanded=job.rank == 1):
            c1, c2, c3 = st.columns(3)
            c1.metric("Fit", f"{match.get('match_score', 0)}/100")
            c2.metric(
                "Verdict",
                match.get("fit_verdict_label", "Fit scored"),
            )
            c3.metric(
                "Action",
                action_label(match.get("match_score", 0)),
            )
            st.write(job.job_analysis.get("summary", ""))
            gaps = (
                match.get("missing_skills", [])
                + match.get("missing_tools", [])
            )[:6]
            if gaps:
                st.caption("Top gaps: " + ", ".join(gaps))
            review_col, link_col = st.columns([2, 1])
            with review_col:
                st.button(
                    "Review and generate application",
                    key=f"generate_rank_{job.rank}",
                    type="primary",
                    use_container_width=True,
                    on_click=load_ranked_job,
                    args=(job,),
                )
            with link_col:
                st.link_button(
                    "Open job page",
                    fetched.source_url,
                    use_container_width=True,
                )

    if selected_ranks:
        st.markdown(
            '<div class="notice warning">Shortlisting does not generate documents. '
            "Use the review button for each selected job to confirm skills and "
            "approve its application separately.</div>",
            unsafe_allow_html=True,
        )
        st.subheader("Shortlist queue")
        for rank in selected_ranks:
            job = options[rank]
            label = (
                f"Review #{rank}: {job.fetched_job.company_name} · "
                f"{job.fetched_job.job_title}"
            )
            st.button(
                label,
                key=f"review_rank_{rank}",
                use_container_width=True,
                on_click=load_ranked_job,
                args=(job,),
            )


def render_draft(draft):
    render_section_label("Document quality review")
    st.subheader("Draft review")
    render_fit(draft.match)
    st.markdown(
        '<div class="notice"><strong>Approval checklist:</strong> confirm the '
        "job title, factual claims, project relevance, dates, and contact details "
        "before saving.</div>",
        unsafe_allow_html=True,
    )

    resume_tab, letter_tab, prep_tab, ats_tab = st.tabs(
        ["Resume", "Cover letter", "Prep pack", "ATS report"]
    )
    resume_text = resume_to_text(draft.resume)
    with resume_tab:
        st.caption("Review wording, evidence, dates, and role relevance.")
        st.text_area(
            "Generated resume content",
            resume_text,
            height=480,
            disabled=True,
        )
        st.download_button(
            "Download resume text",
            resume_text,
            file_name="tailored_resume.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with letter_tab:
        st.caption("Check that the voice feels natural and company-specific.")
        st.text_area(
            "Generated cover letter",
            draft.cover_letter,
            height=480,
            disabled=True,
        )
        st.download_button(
            "Download cover letter text",
            draft.cover_letter,
            file_name="cover_letter.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with prep_tab:
        st.caption(
            "Use this before applying or messaging a recruiter. It is generated "
            "from the fit analysis and verified profile evidence."
        )
        st.text_area(
            "Recruiter message",
            draft.recruiter_message,
            height=180,
            disabled=True,
        )
        st.download_button(
            "Download recruiter message",
            draft.recruiter_message,
            file_name="recruiter_message.txt",
            mime="text/plain",
            use_container_width=True,
        )
        st.markdown("**Match explanation**")
        st.write(draft.match_explanation)
        render_list_panel(
            "Application checklist",
            draft.application_checklist,
            "positive",
        )
    with ats_tab:
        coverage = draft.ats_report["keyword_coverage"]
        st.metric("Keyword coverage", f"{coverage}/100")
        col1, col2 = st.columns(2)
        with col1:
            render_list_panel(
                "Covered terms",
                draft.ats_report.get("covered_terms", []),
                "positive",
            )
        with col2:
            render_list_panel(
                "Missing role terms",
                draft.ats_report.get("missing_terms", []),
            )
        context_terms = draft.ats_report.get("context_terms", [])
        excluded_terms = draft.ats_report.get("excluded_terms", [])
        if context_terms:
            st.caption(
                "Qualification/context terms checked: "
                + ", ".join(context_terms)
            )
        if excluded_terms:
            st.caption(
                "Excluded from ATS score as title, branding, or generic language: "
                + ", ".join(excluded_terms)
            )
        for issue in draft.ats_report.get("issues", []):
            st.warning(issue)

    st.markdown(
        '<div class="notice">Approval creates two PDFs and one Tracker record. '
        "It does not submit the application to the employer.</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        "Approve, create PDFs, and track",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("Creating PDFs and saving the application..."):
                st.session_state.saved = save_application_draft(draft)
            st.success(
                f"Application saved with tracker ID #{st.session_state.saved.application_id}."
            )
        except Exception as exc:
            show_action_error(exc, "Application saving")

    saved = st.session_state.saved
    if saved:
        render_section_label("Saved application")
        preview_choice = st.segmented_control(
            "Preview saved document",
            ["Resume", "Cover letter"],
            default="Resume",
            key=f"saved_preview_{saved.application_id}",
        )
        preview_path = (
            saved.resume_pdf
            if preview_choice == "Resume"
            else saved.cover_letter_pdf
        )
        if preview_path and os.path.exists(preview_path):
            st.pdf(
                preview_path,
                height=720,
                key=f"saved_pdf_{saved.application_id}_{preview_choice}",
            )

        col1, col2 = st.columns(2)
        for column, label, path, document_type in (
            (col1, "Download resume PDF", saved.resume_pdf, "resume"),
            (
                col2,
                "Download cover letter PDF",
                saved.cover_letter_pdf,
                "cover_letter",
            ),
        ):
            with column:
                if os.path.exists(path):
                    with open(path, "rb") as file:
                        st.download_button(
                            label,
                            file.read(),
                            file_name=document_download_name(
                                draft.profile,
                                draft.company_name,
                                document_type,
                            ),
                            mime="application/pdf",
                            use_container_width=True,
                        )


def render_tracker():
    render_page_header(
        "Application Tracker",
        "Manage approved applications and inspect earlier job-ranking runs.",
    )
    tracker_view = st.segmented_control(
        "Tracker view",
        ["Applications", "Ranking history"],
        default="Applications",
        key="tracker_view",
    )
    if tracker_view == "Ranking history":
        render_ranking_history()
        return

    stats = get_stats()
    in_progress = sum(
        stats["by_status"].get(status, 0)
        for status in ("APPLIED", "ASSESSMENT", "INTERVIEW")
    )
    st.markdown(
        f"""
        <div class="metric-strip">
            <div class="metric-cell">
                <div class="metric-value">{stats["total"]}</div>
                <div class="metric-name">Applications</div>
            </div>
            <div class="metric-cell">
                <div class="metric-value">{stats["avg_match"]}/100</div>
                <div class="metric-name">Average fit</div>
            </div>
            <div class="metric-cell">
                <div class="metric-value">{stats["avg_ats"]}/100</div>
                <div class="metric-name">Average ATS</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"Submitted applications in progress: {in_progress}. "
        "Generated drafts are not counted until their status is changed to Applied."
    )

    filter_col, context_col = st.columns([1, 2])
    with filter_col:
        status_filter = st.selectbox(
            "Status filter",
            ["ALL"] + VALID_STATUSES,
            format_func=lambda status: (
                "All applications"
                if status == "ALL"
                else status.replace("_", " ").title()
            ),
        )
    with context_col:
        render_section_label("Application pipeline")
        pipeline = stats.get("by_status", {})
        summary = " · ".join(
            f"{status.replace('_', ' ').title()}: {pipeline.get(status, 0)}"
            for status in VALID_STATUSES
            if pipeline.get(status, 0)
        )
        st.caption(summary or "No application activity recorded yet.")
    applications = list_applications(
        limit=100,
        status_filter=None if status_filter == "ALL" else status_filter,
    )
    if not applications:
        st.markdown(
            '<div class="empty-state">No applications match this filter.</div>',
            unsafe_allow_html=True,
        )
        return
    profile = active_profile()

    for application in applications:
        title = (
            f"#{application['id']} · {application['company_name']} · "
            f"{application['job_title']}"
        )
        with st.expander(title):
            status_class = (
                "positive"
                if application["status"] in {"INTERVIEW", "OFFER"}
                else ""
            )
            st.markdown(
                f'<span class="status-pill {status_class}">'
                f'{escape(application["status"].replace("_", " ").title())}'
                "</span>",
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Fit score", f"{application['match_score']}/100")
            c2.metric("ATS coverage", f"{application['ats_score']}/100")
            c3.metric(
                "Updated",
                str(application.get("updated_at", ""))[:10] or "Unknown",
            )

            status_col, notes_col = st.columns([1, 2])
            with status_col:
                new_status = st.selectbox(
                    "Update status",
                    VALID_STATUSES,
                    index=VALID_STATUSES.index(application["status"]),
                    key=f"status_{application['id']}",
                    format_func=lambda status: status.replace("_", " ").title(),
                )
            with notes_col:
                notes = st.text_input(
                    "Notes",
                    value=application.get("notes") or "",
                    key=f"notes_{application['id']}",
                )
            if st.button(
                "Save status",
                key=f"save_{application['id']}",
                use_container_width=True,
            ):
                update_application_status(
                    application["id"],
                    new_status,
                    notes,
                )
                st.success("Application updated.")
                st.rerun()

            safety_issues = audit_application_documents(
                application.get("resume_path") or "",
                application.get("cover_letter_path") or "",
                profile,
                application.get("notes") or "",
            )
            if safety_issues:
                legacy_issue = any(
                    "source text is unavailable" in issue.lower()
                    for issue in safety_issues
                )
                heading = (
                    "Legacy document review required before applying:"
                    if legacy_issue
                    else "Document safety review required before applying:"
                )
                st.warning(
                    heading + "\n\n- "
                    + "\n- ".join(safety_issues)
                )

            links = st.columns(3)
            if application.get("source_url"):
                links[0].link_button(
                    "Apply link",
                    application["source_url"],
                    use_container_width=True,
                )
            else:
                links[0].button(
                    "No source link",
                    disabled=True,
                    key=f"missing_link_{application['id']}",
                    use_container_width=True,
                    help="This application was created from a manually pasted description without a job URL.",
                )
            for column, label, path in (
                (links[1], "Download Resume", application.get("resume_path")),
                (
                    links[2],
                    "Download Cover Letter",
                    application.get("cover_letter_path"),
                ),
            ):
                if path and os.path.exists(path):
                    with open(path, "rb") as file:
                        column.download_button(
                            label,
                            file.read(),
                            file_name=os.path.basename(path),
                            mime="application/pdf",
                            key=f"{label}_{application['id']}",
                            use_container_width=True,
                        )

            resume_path = application.get("resume_path")
            cover_path = application.get("cover_letter_path")
            available_previews = ["Hide preview"]
            if resume_path and os.path.exists(resume_path):
                available_previews.append("Resume")
            if cover_path and os.path.exists(cover_path):
                available_previews.append("Cover letter")

            if len(available_previews) > 1:
                preview_choice = st.segmented_control(
                    "Document preview",
                    available_previews,
                    default="Hide preview",
                    key=f"preview_{application['id']}",
                )
                preview_path = {
                    "Resume": resume_path,
                    "Cover letter": cover_path,
                }.get(preview_choice)
                if preview_path:
                    st.pdf(
                        preview_path,
                        height=720,
                        key=f"pdf_{application['id']}_{preview_choice}",
                    )


def render_ranking_history():
    """Displays persisted ranking experiments separately from applications."""
    runs = list_job_search_runs(limit=25)
    if not runs:
        st.markdown(
            '<div class="empty-state">No ranking runs have been saved yet. '
            "Analyze multiple job URLs from Job Ranking to create one.</div>",
            unsafe_allow_html=True,
        )
        return

    total_processed = sum(run["total_urls"] for run in runs)
    total_successful = sum(run["successful_jobs"] for run in runs)
    total_failed = sum(run["failed_jobs"] for run in runs)
    c1, c2, c3 = st.columns(3)
    c1.metric("Ranking runs", len(runs))
    c2.metric("Jobs ranked", total_successful)
    c3.metric("Links rejected", total_failed)
    st.caption(
        f"{total_processed} links were evaluated across the latest "
        f"{len(runs)} ranking run(s)."
    )
    st.markdown(
        '<div class="notice">These are previous ranking experiments, not '
        "applications. Historical scores reflect the profile and matching "
        "logic used when each run was created.</div>",
        unsafe_allow_html=True,
    )
    if st.session_state.history_load_error:
        st.error(st.session_state.history_load_error)
        st.session_state.history_load_error = ""

    render_section_label("Recent ranking runs")
    for run in runs:
        created = format_history_time(run.get("created_at", ""))
        run_state = (
            "Failed run"
            if run["successful_jobs"] == 0
            else "Completed run"
        )
        title = (
            f"{run_state} #{run['id']} · {run['successful_jobs']} ranked · "
            f"{run['failed_jobs']} rejected · {created}"
        )
        with st.expander(title):
            jobs = list_ranked_jobs_for_run(run["id"])
            if jobs:
                seen_jobs = set()
                for job in jobs:
                    company = clean_company(job["company_name"])
                    duplicate_key = (
                        company.lower(),
                        job["job_title"].strip().lower(),
                    )
                    is_duplicate = duplicate_key in seen_jobs
                    seen_jobs.add(duplicate_key)
                    verdict = job.get("fit_verdict") or "Fit scored"
                    with st.container(border=True):
                        row_left, row_actions = st.columns([3, 2])
                        with row_left:
                            st.markdown(
                                f"**#{job['rank']} · {company} · "
                                f"{job['job_title']}**"
                            )
                            st.markdown(
                                f'<span class="status-pill '
                                f'{verdict_tone(verdict)}">{escape(verdict)}</span> '
                                f'<span class="status-pill">'
                                f'Fit {job["fit_score"]}/100</span>',
                                unsafe_allow_html=True,
                            )
                            st.caption(
                                "Page extraction: "
                                f"{str(job.get('extraction_quality') or 'unknown').title()}"
                            )
                            if is_duplicate:
                                st.warning(
                                    "Possible duplicate of another job in this run."
                                )
                        with row_actions:
                            st.button(
                                "Review and generate",
                                key=f"history_generate_{run['id']}_{job['rank']}",
                                type="primary",
                                use_container_width=True,
                                on_click=load_historical_job,
                                args=(job,),
                            )
                            st.link_button(
                                "Open job page",
                                job["source_url"],
                                key=f"history_link_{run['id']}_{job['rank']}",
                                use_container_width=True,
                            )
            else:
                st.warning(
                    "Failed run: none of the supplied links produced a rankable job."
                )

            try:
                failures = json.loads(run.get("failures_json") or "[]")
            except (TypeError, json.JSONDecodeError):
                failures = []
            if failures:
                st.markdown("**Rejected links**")
                for failure in failures:
                    st.write(f"- {failure}")

            report_path = run.get("report_path")
            if report_path and os.path.exists(report_path):
                with open(report_path, "rb") as report:
                    st.download_button(
                        "Download ranking report",
                        report.read(),
                        file_name=os.path.basename(report_path),
                        mime="text/plain",
                        key=f"ranking_report_{run['id']}",
                    )


def main():
    apply_styles()
    init_state()
    apply_pending_discovered_job()

    with st.sidebar:
        st.markdown(f"## {PRODUCT_NAME}")
        st.caption(PRODUCT_TAGLINE)
        st.markdown(
            '<span class="status-pill positive">Local workspace</span>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Navigation",
            [
                "Application",
                "Job Discovery",
                "Job Ranking",
                "Profile",
                "Tracker",
            ],
            key="navigation",
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Product Refinement · Demo Readiness")
        st.caption("Profile → Match → Documents → Track")

    if page == "Application":
        render_workspace()
    elif page == "Job Discovery":
        render_job_discovery()
    elif page == "Job Ranking":
        render_job_ranking()
    elif page == "Profile":
        render_profile()
    else:
        render_tracker()


if __name__ == "__main__":
    main()
