"""Shared test setup. Tests use saved fixtures, and any network attempt fails loudly."""
import json
import socket
from pathlib import Path

import pytest

from scanner.config import load_cities, load_config
from scanner.location import LocationResolver

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture(scope="session")
def cities():
    return load_cities(ROOT / "config" / "cities.yaml")


@pytest.fixture(scope="session")
def cfg(cities):
    return load_config(ROOT / "config" / "config.yaml", cities)


@pytest.fixture(scope="session")
def resolver(cfg, cities):
    return LocationResolver(cfg, cities)


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeClient:
    """Stands in for HttpClient, serving saved responses by URL."""

    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def get_json(self, url):
        self.requested.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"no fixture for {url}")
