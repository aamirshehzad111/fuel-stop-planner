"""Normalization of US place and state names.

Price lists, Census files and people spell the same town differently
("St. Louis" / "Saint Louis", "Mc Calla" / "McCalla"). `place_key` maps all
such variants to one lookup key.
"""

import re
import unicodedata

US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}  # fmt: skip

_STATE_BY_NAME = {name.lower(): code for code, name in US_STATES.items()}
_STATE_BY_NAME["washington dc"] = "DC"

_ABBREVIATIONS = {
    "st": "saint",
    "ste": "sainte",
    "ft": "fort",
    "mt": "mount",
    "mtn": "mountain",
    "pt": "point",
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
}

# Legal/statistical descriptions the Census appends to place names.
_CENSUS_DESCRIPTION = re.compile(
    r"\s+(?:city and borough|(?:consolidated|metropolitan|metro|unified) government"
    r"|charter township|city|town|township|village|borough|CDP|CCD|municipality"
    r"|plantation|urban county|unorganized territory|gore|grant|location|purchase)$",
    re.IGNORECASE,
)


def place_key(name: str) -> str:
    """Lookup key for a place name: case, punctuation, spacing and common abbreviations ignored."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[.']", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return "".join(_ABBREVIATIONS.get(word, word) for word in text.split())


def parse_state(text: str) -> str | None:
    """USPS code for a US state or DC given its code or name, else None."""
    cleaned = re.sub(r"\s+", " ", text.replace(".", "")).strip()
    if cleaned.upper() in US_STATES:
        return cleaned.upper()
    return _STATE_BY_NAME.get(cleaned.lower())


def census_place_name(name: str) -> str:
    """Town name from a Census place name ("Oklahoma City city" -> "Oklahoma City")."""
    return _CENSUS_DESCRIPTION.sub("", name.replace("(balance)", "").strip()).strip()
