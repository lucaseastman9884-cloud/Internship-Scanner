"""Parse location text and place it against the config's areas, using the local city table."""
from __future__ import annotations

import math
import re

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
    def __init__(self, cfg: dict, cities: list, geocoder=None):
        self.geocoder = geocoder
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
        # While geocoding is unavailable, distance to an unlisted city cannot be measured. Keeping
        # every such listing would flood the results with Dallas, Montreal, and "Europe", so only
        # states with a table city inside a target area or the home radius stay in play.
        self.nearby_states = {c["state"].upper() for c in cities if self._near_a_target(c)}

    def _near_a_target(self, point: dict) -> bool:
        return (_miles(point, self.home) <= self.radius
                or any(_miles(point, area["center"]) <= area["radius"] for area in self.areas))

    def _lookup(self, place: dict):
        name = (place["city"] or "").lower()
        if place["state"]:
            return self.by_key.get((name, place["state"]))
        # A bare city is accepted only when no country says it is somewhere else.
        return None if place["country"] not in (None, "United States") else self.by_city.get(name)

    def _coordinates(self, place: dict, allow_lookup: bool):
        """City table first, then the geocoder's cache or service. Returns a point or None."""
        known = self._lookup(place)
        if known:
            return known
        if allow_lookup and self.geocoder and place["city"] and place["state"]:
            found = self.geocoder.lookup(place["city"], place["state"])
            if found:
                return {**found, "state": place["state"]}
        return None

    def _geocoder_available(self) -> bool:
        return bool(self.geocoder and self.geocoder.available)

    def _classify(self, place: dict, allow_lookup: bool = True) -> dict:
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

        place = {**place, "lat": None, "lng": None, "miles_from_home": None, "resolved": False}
        if place["state"] in self.whole_states:
            return {**place, "tier": "whole_state", "detail": place["state"]}
        if place["country"] not in (None, "United States"):
            return {**place, "tier": None, "detail": f"outside the United States ({place['country']})"}
        # Part D: a lookup that really failed keeps the listing as "Location unknown".
        if self._geocoder_available() or place["state"] in self.nearby_states:
            return {**place, "tier": "unknown", "detail": "location unknown"}
        where = f"{place['state']} has no target area" if place["state"] else "no state was given"
        return {**place, "tier": None, "detail": f"city not in config/cities.yaml, and {where}"}

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
        rank = {"target_area": 0, "whole_state": 1, "home_radius": 2, "unknown": 3, None: 4}
        places = []
        for piece in self._split_city_lists(physical):
            if _PLACEHOLDER.match(piece):
                places.append({"city": None, "state": None, "country": None, "tier": "unknown", "detail": "location unknown",
                               "resolved": True, "lat": None, "lng": None, "miles_from_home": None})
            else:
                places.append(self._classify(_parse_place(piece), allow_lookup))
        places.sort(key=lambda p: rank[p["tier"]])  # stable, so posting order breaks ties
        best = places[0] if places else {"city": None, "state": None, "country": None, "tier": None, "detail": "no location given",
                                         "resolved": False, "lat": None, "lng": None, "miles_from_home": None}
        # A multi-city posting is as close to home as its closest city (D-016).
        distances = [p["miles_from_home"] for p in places if p["miles_from_home"] is not None]
        nearest = min(distances) if distances else None
        # The source's remote flag wins: a remote job tagged with a home city is still remote.
        is_remote = remote_hint or (mentions_remote and best["tier"] is None)
        return {**best, "miles_from_home": nearest, "is_remote": is_remote}
