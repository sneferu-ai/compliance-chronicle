"""Assemble an issue from a Sneferu research report + operator curation.

Sneferu is an external dependency used through its existing interface:
once a month the operator runs one Sneferu Research workflow against
the Texas cottage-food source sweep and receives a report. This module
is the seam between that report and the shipped issue.

Report schema (``compliance_chronicle.research-report/v1``)::

    {
      "schema": "compliance_chronicle.research-report/v1",
      "run_id": "...",                    # the Sneferu run id, for provenance
      "generated_at": "2026-08-31",       # date the research run completed
      "claims": [
        {
          "id": "CLM-001",
          "title": "...",
          "summary": "...",               # model-drafted; curation may replace
          "citation": {"reference": "...", "url": "...", "source_class": "..."},
          "action": {"description": "...", "deadline": "YYYY-MM-DD", "portal_url": "..."},
          "effective_date": "YYYY-MM-DD"
        }
      ],
      "search_log": [
        {"source_name": "...", "source_class": "...", "checked_at": "YYYY-MM-DD",
         "source_url": "...", "result": "..."}
      ],
      "calendar": [
        {"label": "...", "deadline": "YYYY-MM-DD", "url": "..."}
      ]
    }

Curation file schema (``compliance_chronicle.curation/v1``)::

    {
      "schema": "compliance_chronicle.curation/v1",
      "issue_number": 1,
      "period_label": "2026-08",
      "publish_date": "2026-09-01",
      "intro": "...",
      "quiet_month": false,
      "verification_failure_declared": false,
      "overrides": {"CLM-001": {"summary": "operator rewrite", "drop": false}},
      "extra_search_log": [ ... ],
      "extra_calendar": [ ... ]
    }

The one rule that matters most here: **assembly never drops a claim.**
A claim the report could not cite to an authoritative source becomes an
explicitly unverified item ("we could not verify X"). Silence is the
falsification event; an honest unverified marker is the product.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Dict, List

from . import sources
from .models import (
    STATUS_UNVERIFIED,
    STATUS_VERIFIED,
    Action,
    CalendarEntry,
    ChangeItem,
    Citation,
    Issue,
    SearchLogEntry,
)


class AssemblyError(Exception):
    """Raised when inputs contradict the contract (e.g. quiet + items)."""


def _claim_is_verifiable(claim: dict) -> bool:
    """A claim verifies only with a complete, authoritative citation."""

    citation = claim.get("citation")
    if not citation:
        return False
    if not str(citation.get("reference", "")).strip():
        return False
    if not str(citation.get("url", "")).strip():
        return False
    source_class = str(citation.get("source_class", ""))
    return sources.is_authoritative(source_class) and sources.looks_like_exact_citation(
        str(citation.get("reference", ""))
    )


def _unverified_reason(claim: dict) -> str:
    title = str(claim.get("title", "this item")).strip() or "this item"
    citation = claim.get("citation")
    if citation and citation.get("url"):
        return (
            f"We could not verify: {title}. A lead was found at "
            f"{citation.get('url')} but it is not an authoritative source "
            "for this claim or lacks an exact citation."
        )
    return (
        f"We could not verify: {title}. No authoritative source with an "
        "exact citation was found for this claim in this month's sweep."
    )


def assemble_issue(report: dict, curation: dict) -> Issue:
    """Build an Issue from a research report and the operator's curation."""

    if report.get("schema") not in (None, "compliance_chronicle.research-report/v1"):
        raise AssemblyError(f"unknown report schema: {report.get('schema')!r}")

    claims: List[dict] = list(report.get("claims", []))
    overrides: Dict[str, dict] = dict(curation.get("overrides", {}))
    quiet_month = bool(curation.get("quiet_month", False))

    items: List[ChangeItem] = []
    for position, claim in enumerate(claims, start=1):
        claim_id = str(claim.get("id") or f"CLM-{position:03d}")
        override = overrides.get(claim_id, {})
        if override.get("drop"):
            # An explicit, reasoned drop is recorded as an unverified item
            # rather than vanishing — no silent omission.
            reason = str(override.get("drop_reason", "")).strip()
            items.append(
                ChangeItem(
                    item_id=claim_id,
                    title=str(claim.get("title", "")).strip(),
                    summary="",
                    status=STATUS_UNVERIFIED,
                    unverified_reason=(
                        f"We could not verify: {str(claim.get('title', '')).strip()}. "
                        + (reason or "Excluded from the verified list after curation review.")
                    ),
                )
            )
            continue

        summary = str(override.get("summary") or claim.get("summary") or "").strip()
        citation_data = claim.get("citation")
        citation = Citation.from_dict(citation_data) if citation_data else None
        # Curation may upgrade a missing source_class if the URL classifies.
        if citation and citation.source_class not in sources.SOURCE_CLASSES:
            guessed = sources.classify_url(citation.url)
            if guessed:
                citation.source_class = guessed

        if _claim_is_verifiable({"citation": citation.to_dict() if citation else None}):
            action_data = claim.get("action")
            action = Action.from_dict(action_data) if action_data else None
            effective = claim.get("effective_date")
            items.append(
                ChangeItem(
                    item_id=claim_id,
                    title=str(claim.get("title", "")).strip(),
                    summary=summary,
                    status=STATUS_VERIFIED,
                    citation=citation,
                    action=action,
                    effective_date=_dt.date.fromisoformat(effective) if effective else None,
                )
            )
        else:
            items.append(
                ChangeItem(
                    item_id=claim_id,
                    title=str(claim.get("title", "")).strip(),
                    summary=summary,
                    status=STATUS_UNVERIFIED,
                    citation=citation,
                    unverified_reason=_unverified_reason(claim),
                )
            )

    if quiet_month and items:
        raise AssemblyError(
            "curation declares a quiet month but the report surfaced "
            f"{len(claims)} claim(s) — report the items or withdraw the declaration"
        )

    search_log = [SearchLogEntry.from_dict(e) for e in report.get("search_log", [])]
    search_log.extend(SearchLogEntry.from_dict(e) for e in curation.get("extra_search_log", []))

    calendar = [CalendarEntry.from_dict(e) for e in report.get("calendar", [])]
    calendar.extend(CalendarEntry.from_dict(e) for e in curation.get("extra_calendar", []))

    return Issue(
        issue_number=int(curation.get("issue_number", 0)),
        period_label=str(curation.get("period_label", "")),
        publish_date=_dt.date.fromisoformat(str(curation.get("publish_date", ""))),
        items=items,
        quiet_month=quiet_month,
        search_log=search_log,
        calendar=calendar,
        verification_failure_declared=bool(curation.get("verification_failure_declared", False)),
        intro=str(curation.get("intro", "")),
    )


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_issue(issue: Issue, path: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(issue.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def load_issue(path: str) -> Issue:
    return Issue.from_dict(load_json(path))
