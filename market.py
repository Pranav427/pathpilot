"""Job-market settings (country) used by discovery, defaults and display.

Set PATHPILOT_COUNTRY (GB or IN). The default is GB (United Kingdom).
"""

import os
from dataclasses import dataclass

COUNTRY_ENV = "PATHPILOT_COUNTRY"
DEFAULT_COUNTRY = "GB"


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    adzuna_country: str
    jooble_country: str
    google_gl: str
    default_locations: tuple[str, ...]
    placeholder_locations: frozenset[str]
    location_terms: frozenset[str]
    location_alias_groups: tuple[frozenset[str], ...]
    timezone: str
    location_example: str
    entry_level_query_templates: tuple[str, ...]


UK = Market(
    code="GB",
    name="United Kingdom",
    adzuna_country="gb",
    jooble_country="gb",
    google_gl="uk",
    default_locations=("United Kingdom", "Remote"),
    placeholder_locations=frozenset(
        {"united kingdom", "uk", "your city, state, country", "your city, country"}
    ),
    location_terms=frozenset(
        {
            "united kingdom", "uk", "u.k.", "great britain", "britain", "england",
            "scotland", "wales", "northern ireland", "london", "manchester",
            "birmingham", "leeds", "sheffield", "liverpool", "bristol", "edinburgh",
            "glasgow", "cardiff", "belfast", "newcastle", "nottingham", "leicester",
            "cambridge", "oxford", "reading", "southampton", "brighton", "coventry",
            "aberdeen", "exeter", "bath", "york", "milton keynes", "slough",
        }
    ),
    location_alias_groups=(
        frozenset({"london", "greater london"}),
        frozenset({"uk", "united kingdom", "u.k.", "great britain"}),
        frozenset({"newcastle", "newcastle upon tyne"}),
    ),
    timezone="Europe/London",
    location_example="London, Manchester, Leeds, Remote (UK)",
    entry_level_query_templates=(
        "graduate {role}",
        "junior {role}",
        "{role} graduate scheme",
        "{role} placement year",
        "{role} internship",
        "entry level {role}",
    ),
)

INDIA = Market(
    code="IN",
    name="India",
    adzuna_country="in",
    jooble_country="in",
    google_gl="in",
    default_locations=("India", "Remote"),
    placeholder_locations=frozenset({"india", "your city, state, country"}),
    location_terms=frozenset(
        {
            "india", "andhra pradesh", "bangalore", "bengaluru", "chennai", "delhi",
            "gurugram", "gurgaon", "haryana", "hyderabad", "karnataka", "kolkata",
            "maharashtra", "mumbai", "mysore", "mysuru", "new delhi", "noida", "pune",
            "telangana", "uttar pradesh", "visakhapatnam", "vizag",
        }
    ),
    location_alias_groups=(
        frozenset({"bengaluru", "bangalore"}),
        frozenset({"mysuru", "mysore"}),
        frozenset({"vizag", "visakhapatnam"}),
    ),
    timezone="Asia/Kolkata",
    location_example="Bengaluru, Hyderabad, Remote",
    entry_level_query_templates=(
        "{role} fresher",
        "junior {role}",
        "entry level {role}",
        "{role} internship",
        "associate {role}",
    ),
)

MARKETS = {market.code: market for market in (UK, INDIA)}


def get_market() -> Market:
    """The active market; unknown values fall back to the UK."""
    code = os.getenv(COUNTRY_ENV, DEFAULT_COUNTRY).strip().upper()
    code = {"UK": "GB"}.get(code, code)
    return MARKETS.get(code, UK)
