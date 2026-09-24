import datetime as dt
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compliance_chronicle.models import (  # noqa: E402
    Action,
    CalendarEntry,
    ChangeItem,
    Citation,
    Issue,
    SearchLogEntry,
)

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")


def make_citation(**kwargs) -> Citation:
    defaults = dict(
        reference="Tex. Health & Safety Code ch. 437",
        url="https://statutes.capitol.texas.gov/Docs/HS/htm/HS.437.htm",
        source_class="state_statute",
        publisher="Texas Statutes",
    )
    defaults.update(kwargs)
    return Citation(**defaults)


def make_action(**kwargs) -> Action:
    defaults = dict(
        description="Confirm your labels carry the required statements.",
        deadline=dt.date(2026, 10, 1),
        portal_url="https://statutes.capitol.texas.gov/Docs/HS/htm/HS.437.htm",
    )
    defaults.update(kwargs)
    return Action(**defaults)


def make_verified_item(item_id="CHG-001", **kwargs) -> ChangeItem:
    defaults = dict(
        item_id=item_id,
        title="Governing statute re-verified",
        summary="Chapter 437 remains the governing statute.",
        status="verified",
        citation=make_citation(),
        action=make_action(),
    )
    defaults.update(kwargs)
    return ChangeItem(**defaults)


def make_unverified_item(item_id="CHG-002", **kwargs) -> ChangeItem:
    defaults = dict(
        item_id=item_id,
        title="Rumored fee change",
        summary="",
        status="unverified",
        unverified_reason="We could not verify: rumored fee change. No authoritative source found.",
    )
    defaults.update(kwargs)
    return ChangeItem(**defaults)


def make_search_log() -> list:
    classes = (
        ("state_statute", "Texas Statutes ch. 437"),
        ("state_admin_code", "25 TAC 229.661"),
        ("state_agency_guidance", "DSHS cottage food page"),
        ("fee_schedule", "DSHS fee schedule"),
    )
    return [
        SearchLogEntry(
            source_name=name,
            source_class=cls,
            checked_at=dt.date(2026, 8, 28),
            source_url="https://example.test/" + cls,
            result="no change posted",
        )
        for cls, name in classes
    ]


def make_calendar() -> list:
    return [
        CalendarEntry(
            label="Food-handler certificate renewal window",
            deadline=dt.date(2026, 11, 30),
            url="https://www.dshs.texas.gov/food-handler-training",
        )
    ]


@pytest.fixture
def verified_item() -> ChangeItem:
    return make_verified_item()


@pytest.fixture
def unverified_item() -> ChangeItem:
    return make_unverified_item()


@pytest.fixture
def sample_issue() -> Issue:
    return Issue(
        issue_number=1,
        period_label="2026-08",
        publish_date=dt.date(2026, 9, 1),
        items=[make_verified_item("CHG-001")],
        calendar=make_calendar(),
        intro="Sample issue.",
    )


@pytest.fixture
def quiet_issue() -> Issue:
    return Issue(
        issue_number=2,
        period_label="2026-09",
        publish_date=dt.date(2026, 10, 1),
        items=[],
        quiet_month=True,
        search_log=make_search_log(),
        calendar=make_calendar(),
    )


@pytest.fixture
def samples_dir() -> str:
    return SAMPLES_DIR


@pytest.fixture
def load_sample():
    def _load(name: str) -> dict:
        with open(os.path.join(SAMPLES_DIR, name), "r", encoding="utf-8") as handle:
            return json.load(handle)

    return _load
