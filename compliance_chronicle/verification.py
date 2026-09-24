"""The verification ledger — the visible output of the methodology.

``docs/VERIFICATION_METHODOLOGY.md`` is the internal process; the
ledger rendered into every issue is what the subscriber sees. This
module computes the ledger from the issue's items and decides the two
contract facts that depend on it:

* whether the majority of surfaced items are unverifiable (which the
  issue must flag loudly, never silently), and
* whether a quiet-month search log covers every required source class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set

from . import sources
from .models import STATUS_UNVERIFIED, STATUS_VERIFIED, Issue


@dataclass
class LedgerRow:
    item_id: str
    title: str
    status: str
    citation_reference: str = ""
    citation_url: str = ""
    unverified_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "status": self.status,
            "citation_reference": self.citation_reference,
            "citation_url": self.citation_url,
            "unverified_reason": self.unverified_reason,
        }


@dataclass
class VerificationLedger:
    rows: List[LedgerRow] = field(default_factory=list)
    verified_count: int = 0
    unverified_count: int = 0
    majority_unverified: bool = False

    @property
    def total(self) -> int:
        return len(self.rows)

    def to_dict(self) -> dict:
        return {
            "rows": [r.to_dict() for r in self.rows],
            "verified_count": self.verified_count,
            "unverified_count": self.unverified_count,
            "majority_unverified": self.majority_unverified,
        }


def build_ledger(issue: Issue) -> VerificationLedger:
    """Compute the per-issue ledger from its items."""

    rows: List[LedgerRow] = []
    for item in issue.items:
        rows.append(
            LedgerRow(
                item_id=item.item_id,
                title=item.title,
                status=item.status,
                citation_reference=item.citation.reference if item.citation else "",
                citation_url=item.citation.url if item.citation else "",
                unverified_reason=item.unverified_reason,
            )
        )
    verified = sum(1 for r in rows if r.status == STATUS_VERIFIED)
    unverified = sum(1 for r in rows if r.status == STATUS_UNVERIFIED)
    return VerificationLedger(
        rows=rows,
        verified_count=verified,
        unverified_count=unverified,
        majority_unverified=bool(rows) and unverified > len(rows) / 2,
    )


def quiet_month_missing_sources(issue: Issue) -> Set[str]:
    """Required source classes absent from this issue's search log.

    An empty set means the quiet-month sweep covered every source class
    the methodology requires.
    """

    covered = {entry.source_class for entry in issue.search_log}
    return set(sources.REQUIRED_QUIET_MONTH_SOURCES) - covered
