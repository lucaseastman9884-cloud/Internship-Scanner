import json
import socket

import pytest

from scanner.http_client import USER_AGENT, HttpClient, HttpError, RobotsBlocked

# The exact rules served by the SmartRecruiters API host on 2026-11-02.
SMARTRECRUITERS_ROBOTS = b"User-agent: LinkedInBot\nAllow: /v1/companies/\nUser-agent: *\nDisallow: /\n"


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class FakeTransport:
    """Serves queued replies per URL. robots.txt returns 404 unless a test sets it."""

    def __init__(self, replies=None, robots=(404, b"")):
        self.replies = replies or []
        self.robots = robots
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, headers, timeout))
        if url.endswith("/robots.txt"):
            return self.robots
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def page_calls(self):
        return [c for c in self.calls if not c[0].endswith("/robots.txt")]


def make_client(transport):
    clock = FakeClock()
    return HttpClient(transport=transport, sleep=clock.sleep, clock=clock.time), clock


OK = (200, json.dumps({"ok": True}).encode())


def test_sends_identifying_user_agent_and_a_timeout():
    transport = FakeTransport([OK])
    client, _ = make_client(transport)
    assert client.get_json("https://a.test/x") == {"ok": True}
    _, headers, timeout = transport.page_calls[0]
    assert headers["User-Agent"] == USER_AGENT and "Internship-Scanner" in USER_AGENT
    assert "@" not in USER_AGENT
    assert timeout > 0


def test_waits_at_least_one_second_between_requests_to_a_host():
    transport = FakeTransport([OK, OK])
    client, clock = make_client(transport)
    client.get_json("https://a.test/1")
    client.get_json("https://a.test/2")
    assert len(clock.slept) == 2  # robots.txt to page 1, then page 1 to page 2
    assert all(s >= 1.0 for s in clock.slept)


def test_different_hosts_do_not_wait_for_each_other():
    transport = FakeTransport([OK, OK])
    client, clock = make_client(transport)
    client.get_json("https://a.test/1")
    slept_before = len(clock.slept)
    client.get_json("https://b.test/1")
    assert len(clock.slept) == slept_before + 1  # only b.test's robots.txt to its page


@pytest.mark.parametrize("failure", [(503, b""), (429, b""), socket.timeout(), OSError("reset")])
def test_retries_once_then_succeeds(failure):
    transport = FakeTransport([failure, OK])
    client, _ = make_client(transport)
    assert client.get_json("https://a.test/x") == {"ok": True}
    assert len(transport.page_calls) == 2


def test_gives_up_after_one_retry():
    transport = FakeTransport([(503, b""), (503, b""), OK])
    client, _ = make_client(transport)
    with pytest.raises(HttpError, match="after 1 retry"):
        client.get_json("https://a.test/x")
    assert len(transport.page_calls) == 2


def test_does_not_retry_a_404():
    transport = FakeTransport([(404, b""), OK])
    client, _ = make_client(transport)
    with pytest.raises(HttpError) as err:
        client.get_json("https://a.test/x")
    assert err.value.status == 404
    assert len(transport.page_calls) == 1


def test_bad_json_raises():
    transport = FakeTransport([(200, b"<html>")])
    client, _ = make_client(transport)
    with pytest.raises(HttpError, match="not valid JSON"):
        client.get_json("https://a.test/x")


def test_smartrecruiters_real_robots_rules_block_the_request():
    transport = FakeTransport([OK], robots=(200, SMARTRECRUITERS_ROBOTS))
    client, _ = make_client(transport)
    with pytest.raises(RobotsBlocked):
        client.get_json("https://api.smartrecruiters.com/v1/companies/RRDonnelley/postings?limit=100")
    assert transport.page_calls == []  # the request itself was never sent


def test_robots_404_means_no_rules():
    transport = FakeTransport([OK], robots=(404, b""))
    client, _ = make_client(transport)
    assert client.get_json("https://a.test/x") == {"ok": True}


def test_robots_server_error_means_stay_away():
    transport = FakeTransport([OK], robots=(500, b""))
    client, _ = make_client(transport)
    with pytest.raises(RobotsBlocked):
        client.get_json("https://a.test/x")
    assert transport.page_calls == []


def test_robots_is_read_once_per_host():
    transport = FakeTransport([OK, OK])
    client, _ = make_client(transport)
    client.get_json("https://a.test/1")
    client.get_json("https://a.test/2")
    assert sum(c[0].endswith("/robots.txt") for c in transport.calls) == 1


def test_crawl_delay_is_honored_when_longer_than_one_second():
    transport = FakeTransport([OK], robots=(200, b"User-agent: *\nAllow: /\nCrawl-delay: 5\n"))
    client, clock = make_client(transport)
    client.get_json("https://a.test/1")
    assert clock.slept == [5.0]
