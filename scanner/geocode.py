"""Look up coordinates for cities missing from config/cities.yaml, caching every answer.

Service: Nominatim. Usage policy: https://operations.osmfoundation.org/policies/nominatim/
Data (c) OpenStreetMap contributors, ODbL. The policy requires caching and attribution, and asks
that the service can be switched off without a software update: that is geocoding.enabled.

Requests go through the shared client, so robots.txt applies. Nominatim's robots.txt currently
disallows /search, which is why config ships with this switched off (D-022).
"""
from __future__ import annotations

from urllib.parse import urlencode

from .http_client import FormatChanged, HttpError, RobotsBlocked
from .location import STATES

HOST = "nominatim.openstreetmap.org"
STATE_NAMES = {code: name.title() for name, code in STATES.items()}


def cache_key(city: str, state: str) -> str:
    return f"{city.strip().lower()}, {state.strip().upper()}"


class Geocoder:
    def __init__(self, client, cache: dict, settings: dict):
        self.client = client
        self.cache = cache
        self.enabled = settings["enabled"]
        self.budget = settings["max_lookups_per_run"]
        self.available = self.enabled  # False once blocked, switched off, or out of budget
        self.stats = {"cache_hits": 0, "lookups": 0, "not_found": 0, "failed": 0, "blocked": False}
        if self.enabled and hasattr(client, "set_min_interval"):
            client.set_min_interval(HOST, settings["min_seconds_between_requests"])

    def lookup(self, city: str, state: str):
        """Return {lat, lng}, or None when the place is unknown or could not be looked up."""
        key = cache_key(city, state)
        if key in self.cache:
            self.stats["cache_hits"] += 1
            return self.cache[key]
        if not self.available:
            return None
        if self.stats["lookups"] >= self.budget:
            self.available = False  # the rest wait for the next run
            return None

        query = urlencode({"city": city, "state": STATE_NAMES.get(state, state), "country": "United States",
                           "format": "jsonv2", "limit": 1})
        self.stats["lookups"] += 1
        try:
            results = self.client.get_json(f"https://{HOST}/search?{query}")
        except RobotsBlocked:
            self.stats["blocked"] = True
            self.available = False
            return None
        except HttpError:
            self.stats["failed"] += 1  # not cached, so a temporary failure gets another chance
            return None
        if not isinstance(results, list):
            raise FormatChanged("unexpected Nominatim response")
        if not results:
            self.stats["not_found"] += 1
            self.cache[key] = None  # the policy forbids repeating queries, including failed ones
            return None
        self.cache[key] = {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
        return self.cache[key]
