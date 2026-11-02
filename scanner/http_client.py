"""Shared polite HTTP client. Every network call in the pipeline goes through here."""
from __future__ import annotations

import json
import socket
import time
from collections import Counter
import urllib.error
import urllib.request
import urllib.robotparser
from typing import Callable, Optional
from urllib.parse import urlparse

USER_AGENT = "InternshipScanner/0.3 (+https://github.com/lucaseastman9884-cloud/Internship-Scanner)"
MIN_SECONDS_BETWEEN_REQUESTS = 1.0
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 50_000_000
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
JSON_ACCEPT = "application/json"
# Some hosts answer 406 to a JSON-only Accept header. A 4xx means "no rules" under RFC 9309,
# so asking the wrong way could silently skip a host's real rules.
ROBOTS_ACCEPT = "text/plain, */*"
NETWORK_ERRORS = (urllib.error.URLError, socket.timeout, TimeoutError, OSError)


class HttpError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class RobotsBlocked(HttpError):
    """The host's robots.txt does not allow this request, so it was never sent."""


class FormatChanged(HttpError):
    """The source answered, but not in the shape we expect."""


def _urllib_transport(url: str, headers: dict, timeout: float, body: Optional[bytes] = None) -> tuple:
    # urlopen's default opener keeps no cookies, so none are ever stored or sent.
    request = urllib.request.Request(url, headers=headers, data=body)
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
        self.request_counts: Counter = Counter()

    def set_min_interval(self, host: str, seconds: float) -> None:
        """Slow down one host further, for example when its usage policy asks for it."""
        self._interval[host] = max(seconds, self._interval.get(host, MIN_SECONDS_BETWEEN_REQUESTS))

    def _send(self, url: str, accept: str = JSON_ACCEPT, body: Optional[bytes] = None) -> tuple:
        host = urlparse(url).netloc
        gap = self._interval.get(host, MIN_SECONDS_BETWEEN_REQUESTS)
        if host in self._last_request:
            wait = gap - (self._clock() - self._last_request[host])
            if wait > 0:
                self._sleep(wait)
        headers = {"User-Agent": USER_AGENT, "Accept": accept}
        self.request_counts[host] += 1
        try:
            if body is None:
                return self._transport(url, headers, TIMEOUT_SECONDS)
            headers["Content-Type"] = "application/json"
            return self._transport(url, headers, TIMEOUT_SECONDS, body)
        finally:
            self._last_request[host] = self._clock()

    def _load_robots(self, base: str, host: str):
        """Returns a parser, None when no rules apply, or False when rules could not be read.

        Follows RFC 9309: a 4xx means no rules exist; a 5xx or network failure means stay away.
        """
        try:
            status, body = self._send(base + "/robots.txt", ROBOTS_ACCEPT)
        except NETWORK_ERRORS:
            return False
        if 200 <= status < 300:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(body.decode("utf-8", "replace").splitlines())
            delay = parser.crawl_delay(USER_AGENT)
            if delay and float(delay) > MIN_SECONDS_BETWEEN_REQUESTS:
                self.set_min_interval(host, float(delay))
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
        return self._request_json(url)

    def post_json(self, url: str, payload: dict):
        return self._request_json(url, json.dumps(payload, sort_keys=True).encode("utf-8"))

    def _request_json(self, url: str, body: Optional[bytes] = None):
        self._check_robots(url)
        problem, last_status = "", None
        for _attempt in range(2):  # the first try plus at most one retry
            try:
                status, content = self._send(url, body=body)
            except NETWORK_ERRORS as err:
                problem, last_status = f"network error ({type(err).__name__})", None
                continue
            if status in RETRYABLE_STATUS:
                problem, last_status = f"HTTP {status}", status
                continue
            if status != 200:
                raise HttpError(f"HTTP {status} from {url}", status)
            try:
                return json.loads(content.decode("utf-8", "replace"))
            except ValueError:
                raise FormatChanged(f"response from {url} was not valid JSON") from None
        raise HttpError(f"{problem} from {url} after 1 retry", last_status)
