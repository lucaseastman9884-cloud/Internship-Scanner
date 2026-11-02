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


def _miles(a: dict, b: dict) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def _parse_place(text: str) -> dict:
    parts = [_ZIP.sub("", p).strip() for p in text.split(",")]
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
    city = parts[0] if parts else None
    return {"city": city, "state": state, "country": country}


class LocationResolver:
    def __init__(self, cfg: dict, cities: list):
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
            return self.by_key.get((name, place["state"]))
        # A bare city is accepted only when no country says it is somewhere else.
        return None if place["country"] not in (None, "United States") else self.by_city.get(name)

    def _classify(self, place: dict) -> dict:
        known = self._lookup(place)
        if known:
            place = {**place, "state": known["state"], "country": "United States"}
            for area in self.areas:
                if _miles(known, area["center"]) <= area["radius"]:
                    return {**place, "tier": "target_area", "detail": area["name"], "resolved": True}
            if known["state"] in self.whole_states:
                return {**place, "tier": "whole_state", "detail": known["state"], "resolved": True}
            miles = _miles(known, self.home)
            detail = f"{miles:.0f} miles from {self.home['city']}"
            return {**place, "tier": "home_radius" if miles <= self.radius else None, "detail": detail, "resolved": True}
        if place["state"] in self.whole_states:
            return {**place, "tier": "whole_state", "detail": place["state"], "resolved": False}
        return {**place, "tier": None, "detail": "city not in config/cities.yaml", "resolved": False}

    def resolve(self, location_raw: str, remote_hint: bool = False) -> dict:
        """Return the best-matching place. A multi-city posting counts if any of its cities qualifies."""
        pieces = [p.strip() for p in re.split(r";|\s\|\s|\n", location_raw or "") if p.strip()]
        physical = [p for p in pieces if not _REMOTE.search(p)]
        mentions_remote = len(physical) < len(pieces)
        rank = {"target_area": 0, "whole_state": 1, "home_radius": 2, None: 3}
        places = [self._classify(_parse_place(p)) for p in physical]
        places.sort(key=lambda p: rank[p["tier"]])  # stable, so posting order breaks ties
        best = places[0] if places else {"city": None, "state": None, "country": None,
                                         "tier": None, "detail": "no location given", "resolved": False}
        # The source's remote flag wins: a remote job tagged with a home city is still remote.
        is_remote = remote_hint or (mentions_remote and best["tier"] is None)
        return {**best, "is_remote": is_remote}
