"""Publish gates — the falsification criteria, made executable.

Each gate in this module corresponds to a numbered falsification
criterion in ``spec.md`` ("Acceptance" / "Falsification"). A gate
result with ``severity == "fail"`` blocks shipping; ``"warn"`` rides
along visibly but does not block. There is deliberately no way to
ship an issue that fails a hard gate through this module's caller
contract (``assert_shippable`` raises).

Gate inventory:

* ``model-validation`` — every model-level contract violation
  (falsification 1 & 3: citation-or-marker, action/deadline/portal).
* ``read-time`` — falsification 2: over ten minutes fails.
* ``lead-time`` — falsification 4: an issue arriving on or after the
  earliest deadline it reports fails; short lead time warns.
* ``quiet-search-log`` — falsification 5: a quiet month without an
  auditable, methodologically complete search log fails.
* ``quiet-calendar`` — a quiet month without a forward deadline
  calendar fails (Acceptance).
* ``verification-majority`` — falsification 6: a majority-unverifiable
  issue that does not declare the failure fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import render_email
from .models import Issue
from .verification import build_ledger, quiet_month_missing_sources

SEVERITY_FAIL = "fail"
SEVERITY_WARN = "warn"

#: Minimum days of actionable lead time before the earliest reported
#: deadline before the gate starts warning. Publishing on or after the
#: deadline itself is a hard fail, not a warning.
DEFAULT_MIN_LEAD_DAYS = 7


@dataclass
class GateResult:
    gate_id: str
    passed: bool
    severity: str  # "fail" or "warn"
    message: str

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }


def validate_issue(issue: Issue, min_lead_days: int = DEFAULT_MIN_LEAD_DAYS) -> List[GateResult]:
    results: List[GateResult] = []

    # -- model validation (citation coverage + action completeness) ---
    model_errors = issue.validate()
    results.append(
        GateResult(
            gate_id="model-validation",
            passed=not model_errors,
            severity=SEVERITY_FAIL,
            message="; ".join(model_errors) if model_errors else "all items satisfy the citation/action contract",
        )
    )

    # -- read time -----------------------------------------------------
    text = render_email.render_plain(issue)
    minutes = render_email.read_minutes(text)
    results.append(
        GateResult(
            gate_id="read-time",
            passed=minutes <= render_email.MAX_READ_MINUTES,
            severity=SEVERITY_FAIL,
            message=(
                f"estimated read time {minutes:.1f} min "
                f"({len(text.split())} words at {render_email.WORDS_PER_MINUTE} wpm); "
                f"limit is {render_email.MAX_READ_MINUTES} min"
            ),
        )
    )

    # -- lead time ------------------------------------------------------
    earliest = issue.earliest_deadline()
    if earliest is None:
        results.append(
            GateResult(
                gate_id="lead-time",
                passed=True,
                severity=SEVERITY_FAIL,
                message="issue reports no deadlines; the lead-time rule is vacuously satisfied",
            )
        )
    else:
        lead = (earliest - issue.publish_date).days
        if lead < 0:
            results.append(
                GateResult(
                    gate_id="lead-time",
                    passed=False,
                    severity=SEVERITY_FAIL,
                    message=(
                        f"issue publishes {issue.publish_date.isoformat()} but the earliest "
                        f"deadline it reports is {earliest.isoformat()} — it would arrive "
                        "after a deadline it reports"
                    ),
                )
            )
        elif lead < min_lead_days:
            results.append(
                GateResult(
                    gate_id="lead-time",
                    passed=False,
                    severity=SEVERITY_WARN,
                    message=(
                        f"only {lead} day(s) of lead time before the earliest deadline "
                        f"({earliest.isoformat()}); target is at least {min_lead_days} — "
                        "that deadline should have appeared in a prior issue's forward calendar"
                    ),
                )
            )
        else:
            results.append(
                GateResult(
                    gate_id="lead-time",
                    passed=True,
                    severity=SEVERITY_FAIL,
                    message=(
                        f"{lead} day(s) of lead time before the earliest deadline "
                        f"({earliest.isoformat()})"
                    ),
                )
            )

    # -- quiet-month evidence ------------------------------------------
    if issue.quiet_month:
        log_errors: List[str] = []
        if not issue.search_log:
            log_errors.append("quiet month declared with an empty search log")
        missing = quiet_month_missing_sources(issue)
        if missing:
            log_errors.append(
                "search log does not cover required source classes: " + ", ".join(sorted(missing))
            )
        for entry in issue.search_log:
            if entry.checked_at > issue.publish_date:
                log_errors.append(
                    f"search log entry for {entry.source_name!r} is dated "
                    f"{entry.checked_at.isoformat()}, after the publish date"
                )
        results.append(
            GateResult(
                gate_id="quiet-search-log",
                passed=not log_errors,
                severity=SEVERITY_FAIL,
                message="; ".join(log_errors) if log_errors else "quiet month carries a complete auditable search log",
            )
        )
        results.append(
            GateResult(
                gate_id="quiet-calendar",
                passed=bool(issue.calendar),
                severity=SEVERITY_FAIL,
                message=(
                    "quiet month carries a forward deadline calendar"
                    if issue.calendar
                    else "quiet month declared without a forward deadline calendar — "
                    "a quiet month is a confirmation plus a calendar, never silence"
                ),
            )
        )
    else:
        results.append(
            GateResult(
                gate_id="quiet-search-log",
                passed=True,
                severity=SEVERITY_FAIL,
                message="not a quiet month; search-log gate not applicable",
            )
        )
        results.append(
            GateResult(
                gate_id="quiet-calendar",
                passed=True,
                severity=SEVERITY_FAIL,
                message="not a quiet month; calendar gate not applicable",
            )
        )

    # -- verification majority ------------------------------------------
    ledger = build_ledger(issue)
    if ledger.majority_unverified and not issue.verification_failure_declared:
        results.append(
            GateResult(
                gate_id="verification-majority",
                passed=False,
                severity=SEVERITY_FAIL,
                message=(
                    f"{ledger.unverified_count} of {ledger.total} items are unverified "
                    "but the issue does not declare the verification failure — "
                    "shipping it silently would violate the product standard"
                ),
            )
        )
    else:
        results.append(
            GateResult(
                gate_id="verification-majority",
                passed=True,
                severity=SEVERITY_FAIL,
                message=(
                    f"{ledger.verified_count}/{ledger.total} items verified"
                    + (" (majority-unverified failure is declared)" if ledger.majority_unverified else "")
                ),
            )
        )

    return results


def is_shippable(results: List[GateResult]) -> bool:
    """True only when every hard gate passed (warnings never block)."""

    return all(r.passed for r in results if r.severity == SEVERITY_FAIL)


def assert_shippable(issue: Issue, min_lead_days: int = DEFAULT_MIN_LEAD_DAYS) -> List[GateResult]:
    """Return the gate results, or raise if any hard gate failed."""

    results = validate_issue(issue, min_lead_days=min_lead_days)
    failures = [r for r in results if not r.passed and r.severity == SEVERITY_FAIL]
    if failures:
        summary = "; ".join(f"[{r.gate_id}] {r.message}" for r in failures)
        raise IssueNotShippable(f"issue #{issue.issue_number} cannot ship: {summary}", results)
    return results


class IssueNotShippable(Exception):
    """Raised when an issue fails a hard publish gate."""

    def __init__(self, message: str, results: Optional[List[GateResult]] = None):
        super().__init__(message)
        self.results = results or []
