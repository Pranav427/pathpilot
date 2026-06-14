import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MIN_DESCRIPTION_CHARS = 500
AGGREGATOR_COMPANIES = {
    "Freshershunt",
    "Kickcharm",
    "Fhlinks",
}
TITLE_COMPANY_PATTERNS = [
    r"^(.+?)\s+Off\s+Campus",
    r"^(.+?)\s+Careers",
    r"^(.+?)\s+Recruitment",
    r"^(.+?)\s+Internship",
    r"^(.+?)\s+Mega\s+Off",
]
COMPANY_DISPLAY_NAMES = {
    "hp": "HP",
    "hpe": "HPE",
    "hcltech": "HCLTech",
    "ibm": "IBM",
    "iqvia": "IQVIA",
    "bnp paribas": "BNP Paribas",
    "kpit": "KPIT",
    "ntt data": "NTT DATA",
    "goodlight ai": "Goodlight AI",
    "domynspa": "Domyn SpA",
    "domyn spa": "Domyn SpA",
    "rolls": "Rolls-Royce",
    "rolls royce": "Rolls-Royce",
}
LISTING_TITLE_PATTERNS = (
    r"^\d[\d,+]*\s+.+\s+jobs?\s+in\b",
    r"^\d[\d,+]*\s+.+\s+jobs?$",
    r"^search jobs?$",
    r"^job search\b",
    r"^explore .+ careers",
)
LISTING_PATH_PATTERNS = (
    r"^/jobs/search/?$",
    r"^/jobs/?$",
    r"^/job/?$",
    r"^/jobs/results/?$",
    r"^/joblist/?$",
    r"^/careers?/?$",
    r"^/careers?/students?/?$",
    r"/careers?/students?/?$",
    r"/careers?\.html$",
    r"^/locations?/",
    r"/locations?/",
)


@dataclass
class FetchedJob:
    company_name: str
    job_title: str
    job_description: str
    source_url: str
    extraction_quality: str


class JobPageParser(HTMLParser):
    """Small stdlib HTML extractor for public job pages."""

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.current_tag = ""
        self.title_parts = []
        self.h1_parts = []
        self.meta = {}
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag.lower()
        if self.current_tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

        attrs_dict = {key.lower(): value for key, value in attrs if key and value}
        if self.current_tag == "meta":
            name = attrs_dict.get("name") or attrs_dict.get("property")
            content = attrs_dict.get("content")
            if name and content:
                self.meta[name.lower()] = unescape(content.strip())

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
        self.current_tag = ""

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = clean_space(data)
        if not text:
            return
        if self.current_tag == "title":
            self.title_parts.append(text)
        elif self.current_tag == "h1":
            self.h1_parts.append(text)
        self.text_parts.append(text)


def clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(str(text))).strip()


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise ValueError("Job URL is empty")
    if any(character.isspace() for character in url):
        raise ValueError(
            "Invalid job URL. Paste only the public http:// or https:// link."
        )
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("Invalid job URL")
    return url


def fetch_html(url: str, timeout: int = 20) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "ApplySmartAI/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                raise ValueError(f"URL did not return HTML content: {content_type}")
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"Could not fetch job URL. HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not fetch job URL: {exc.reason}") from exc


def guess_company(parser: JobPageParser, url: str) -> str:
    for key in ["og:site_name", "application-name"]:
        value = parser.meta.get(key)
        if value:
            return clean_company(value)

    hostname = urlparse(url).netloc.lower().replace("www.", "")
    parts = hostname.split(".")
    if parts:
        return clean_company(parts[0])
    return "Company"


def clean_company(value: str) -> str:
    value = clean_space(value)
    value = re.sub(r"\s*\|\s*.*$", "", value)
    value = re.sub(r"\s*-\s*careers?.*$", "", value, flags=re.IGNORECASE)
    value = value.strip()
    if not value:
        return "Company"
    return COMPANY_DISPLAY_NAMES.get(value.lower(), value.title())


def infer_company_from_title(title: str) -> str:
    """Extracts employer name from common aggregator-page titles."""
    clean = clean_space(title)
    for pattern in TITLE_COMPANY_PATTERNS:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            company = match.group(1)
            company = re.sub(r"(?i)\bis hiring freshers.*$", "", company)
            company = re.sub(r"[:|–—-].*$", "", company)
            company = company.strip()
            if company:
                return clean_company(company)
    return ""


