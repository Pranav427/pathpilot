"""Finds a stated salary in job text and annualises it (GBP).

Works on any source because it reads the advert text. Salaries that are not
stated ("competitive") return None; ambiguous numbers are ignored.
"""

import re
from dataclasses import dataclass

# Indicative UK Skilled Worker salary thresholds (GBP a year). These change often
# and vary by occupation: always verify on gov.uk before relying on them.
GENERAL_SALARY_THRESHOLD = 41_700
NEW_ENTRANT_SALARY_THRESHOLD = 33_400
THRESHOLDS_NOTE = (
    "Indicative Skilled Worker thresholds (from July 2025); occupation-specific "
    "rules apply. Check gov.uk."
)

HOURS_PER_YEAR = 1950  # 37.5 hours x 52 weeks
DAYS_PER_YEAR = 260
WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12

_AMOUNT = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|m|bn|million|billion)?\b"
_RANGE = re.compile(
    rf"£\s?{_AMOUNT}(?:\s*(?:-|–|—|to)\s*£?\s?{_AMOUNT})?",
    re.IGNORECASE,
)

_PERIODS = (
    ("year", re.compile(r"^\s*(?:per\s+annum|p\.?a\.?\b|per\s+year|a\s+year|annually|/\s*(?:yr|year|annum)|per\s+yr)", re.I)),
    ("hour", re.compile(r"^\s*(?:per\s+hour|an\s+hour|/\s*h(?:ou)?r|p\.?h\.?\b|hourly|per\s+hr)", re.I)),
    ("day", re.compile(r"^\s*(?:per\s+day|a\s+day|/\s*day|p\.?d\.?\b|day\s+rate|daily)", re.I)),
    ("week", re.compile(r"^\s*(?:per\s+week|a\s+week|/\s*(?:wk|week)|weekly|p\.?w\.?\b)", re.I)),
    ("month", re.compile(r"^\s*(?:per\s+month|a\s+month|/\s*month|monthly|p\.?m\.?\b)", re.I)),
)
_NOT_PAY = re.compile(r"bonus|signing|relocation|referral|voucher|allowance|stipend for|commission", re.I)


@dataclass(frozen=True)
class SalaryInfo:
    low: float
    high: float
    period: str  # year, hour, day, week, month
    annual_low: float
    annual_high: float


def _value(number: str, suffix: str | None) -> float | None:
    amount = float(number.replace(",", ""))
    suffix = (suffix or "").lower()
    if suffix in {"m", "bn", "million", "billion"}:
        return None  # revenue or budget figures, not pay
    if suffix == "k":
        amount *= 1000
    return amount


def _annualise(amount: float, period: str) -> float:
    return {
        "year": amount,
        "hour": amount * HOURS_PER_YEAR,
        "day": amount * DAYS_PER_YEAR,
        "week": amount * WEEKS_PER_YEAR,
        "month": amount * MONTHS_PER_YEAR,
    }[period]


def _detect_period(text: str, end: int, amount: float) -> str:
    window = text[end : end + 40]
    for period, pattern in _PERIODS:
        if pattern.match(window):
            return period
    # No stated period: only accept values that are plausibly annual.
    return "year" if 8_000 <= amount <= 500_000 else ""


def parse_salary(text: str) -> SalaryInfo | None:
    """Return the first clearly stated salary, or None."""
    value = str(text or "")
    for match in _RANGE.finditer(value):
        low = _value(match.group(1), match.group(2))
        if low is None:
            continue
        high = low
        if match.group(3):
            candidate = _value(match.group(3), match.group(4) or match.group(2))
            if candidate is None:
                continue
            high = candidate
            # "£28-32k" style: the first number inherits the shared k suffix.
            if (match.group(4) or "").lower() == "k" and not match.group(2) and low < 1000:
                low *= 1000
        if high < low:
            low, high = high, low
        context = value[max(0, match.start() - 30) : match.end() + 30]
        if _NOT_PAY.search(context):
            continue
        period = _detect_period(value, match.end(), high)
        if not period:
            continue
        # Hourly/day/week/month values must look like pay for that period.
        if period == "hour" and not 5 <= low <= 500:
            continue
        if period == "day" and not 50 <= low <= 3000:
            continue
        return SalaryInfo(
            low=low,
            high=high,
            period=period,
            annual_low=_annualise(low, period),
            annual_high=_annualise(high, period),
        )
    return None


def format_salary(info: SalaryInfo) -> str:
    def money(amount: float) -> str:
        return f"£{amount:,.0f}" if amount >= 100 or float(amount).is_integer() else f"£{amount:,.2f}"

    unit = {"year": "a year", "hour": "an hour", "day": "a day", "week": "a week", "month": "a month"}[info.period]
    span = money(info.low) if info.low == info.high else f"{money(info.low)}–{money(info.high)}"
    text = f"{span} {unit}"
    if info.period != "year":
        text += f" (about {money(info.annual_low)}–{money(info.annual_high)} a year)" if info.low != info.high else f" (about {money(info.annual_low)} a year)"
    return text


def below_sponsorship_threshold(info: SalaryInfo | None) -> bool:
    """True only when the stated pay is clearly below even the lowest threshold."""
    return bool(info) and info.annual_high < NEW_ENTRANT_SALARY_THRESHOLD
