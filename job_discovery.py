"""Provider-neutral discovery with sample, Greenhouse, and Lever providers."""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from http.client import IncompleteRead
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from job_preferences import (
    ENTRY_LEVEL_REVIEW_MAX_YEARS,
    JobPreferences,
    preference_rejection_reason,
    required_experience_years,
)

load_dotenv()

GREENHOUSE_BOARDS_ENV = "GREENHOUSE_BOARDS"
GREENHOUSE_API_ROOT = "https://boards-api.greenhouse.io/v1/boards"
LEVER_SITES_ENV = "LEVER_SITES"
LEVER_API_ROOTS = {
    "global": "https://api.lever.co/v0/postings",
    "eu": "https://api.eu.lever.co/v0/postings",
}
ASHBY_BOARDS_ENV = "ASHBY_BOARDS"
ASHBY_API_ROOT = "https://api.ashbyhq.com/posting-api/job-board"
JOOBLE_API_KEY_ENV = "JOOBLE_API_KEY"
JOOBLE_API_ROOT = "https://jooble.org/api"
JOOBLE_RESULTS_PER_QUERY = 50
JOOBLE_MAX_QUERIES = 32
JOOBLE_CACHE_TTL_SECONDS = 15 * 60
REMOTIVE_API_ROOT = "https://remotive.com/api/remote-jobs"
REMOTIVE_MAX_QUERIES = 10
REMOTIVE_RESULTS_PER_QUERY = 60
REMOTIVE_CACHE_TTL_SECONDS = 30 * 60
ARBEITNOW_API_ROOT = "https://www.arbeitnow.com/api/job-board-api"
ARBEITNOW_MAX_PAGES = 2
ARBEITNOW_CACHE_TTL_SECONDS = 30 * 60
REMOTEOK_API_ROOT = "https://remoteok.com/api"
REMOTEOK_MAX_TAGS = 6
REMOTEOK_RESULTS_PER_TAG = 80
REMOTEOK_CACHE_TTL_SECONDS = 30 * 60
SERPAPI_API_KEY_ENV = "SERPAPI_API_KEY"
SERPAPI_API_ROOT = "https://serpapi.com/search.json"
SERPAPI_MAX_QUERIES = 32
SERPAPI_CACHE_TTL_SECONDS = 15 * 60
DISCOVERY_INVENTORY_WINDOW_DAYS_ENV = "APPLYSMART_JOB_INVENTORY_WINDOW_DAYS"
DEFAULT_DISCOVERY_INVENTORY_WINDOW_DAYS = 90
ADZUNA_APP_ID_ENV = "ADZUNA_APP_ID"
ADZUNA_APP_KEY_ENV = "ADZUNA_APP_KEY"
ADZUNA_COUNTRY_ENV = "ADZUNA_COUNTRY"
ADZUNA_API_ROOT = "https://api.adzuna.com/v1/api/jobs"
ADZUNA_RESULTS_PER_QUERY = 50
ADZUNA_MAX_QUERIES = 16
ADZUNA_CACHE_TTL_SECONDS = 15 * 60
TARGET_DISCOVERY_RESULTS = 10
_ADZUNA_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
_JOOBLE_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
_REMOTIVE_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
_ARBEITNOW_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
_REMOTEOK_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
_SERPAPI_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
DEFAULT_DISCOVERY_LIMIT = 50
LIVE_PROVIDER_TIMEOUT_SECONDS = 5
BROAD_PROVIDER_TIMEOUT_SECONDS = 6
DIRECT_FEED_MAX_WORKERS = 24
BROAD_SEARCH_MAX_WORKERS = 8
COMBINED_PROVIDER_MAX_WORKERS = 5
LIVE_FEED_CACHE_TTL_SECONDS = 15 * 60
_GREENHOUSE_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
_LEVER_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
_ASHBY_CACHE: dict[tuple, tuple[float, list["DiscoveredJob"]]] = {}
CURATED_GREENHOUSE_BOARDS = {
    # India-heavy or India-present tech/product companies.
    "phonepe": "PhonePe",
    "groww": "Groww",
    "slice": "Slice",
    "rubrik": "Rubrik",
    "databricks": "Databricks",
    "elastic": "Elastic",
    "thoughtworks": "Thoughtworks",
    "tekion": "Tekion",
    "zscaler": "Zscaler",
    "mongodb": "MongoDB",
    "postman": "Postman",
    "inmobi": "InMobi",
    "observeai": "Observe.AI",
    "sigmoid": "Sigmoid",
    # Remote/global feeds that often expose junior, graduate, or AI-adjacent roles.
    "canonical": "Canonical",
    "scaleai": "Scale AI",
    # Existing vetted feeds kept for broader AI/product coverage.
    "anthropic": "Anthropic",
    "appian": "Appian",
    "commvault": "Commvault",
    "energyexemplarllc": "Energy Exemplar",
    "enterpret": "Enterpret",
    "gleanwork": "Glean",
    "jumio": "Jumio",
    "prathaminternational": "Pratham International",
    "project44": "project44",
    "rzr": "RZR Global",
    "smartsheet": "Smartsheet",
}
CURATED_LEVER_SITES = {
    # India feeds with public Lever postings.
    "zeta": ("Zeta", "global"),
    "paytm": ("Paytm", "global"),
    "cred": ("CRED", "global"),
    "meesho": ("Meesho", "global"),
    "mindtickle": ("Mindtickle", "global"),
    # Existing AI/data/product feeds.
    "levelai": ("Level AI", "global"),
    "economicmodeling": ("Lightcast", "global"),
    "auxia": ("Auxia", "global"),
}
CURATED_ASHBY_BOARDS = {
    # Public Ashby boards with AI/data/software-heavy roles.
    "clueso": "Clueso",
    "atlan": "Atlan",
    "navi": "Navi",
    "airwallex": "Airwallex",
    "CUBE": "CUBE",
    "sentilink": "SentiLink",
    "harvey": "Harvey",
    "spector-ai": "Spector AI",
    "orb": "Orb",
    "mercury": "Mercury",
}
DIRECT_COMPANY_SOURCE_PREFIXES = ("Greenhouse", "Lever", "Ashby")


def environment_flag(name: str, *, default: bool = False) -> bool:
    """Reads a conservative boolean environment flag."""
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def use_curated_live_sources() -> bool:
    """Returns whether vetted public company feeds should be used by default."""
    return environment_flag("APPLYSMART_USE_CURATED_LIVE_SOURCES", default=True)


def early_career_sources_enabled() -> bool:
    """Returns whether no-key early-career public feeds should be queried."""
    return environment_flag("APPLYSMART_ENABLE_EARLY_CAREER_SOURCES", default=True)


class JobDiscoveryError(RuntimeError):
    """A readable live-provider failure that is safe to show in the UI."""


def collect_parallel(
    items,
    worker,
    *,
    max_workers: int,
    failure_label,
) -> tuple[list, list[str]]:
    """Runs bounded I/O work in parallel while preserving readable failures."""
    item_list = list(items)
    if not item_list:
        return [], []
    results = []
    failures = []
    worker_count = max(1, min(int(max_workers), len(item_list)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_item = {
            executor.submit(worker, item): item for item in item_list
        }
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                results.extend(future.result())
            except JobDiscoveryError as exc:
                failures.append(f"{failure_label(item)}: {exc}")
    return results, failures


def clear_discovery_provider_caches() -> None:
    """Clears broad-provider caches during interactive discovery retesting."""
    _GREENHOUSE_CACHE.clear()
    _LEVER_CACHE.clear()
    _ASHBY_CACHE.clear()
    _ADZUNA_CACHE.clear()
    _JOOBLE_CACHE.clear()
    _REMOTIVE_CACHE.clear()
    _ARBEITNOW_CACHE.clear()
    _REMOTEOK_CACHE.clear()
    _SERPAPI_CACHE.clear()


class _HTMLTextExtractor(HTMLParser):
    """Converts Greenhouse job HTML into readable plain text."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = unescape(str(data)).strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def html_to_text(value: str) -> str:
    """Returns normalized text from a small HTML fragment."""
    parser = _HTMLTextExtractor()
    parser.feed(str(value or ""))
    return parser.text()


def parse_greenhouse_boards(value: str | None = None) -> dict[str, str]:
    """
    Parses `board_token|Company Name` pairs from configuration.

    Multiple boards may be separated by commas or newlines.
    """
    if value is None:
        raw_value = os.getenv(GREENHOUSE_BOARDS_ENV, "")
        if not raw_value.strip() and use_curated_live_sources():
            return dict(CURATED_GREENHOUSE_BOARDS)
    else:
        raw_value = value
    boards = {}
    for raw_item in re.split(r"[,\n]+", str(raw_value)):
        item = raw_item.strip()
        if not item:
            continue
        token, separator, company = item.partition("|")
        token = token.strip()
        company = company.strip()
        if not separator or not token or not company:
            raise ValueError(
                "GREENHOUSE_BOARDS must use "
                "'board_token|Company Name' entries."
            )
        if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            raise ValueError(
                f"Invalid Greenhouse board token: {token!r}."
            )
        boards[token] = company
    return boards


def parse_lever_sites(
    value: str | None = None,
) -> dict[str, tuple[str, str]]:
    """
    Parses `site|Company Name|region` entries from configuration.

    Region is optional and defaults to `global`; supported values are
    `global` and `eu`.
    """
    if value is None:
        raw_value = os.getenv(LEVER_SITES_ENV, "")
        if not raw_value.strip() and use_curated_live_sources():
            return dict(CURATED_LEVER_SITES)
    else:
        raw_value = value
    sites = {}
    for raw_item in re.split(r"[,\n]+", str(raw_value)):
        item = raw_item.strip()
        if not item:
            continue
        parts = [part.strip() for part in item.split("|")]
        if len(parts) not in {2, 3} or not parts[0] or not parts[1]:
            raise ValueError(
                "LEVER_SITES must use "
                "'site|Company Name|global' entries."
            )
        site, company = parts[:2]
        region = parts[2].lower() if len(parts) == 3 else "global"
        if not re.fullmatch(r"[A-Za-z0-9_-]+", site):
            raise ValueError(f"Invalid Lever site name: {site!r}.")
        if region not in LEVER_API_ROOTS:
            raise ValueError(
                f"Invalid Lever region for {site!r}: {region!r}."
            )
        sites[site] = (company, region)
    return sites


def parse_ashby_boards(value: str | None = None) -> dict[str, str]:
    """Parses `job_board_name|Company Name` Ashby configuration entries."""
    if value is None:
        raw_value = os.getenv(ASHBY_BOARDS_ENV, "")
        if not raw_value.strip() and use_curated_live_sources():
            return dict(CURATED_ASHBY_BOARDS)
    else:
        raw_value = value
    boards = {}
    for raw_item in re.split(r"[,\n]+", str(raw_value)):
        item = raw_item.strip()
        if not item:
            continue
        board, separator, company = item.partition("|")
        board = board.strip()
        company = company.strip()
        if not separator or not board or not company:
            raise ValueError(
                "ASHBY_BOARDS must use 'job_board_name|Company Name' entries."
            )
        if not re.fullmatch(r"[A-Za-z0-9_-]+", board):
            raise ValueError(f"Invalid Ashby job board name: {board!r}.")
        boards[board] = company
    return boards


def jooble_is_configured() -> bool:
    """Returns whether the broad Jooble API can be used."""
    return bool(os.getenv(JOOBLE_API_KEY_ENV, "").strip())


def serpapi_is_configured() -> bool:
    """Returns whether Google Jobs via SerpAPI can be used."""
    return bool(os.getenv(SERPAPI_API_KEY_ENV, "").strip())


def expanded_market_locations(locations: list[str]) -> list[str]:
    """Adds broader market locations after user-selected cities."""
    expanded = []
    seen = set()
    for location in locations:
        item = str(location).strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            expanded.append(item)
    for fallback in ("India", ""):
        if fallback.lower() not in seen:
            seen.add(fallback.lower())
            expanded.append(fallback)
    return expanded


def expanded_role_queries(roles: list[str]) -> list[str]:
    """Adds high-value entry-level role variants for broad market APIs."""
    expanded = []
    seen = set()

    def add(value: str) -> None:
        item = str(value).strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            expanded.append(item)

    for role in roles:
        add(role)
        normalized = str(role).lower()
        if "data scientist" in normalized or "data science" in normalized:
            add("Junior Data Scientist")
            add("Data Science Fresher")
            add("Data Science Intern")
            add("Data Science Trainee")
            add("Data Scientist New Graduate")
            add("Associate Data Scientist")
        if "machine learning" in normalized or "ai/ml" in normalized:
            add("Junior Machine Learning Engineer")
            add("AI Engineer")
            add("Artificial Intelligence Engineer")
            add("Generative AI Engineer")
            add("Agentic AI Engineer")
            add("AI ML Fresher")
            add("AI Engineer Fresher")
            add("AI ML Intern")
            add("AI Engineer Intern")
            add("Machine Learning Intern")
            add("Graduate Machine Learning Engineer")
            add("Associate Machine Learning Engineer")
        if "computer vision" in normalized:
            add("Computer Vision Intern")
            add("Junior Computer Vision Engineer")
            add("Computer Vision Fresher")
        if "nlp" in normalized or "natural language" in normalized:
            add("NLP Intern")
            add("Junior NLP Engineer")
            add("NLP Fresher")
    return expanded


def discovery_inventory_window_days(
    preferences: JobPreferences | None = None,
) -> int:
    """Returns how far back the local source inventory should be considered."""
    configured = os.getenv(DISCOVERY_INVENTORY_WINDOW_DAYS_ENV, "").strip()
    try:
        window = int(configured) if configured else DEFAULT_DISCOVERY_INVENTORY_WINDOW_DAYS
    except ValueError:
        window = DEFAULT_DISCOVERY_INVENTORY_WINDOW_DAYS
    if preferences is not None:
        window = max(window, int(preferences.maximum_job_age_days))
    return max(1, min(window, 365))


def profile_search_role_queries(preferences: JobPreferences) -> list[str]:
    """Builds profile-aware broad-search queries with early-career intent first."""
    entry_level_search = set(preferences.experience_levels).issubset(
        {"Internship", "Fresher / Entry level"}
    )
    preferred_skills = [
        skill
        for skill in preferences.preferred_skills
        if skill.lower()
        in {
            "python",
            "sql",
            "machine learning",
            "deep learning",
            "natural language processing (nlp)",
            "nlp",
            "computer vision",
            "tensorflow",
            "pytorch",
            "scikit-learn",
        }
    ][:3]
    queries = []
    seen = set()

    def add(value: str) -> None:
        item = str(value).strip()
        key = re.sub(r"\s+", " ", item.lower())
        if item and key not in seen:
            seen.add(key)
            queries.append(item)

    primary_roles = [
        role.strip()
        for role in preferences.target_roles
        if str(role).strip()
    ]
    expanded_roles = [
        role
        for role in expanded_role_queries(preferences.target_roles)
        if role not in primary_roles
    ]
    if entry_level_search:
        for template in (
            "{role} fresher",
            "junior {role}",
            "entry level {role}",
            "{role} internship",
            "associate {role}",
        ):
            for role in primary_roles:
                add(template.format(role=role))
                normalized_role = role.lower()
                if "ai/ml" in normalized_role or "artificial intelligence" in normalized_role:
                    for alias in (
                        "AI Engineer",
                        "Artificial Intelligence Engineer",
                        "Generative AI Engineer",
                    ):
                        add(template.format(role=alias))

    for role in primary_roles:
        for skill in preferred_skills[:2]:
            add(f"{role} {skill}")
        add(role)

    for role in expanded_roles:
        if entry_level_search:
            add(f"{role} fresher")
            add(f"junior {role}")
            add(f"entry level {role}")
            add(f"{role} internship")
            add(f"associate {role}")
        for skill in preferred_skills[:2]:
            add(f"{role} {skill}")
        add(role)
    return queries


def interleaved_role_location_queries(
    roles: list[str],
    locations: list[str],
    *,
    limit: int,
    preferences: JobPreferences | None = None,
) -> list[tuple[str, str]]:
    """Builds a balanced role/location query plan instead of exhausting one role."""
    if preferences is None:
        primary_roles = [
            role.strip()
            for role in roles
            if str(role).strip()
        ]
        expanded_roles = [
            role
            for role in expanded_role_queries(roles)
            if role not in primary_roles
        ]
        role_groups = (primary_roles, expanded_roles)
    else:
        role_groups = (profile_search_role_queries(preferences),)
    location_queries = expanded_market_locations(locations)
    queries = []
    seen = set()
    for role_group in role_groups:
        for role in role_group:
            for location in location_queries:
                key = (role.lower(), location.lower())
                if key in seen:
                    continue
                seen.add(key)
                queries.append((role, location))
                if len(queries) >= limit:
                    return queries
    return queries


def parse_greenhouse_date(value: str) -> date:
    """Parses the public API update timestamp, with a safe current-date fallback."""
    text = str(value or "").strip()
    if not text:
        return date.today()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


def parse_iso_date(value: str) -> date:
    """Parses a provider timestamp without claiming freshness on failure."""
    text = str(value or "").strip()
    if not text:
        return date.today()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


def has_valid_iso_date(value: str) -> bool:
    """Reports whether a provider date can support freshness claims."""
    text = str(value or "").strip()
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def parse_public_timestamp(value) -> date:
    """Parses ISO strings or Unix timestamps from public job APIs."""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).date()
        except (OverflowError, OSError, ValueError):
            return date.today()
    return parse_iso_date(str(value or ""))


def has_valid_public_timestamp(value) -> bool:
    """Reports whether a public API timestamp supports freshness filtering."""
    if isinstance(value, (int, float)):
        try:
            datetime.fromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return False
        return True
    return has_valid_iso_date(str(value or ""))


def infer_discovery_metadata(title: str, description: str, location: str) -> dict:
    """Infers only high-confidence metadata from public job text."""
    searchable = f"{title} {description} {location}".lower()
    title_lower = title.lower()

    if "remote" in searchable:
        work_mode = "Remote"
    elif "hybrid" in searchable:
        work_mode = "Hybrid"
    else:
        work_mode = ""

    internship = any(
        marker in title_lower
        for marker in ("intern", "internship", "trainee", "apprentice")
    )
    if internship:
        job_type = "Internship"
        experience_level = "Internship"
    elif re.search(
        r"\b(?:software|machine learning|ai|ml) engineer\s+(?:i|1)\b",
        title_lower,
    ) or any(
        marker in searchable
        for marker in (
            "fresher",
            "freshers",
            "recent graduate",
            "new graduate",
            "no experience required",
            "0-1 years",
            "0 to 1 years",
            "0-2 years",
            "0 to 2 years",
        )
    ):
        job_type = ""
        experience_level = "Fresher / Entry level"
    else:
        job_type = ""
        experience_level = ""

    return {
        "work_mode": work_mode,
        "job_type": job_type,
        "experience_level": experience_level,
    }


def has_entry_level_evidence(title: str, description: str) -> bool:
    """Returns true when job text explicitly signals early-career suitability."""
    title_lower = str(title or "").lower()
    text = f"{title} {description}".lower()
    explicit_title_markers = (
        "intern",
        "internship",
        "trainee",
        "apprentice",
        "graduate",
        "entry level",
        "entry-level",
        "fresher",
        "freshers",
        "campus",
        "university graduate",
    )
    if any(marker in title_lower for marker in explicit_title_markers):
        return True
    text_markers = (
        "0-1 years",
        "0 to 1 years",
        "0-2 years",
        "0 to 2 years",
        "no experience required",
        "fresh graduate",
        "recent graduate",
        "new graduate",
        "2025 batch",
        "2026 batch",
        "iit freshers",
        "freshers can apply",
    )
    return any(marker in text for marker in text_markers)


def has_likely_entry_level_evidence(title: str, description: str) -> bool:
    """Returns true for softer early-career title signals requiring review."""
    if has_entry_level_evidence(title, description):
        return False
    title_lower = str(title or "").lower()
    if any(marker in title_lower for marker in ("associate", "junior")):
        return True
    if re.search(
        r"\b(?:software|machine learning|ai|ml|data|computer vision)\s+"
        r"(?:engineer|scientist|developer)\s+(?:i|1)\b",
        title_lower,
    ):
        return True
    return False


def has_manual_review_level_marker(title: str) -> bool:
    """Returns true when the title suggests the role is above entry level."""
    title_lower = str(title or "").lower()
    text_markers = (
        "advanced",
        "specialist",
        "sr.",
        "sr ",
        "senior",
        "lead",
        "principal",
        "staff",
        "manager",
        "director",
        "head of",
        "architect",
    )
    if any(marker in title_lower for marker in text_markers):
        return True
    return bool(
        re.search(
            r"\b(?:l[2-9]|level\s+[2-9]|[2-9][a-z]?)\b",
            title_lower,
        )
        or re.search(
            r"\b(?:engineer|scientist|developer)\s+(?:ii|iii|iv|v)\b",
            title_lower,
        )
    )


@dataclass(frozen=True)
class DiscoveredJob:
    """A normalized vacancy returned by any future discovery provider."""

    provider_job_id: str
    source: str
    company_name: str
    job_title: str
    location: str
    work_mode: str
    job_type: str
    experience_level: str
    posted_date: date
    job_description: str
    date_label: str = "Posted"
    freshness_verified: bool = True
    source_url: str = ""
    apply_url: str = ""
    relevance_score: int = 0


class JobDiscoveryProvider(Protocol):
    """Contract implemented by local, API, feed, or partner providers."""

    name: str

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Returns normalized jobs that may still require filtering."""


class GreenhouseJobProvider:
    """Reads active jobs from configured public Greenhouse job boards."""

    name = "Greenhouse public boards"

    def __init__(
        self,
        boards: dict[str, str],
        *,
        timeout: int = LIVE_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_workers: int = DIRECT_FEED_MAX_WORKERS,
    ):
        if not boards:
            raise ValueError(
                "Configure at least one Greenhouse board before live discovery."
            )
        self.boards = dict(boards)
        self.timeout = timeout
        self.opener = opener
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_board(self, token: str, company: str) -> list[DiscoveredJob]:
        cache_key = (token, company)
        cached = _GREENHOUSE_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < LIVE_FEED_CACHE_TTL_SECONDS:
            return list(cached[1])
        url = f"{GREENHOUSE_API_ROOT}/{quote(token)}/jobs?content=true"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"{company}: Greenhouse returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError(
                f"{company}: Greenhouse could not be reached."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                f"{company}: Greenhouse returned an invalid response."
            ) from exc

        jobs = []
        for item in payload.get("jobs", []):
            description = html_to_text(item.get("content", ""))
            if len(description.split()) < 20:
                continue
            title = str(item.get("title", "")).strip()
            location = str(
                (item.get("location") or {}).get("name", "")
            ).strip()
            metadata = infer_discovery_metadata(
                title,
                description,
                location,
            )
            jobs.append(
                DiscoveredJob(
                    provider_job_id=str(item.get("id", "")).strip(),
                    source=f"Greenhouse · {company}",
                    company_name=company,
                    job_title=title,
                    location=location,
                    work_mode=metadata["work_mode"],
                    job_type=metadata["job_type"],
                    experience_level=metadata["experience_level"],
                    posted_date=parse_greenhouse_date(item.get("updated_at", "")),
                    job_description=description,
                    date_label="Active listing",
                    freshness_verified=False,
                    source_url=str(item.get("absolute_url", "")).strip(),
                    apply_url=str(item.get("absolute_url", "")).strip(),
                )
            )
        if self.cache_enabled:
            _GREENHOUSE_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Returns live normalized jobs while isolating individual board failures."""
        del preferences
        self.failures = []
        jobs, self.failures = collect_parallel(
            self.boards.items(),
            lambda item: self._fetch_board(item[0], item[1]),
            max_workers=self.max_workers,
            failure_label=lambda item: item[1],
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No configured Greenhouse boards could be loaded. "
                + " ".join(self.failures)
            )
        return jobs


def lever_job_type(commitment: str, title: str) -> str:
    """Maps high-confidence Lever commitment values to PathPilot types."""
    text = f"{commitment} {title}".lower()
    if any(term in text for term in ("intern", "trainee", "apprentice")):
        return "Internship"
    if "contract" in text:
        return "Contract"
    if any(
        term in text
        for term in ("full-time", "full time", "fulltime", "permanent")
    ):
        return "Full-time"
    return ""


def lever_work_mode(value: str) -> str:
    """Maps Lever workplace types to PathPilot display values."""
    return {
        "remote": "Remote",
        "hybrid": "Hybrid",
        "on-site": "Onsite",
        "onsite": "Onsite",
    }.get(str(value or "").strip().lower(), "")


def lever_description(item: dict) -> str:
    """Builds complete plain text from Lever's structured posting fields."""
    parts = [str(item.get("descriptionPlain", "")).strip()]
    for section in item.get("lists", []) or []:
        heading = str(section.get("text", "")).strip()
        content = html_to_text(section.get("content", ""))
        if heading or content:
            parts.append(" ".join(part for part in (heading, content) if part))
    additional = str(item.get("additionalPlain", "")).strip()
    if additional:
        parts.append(additional)
    return re.sub(r"\s+", " ", " ".join(filter(None, parts))).strip()


class LeverJobProvider:
    """Reads published jobs from configured public Lever posting sites."""

    name = "Lever public sites"

    def __init__(
        self,
        sites: dict[str, tuple[str, str]],
        *,
        timeout: int = LIVE_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_workers: int = DIRECT_FEED_MAX_WORKERS,
    ):
        if not sites:
            raise ValueError(
                "Configure at least one Lever site before live discovery."
            )
        self.sites = dict(sites)
        self.timeout = timeout
        self.opener = opener
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_site(
        self,
        site: str,
        company: str,
        region: str,
    ) -> list[DiscoveredJob]:
        cache_key = (site, company, region)
        cached = _LEVER_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < LIVE_FEED_CACHE_TTL_SECONDS:
            return list(cached[1])
        root = LEVER_API_ROOTS[region]
        url = f"{root}/{quote(site)}?mode=json"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"{company}: Lever returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError(
                f"{company}: Lever could not be reached."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                f"{company}: Lever returned an invalid response."
            ) from exc

        if not isinstance(payload, list):
            raise JobDiscoveryError(
                f"{company}: Lever returned an unexpected response."
            )

        jobs = []
        for item in payload:
            description = lever_description(item)
            if len(description.split()) < 20:
                continue
            title = str(item.get("text", "")).strip()
            categories = item.get("categories") or {}
            location = str(categories.get("location", "")).strip()
            commitment = str(categories.get("commitment", "")).strip()
            metadata = infer_discovery_metadata(title, description, location)
            job_type = lever_job_type(commitment, title)
            if job_type == "Internship":
                experience_level = "Internship"
            else:
                experience_level = metadata["experience_level"]
            jobs.append(
                DiscoveredJob(
                    provider_job_id=str(item.get("id", "")).strip(),
                    source=f"Lever · {company}",
                    company_name=company,
                    job_title=title,
                    location=location,
                    work_mode=(
                        lever_work_mode(item.get("workplaceType", ""))
                        or metadata["work_mode"]
                    ),
                    job_type=job_type,
                    experience_level=experience_level,
                    posted_date=date.today(),
                    job_description=description,
                    date_label="Active listing",
                    freshness_verified=False,
                    source_url=str(
                        item.get("hostedUrl") or item.get("applyUrl") or ""
                    ).strip(),
                    apply_url=str(
                        item.get("applyUrl") or item.get("hostedUrl") or ""
                    ).strip(),
                )
            )
        if self.cache_enabled:
            _LEVER_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Returns public Lever jobs while isolating individual site failures."""
        del preferences
        self.failures = []
        jobs, self.failures = collect_parallel(
            self.sites.items(),
            lambda item: self._fetch_site(
                item[0],
                item[1][0],
                item[1][1],
            ),
            max_workers=self.max_workers,
            failure_label=lambda item: item[1][0],
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No configured Lever sites could be loaded. "
                + " ".join(self.failures)
            )
        return jobs


def ashby_location(item: dict) -> str:
    """Returns a readable Ashby location from its public posting shape."""
    location = item.get("location") or {}
    if isinstance(location, dict):
        text = (
            location.get("name")
            or location.get("city")
            or location.get("region")
            or location.get("country")
            or ""
        )
        return str(text).strip()
    return str(location or item.get("locationName") or "").strip()


def ashby_description(item: dict) -> str:
    """Builds plain job text from Ashby's public posting fields."""
    parts = []
    for key in (
        "descriptionPlain",
        "descriptionHtml",
        "description",
        "content",
    ):
        value = item.get(key)
        if value:
            parts.append(html_to_text(value) if "<" in str(value) else str(value))
    for section in item.get("sections", []) or []:
        if isinstance(section, dict):
            heading = str(section.get("title") or section.get("heading") or "").strip()
            body = html_to_text(section.get("body") or section.get("content") or "")
            if heading or body:
                parts.append(" ".join(part for part in (heading, body) if part))
    return re.sub(r"\s+", " ", " ".join(filter(None, parts))).strip()


class AshbyJobProvider:
    """Reads active jobs from configured public Ashby job boards."""

    name = "Ashby public boards"

    def __init__(
        self,
        boards: dict[str, str],
        *,
        timeout: int = LIVE_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_workers: int = DIRECT_FEED_MAX_WORKERS,
    ):
        if not boards:
            raise ValueError(
                "Configure at least one Ashby board before live discovery."
            )
        self.boards = dict(boards)
        self.timeout = timeout
        self.opener = opener
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_board(self, board: str, company: str) -> list[DiscoveredJob]:
        cache_key = (board, company)
        cached = _ASHBY_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < LIVE_FEED_CACHE_TTL_SECONDS:
            return list(cached[1])
        url = f"{ASHBY_API_ROOT}/{quote(board)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"{company}: Ashby returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError(
                f"{company}: Ashby could not be reached."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                f"{company}: Ashby returned an invalid response."
            ) from exc

        raw_jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        jobs = []
        for item in raw_jobs:
            if item.get("isListed") is False:
                continue
            description = ashby_description(item)
            if len(description.split()) < 20:
                continue
            title = str(item.get("title") or item.get("name") or "").strip()
            location = ashby_location(item)
            metadata = infer_discovery_metadata(title, description, location)
            hosted_url = str(
                item.get("jobUrl")
                or item.get("url")
                or item.get("hostedUrl")
                or ""
            ).strip()
            apply_url = str(
                item.get("applyUrl")
                or item.get("applicationUrl")
                or hosted_url
            ).strip()
            jobs.append(
                DiscoveredJob(
                    provider_job_id=str(
                        item.get("id") or item.get("jobId") or hosted_url
                    ).strip(),
                    source=f"Ashby · {company}",
                    company_name=company,
                    job_title=title,
                    location=location,
                    work_mode=metadata["work_mode"],
                    job_type=metadata["job_type"],
                    experience_level=metadata["experience_level"],
                    posted_date=date.today(),
                    job_description=description,
                    date_label="Active listing",
                    freshness_verified=False,
                    source_url=hosted_url,
                    apply_url=apply_url,
                )
            )
        if self.cache_enabled:
            _ASHBY_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Returns public Ashby jobs while isolating individual board failures."""
        del preferences
        self.failures = []
        jobs, self.failures = collect_parallel(
            self.boards.items(),
            lambda item: self._fetch_board(item[0], item[1]),
            max_workers=self.max_workers,
            failure_label=lambda item: item[1],
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No configured Ashby boards could be loaded. "
                + " ".join(self.failures)
            )
        return jobs


class AdzunaJobProvider:
    """Searches Adzuna's licensed broad job-search API."""

    name = "Adzuna broad search"

    def __init__(
        self,
        app_id: str,
        app_key: str,
        *,
        country: str = "in",
        timeout: int = BROAD_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_queries: int = ADZUNA_MAX_QUERIES,
        max_workers: int = BROAD_SEARCH_MAX_WORKERS,
    ):
        if not str(app_id).strip() or not str(app_key).strip():
            raise ValueError("Configure both ADZUNA_APP_ID and ADZUNA_APP_KEY.")
        if not re.fullmatch(r"[a-z]{2}", str(country).strip().lower()):
            raise ValueError("ADZUNA_COUNTRY must be a two-letter country code.")
        self.app_id = str(app_id).strip()
        self.app_key = str(app_key).strip()
        self.country = str(country).strip().lower()
        self.timeout = timeout
        self.opener = opener
        self.max_queries = max(1, int(max_queries))
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_role_location(
        self,
        role: str,
        location: str,
        preferences: JobPreferences,
    ) -> list[DiscoveredJob]:
        params_data = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": ADZUNA_RESULTS_PER_QUERY,
            "what": role,
            "max_days_old": preferences.maximum_job_age_days,
            "content-type": "application/json",
        }
        if str(location).strip():
            params_data["where"] = str(location).strip()
        params = urlencode(params_data)
        url = f"{ADZUNA_API_ROOT}/{self.country}/search/1?{params}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"Adzuna search returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError("Adzuna search could not be reached.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                "Adzuna search returned an invalid response."
            ) from exc

        results = payload.get("results", []) if isinstance(payload, dict) else []
        jobs = []
        for item in results:
            description = html_to_text(item.get("description", ""))
            if len(description.split()) < 20:
                continue
            title = str(item.get("title", "")).strip()
            location_data = item.get("location") or {}
            location = str(location_data.get("display_name", "")).strip()
            company_data = item.get("company") or {}
            company = str(company_data.get("display_name", "Unknown")).strip()
            contract_type = str(item.get("contract_type", "")).strip()
            metadata = infer_discovery_metadata(title, description, location)
            job_type = lever_job_type(contract_type, title)
            source_url = str(item.get("redirect_url", "")).strip()
            created = item.get("created", "")
            jobs.append(
                DiscoveredJob(
                    provider_job_id=f"adzuna-{item.get('id', '')}",
                    source="Adzuna",
                    company_name=company or "Unknown",
                    job_title=title,
                    location=location,
                    work_mode=metadata["work_mode"],
                    job_type=job_type,
                    experience_level=metadata["experience_level"],
                    posted_date=parse_iso_date(created),
                    job_description=description,
                    date_label=("Posted" if has_valid_iso_date(created) else "Active listing"),
                    freshness_verified=has_valid_iso_date(created),
                    source_url=source_url,
                    apply_url=source_url,
                )
            )
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Searches a bounded set of target roles and isolates query failures."""
        self.failures = []
        queries = interleaved_role_location_queries(
            preferences.target_roles,
            preferences.locations,
            limit=self.max_queries,
            preferences=preferences,
        )
        cache_key = (
            self.country,
            tuple(queries),
            preferences.maximum_job_age_days,
            self.max_queries,
        )
        cached = _ADZUNA_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < ADZUNA_CACHE_TTL_SECONDS:
            return list(cached[1])
        jobs, self.failures = collect_parallel(
            queries,
            lambda query: self._fetch_role_location(
                query[0],
                query[1],
                preferences,
            ),
            max_workers=self.max_workers,
            failure_label=lambda query: (
                f"{query[0]} / {query[1] or 'Any location'}"
            ),
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No Adzuna role searches could be loaded. "
                + " ".join(self.failures)
            )
        if self.cache_enabled and jobs:
            _ADZUNA_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs


class JoobleJobProvider:
    """Searches Jooble's broad job-search API as a second market source."""

    name = "Jooble broad search"

    def __init__(
        self,
        api_key: str,
        *,
        country: str = "in",
        timeout: int = BROAD_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_queries: int = JOOBLE_MAX_QUERIES,
        max_workers: int = BROAD_SEARCH_MAX_WORKERS,
    ):
        if not str(api_key).strip():
            raise ValueError("Configure JOOBLE_API_KEY.")
        if not re.fullmatch(r"[a-z]{2}", str(country).strip().lower()):
            raise ValueError("JOOBLE_COUNTRY must be a two-letter country code.")
        self.api_key = str(api_key).strip()
        self.country = str(country).strip().lower()
        self.timeout = timeout
        self.opener = opener
        self.max_queries = max(1, int(max_queries))
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_role_location(
        self,
        role: str,
        location: str,
        preferences: JobPreferences,
    ) -> list[DiscoveredJob]:
        url = f"{JOOBLE_API_ROOT}/{quote(self.api_key)}"
        payload = {
            "keywords": role,
            "location": location,
            "page": 1,
            "searchMode": 1,
            "dateSearch": preferences.maximum_job_age_days,
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"Jooble search returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError("Jooble search could not be reached.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                "Jooble search returned an invalid response."
            ) from exc

        results = (
            response_payload.get("jobs", [])
            if isinstance(response_payload, dict)
            else []
        )
        jobs = []
        for item in results[:JOOBLE_RESULTS_PER_QUERY]:
            description = html_to_text(item.get("snippet") or item.get("description") or "")
            if len(description.split()) < 20:
                continue
            title = str(item.get("title", "")).strip()
            company = str(item.get("company", "Unknown")).strip() or "Unknown"
            job_location = str(item.get("location", location)).strip()
            metadata = infer_discovery_metadata(title, description, job_location)
            source_url = str(item.get("link", "")).strip()
            posted = str(item.get("updated") or item.get("date") or "").strip()
            jobs.append(
                DiscoveredJob(
                    provider_job_id=f"jooble-{item.get('id') or source_url}",
                    source="Jooble",
                    company_name=company,
                    job_title=title,
                    location=job_location,
                    work_mode=metadata["work_mode"],
                    job_type=metadata["job_type"],
                    experience_level=metadata["experience_level"],
                    posted_date=parse_iso_date(posted),
                    job_description=description,
                    date_label=("Posted" if has_valid_iso_date(posted) else "Active listing"),
                    freshness_verified=has_valid_iso_date(posted),
                    source_url=source_url,
                    apply_url=source_url,
                )
            )
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Searches bounded role/location combinations and isolates failures."""
        self.failures = []
        queries = interleaved_role_location_queries(
            preferences.target_roles,
            preferences.locations,
            limit=self.max_queries,
            preferences=preferences,
        )
        cache_key = (
            self.country,
            tuple(queries),
            preferences.maximum_job_age_days,
            self.max_queries,
        )
        cached = _JOOBLE_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < JOOBLE_CACHE_TTL_SECONDS:
            return list(cached[1])

        jobs, self.failures = collect_parallel(
            queries,
            lambda query: self._fetch_role_location(
                query[0],
                query[1],
                preferences,
            ),
            max_workers=self.max_workers,
            failure_label=lambda query: (
                f"{query[0]} / {query[1] or 'Any location'}"
            ),
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No Jooble searches could be loaded. " + " ".join(self.failures)
            )
        if self.cache_enabled and jobs:
            _JOOBLE_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs


def remotive_role_queries(preferences: JobPreferences) -> list[str]:
    """Builds a small Remotive query plan with early-career intent first."""
    queries = []
    seen = set()

    def add(value: str) -> None:
        item = str(value).strip()
        key = re.sub(r"\s+", " ", item.lower())
        if item and key not in seen:
            seen.add(key)
            queries.append(item)

    for query in profile_search_role_queries(preferences):
        add(query)
        if len(queries) >= REMOTIVE_MAX_QUERIES:
            break
    for fallback in ("data science intern", "junior data scientist", "machine learning intern"):
        add(fallback)
        if len(queries) >= REMOTIVE_MAX_QUERIES:
            break
    return queries[:REMOTIVE_MAX_QUERIES]


class RemotiveJobProvider:
    """Searches Remotive's no-key remote job API for extra tech coverage."""

    name = "Remotive remote jobs"

    def __init__(
        self,
        *,
        timeout: int = BROAD_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_queries: int = REMOTIVE_MAX_QUERIES,
        max_workers: int = BROAD_SEARCH_MAX_WORKERS,
    ):
        self.timeout = timeout
        self.opener = opener
        self.max_queries = max(1, int(max_queries))
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_query(self, query: str) -> list[DiscoveredJob]:
        params = urlencode({"search": query})
        url = f"{REMOTIVE_API_ROOT}?{params}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"Remotive search returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError("Remotive search could not be reached.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                "Remotive search returned an invalid response."
            ) from exc

        raw_jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        jobs = []
        for item in raw_jobs[:REMOTIVE_RESULTS_PER_QUERY]:
            description = html_to_text(item.get("description", ""))
            if len(description.split()) < 20:
                continue
            title = str(item.get("title", "")).strip()
            location = str(
                item.get("candidate_required_location") or "Remote"
            ).strip()
            metadata = infer_discovery_metadata(title, description, location)
            raw_type = str(item.get("job_type") or "").replace("_", " ")
            job_type = lever_job_type(raw_type, title) or metadata["job_type"]
            published = item.get("publication_date", "")
            source_url = str(item.get("url", "")).strip()
            jobs.append(
                DiscoveredJob(
                    provider_job_id=f"remotive-{item.get('id') or source_url}",
                    source="Remotive",
                    company_name=str(item.get("company_name") or "Unknown").strip()
                    or "Unknown",
                    job_title=title,
                    location=location,
                    work_mode="Remote",
                    job_type=job_type,
                    experience_level=(
                        "Internship"
                        if job_type == "Internship"
                        else metadata["experience_level"]
                    ),
                    posted_date=parse_public_timestamp(published),
                    job_description=description,
                    date_label=(
                        "Posted"
                        if has_valid_public_timestamp(published)
                        else "Active listing"
                    ),
                    freshness_verified=has_valid_public_timestamp(published),
                    source_url=source_url,
                    apply_url=source_url,
                )
            )
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Searches a bounded set of early-career remote-role queries."""
        self.failures = []
        queries = remotive_role_queries(preferences)[: self.max_queries]
        cache_key = (tuple(queries), preferences.maximum_job_age_days, self.max_queries)
        cached = _REMOTIVE_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < REMOTIVE_CACHE_TTL_SECONDS:
            return list(cached[1])
        jobs, self.failures = collect_parallel(
            queries,
            self._fetch_query,
            max_workers=self.max_workers,
            failure_label=lambda query: f"Remotive {query}",
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No Remotive searches could be loaded. " + " ".join(self.failures)
            )
        if self.cache_enabled and jobs:
            _REMOTIVE_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs


def arbeitnow_job_type(job_types, title: str) -> str:
    """Maps Arbeitnow job type arrays to PathPilot job type labels."""
    raw = " ".join(str(item) for item in (job_types or []))
    return lever_job_type(raw, title)


class ArbeitnowJobProvider:
    """Reads Arbeitnow's no-key public job board API for global tech jobs."""

    name = "Arbeitnow public jobs"

    def __init__(
        self,
        *,
        timeout: int = BROAD_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_pages: int = ARBEITNOW_MAX_PAGES,
    ):
        self.timeout = timeout
        self.opener = opener
        self.max_pages = max(1, int(max_pages))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_page(self, page: int) -> list[DiscoveredJob]:
        url = f"{ARBEITNOW_API_ROOT}?{urlencode({'page': page})}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"Arbeitnow returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError("Arbeitnow could not be reached.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                "Arbeitnow returned an invalid response."
            ) from exc

        raw_jobs = payload.get("data", []) if isinstance(payload, dict) else []
        jobs = []
        for item in raw_jobs:
            description = html_to_text(item.get("description", ""))
            if len(description.split()) < 20:
                continue
            title = str(item.get("title", "")).strip()
            location = str(item.get("location") or "").strip()
            if item.get("remote") and "remote" not in location.lower():
                location = f"Remote · {location}" if location else "Remote"
            metadata = infer_discovery_metadata(title, description, location)
            job_type = arbeitnow_job_type(item.get("job_types"), title) or metadata["job_type"]
            created = item.get("created_at")
            source_url = str(item.get("url", "")).strip()
            jobs.append(
                DiscoveredJob(
                    provider_job_id=f"arbeitnow-{item.get('slug') or source_url}",
                    source="Arbeitnow",
                    company_name=str(item.get("company_name") or "Unknown").strip()
                    or "Unknown",
                    job_title=title,
                    location=location,
                    work_mode=(
                        "Remote"
                        if item.get("remote")
                        else metadata["work_mode"]
                    ),
                    job_type=job_type,
                    experience_level=(
                        "Internship"
                        if job_type == "Internship"
                        else metadata["experience_level"]
                    ),
                    posted_date=parse_public_timestamp(created),
                    job_description=description,
                    date_label=(
                        "Posted"
                        if has_valid_public_timestamp(created)
                        else "Active listing"
                    ),
                    freshness_verified=has_valid_public_timestamp(created),
                    source_url=source_url,
                    apply_url=source_url,
                )
            )
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Fetches recent public postings and lets PathPilot filter locally."""
        del preferences
        self.failures = []
        pages = tuple(range(1, self.max_pages + 1))
        cache_key = (pages,)
        cached = _ARBEITNOW_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < ARBEITNOW_CACHE_TTL_SECONDS:
            return list(cached[1])
        jobs, self.failures = collect_parallel(
            pages,
            self._fetch_page,
            max_workers=min(BROAD_SEARCH_MAX_WORKERS, len(pages)),
            failure_label=lambda page: f"Arbeitnow page {page}",
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No Arbeitnow pages could be loaded. " + " ".join(self.failures)
            )
        if self.cache_enabled and jobs:
            _ARBEITNOW_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs


def remoteok_tags(preferences: JobPreferences) -> list[str]:
    """Selects high-signal RemoteOK tags from the current profile."""
    text = " ".join(
        preferences.target_roles
        + preferences.preferred_skills
    ).lower()
    tags = []
    seen = set()

    def add(value: str) -> None:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            tags.append(item)

    if any(term in text for term in ("data scientist", "data science", "sql")):
        add("data-science")
    if any(term in text for term in ("machine learning", "ai/ml", "tensorflow", "pytorch")):
        add("machine-learning")
    if any(term in text for term in ("python", "scikit")):
        add("python")
    if any(term in text for term in ("ai", "artificial intelligence", "nlp")):
        add("ai")
    if "computer vision" in text:
        add("computer-vision")
    add("engineer")
    return tags[:REMOTEOK_MAX_TAGS]


class RemoteOKJobProvider:
    """Searches RemoteOK's no-key tagged API for remote tech listings."""

    name = "RemoteOK remote jobs"

    def __init__(
        self,
        *,
        timeout: int = BROAD_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_tags: int = REMOTEOK_MAX_TAGS,
        max_workers: int = BROAD_SEARCH_MAX_WORKERS,
    ):
        self.timeout = timeout
        self.opener = opener
        self.max_tags = max(1, int(max_tags))
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_tag(self, tag: str) -> list[DiscoveredJob]:
        url = f"{REMOTEOK_API_ROOT}?{urlencode({'tags': tag})}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"RemoteOK returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError("RemoteOK could not be reached.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                "RemoteOK returned an invalid response."
            ) from exc

        raw_jobs = payload if isinstance(payload, list) else []
        jobs = []
        for item in raw_jobs[:REMOTEOK_RESULTS_PER_TAG]:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            description = html_to_text(item.get("description", ""))
            if len(description.split()) < 20:
                continue
            title = str(item.get("position") or "").strip()
            raw_location = str(item.get("location") or "").strip()
            location = raw_location
            if not location or location.lower() in {"remote", "anywhere"}:
                location = "Worldwide"
            metadata = infer_discovery_metadata(title, description, location)
            job_type = metadata["job_type"]
            published = item.get("date") or item.get("epoch")
            source_url = str(item.get("url") or item.get("apply_url") or "").strip()
            jobs.append(
                DiscoveredJob(
                    provider_job_id=f"remoteok-{item.get('id') or item.get('slug') or source_url}",
                    source="RemoteOK",
                    company_name=str(item.get("company") or "Unknown").strip()
                    or "Unknown",
                    job_title=title,
                    location=location,
                    work_mode="Remote",
                    job_type=job_type,
                    experience_level=metadata["experience_level"],
                    posted_date=parse_public_timestamp(published),
                    job_description=description,
                    date_label=(
                        "Posted"
                        if has_valid_public_timestamp(published)
                        else "Active listing"
                    ),
                    freshness_verified=has_valid_public_timestamp(published),
                    source_url=source_url,
                    apply_url=str(item.get("apply_url") or source_url).strip(),
                )
            )
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Fetches profile-selected RemoteOK tags and filters downstream."""
        self.failures = []
        tags = tuple(remoteok_tags(preferences)[: self.max_tags])
        cache_key = (tags, self.max_tags)
        cached = _REMOTEOK_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < REMOTEOK_CACHE_TTL_SECONDS:
            return list(cached[1])
        jobs, self.failures = collect_parallel(
            tags,
            self._fetch_tag,
            max_workers=self.max_workers,
            failure_label=lambda tag: f"RemoteOK {tag}",
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No RemoteOK tags could be loaded. " + " ".join(self.failures)
            )
        if self.cache_enabled and jobs:
            _REMOTEOK_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs


def parse_google_jobs_posted_at(value: str) -> tuple[date, bool]:
    """Converts Google Jobs relative posted strings into a best-effort date."""
    text = str(value or "").strip().lower()
    today = date.today()
    if not text:
        return today, False
    if text in {"today", "just posted"} or "hour" in text or "minute" in text:
        return today, True
    if "yesterday" in text:
        return today - timedelta(days=1), True
    match = re.search(r"(\d+)\+?\s+(day|week|month)s?", text)
    if not match:
        return today, False
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "day":
        return today - timedelta(days=amount), True
    if unit == "week":
        return today - timedelta(days=amount * 7), True
    return today - timedelta(days=amount * 30), True


class SerpApiGoogleJobsProvider:
    """Searches Google Jobs via SerpAPI for platform and company listings."""

    name = "Google Jobs via SerpAPI"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: int = BROAD_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_queries: int = SERPAPI_MAX_QUERIES,
        max_workers: int = BROAD_SEARCH_MAX_WORKERS,
    ):
        if not str(api_key).strip():
            raise ValueError("Configure SERPAPI_API_KEY.")
        self.api_key = str(api_key).strip()
        self.timeout = timeout
        self.opener = opener
        self.max_queries = max(1, int(max_queries))
        self.max_workers = max(1, int(max_workers))
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    def _fetch_role_location(
        self,
        role: str,
        location: str,
        preferences: JobPreferences,
    ) -> list[DiscoveredJob]:
        params = urlencode(
            {
                "engine": "google_jobs",
                "q": role,
                "location": location or "India",
                "hl": "en",
                "api_key": self.api_key,
            }
        )
        url = f"{SERPAPI_API_ROOT}?{params}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(
                f"Google Jobs search returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError(
                "Google Jobs search could not be reached."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError(
                "Google Jobs search returned an invalid response."
            ) from exc

        if isinstance(payload, dict) and payload.get("error"):
            raise JobDiscoveryError(f"Google Jobs search error: {payload['error']}")

        raw_jobs = payload.get("jobs_results", []) if isinstance(payload, dict) else []
        jobs = []
        for item in raw_jobs:
            description = html_to_text(item.get("description", ""))
            if len(description.split()) < 20:
                continue
            title = str(item.get("title", "")).strip()
            job_location = str(item.get("location") or location or "India").strip()
            company = str(item.get("company_name") or "Unknown").strip() or "Unknown"
            detected = item.get("detected_extensions") or {}
            extensions = item.get("extensions") or []
            posted_date, freshness_verified = parse_google_jobs_posted_at(
                detected.get("posted_at") or next(
                    (
                        extension
                        for extension in extensions
                        if "ago" in str(extension).lower()
                        or str(extension).lower() in {"today", "yesterday"}
                    ),
                    "",
                )
            )
            source_url = str(item.get("share_link") or "").strip()
            apply_options = item.get("apply_options") or []
            apply_url = ""
            if apply_options and isinstance(apply_options[0], dict):
                apply_url = str(apply_options[0].get("link") or "").strip()
            via = str(item.get("via") or "Google Jobs").replace("via ", "").strip()
            schedule = str(detected.get("schedule_type") or " ".join(extensions))
            metadata = infer_discovery_metadata(
                title,
                description,
                job_location,
            )
            job_type = lever_job_type(schedule, title) or metadata["job_type"]
            jobs.append(
                DiscoveredJob(
                    provider_job_id=f"serpapi-{item.get('job_id') or source_url or apply_url}",
                    source=f"Google Jobs · {via}",
                    company_name=company,
                    job_title=title,
                    location=job_location,
                    work_mode=(
                        "Remote"
                        if detected.get("work_from_home")
                        else metadata["work_mode"]
                    ),
                    job_type=job_type,
                    experience_level=(
                        "Internship"
                        if job_type == "Internship"
                        else metadata["experience_level"]
                    ),
                    posted_date=posted_date,
                    job_description=description,
                    date_label="Posted" if freshness_verified else "Active listing",
                    freshness_verified=freshness_verified,
                    source_url=source_url or apply_url,
                    apply_url=apply_url or source_url,
                )
            )
        return jobs

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        """Searches Google Jobs role/location combinations via SerpAPI."""
        self.failures = []
        queries = interleaved_role_location_queries(
            preferences.target_roles,
            preferences.locations,
            limit=self.max_queries,
            preferences=preferences,
        )
        cache_key = (tuple(queries), preferences.maximum_job_age_days, self.max_queries)
        cached = _SERPAPI_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < SERPAPI_CACHE_TTL_SECONDS:
            return list(cached[1])
        jobs, self.failures = collect_parallel(
            queries,
            lambda query: self._fetch_role_location(
                query[0],
                query[1],
                preferences,
            ),
            max_workers=self.max_workers,
            failure_label=lambda query: (
                f"Google Jobs {query[0]} / {query[1] or 'India'}"
            ),
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No Google Jobs searches could be loaded. "
                + " ".join(self.failures)
            )
        if self.cache_enabled and jobs:
            _SERPAPI_CACHE[cache_key] = (time.monotonic(), list(jobs))
        return jobs


class EarlyCareerWebJobProvider:
    """Combines public no-key feeds that can add early-career web coverage."""

    name = "Early-career web sources"

    def __init__(self, providers: list[JobDiscoveryProvider] | None = None):
        self.providers = providers or [
            RemotiveJobProvider(),
            ArbeitnowJobProvider(),
            RemoteOKJobProvider(),
        ]
        self.failures: list[str] = []

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        self.failures = []
        provider = CombinedJobProvider(self.providers)
        jobs = provider.discover(preferences)
        self.failures = list(provider.failures)
        return jobs


class CombinedJobProvider:
    """Combines live providers while keeping failures isolated by source."""

    name = "All configured live sources"

    def __init__(self, providers: list[JobDiscoveryProvider]):
        if not providers:
            raise ValueError("Configure at least one live discovery provider.")
        self.providers = list(providers)
        self.failures: list[str] = []

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        self.failures = []
        jobs = []
        with ThreadPoolExecutor(
            max_workers=min(COMBINED_PROVIDER_MAX_WORKERS, len(self.providers))
        ) as executor:
            future_to_provider = {
                executor.submit(provider.discover, preferences): provider
                for provider in self.providers
            }
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    jobs.extend(future.result())
                    self.failures.extend(getattr(provider, "failures", []))
                except JobDiscoveryError as exc:
                    self.failures.append(str(exc))
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No configured live sources could be loaded. "
                + " ".join(self.failures)
            )
        return jobs


def normalized_terms(values: list[str]) -> set[str]:
    """Creates comparable lowercase terms from preference values."""
    return {str(value).strip().lower() for value in values if str(value).strip()}


LOCATION_ALIAS_GROUPS = (
    {"bengaluru", "bangalore"},
    {"mysuru", "mysore"},
    {"vizag", "visakhapatnam"},
)
INDIA_LOCATION_TERMS = {
    "india",
    "andhra pradesh",
    "bangalore",
    "bengaluru",
    "chennai",
    "delhi",
    "gurugram",
    "gurgaon",
    "haryana",
    "hyderabad",
    "karnataka",
    "kolkata",
    "maharashtra",
    "mumbai",
    "mysore",
    "mysuru",
    "new delhi",
    "noida",
    "pune",
    "telangana",
    "uttar pradesh",
    "visakhapatnam",
    "vizag",
}


def normalized_location_variants(values: list[str]) -> set[str]:
    """Expands common city aliases while preserving explicit user locations."""
    variants = normalized_terms(values)
    for aliases in LOCATION_ALIAS_GROUPS:
        if variants.intersection(aliases):
            variants.update(aliases)
    return variants


def is_india_location(location: str) -> bool:
    """Returns true when a provider location looks India-based."""
    text = str(location or "").lower()
    return any(term in text for term in INDIA_LOCATION_TERMS)


def title_matches_target_role(title: str, target_roles: list[str]) -> bool:
    """Matches common role-title variants without using description keywords."""
    normalized_title = str(title).strip().lower()
    non_practitioner_markers = (
        "trainer",
        "faculty",
        "instructor",
        "professor",
        "teacher",
        "tutor",
    )
    if any(marker in normalized_title for marker in non_practitioner_markers):
        return False
    alias_groups = {
        "data scientist": (
            "data scientist",
            "data science",
            "decision scientist",
        ),
        "machine learning": (
            "machine learning",
            "ml engineer",
            "ml scientist",
        ),
        "ai/ml": (
            "ai/ml",
            "ai ml",
            "ai engineer",
            "ai engineering",
            "artificial intelligence",
            "generative ai",
            "genai",
            "agentic ai",
            "machine learning",
            "ml engineer",
        ),
        "nlp": ("nlp", "natural language"),
        "computer vision": ("computer vision", "vision engineer"),
        "software engineer": (
            "software engineer",
            "software developer",
            "software development engineer",
            "graduate software",
        ),
        "associate software": (
            "associate software",
            "software engineer i",
            "software engineer 1",
            "graduate software",
        ),
    }
    for role in target_roles:
        normalized_role = str(role).strip().lower()
        for family, aliases in alias_groups.items():
            if family in normalized_role and any(
                alias in normalized_title for alias in aliases
            ):
                return True
        significant_tokens = [
            token
            for token in normalized_role.replace("/", " ").split()
            if token not in {"junior", "entry", "level", "engineer"}
        ]
        if len(significant_tokens) >= 2 and all(
            token in normalized_title for token in significant_tokens
        ):
            return True
    return False


def role_relevance(job: DiscoveredJob, preferences: JobPreferences) -> int:
    """Scores discovery relevance without changing the candidate fit score."""
    title = job.job_title.lower()
    description = job.job_description.lower()
    searchable = f"{title} {description}"
    role_terms = normalized_terms(preferences.target_roles)
    skill_terms = normalized_terms(preferences.preferred_skills)
    ai_interest = any(
        term in " ".join(role_terms)
        for term in ("ai/ml", "ai engineer", "machine learning", "nlp", "computer vision")
    )
    analyst_bi_interest = any(
        term in " ".join(role_terms)
        for term in ("analyst", "business intelligence", "data engineer")
    )
    analyst_bi_hybrid = any(
        marker in searchable
        for marker in (
            "data analyst",
            "business intelligence",
            "power bi",
            "tableau",
            "excel",
            "azure data factory",
            "azure databricks",
            "data warehouse",
            "data warehousing",
        )
    )

    role_hits = int(title_matches_target_role(title, list(role_terms)))
    skill_hits = sum(1 for skill in skill_terms if skill in description)
    confidence_bonus = {
        "Verified selected level": 20,
        "Likely entry-level": 12,
        "Experience not stated": 0,
        "Experience requirement detected": -25,
    }.get(experience_confidence(job), 0)
    source_bonus = 8 if source_priority(job) == 2 else 0
    title_bonus = 0
    if any(
        marker in title
        for marker in (
            "fresher",
            "freshers",
            "intern",
            "graduate",
            "junior",
            "associate",
            "engineer i",
            "scientist i",
        )
    ):
        title_bonus = 10
    interest_bonus = 0
    if ai_interest:
        if any(
            marker in searchable
            for marker in (
                "ai engineer",
                "artificial intelligence",
                "generative ai",
                "genai",
                "agentic ai",
                "machine learning",
                "ml engineer",
                "deep learning",
                "nlp",
                "natural language",
                "computer vision",
            )
        ):
            interest_bonus += 12
        if analyst_bi_hybrid and not analyst_bi_interest:
            interest_bonus -= 22
    raw_score = (
        role_hits * 45
        + skill_hits * 10
        + confidence_bonus
        + source_bonus
        + title_bonus
        + interest_bonus
    )
    score = min(100, max(0, raw_score))
    if ai_interest and analyst_bi_hybrid and not analyst_bi_interest:
        score = min(score, 68)
    return score


def job_matches_preferences(
    job: DiscoveredJob,
    preferences: JobPreferences,
    *,
    today: date | None = None,
    allow_location_expansion: bool = False,
) -> tuple[bool, str]:
    """Applies deterministic freshness and preference filters."""
    today = today or date.today()
    if is_broad_market_source(job.source):
        company_issue = broad_source_company_quality_issue(job.company_name)
        if company_issue:
            return False, company_issue
        title_issue = broad_source_title_quality_issue(job.job_title)
        if title_issue:
            return False, title_issue
    if job.freshness_verified and isinstance(job.posted_date, date):
        age_days = (today - job.posted_date).days
        if age_days < 0:
            return False, "Posting date is in the future"
        if age_days > preferences.maximum_job_age_days:
            return False, "Outside the selected freshness window"

    if (
        job.work_mode
        and job.work_mode not in preferences.work_modes
    ):
        return False, f"Work mode excluded: {job.work_mode}"
    if job.job_type and job.job_type not in preferences.job_types:
        return False, f"Job type excluded: {job.job_type}"
    inferred_entry_level = has_entry_level_evidence(
        job.job_title,
        job.job_description,
    ) or has_likely_entry_level_evidence(
        job.job_title,
        job.job_description,
    )
    if job.experience_level and job.experience_level not in preferences.experience_levels:
        return False, f"Experience level excluded: {job.experience_level}"
    if (
        not job.experience_level
        and inferred_entry_level
        and not set(preferences.experience_levels).intersection(
            {"Internship", "Fresher / Entry level"}
        )
    ):
        return False, "Entry-level role excluded by selected experience levels"

    requested_locations = normalized_location_variants(preferences.locations)
    job_location = job.location.lower()
    remote_requested = "remote" in requested_locations
    location_match = any(
        location in job_location or job_location in location
        for location in requested_locations
        if location != "remote"
    )
    if job.work_mode == "Remote":
        unrestricted_remote = any(
            marker in job_location
            for marker in ("worldwide", "anywhere", "global", "india")
        )
        if remote_requested or (
            "Remote" in preferences.work_modes and unrestricted_remote
        ):
            location_match = True
    if (
        requested_locations
        and not location_match
        and allow_location_expansion
        and is_india_location(job.location)
    ):
        location_match = True
    if requested_locations and not location_match:
        return False, f"Location excluded: {job.location}"

    rejection = preference_rejection_reason(
        job_title=job.job_title,
        job_description=job.job_description,
        preferences=preferences,
    )
    if rejection:
        return False, rejection
    if not title_matches_target_role(
        job.job_title,
        preferences.target_roles,
    ):
        return False, "Job title is outside the selected target roles"
    return True, ""


def experience_confidence(job: DiscoveredJob) -> str:
    """Classifies whether a result has positive selected-level evidence."""
    required_years = required_experience_years(job.job_title, job.job_description)
    entry_evidence = has_entry_level_evidence(job.job_title, job.job_description)
    likely_evidence = has_likely_entry_level_evidence(
        job.job_title,
        job.job_description,
    )
    if has_manual_review_level_marker(job.job_title):
        return "Experience requirement detected"
    if is_broad_market_source(job.source) and broad_source_recommendation_issue(job):
        return "Experience not stated"
    if is_broad_market_source(job.source) and not (
        entry_evidence or likely_evidence
    ):
        if required_years is None:
            return "Experience not stated"
        return "Experience requirement detected"
    if job.experience_level in {"Internship", "Fresher / Entry level"}:
        return "Verified selected level"
    if entry_evidence:
        return "Verified selected level"
    if (
        likely_evidence
        and (
            required_years is None
            or required_years <= ENTRY_LEVEL_REVIEW_MAX_YEARS
        )
    ):
        return "Likely entry-level"
    if required_years is None:
        return "Experience not stated"
    return "Experience requirement detected"


def experience_priority(job: DiscoveredJob) -> int:
    """Sorts clearer early-career evidence above manual-review results."""
    return {
        "Verified selected level": 3,
        "Likely entry-level": 2,
        "Experience not stated": 1,
        "Experience requirement detected": 0,
    }.get(experience_confidence(job), 0)


def source_priority(job: DiscoveredJob) -> int:
    """Prefers direct company feeds over broad aggregator sources."""
    if is_direct_company_source(job.source):
        return 2
    if is_broad_market_source(job.source):
        return 1
    return 0


def is_direct_company_source(source: str) -> bool:
    """Returns true for company-career ATS feeds we can attribute directly."""
    return str(source or "").lower().startswith(
        tuple(prefix.lower() for prefix in DIRECT_COMPANY_SOURCE_PREFIXES)
    )


def is_broad_market_source(source: str) -> bool:
    """Returns true for broad-market aggregators that need extra verification."""
    return str(source or "").lower().startswith(
        ("adzuna", "jooble", "remotive", "arbeitnow", "remoteok", "google jobs")
    )


def broad_source_company_quality_issue(company_name: str) -> str:
    """Flags broad-market listings with non-employer-looking names."""
    company = str(company_name or "").strip()
    normalized = company.lower()
    if not company or normalized in {
        "unknown",
        "confidential",
        "company",
        "unspecified",
    }:
        return "Company name is missing or generic"
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    junk_markers = (
        "frontend",
        "backend",
        "production",
        "railwayapp",
        "uprailwayapp",
        "localhost",
        "vercelapp",
        "netlifyapp",
        "renderapp",
        "herokuapp",
    )
    marker_hits = sum(1 for marker in junk_markers if marker in compact)
    if marker_hits >= 2:
        return "Company name looks like a deployment artifact"
    if len(compact) > 28 and not re.search(r"\s", company):
        return "Company name looks machine-generated"
    if re.fullmatch(r"\d+(?:\.[a-z0-9]+)+", normalized):
        return "Company name looks like an aggregator artifact"
    if normalized.endswith((".app", ".com", ".in", ".org", ".net")):
        domain_like = re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", normalized)
        if domain_like:
            return "Company name looks like a website instead of an employer"
    return ""


def broad_source_title_quality_issue(job_title: str) -> str:
    """Flags broad-market titles that are too vague or listing-like."""
    title = re.sub(r"\s+", " ", str(job_title or "").strip().lower())
    if not title:
        return "Job title is missing"
    vague_markers = (
        "reputed company",
        "urgent hiring",
        "immediate hiring",
        "walk in",
        "walk-in",
        "multiple openings",
        "hiring for",
    )
    if any(marker in title for marker in vague_markers):
        return "Job title looks like a generic hiring advertisement"
    if re.search(r"\b(?:job|jobs)\s+(?:in|for)\b", title):
        return "Job title looks like a search-result page"
    return ""


def broad_source_recommendation_issue(job: DiscoveredJob) -> str:
    """Flags broad-market rows that should stay inspectable but not recommended."""
    company = re.sub(r"\s+", " ", str(job.company_name or "").strip().lower())
    title = re.sub(r"\s+", " ", str(job.job_title or "").strip().lower())
    if re.match(r"^\d{3,}\b", company):
        return "Company name looks like a legal-entity artifact"
    if company in {
        "remote target jobs",
        "bebee",
        "jobaaj",
        "shine",
        "simplyhired",
    }:
        return "Company name looks like a job board"
    if "/" in title and any(
        marker in title
        for marker in ("jr java developer", "java developer", "programmer")
    ):
        return "Title combines multiple roles"
    return ""


def deduplicate_jobs(jobs: list[DiscoveredJob]) -> list[DiscoveredJob]:
    """Removes repeated provider IDs, URLs, or company-title combinations."""
    unique = []
    seen = set()
    seen_role_variants = set()
    seen_broad_roles = set()
    for job in jobs:
        title_without_brackets = re.sub(
            r"\[[^\]]+\]|\([^)]*\)",
            " ",
            job.job_title.lower(),
        )
        normalized_title = re.sub(
            r"\s+",
            " ",
            re.sub(r"[^a-z0-9]+", " ", title_without_brackets),
        ).strip()
        raw_title_key = re.sub(
            r"\s+",
            " ",
            re.sub(r"[^a-z0-9]+", " ", job.job_title.lower()),
        ).strip()
        normalized_company = re.sub(
            r"\s+",
            " ",
            re.sub(
                r"\b(?:private|pvt|limited|ltd|inc|llc|corp|corporation|india)\b|[^a-z0-9]+",
                " ",
                job.company_name.lower(),
            ),
        ).strip()
        identity = (
            job.source_url.strip().lower()
            or f"{job.company_name}|{job.job_title}|{job.location}".lower()
        )
        role_identity = (normalized_company, normalized_title)
        provider_identity = (
            job.source.lower(),
            job.provider_job_id.lower(),
        )
        broad_source = is_broad_market_source(job.source)
        is_tracking_variant = raw_title_key != normalized_title or normalized_company != re.sub(
            r"\s+",
            " ",
            re.sub(r"[^a-z0-9]+", " ", job.company_name.lower()),
        ).strip()
        if (
            identity in seen
            or provider_identity in seen
            or (is_tracking_variant and role_identity in seen_role_variants)
            or (broad_source and role_identity in seen_broad_roles)
        ):
            continue
        seen.add(identity)
        seen.add(provider_identity)
        seen_role_variants.add(role_identity)
        if broad_source:
            seen_broad_roles.add(role_identity)
        unique.append(job)
    return unique


def discover_jobs(
    preferences: JobPreferences,
    provider: JobDiscoveryProvider,
    *,
    today: date | None = None,
    limit: int = DEFAULT_DISCOVERY_LIMIT,
) -> tuple[list[DiscoveredJob], list[str]]:
    """Discovers, filters, deduplicates, and ranks normalized jobs."""
    accepted = []
    expanded_location_matches = []
    rejected = []
    for job in deduplicate_jobs(provider.discover(preferences)):
        matches, reason = job_matches_preferences(
            job,
            preferences,
            today=today,
        )
        if not matches:
            if reason.startswith("Location excluded:") and is_india_location(
                job.location
            ):
                expanded_matches, expanded_reason = job_matches_preferences(
                    job,
                    preferences,
                    today=today,
                    allow_location_expansion=True,
                )
                if expanded_matches:
                    expanded_location_matches.append(
                        replace(
                            job,
                            relevance_score=role_relevance(job, preferences),
                        )
                    )
                    continue
                reason = expanded_reason
            rejected.append(
                f"{job.source.split(' · ', 1)[0]} · "
                f"{job.company_name} · {job.job_title}: {reason}"
            )
            continue
        accepted.append(
            replace(
                job,
                relevance_score=role_relevance(job, preferences),
            )
        )
    accepted.sort(
        key=lambda job: (
            experience_priority(job),
            source_priority(job),
            job.relevance_score,
            job.posted_date,
        ),
        reverse=True,
    )
    expanded_location_matches.sort(
        key=lambda job: (
            experience_priority(job),
            source_priority(job),
            job.relevance_score,
            job.posted_date,
        ),
        reverse=True,
    )
    if len(accepted) < TARGET_DISCOVERY_RESULTS:
        accepted.extend(
            expanded_location_matches[
                : max(0, TARGET_DISCOVERY_RESULTS - len(accepted))
            ]
        )
    return accepted[: max(1, int(limit))], rejected


class LocalSampleJobProvider:
    """Deterministic catalog for validating discovery UX without scraping."""

    name = "Local sample catalog"

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        today = date.today()
        return [
            DiscoveredJob(
                provider_job_id="sample-ml-001",
                source=self.name,
                company_name="Northstar Analytics",
                job_title="Machine Learning Engineer - Entry Level",
                location="Bengaluru, India",
                work_mode="Hybrid",
                job_type="Full-time",
                experience_level="Fresher / Entry level",
                posted_date=today - timedelta(days=2),
                job_description=(
                    "The Machine Learning Engineer will help build, test, and "
                    "evaluate practical machine learning models for analytics "
                    "products. Responsibilities include preparing datasets, "
                    "performing feature engineering, comparing model performance, "
                    "and documenting experiments. The role uses Python, "
                    "scikit-learn, pandas, NumPy, Git, and standard model "
                    "evaluation techniques. The engineer will collaborate with "
                    "data scientists and software developers, communicate results "
                    "clearly, and improve solutions based on review feedback."
                ),
            ),
            DiscoveredJob(
                provider_job_id="sample-ds-002",
                source=self.name,
                company_name="Civic Data Labs",
                job_title="Data Scientist",
                location="Hyderabad, India",
                work_mode="Onsite",
                job_type="Full-time",
                experience_level="Fresher / Entry level",
                posted_date=today - timedelta(days=4),
                job_description=(
                    "The Data Scientist will analyze structured datasets using "
                    "Python and SQL to support product and operational decisions. "
                    "The work includes data cleaning, exploratory data analysis, "
                    "statistical analysis, feature engineering, visualization, "
                    "and predictive modeling. The candidate will validate results, "
                    "prepare clear reports and dashboards, explain findings to "
                    "technical and non-technical teammates, and maintain "
                    "reproducible notebooks and documentation throughout the "
                    "analysis workflow."
                ),
            ),
            DiscoveredJob(
                provider_job_id="sample-ai-003",
                source=self.name,
                company_name="Orbit AI Studio",
                job_title="AI/ML Intern",
                location="Remote, India",
                work_mode="Remote",
                job_type="Internship",
                experience_level="Internship",
                posted_date=today - timedelta(days=1),
                job_description=(
                    "The AI and Machine Learning Intern will support supervised "
                    "experiments across natural language processing and deep "
                    "learning projects. Responsibilities include preparing data, "
                    "running model training and evaluation, reviewing errors, and "
                    "documenting results. The internship uses Python, TensorFlow, "
                    "PyTorch, pandas, and NumPy. The intern will work with senior "
                    "engineers, participate in technical discussions, test model "
                    "outputs carefully, and present concise findings from each "
                    "experiment."
                ),
            ),
            DiscoveredJob(
                provider_job_id="sample-senior-004",
                source=self.name,
                company_name="Enterprise Model Systems",
                job_title="Senior Data Science Manager",
                location="Bengaluru, India",
                work_mode="Hybrid",
                job_type="Full-time",
                experience_level="2-4 years",
                posted_date=today - timedelta(days=3),
                job_description=(
                    "Lead senior data science teams, manage roadmaps, and own "
                    "enterprise machine learning delivery."
                ),
            ),
            DiscoveredJob(
                provider_job_id="sample-old-005",
                source=self.name,
                company_name="Archive Insights",
                job_title="Junior Data Analyst",
                location="Bengaluru, India",
                work_mode="Onsite",
                job_type="Full-time",
                experience_level="Fresher / Entry level",
                posted_date=today - timedelta(days=45),
                job_description=(
                    "Use Python, SQL, data cleaning, exploratory data analysis, "
                    "and visualization to support reporting."
                ),
            ),
        ]