def choose_company(parser: JobPageParser, url: str, job_title: str) -> str:
    """Chooses real employer when source site is an aggregator."""
    source_company = guess_company(parser, url)
    inferred_company = infer_company_from_title(job_title)
    if source_company in AGGREGATOR_COMPANIES and inferred_company:
        return inferred_company
    return source_company


def guess_title(parser: JobPageParser) -> str:
    candidates = []
    candidates.extend(parser.h1_parts[:2])
    for key in ["og:title", "twitter:title"]:
        if parser.meta.get(key):
            candidates.append(parser.meta[key])
    if parser.title_parts:
        candidates.append(" ".join(parser.title_parts))

    for candidate in candidates:
        title = clean_title(candidate)
        if title and len(title) <= 120:
            return title
    return "Role"


def clean_title(value: str) -> str:
    value = clean_space(value)
    value = re.sub(r"\s*\|\s*.*$", "", value)
    value = re.sub(r"\s+-\s+(careers?|jobs?|greenhouse|lever|workable).*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"(?i)^job opening:\s*", "", value)
    return value.strip()


def extract_readable_text(parser: JobPageParser) -> str:
    lines = []
    seen = set()
    for part in parser.text_parts:
        text = clean_space(part)
        if len(text) < 3:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(text)
    return "\n".join(lines)


def quality_for_text(text: str) -> str:
    lower = text.lower()
    signals = [
        "responsibilities",
        "requirements",
        "qualifications",
        "skills",
        "experience",
        "about the role",
        "what you'll do",
        "job description",
    ]
    score = sum(1 for signal in signals if signal in lower)
    if len(text) >= 1500 and score >= 2:
        return "high"
    if len(text) >= MIN_DESCRIPTION_CHARS and score >= 1:
        return "medium"
    return "low"


def is_likely_job_listing(url: str, title: str) -> bool:
    """Returns True for search results and career hubs, not job-detail pages."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    lower_url = url.lower()
    lower_title = clean_space(title).lower()

    if path == "/":
        return True

    if any(
        re.search(pattern, lower_title, flags=re.IGNORECASE)
        for pattern in LISTING_TITLE_PATTERNS
    ):
        return True

    if any(
        re.search(pattern, path, flags=re.IGNORECASE)
        for pattern in LISTING_PATH_PATTERNS
    ):
        return True

    search_query_markers = (
        "linkedin.com/jobs/search",
        "indeed.com/jobs?",
        "indeed.co.in/jobs?",
        "naukri.com/machine-learning-jobs",
        "naukri.com/data-scientist-jobs",
        "naukri.com/fresher-jobs",
        "naukri.com/software-engineer-jobs",
        "internshala.com/jobs/",
        "wellfound.com/jobs?",
        "glassdoor.co.in/job/",
        "/joblist",
        "myworkdayjobs.com/nvidiaexternalcareersite",
    )
    return any(marker in lower_url for marker in search_query_markers)


def fetch_job_from_url(url: str) -> FetchedJob:
    normalized_url = normalize_url(url)
    html = fetch_html(normalized_url)
    parser = JobPageParser()
    parser.feed(html)

    job_title = guess_title(parser)
    if is_likely_job_listing(normalized_url, job_title):
        raise RuntimeError(
            "This URL appears to be a job search, listing, location, or careers "
            "page rather than one job posting. Open a specific job and use its "
            "individual job-detail URL."
        )

    job_description = extract_readable_text(parser)
    quality = quality_for_text(job_description)
    if quality == "low":
        raise RuntimeError(
            "Could not extract a reliable job description from this URL. "
            "The site may block automated access or render the posting with "
            "JavaScript. Copy the complete job description from the page and "
            "paste it manually in the Application workspace."
        )

    return FetchedJob(
        company_name=choose_company(parser, normalized_url, job_title),
        job_title=job_title,
        job_description=job_description,
        source_url=normalized_url,
        extraction_quality=quality,
    )


def display_fetched_job(job: FetchedJob):
    print("\n" + "=" * 60)
    print("           FETCHED JOB DETAILS")
    print("=" * 60)
    print(f"Company          : {job.company_name}")
    print(f"Job Title        : {job.job_title}")
    print(f"Source URL       : {job.source_url}")
    print(f"Extraction       : {job.extraction_quality}")
    print(f"Description size : {len(job.job_description)} characters")
    print("=" * 60)


if __name__ == "__main__":
    url = input("Enter job URL: ").strip()
    fetched = fetch_job_from_url(url)
    display_fetched_job(fetched)
    print("\nPreview:\n")
    print(fetched.job_description[:2000])
