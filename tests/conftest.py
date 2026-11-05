"""Shared test setup. Tests use saved fixtures, and any network attempt fails loudly."""
import json
import socket
from pathlib import Path

import pytest

from scanner.config import load_cities, load_config
from scanner.location import LocationResolver

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SITE_TESTS = Path(__file__).resolve().parent / "site"


# P8: every test in tests/site/ is a web app test and gets the `site` marker. pytest.ini's
# `-m "not site"` leaves them out of a plain `pytest`, which is what the Daily scan runs, so a
# broken site script can never stop a scan. Deploy site runs them with `pytest -m site`.
@pytest.hookimpl(tryfirst=True)  # before pytest's own -m deselection reads the markers
def pytest_collection_modifyitems(items):
    for item in items:
        if SITE_TESTS in Path(str(item.fspath)).resolve().parents:
            item.add_marker(pytest.mark.site)


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
        self.posted = []

    def _reply(self, url, payload=None):
        self.requested.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                if callable(response):
                    response = response(url, payload)
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"no fixture for {url}")

    def get_json(self, url):
        return self._reply(url)

    def post_json(self, url, payload):
        self.posted.append(payload)
        return self._reply(url, payload)
