"""Core data model for The Compliance Chronicle.

Every rule in this file is a direct encoding of the product contract
in ``spec.md``:

* Every regulatory claim is either verified-with-citation or carries an
  explicit "we could not verify X" marker. There is no third state and
  no silent omission.
* A verified change ships with a required action, a deadline, and a
  direct filing-portal link.
* A quiet month is a first-class issue shape that must carry an
  auditable search log and a forward deadline calendar.

The models validate themselves (``validate()`` returns a list of
human-readable contract violations); the hard publish/no-publish
decision lives in ``gates.py``.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import List, Optional

from . import sources


STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"
STATUSES = (STATUS_VERIFIED, STATUS_UNVERIFIED)

#: The disclaimer ships verbatim at the top of every issue, in email
#: and PDF, above the first item. It is a constant on purpose: an
#: issue that edits it down is an issue that drifts from the contract.
DISCLAIMER = (
    "The Compliance Chronicle is an information service, not a law firm. "
    "Nothing in this issue is legal advice, and reading it does not create "
    "an attorney-client relationship. Plain-English summaries are provided "
    "for general awareness; the cited source text governs. For advice about "
    "your specific situation, consult a licensed Texas attorney."
)

#: Action lists point subscribers at the official portal or form. They
#: must never read as instructions on how to complete a filing — that
#: would cross into legal guidance. This sentence accompanies every
#: action list to hold that line.
ACTION_LIST_NOTE = (
    "Action items identify what changed, the published deadline, and the "
    "official portal or form. They are pointers to the authorities, not "
    "instructions for completing a filing."
)


def _parse_date(value) -> _dt.date:
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str):
        return _dt.date.fromisoformat(value.strip())
    raise ValueError("not a date: %r" % (value,))


@dataclass
class Citation:
    """An exact, checkable citation to an authoritative source."""

    reference: str  # e.g. "Tex. Health & Safety Code § 437.001" — the pinpoint
    url: str  # direct link to the source text
    source_class: str  # key into sources.SOURCE_CLASSES
    publisher: str = ""
    accessed: Optional[_dt.date] = None

    def validate(self, prefix: str = "citation") -> List[str]:
        errors: List[str] = []
        if not self.reference or not self.reference.strip():
            errors.append(f"{prefix}: missing exact citation reference")
        elif not sources.looks_like_exact_citation(self.reference):
            errors.append(
                f"{prefix}: {self.reference!r} is not an exact pinpoint citation "
                "(must name a section, chapter, or bill number)"
            )
        if not self.url or not self.url.strip():
            errors.append(f"{prefix}: missing source URL")
        elif not (self.url.startswith("http://") or self.url.startswith("https://")):
            errors.append(f"{prefix}: source URL is not a URL: {self.url!r}")
        if self.source_class not in sources.SOURCE_CLASSES:
            errors.append(
                f"{prefix}: unknown source class {self.source_class!r} "
                f"(known: {', '.join(sources.source_class_keys())})"
            )
        elif not sources.is_authoritative(self.source_class):
            errors.append(
                f"{prefix}: source class {self.source_class!r} is not authoritative "
                "and cannot verify a regulatory claim"
            )
        return errors

    def to_dict(self) -> dict:
        return {
            "reference": self.reference,
            "url": self.url,
            "source_class": self.source_class,
            "publisher": self.publisher,
            "accessed": self.accessed.isoformat() if self.accessed else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Citation":
        return cls(
            reference=str(data.get("reference", "")),
            url=str(data.get("url", "")),
            source_class=str(data.get("source_class", "")),
            publisher=str(data.get("publisher", "")),
            accessed=_parse_date(data["accessed"]) if data.get("accessed") else None,
        )


@dataclass
class Action:
    """What the subscriber must do, by when, and where."""

    description: str
    deadline: _dt.date
    portal_url: str  # direct link to the filing portal or official form

    def validate(self, prefix: str = "action") -> List[str]:
        errors: List[str] = []
        if not self.description or not self.description.strip():
            errors.append(f"{prefix}: missing action description")
        if not isinstance(self.deadline, _dt.date):
            errors.append(f"{prefix}: missing or invalid deadline")
        if not self.portal_url or not (
            self.portal_url.startswith("http://") or self.portal_url.startswith("https://")
        ):
            errors.append(f"{prefix}: missing or invalid filing-portal link")
        return errors

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "deadline": self.deadline.isoformat(),
            "portal_url": self.portal_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(
            description=str(data.get("description", "")),
            deadline=_parse_date(data.get("deadline", "")),
            portal_url=str(data.get("portal_url", "")),
        )


@dataclass
class ChangeItem:
    """One regulatory change (or explicitly unverifiable candidate).

    The two states are exhaustive: ``verified`` items carry a full
    citation and action; ``unverified`` items carry an explicit reason
    beginning from the claim that could not be verified. Assembly never
    drops a claim — it converts it.
    """

    item_id: str
    title: str
    summary: str  # operator's plain-English restatement (information, not advice)
    status: str
    citation: Optional[Citation] = None
    action: Optional[Action] = None
    unverified_reason: str = ""
    effective_date: Optional[_dt.date] = None

    def validate(self) -> List[str]:
        errors: List[str] = []
        prefix = f"item {self.item_id or '<no-id>'}"
        if not self.item_id or not self.item_id.strip():
            errors.append("item: missing id")
        if not self.title or not self.title.strip():
            errors.append(f"{prefix}: missing title")
        if self.status not in STATUSES:
            errors.append(f"{prefix}: status must be one of {STATUSES}, got {self.status!r}")
            return errors  # nothing below is meaningful without a valid status
        if self.status == STATUS_VERIFIED:
            if not self.summary or not self.summary.strip():
                errors.append(f"{prefix}: verified item missing plain-English summary")
            if self.citation is None:
                errors.append(
                    f"{prefix}: verified item has no citation — mark it "
                    '"we could not verify" instead of shipping it bare'
                )
            else:
                errors.extend(self.citation.validate(prefix=prefix))
            if self.action is None:
                errors.append(
                    f"{prefix}: verified item has no action — the subscriber must be "
                    "able to find what to do, the deadline, and the portal link"
                )
            else:
                errors.extend(self.action.validate(prefix=prefix))
        else:  # unverified
            if not self.unverified_reason or not self.unverified_reason.strip():
                errors.append(
                    f"{prefix}: unverified item must say what could not be verified "
                    '("we could not verify X")'
                )
        return errors

    @property
    def deadline(self) -> Optional[_dt.date]:
        if self.action is not None:
            return self.action.deadline
        return None

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "summary": self.summary,
            "status": self.status,
            "citation": self.citation.to_dict() if self.citation else None,
            "action": self.action.to_dict() if self.action else None,
            "unverified_reason": self.unverified_reason,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeItem":
        return cls(
            item_id=str(data.get("item_id", "")),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            status=str(data.get("status", "")),
            citation=Citation.from_dict(data["citation"]) if data.get("citation") else None,
            action=Action.from_dict(data["action"]) if data.get("action") else None,
            unverified_reason=str(data.get("unverified_reason", "")),
            effective_date=(
                _parse_date(data["effective_date"]) if data.get("effective_date") else None
            ),
        )


@dataclass
class SearchLogEntry:
    """One row of the auditable search log.

    A quiet month is only as real as this log: which sources were
    checked, when, and with what result.
    """

    source_name: str
    source_class: str
    checked_at: _dt.date
    source_url: str = ""
    result: str = ""  # what the sweep found, e.g. "no amendments posted"

    def validate(self, prefix: str = "search log entry") -> List[str]:
        errors: List[str] = []
        if not self.source_name or not self.source_name.strip():
            errors.append(f"{prefix}: missing source name")
        if self.source_class not in sources.SOURCE_CLASSES:
            errors.append(f"{prefix}: unknown source class {self.source_class!r}")
        if not isinstance(self.checked_at, _dt.date):
            errors.append(f"{prefix}: missing checked date")
        return errors

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "source_class": self.source_class,
            "checked_at": self.checked_at.isoformat(),
            "source_url": self.source_url,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SearchLogEntry":
        return cls(
            source_name=str(data.get("source_name", "")),
            source_class=str(data.get("source_class", "")),
            checked_at=_parse_date(data.get("checked_at", "")),
            source_url=str(data.get("source_url", "")),
            result=str(data.get("result", "")),
        )


@dataclass
class CalendarEntry:
    """A known future deadline carried forward for the subscriber."""

    label: str
    deadline: _dt.date
    url: str = ""

    def validate(self, prefix: str = "calendar entry") -> List[str]:
        errors: List[str] = []
        if not self.label or not self.label.strip():
            errors.append(f"{prefix}: missing label")
        if not isinstance(self.deadline, _dt.date):
            errors.append(f"{prefix}: missing deadline")
        return errors

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "deadline": self.deadline.isoformat(),
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CalendarEntry":
        return cls(
            label=str(data.get("label", "")),
            deadline=_parse_date(data.get("deadline", "")),
            url=str(data.get("url", "")),
        )


@dataclass
class Issue:
    """One monthly issue — the unit the gates judge."""

    issue_number: int
    period_label: str  # coverage period, e.g. "2026-08" (the month reviewed)
    publish_date: _dt.date
    items: List[ChangeItem] = field(default_factory=list)
    quiet_month: bool = False
    search_log: List[SearchLogEntry] = field(default_factory=list)
    calendar: List[CalendarEntry] = field(default_factory=list)
    verification_failure_declared: bool = False
    intro: str = ""
    disclaimer: str = DISCLAIMER

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.issue_number < 1:
            errors.append("issue: issue_number must be >= 1")
        if not self.period_label or not self.period_label.strip():
            errors.append("issue: missing coverage period label")
        if not isinstance(self.publish_date, _dt.date):
            errors.append("issue: missing publish date")
        if not self.disclaimer or DISCLAIMER not in self.disclaimer:
            errors.append("issue: the standard disclaimer must ship verbatim")
        if self.quiet_month and self.items:
            errors.append(
                "issue: a quiet-month declaration cannot carry change items — "
                "either report the items or withdraw the quiet declaration"
            )
        seen_ids = set()
        for item in self.items:
            errors.extend(item.validate())
            if item.item_id in seen_ids:
                errors.append(f"issue: duplicate item id {item.item_id!r}")
            seen_ids.add(item.item_id)
        for i, entry in enumerate(self.search_log, start=1):
            errors.extend(entry.validate(prefix=f"search log entry {i}"))
        for i, entry in enumerate(self.calendar, start=1):
            errors.extend(entry.validate(prefix=f"calendar entry {i}"))
        return errors

    # -- derived facts -------------------------------------------------

    @property
    def verified_items(self) -> List[ChangeItem]:
        return [i for i in self.items if i.status == STATUS_VERIFIED]

    @property
    def unverified_items(self) -> List[ChangeItem]:
        return [i for i in self.items if i.status == STATUS_UNVERIFIED]

    @property
    def majority_unverified(self) -> bool:
        if not self.items:
            return False
        return len(self.unverified_items) > len(self.items) / 2

    def earliest_deadline(self) -> Optional[_dt.date]:
        deadlines = [i.deadline for i in self.items if i.deadline is not None]
        deadlines.extend(e.deadline for e in self.calendar)
        return min(deadlines) if deadlines else None

    def slug(self) -> str:
        return f"issue-{self.issue_number:03d}"

    def to_dict(self) -> dict:
        return {
            "schema": "compliance_chronicle.issue/v1",
            "issue_number": self.issue_number,
            "period_label": self.period_label,
            "publish_date": self.publish_date.isoformat(),
            "items": [i.to_dict() for i in self.items],
            "quiet_month": self.quiet_month,
            "search_log": [e.to_dict() for e in self.search_log],
            "calendar": [e.to_dict() for e in self.calendar],
            "verification_failure_declared": self.verification_failure_declared,
            "intro": self.intro,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Issue":
        return cls(
            issue_number=int(data.get("issue_number", 0)),
            period_label=str(data.get("period_label", "")),
            publish_date=_parse_date(data.get("publish_date", "")),
            items=[ChangeItem.from_dict(i) for i in data.get("items", [])],
            quiet_month=bool(data.get("quiet_month", False)),
            search_log=[SearchLogEntry.from_dict(e) for e in data.get("search_log", [])],
            calendar=[CalendarEntry.from_dict(e) for e in data.get("calendar", [])],
            verification_failure_declared=bool(data.get("verification_failure_declared", False)),
            intro=str(data.get("intro", "")),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )
