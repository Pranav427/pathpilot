"""Reed.co.uk job search (UK) as a PathPilot discovery provider.

API: https://www.reed.co.uk/developers/jobseeker (free key, HTTP Basic auth with
the key as username and an empty password). Search returns a short description
snippet, so full text is fetched from the per-job endpoint for a bounded number
of results; failures there keep the snippet.

JSON field names follow Reed's published API and community clients
(jobId, jobTitle, employerName, locationName, date, jobDescription, jobUrl).
Parsing is defensive because the field list is not published in the docs.
"""

import base64
import json
import os
import re
import time
from dataclasses import replace
from datetime import date, datetime
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from job_discovery import (
    BROAD_PROVIDER_TIMEOUT_SECONDS,
    BROAD_SEARCH_MAX_WORKERS,
    DiscoveredJob,
    JobDiscoveryError,
    collect_parallel,
    html_to_text,
    infer_discovery_metadata,
    interleaved_role_location_queries,
    lever_job_type,
)
from job_preferences import JobPreferences

REED_API_KEY_ENV = "REED_API_KEY"
REED_API_ROOT = "https://www.reed.co.uk/api/1.0"
REED_RESULTS_PER_QUERY = 50
REED_MAX_QUERIES = 12
REED_MAX_DETAIL_REQUESTS = 25
REED_CACHE_TTL_SECONDS = 15 * 60
_REED_CACHE: dict[tuple, tuple[float, list[DiscoveredJob]]] = {}


def reed_is_configured() -> bool:
    return bool(os.getenv(REED_API_KEY_ENV, "").strip())


def clear_reed_cache() -> None:
    _REED_CACHE.clear()


def reed_salary_line(item: dict) -> str:
    """Render Reed's structured salary as text the salary parser understands."""
    try:
        low = float(item.get("minimumSalary") or 0)
        high = float(item.get("maximumSalary") or 0)
    except (TypeError, ValueError):
        return ""
    if str(item.get("currency", "GBP")).upper() not in {"", "GBP"}:
        return ""
    low, high = (low or high), (high or low)
    if not low:
        return ""
    if low >= 5000:
        unit = "per annum"
    elif 5 <= low <= 500:
        unit = "per hour"
    else:
        return ""
    span = f"£{low:,.0f}" if low == high else f"£{low:,.0f} - £{high:,.0f}"
    if unit == "per hour":
        span = span.replace(",", "")
    return f"Salary: {span} {unit}"


def parse_reed_date(value) -> tuple[date, bool]:
    """Parse Reed's dd/mm/yyyy (or ISO) date. Returns (date, is_valid)."""
    text = str(value or "").strip()
    if not text:
        return date.today(), False
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date(), True
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date(), True
    except ValueError:
        return date.today(), False


