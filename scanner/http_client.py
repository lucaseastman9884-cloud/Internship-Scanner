"""Shared polite HTTP client. Every network call in the pipeline goes through here."""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
import urllib.robotparser
from typing import Callable, Optional
from urllib.parse import urlparse

USER_AGENT = "InternshipScanner/0.2 (+https://github.com/lucaseastman9884-cloud/Internship-Scanner)"
MIN_SECONDS_BETWEEN_REQUESTS = 1.0
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 50_000_000
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
NETWORK_ERRORS = (urllib.error.URLError, socket.timeout, TimeoutError, OSError)


class HttpError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class RobotsBlocked(HttpError):
    """The host's robots.txt does not allow this request, so it was never sent."""


def _urllib_transport(url: str, headers: dict, timeout: float) -> tuple:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as err:
        return err.code, b""


class HttpClient:
    """Identifying User-Agent, spacing per host, timeouts, robots.txt, and at most one retry."""

    def __init__(self, transport: Callable = _urllib_transport, sleep: Callable = time.sleep,
                 clock: Callable = time.monotonic):
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict = {}
        self._robots: dict = {}
        self._interval: dict = {}

    def _send(self, url: str) -> tuple:
        host = urlparse(url).netloc
        gap = self._interval.get(host, MIN_SECONDS_BETWEEN_REQUESTS)
        if host in self._last_request:
            wait = gap - (self._clock() - self._last_request[host])
            if wait > 0:
                self._sleep(wait)
        try:
            return self._transport(
                url, {"User-Agent": USER_AGENT, "Accept": "application/json, text/plain"}, TIMEOUT_SECONDS
            )
        finally:
            self._last_request[host] = self._clock()

    def _load_robots(self, base: str, host: str):
        """Returns a parser, None when no rules apply, or False when rules could not be read.

        Follows RFC 9309: a 4xx means no rules exist; a 5xx or network failure means stay away.
        """
        try:
            status, body = self._send(base + "/robots.txt")
        except NETWORK_ERRORS:
            return False
        if 200 <= status < 300:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(body.decode("utf-8", "replace").splitlines())
            delay = parser.crawl_delay(USER_AGENT)
            if delay and float(delay) > MIN_SECONDS_BETWEEN_REQUESTS:
                self._interval[host] = float(delay)
            return parser
        return None if 400 <= status < 500 else False

    def _check_robots(self, url: str) -> None:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            self._robots[base] = self._load_robots(base, parsed.netloc)
        rules = self._robots[base]
        if rules is False:
            raise RobotsBlocked(f"could not read {base}/robots.txt, so the request was not sent")
        if rules is not None and not rules.can_fetch(USER_AGENT, url):
            raise RobotsBlocked(f"{base}/robots.txt does not allow this request, so it was not sent")

    def get_json(self, url: str):
        self._check_robots(url)
        problem, last_status = "", None
        for _attempt in range(2):  # the first try plus at most one retry
            try:
                status, body = self._send(url)
            except NETWORK_ERRORS as err:
                problem, last_status = f"network error ({type(err).__name__})", None
                continue
            if status in RETRYABLE_STATUS:
                problem, last_status = f"HTTP {status}", status
                continue
            if status != 200:
                raise HttpError(f"HTTP {status} from {url}", status)
            try:
                return json.loads(body.decode("utf-8", "replace"))
            except ValueError:
                raise HttpError(f"response from {url} was not valid JSON") from None
        raise HttpError(f"{problem} from {url} after 1 retry", last_status)
