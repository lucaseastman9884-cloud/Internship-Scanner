"""Adapter registry.

SmartRecruiters is deliberately absent (D-015): its API's robots.txt disallows us, so no request
may go there. The adapter file stays, tested offline, in case that rule ever changes.
"""
from .ashby import AshbyAdapter
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .workday import WorkdayAdapter

ADAPTERS = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
    "workday": WorkdayAdapter,
}