class ReedJobProvider:
    """Searches Reed.co.uk, the UK's largest dedicated job board."""

    name = "Reed search"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: int = BROAD_PROVIDER_TIMEOUT_SECONDS,
        opener=urlopen,
        max_queries: int = REED_MAX_QUERIES,
        max_workers: int = BROAD_SEARCH_MAX_WORKERS,
        max_detail_requests: int = REED_MAX_DETAIL_REQUESTS,
        graduate_only: bool = False,
    ):
        if not str(api_key).strip():
            raise ValueError("Configure REED_API_KEY.")
        self.api_key = str(api_key).strip()
        self.timeout = timeout
        self.opener = opener
        self.max_queries = max(1, int(max_queries))
        self.max_workers = max(1, int(max_workers))
        self.max_detail_requests = max(0, int(max_detail_requests))
        self.graduate_only = graduate_only
        self.cache_enabled = opener is urlopen
        self.failures: list[str] = []

    # -- HTTP ---------------------------------------------------------
    def _get_json(self, url: str):
        token = base64.b64encode(f"{self.api_key}:".encode("utf-8")).decode("ascii")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {token}",
                "User-Agent": "PathPilot/1.0",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise JobDiscoveryError(f"Reed returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise JobDiscoveryError("Reed could not be reached.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JobDiscoveryError("Reed returned an invalid response.") from exc

    # -- search -------------------------------------------------------
    def _fetch_role_location(
        self, role: str, location: str, preferences: JobPreferences
    ) -> list[DiscoveredJob]:
        params = {"keywords": role, "resultsToTake": REED_RESULTS_PER_QUERY}
        place = str(location).strip()
        if place and place.lower() not in {"united kingdom", "uk", "remote"}:
            params["locationName"] = place
        if self.graduate_only:
            params["graduate"] = "true"
        payload = self._get_json(f"{REED_API_ROOT}/search?{urlencode(params)}")
        results = payload.get("results", []) if isinstance(payload, dict) else []
        jobs = []
        for item in results if isinstance(results, list) else []:
            job = self._normalise(item)
            if job is not None:
                jobs.append(job)
        return jobs

    def _normalise(self, item: dict) -> DiscoveredJob | None:
        if not isinstance(item, dict):
            return None
        job_id = item.get("jobId")
        title = str(item.get("jobTitle", "")).strip()
        if not job_id or not title:
            return None
        description = html_to_text(item.get("jobDescription", ""))
        salary_line = reed_salary_line(item)
        if salary_line and "£" not in description[:400]:
            description = f"{salary_line}. {description}".strip()
        location = str(item.get("locationName", "")).strip()
        company = str(item.get("employerName", "")).strip() or "Unknown"
        posted, valid = parse_reed_date(item.get("date"))
        url = str(item.get("jobUrl", "")).strip() or f"https://www.reed.co.uk/jobs/{job_id}"
        metadata = infer_discovery_metadata(title, description, location)
        return DiscoveredJob(
            provider_job_id=f"reed-{job_id}",
            source="Reed",
            company_name=company,
            job_title=title,
            location=location,
            work_mode=metadata["work_mode"],
            job_type=lever_job_type("", title) or metadata["job_type"],
            experience_level=metadata["experience_level"],
            posted_date=posted,
            job_description=description,
            date_label="Posted" if valid else "Active listing",
            freshness_verified=valid,
            source_url=url,
            apply_url=url,
        )

    # -- full descriptions ---------------------------------------------
    def _with_full_description(self, job: DiscoveredJob) -> list[DiscoveredJob]:
        job_id = job.provider_job_id.removeprefix("reed-")
        detail = self._get_json(f"{REED_API_ROOT}/jobs/{job_id}")
        if not isinstance(detail, dict):
            return [job]
        full = html_to_text(detail.get("jobDescription", ""))
        prefix_match = re.match(r"Salary: .*?per (?:annum|hour)\. ", job.job_description)
        salary_prefix = prefix_match.group(0) if prefix_match else ""
        snippet = job.job_description[len(salary_prefix):]
        if len(full) > len(snippet):
            if not salary_prefix:
                line = reed_salary_line(detail)
                salary_prefix = f"{line}. " if line and "£" not in full[:400] else ""
            description = f"{salary_prefix}{full}"
        else:
            description = job.job_description
        contract = " ".join(
            str(detail.get(key, ""))
            for key in ("contractType", "jobType")
            if detail.get(key)
        )
        job_type = job.job_type or lever_job_type(contract, job.job_title)
        external = str(detail.get("externalUrl") or "").strip()
        metadata = infer_discovery_metadata(job.job_title, description, job.location)
        return [
            replace(
                job,
                job_description=description,
                job_type=job_type,
                apply_url=external or job.apply_url,
                work_mode=job.work_mode or metadata["work_mode"],
                experience_level=job.experience_level or metadata["experience_level"],
            )
        ]

    def discover(self, preferences: JobPreferences) -> list[DiscoveredJob]:
        self.failures = []
        queries = interleaved_role_location_queries(
            preferences.target_roles,
            preferences.locations,
            limit=self.max_queries,
            preferences=preferences,
        )
        cache_key = (tuple(queries), self.graduate_only, self.max_queries)
        cached = _REED_CACHE.get(cache_key) if self.cache_enabled else None
        if cached and time.monotonic() - cached[0] < REED_CACHE_TTL_SECONDS:
            return list(cached[1])

        jobs, self.failures = collect_parallel(
            queries,
            lambda query: self._fetch_role_location(query[0], query[1], preferences),
            max_workers=self.max_workers,
            failure_label=lambda query: f"{query[0]} / {query[1] or 'Any location'}",
        )
        if self.failures and not jobs:
            raise JobDiscoveryError(
                "No Reed role searches could be loaded. " + " ".join(self.failures)
            )

        unique = list({job.provider_job_id: job for job in jobs}.values())
        # Newest first, then fetch full text for the most recent postings only.
        unique.sort(key=lambda job: job.posted_date, reverse=True)
        enriched, detail_failures = collect_parallel(
            unique[: self.max_detail_requests],
            self._with_full_description,
            max_workers=self.max_workers,
            failure_label=lambda job: job.provider_job_id,
        )
        # Keep the snippet-only job when its detail request failed.
        by_id = {job.provider_job_id: job for job in enriched}
        result = [by_id.get(job.provider_job_id, job) for job in unique]
        if detail_failures:
            self.failures.extend(detail_failures[:3])
        if self.cache_enabled and result:
            _REED_CACHE[cache_key] = (time.monotonic(), list(result))
        return result
