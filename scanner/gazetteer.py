"""Offline U.S. place coordinates from the Census Gazetteer (D-022). No requests at run time.

The file and its source are described in data/reference/README.md.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "2026_Gaz_place_national.txt"
REQUIRED_COLUMNS = {"USPS", "NAME", "FUNCSTAT", "ALAND", "INTPTLAT", "INTPTLONG"}
_BALANCE = re.compile(r"\s+\(balance\)$")
_KIND = re.compile(r"\s+(city|town|village|borough|cdp|municipality|comunidad|zona urbana|urban county|"
                   r"(?:metro|metropolitan|consolidated|unified) government)$", re.I)
_CONSOLIDATED = re.compile(r"(government|urban county)(\s+\(balance\))?$", re.I)
_LONG_FORMS = (("saint ", "st "), ("sainte ", "ste "), ("mount ", "mt "), ("fort ", "ft "))


def _key(name: str) -> str:
    """'St. Louis', 'Saint Louis', and 'ST LOUIS' are one place, as are 'Lee's' and 'Lees'."""
    text = re.sub(r"[.'’]", "", name.strip().lower()).replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    for long_form, short_form in _LONG_FORMS:
        if text.startswith(long_form):
            text = short_form + text[len(long_form):]
    return text


def _place_name(raw: str) -> str:
    """'West Des Moines city' becomes 'West Des Moines'. The word 'city' goes only once, so 'Kansas City city' stays right."""
    consolidated = _CONSOLIDATED.search(raw)
    name = _KIND.sub("", _BALANCE.sub("", raw))
    if consolidated:  # 'Nashville-Davidson metropolitan government (balance)' is known as Nashville
        name = re.split(r"[-/]", name)[0]
    return re.sub(r"^Urban (?=Honolulu)", "", name)


class Gazetteer:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.places: dict = {}
        ranks: dict = {}
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="|")
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path} is missing columns {sorted(missing)}")
            for row in reader:
                key = (_key(_place_name(row["NAME"])), row["USPS"])
                # A state can have a town and a CDP with one name. A functioning government, then the larger area, wins.
                rank = (row["FUNCSTAT"] != "S", int(row["ALAND"]))
                if key not in ranks or rank > ranks[key]:
                    ranks[key] = rank
                    self.places[key] = {"lat": float(row["INTPTLAT"]), "lng": float(row["INTPTLONG"])}

    def lookup(self, city: str, state: str) -> Optional[dict]:
        """Return {city, state, lat, lng}, or None when the file has no such place."""
        state = state.strip().upper()
        key = _key(city)
        found = self.places.get((key, state))
        if found is None and key.endswith(" city"):  # 'New York City' is 'New York city' in the file
            found = self.places.get((key[: -len(" city")], state))
        return {"city": city.strip(), "state": state, **found} if found else None


@lru_cache(maxsize=1)
def default() -> Gazetteer:
    return Gazetteer()
