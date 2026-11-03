"""Parse location text and place it against the config's areas, using Census Gazetteer coordinates."""
from __future__ import annotations

import math
import re

from . import gazetteer
from .text import has_phrase

STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}
STATE_CODES = set(STATES.values())
STATE_NAMES = {code: name for name, code in STATES.items()}
US_NAMES = {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"}
BOTH_CITY_AND_STATE = {"new york", "washington"}  # alone, these usually mean the city
_REMOTE = re.compile(r"\b(remote|work from home|wfh|telecommute|virtual)\b", re.I)
_ZIP = re.compile(r"\s+\d{5}(?:-\d{4})?$")
_PARENS = re.compile(r"\s*\([^)]*\)")
_AFTER_COUNTRY = re.compile(r"(,\s*(?:USA|US|United States))\s+[-–—]\s+.*$", re.I)
_DASH_US = re.compile(r"\s+[-–—]\s+(?:U\.?S\.?A?\.?|United States)$", re.I)
_SITE_WORD = re.compile(r"\s+(?:campus|office|hq|headquarters)$", re.I)
_DASH = re.compile(r"\s+[-–—]\s+")
_US_DASHED = re.compile(r"^US-([A-Z]{2})-([^-]+)")
_USA_SPACED = re.compile(r"^USA ([A-Z]{2}) (.+)$")
_ENDS_US = re.compile(r"^(.+?)\s+(?:United States|USA)$", re.I)
# Workday's list view says "3 Locations" until the detail page names them.
_PLACEHOLDER = re.compile(r"^(\d+|multiple)\s+locations?$", re.I)


# One to three capitalized words, then a comma and a state code: "Cincinnati, OH", "St. Louis, MO",
# "King of Prussia, PA", "Winston-Salem, NC". A trailing hyphen ends a word, so "Tax- Cincinnati, OH"
# gives Cincinnati. The city needs a lowercase letter, so "Remote (IL, CA, NY)" names no city.
_WORD = r"[A-Z][A-Za-z.'’]*(?:-[A-Z][A-Za-z.'’]*)*"
_TITLE_PLACE = re.compile(rf"(?<![\w-])((?:{_WORD} (?:(?:of|de|la|del|du) )?){{0,2}}{_WORD}), ?([A-Z]{{2}})(?![\w-])")


def title_place(title: str):
    """The (city, state code) a title names, or None. Text only: it is never geocoded (D-022)."""
    for m in _TITLE_PLACE.finditer(title or ""):
        if m.group(2) in STATE_CODES and re.search(r"[a-z]", m.group(1)):
            return m.group(1), m.group(2)
    return None


def title_names_city(named_city: str, city: str) -> bool:
    """True when the title's text ends with the city, cut at a space or hyphen.

    The pattern can't tell "Winston-Salem" from "Advisor-Pella", so "Wealth Management
    Advisor-Pella" counts as naming Pella, and "Central Salt Lake City" as Salt Lake City."""
    text, city = named_city.lower(), city.lower()
    return any(text[i:] == city for i in range(len(text)) if i == 0 or text[i - 1] in " -")


def _miles(a: dict, b: dict) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def _state_code(word: str):
    if word.upper() in STATE_CODES:
        return word.upper()
    return STATES.get(word.lower())


def _tidy(text: str) -> str:
    """Rewrite the shapes real boards use into 'City, ST'. Every pattern here was seen on a live board."""
    text = _PARENS.sub("", text).strip()
    text = _AFTER_COUNTRY.sub(r"\1", text)
    text = _DASH_US.sub("", text)
    text = _SITE_WORD.sub("", text).strip()
    m = _US_DASHED.match(text)  # 'US-IL-Chicago-10 SWacker-3100'
    if m:
        return f"{m.group(2)}, {m.group(1)}"
    m = _USA_SPACED.match(text)  # 'USA NM Albuquerque'
    if m:
        return f"{m.group(2)}, {m.group(1)}"
    pieces = _DASH.split(text)
    if len(pieces) >= 2 and pieces[0] in STATE_CODES:
        # 'IL - Chicago', and 'MO - Southeast - Cape Girardeau - Cape Girardeau Main'
        return f"{pieces[2] if len(pieces) >= 4 else pieces[-1]}, {pieces[0]}"
    if "," in text:
        return text
    if len(pieces) >= 2:
        return pieces[0]  # 'Chicago - 155 Wacker' is a city and a building
    m = _ENDS_US.match(text)  # 'Tampa Florida United States'
    if m:
        text = m.group(1)
    for size in (2, 1):  # 'New York New York', 'Kansas City MO', 'Ogden UT'
        words = text.split()
        if len(words) > size and _state_code(" ".join(words[-size:])):
            # A lowercase or full-word match needs care: 'Iowa City' has no state after it.
            ending = " ".join(words[-size:])
            if m or ending in STATE_CODES:
                return f"{' '.join(words[:-size])}, {_state_code(ending)}"
    return text


def _parse_place(text: str) -> dict:
    parts = [_ZIP.sub("", p).strip() for p in _tidy(text).split(",")]
    parts = [p for p in parts if p]
    country = None
    if parts and parts[-1].lower() in US_NAMES:
        country = "United States"
        parts = parts[:-1]
    if len(parts) == 1 and parts[0].lower() in STATES and parts[0].lower() not in BOTH_CITY_AND_STATE:
        return {"city": None, "state": STATES[parts[0].lower()], "country": "United States"}
    state = None
    if len(parts) >= 2:
        last = parts[-1]
        if last.upper() in STATE_CODES:
            state = last.upper()
        elif last.lower() in STATES:
            state = STATES[last.lower()]
        if state:
            parts = parts[:-1]
            country = "United States"
        elif country is None:
            country = last
            parts = parts[:-1]
    # With a state, the city sits right before it: 'Des Moines #3, Park Avenue, Des Moines, IA'.
    city = (parts[-1] if state else parts[0]) if parts else None
    return {"city": city, "state": state, "country": country}


class LocationResolver:
    def __init__(self, cfg: dict, cities: list, geocoder=None, gaz=None):
        self.geocoder = geocoder
        self.gazetteer = gaz or gazetteer.default()
        self.remote_states = [s.upper() for s in cfg["remote_allowed_states"]]
        self.by_key = {(c["city"].lower(), c["state"].upper()): c for c in cities}
        self.by_city: dict = {}
        for c in cities:
            self.by_city.setdefault(c["city"].lower(), c)
        self.home = self.by_key[(cfg["home"]["city"].lower(), cfg["home"]["state"].upper())]
        self.radius = cfg["radius_miles"]
        self.whole_states = {s.upper() for s in cfg["include_whole_states"]}
        self.areas = []
        for area in cfg["target_areas"]:
            city, state = [p.strip() for p in area["center"].split(",")]
            self.areas.append({"name": area["name"], "radius": area["radius_miles"],
                               "center": self.by_key[(city.lower(), state.upper())]})

    def _lookup(self, place: dict):
        name = (place["city"] or "").lower()
        if place["state"]:
            found = self.by_key.get((name, place["state"]))
            return found or (self.gazetteer.lookup(place["city"], place["state"]) if place["city"] else None)
        # A bare city is accepted only when no country says it is somewhere else.
        return None if place["country"] not in (None, "United States") else self.by_city.get(name)

    def _coordinates(self, place: dict, allow_lookup: bool):
        """Gazetteer first. The geocoder stays off (D-022) unless config turns it on. Returns a point or None."""
        known = self._lookup(place)
        if known:
            return known
        if allow_lookup and self.geocoder and place["city"] and place["state"]:
            found = self.geocoder.lookup(place["city"], place["state"])
            if found:
                return {**found, "state": place["state"]}
        return None

    def _names_a_target_metro(self, text: str) -> bool:
        return any(has_phrase(text, area["center"]["city"]) for area in self.areas)

    def _classify(self, place: dict, text: str, allow_lookup: bool = True) -> dict:
        point = self._coordinates(place, allow_lookup)
        if point:
            miles = _miles(point, self.home)
            place = {**place, "state": point["state"], "country": "United States",
                     "lat": point["lat"], "lng": point["lng"], "miles_from_home": miles, "resolved": True}
            for area in self.areas:
                if _miles(point, area["center"]) <= area["radius"]:
                    return {**place, "tier": "target_area", "detail": area["name"]}
            if point["state"] in self.whole_states:
                return {**place, "tier": "whole_state", "detail": point["state"]}
            detail = f"{miles:.0f} miles from {self.home['city']}"
            return {**place, "tier": "home_radius" if miles <= self.radius else None, "detail": detail}

        # D-022: an unknown distance never passes a distance check. Such a listing stays only if
        # it is in a whole-state area such as Iowa, or names a target metro.
        place = {**place, "lat": None, "lng": None, "miles_from_home": None, "resolved": False}
        if place["state"] in self.whole_states:
            return {**place, "tier": "whole_state", "detail": place["state"]}
        if place["country"] not in (None, "United States"):
            return {**place, "tier": None, "detail": f"outside the United States ({place['country']})"}
        if self._names_a_target_metro(text):
            return {**place, "tier": "unknown", "detail": "location unknown"}
        return {**place, "tier": None, "distance_unknown": True, "detail": "location unknown"}

    def _split_city_lists(self, pieces: list) -> list:
        """'Chicago, New York City' lists two cities, but would parse as Chicago in New York State."""
        out = []
        for piece in pieces:
            parts = [p.strip() for p in piece.split(",")]
            if len(parts) == 2 and parts[0].lower() in self.by_city and parts[1].lower().startswith("new york"):
                out += [parts[0], parts[1]]
            else:
                out.append(piece)
        return out

    def resolve(self, location_raw: str, remote_hint: bool = False, allow_lookup: bool = True) -> dict:
        """Return the best-matching place. A multi-city posting counts if any of its cities qualifies."""
        pieces = [p.strip() for p in re.split(r";|\s\|\s|\n", location_raw or "") if p.strip()]
        physical = [p for p in pieces if not _REMOTE.search(p)]
        mentions_remote = len(physical) < len(pieces)
        rank = {"target_area": 0, "whole_state": 1, "home_radius": 2, "unknown": 3, "placeholder": 4, None: 5}
        places = []
        for piece in self._split_city_lists(physical):
            if _PLACEHOLDER.match(piece):
                # Tier "placeholder" earns a look at the detail page, which names the real cities.
                # If it never does, filtering excludes the listing as location unknown.
                places.append({"city": None, "state": None, "country": None, "tier": "placeholder", "distance_unknown": True,
                               "detail": "location unknown", "resolved": True, "lat": None, "lng": None, "miles_from_home": None})
            else:
                places.append(self._classify(_parse_place(piece), piece, allow_lookup))
        places.sort(key=lambda p: rank[p["tier"]])  # stable, so posting order breaks ties
        best = places[0] if places else {"city": None, "state": None, "country": None, "tier": None, "distance_unknown": True,
                                         "detail": "no location given", "resolved": False, "lat": None, "lng": None,
                                         "miles_from_home": None}
        # A multi-city posting is as close to home as its closest city (D-016).
        distances = [p["miles_from_home"] for p in places if p["miles_from_home"] is not None]
        nearest = min(distances) if distances else None
        # The source's remote flag wins: a remote job tagged with a home city is still remote.
        is_remote = remote_hint or (mentions_remote and best["tier"] is None)
        remote_state = self._remote_state(pieces, best) if is_remote else None
        return {**best, "state": best["state"] or remote_state, "miles_from_home": nearest,
                "is_remote": is_remote, "remote_state": remote_state}

    def _remote_state(self, pieces: list, best: dict):
        """D-029: the allowed state a remote job is tied to, as in 'Iowa - Work From Home', or None."""
        for code in self.remote_states:
            if best["state"] == code:
                return code
            for piece in pieces:
                # The code must be capitals, or the 'ia' in 'Remote - ia' style noise would match.
                if re.search(rf"\b{code}\b", piece) or has_phrase(piece, STATE_NAMES[code]):
                    return code
        return None


def remote_tag(state_code: str) -> str:
    """'IA' becomes 'remote_iowa'."""
    return "remote_" + STATE_NAMES[state_code].replace(" ", "_")
