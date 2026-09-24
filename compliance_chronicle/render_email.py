"""Render an issue as the monthly email (plain text + HTML).

The plain-text rendering is canonical: it is what the read-time gate
measures and what the PDF rendering follows. Every issue, in order:

1. Header (issue number, coverage period, publish date).
2. The standard disclaimer, verbatim and prominent.
3. A verification-failure banner, when the issue declares one.
4. The changes — each with its citation and action, or its explicit
   "we could not verify X".
5. The verification ledger (the methodology's visible output).
6. The forward deadline calendar.
7. On a quiet month: the "no material changes" confirmation and the
   auditable search log.
8. Footer repeating the information-not-advice line.
"""

from __future__ import annotations

import html
import textwrap
from typing import List

from .models import ACTION_LIST_NOTE, STATUS_VERIFIED, Issue
from .verification import build_ledger

WORDS_PER_MINUTE = 200
MAX_READ_MINUTES = 10

QUIET_CONFIRMATION = "No material changes this month."


def _indent_wrap(text: str, indent: str, width: int = 78) -> List[str]:
    return textwrap.wrap(
        text, width=width, initial_indent=indent, subsequent_indent=indent
    ) or [indent.rstrip()]


def _labeled(label: str, value: str, width: int = 78) -> List[str]:
    """Render '   Label: value' wrapped with a hanging indent."""
    prefix = f"   {label}"
    wrapped = textwrap.wrap(
        value, width=width, initial_indent=prefix, subsequent_indent=" " * len(prefix)
    )
    return wrapped or [prefix]


def _wrap(text: str, width: int = 78) -> List[str]:
    lines: List[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
        else:
            lines.extend(textwrap.wrap(paragraph, width=width))
    return lines


def read_minutes(text: str, words_per_minute: int = WORDS_PER_MINUTE) -> float:
    words = len(text.split())
    return words / float(words_per_minute)


def render_plain(issue: Issue) -> str:
    lines: List[str] = []
    title = "THE COMPLIANCE CHRONICLE"
    lines.append(title)
    lines.append("Texas Cottage-Food Operators Edition")
    lines.append(
        f"Issue #{issue.issue_number} — covering {issue.period_label} — "
        f"published {issue.publish_date.isoformat()}"
    )
    lines.append("=" * 72)
    lines.append("")
    lines.append("IMPORTANT — PLEASE READ")
    lines.extend(_wrap(issue.disclaimer))
    lines.append("")

    if issue.verification_failure_declared:
        lines.append("!" * 72)
        lines.append("VERIFICATION WARNING FOR THIS ISSUE")
        lines.extend(
            _wrap(
                "Most items surfaced this month could not be verified against an "
                "authoritative source. Treat this issue as a watch list, not as "
                "confirmed regulatory change. Each unverified item below says "
                "exactly what we could not verify."
            )
        )
        lines.append("!" * 72)
        lines.append("")

    if issue.intro:
        lines.extend(_wrap(issue.intro))
        lines.append("")

    if issue.quiet_month:
        lines.append(QUIET_CONFIRMATION.upper())
        lines.append("-" * 72)
        lines.extend(
            _wrap(
                "We searched the authoritative Texas cottage-food sources for this "
                "period and found no changes that affect your operation. The search "
                "log below shows exactly which sources were checked and when."
            )
        )
        lines.append("")
    else:
        lines.append(f"WHAT CHANGED ({len(issue.items)} item(s))")
        lines.append("-" * 72)
        lines.append("")
        for index, item in enumerate(issue.items, start=1):
            lines.append(f"{index}. {item.title}")
            if item.status == STATUS_VERIFIED:
                lines.extend(_wrap(item.summary))
                if item.effective_date:
                    lines.append(f"   Effective: {item.effective_date.isoformat()}")
                if item.citation:
                    lines.append(f"   Citation: {item.citation.reference}")
                    lines.append(f"   Source:   {item.citation.url}")
                if item.action:
                    lines.extend(_labeled("Action:   ", item.action.description))
                    lines.append(f"   Deadline: {item.action.deadline.isoformat()}")
                    lines.append(f"   File at:  {item.action.portal_url}")
            else:
                lines.append(f"   WE COULD NOT VERIFY THIS ITEM.")
                lines.extend(_indent_wrap(item.unverified_reason, "   "))
                if item.citation and item.citation.url:
                    lines.append(f"   Lead source (unverified): {item.citation.url}")
            lines.append("")
        lines.extend(_wrap(ACTION_LIST_NOTE))
        lines.append("")

    ledger = build_ledger(issue)
    lines.append("VERIFICATION LEDGER")
    lines.append("-" * 72)
    if ledger.rows:
        for row in ledger.rows:
            if row.status == STATUS_VERIFIED:
                lines.append(f"[VERIFIED]   {row.item_id} — {row.title}")
                lines.append(f"             {row.citation_reference}")
            else:
                lines.append(f"[UNVERIFIED] {row.item_id} — {row.title}")
                lines.extend(_indent_wrap(row.unverified_reason, "             "))
        lines.append(
            f"Totals: {ledger.verified_count} verified, "
            f"{ledger.unverified_count} unverified."
        )
    else:
        lines.append("No regulatory claims were surfaced for this period.")
    lines.append("")

    if issue.calendar:
        lines.append("FORWARD DEADLINE CALENDAR")
        lines.append("-" * 72)
        for entry in sorted(issue.calendar, key=lambda e: e.deadline):
            suffix = f" — {entry.url}" if entry.url else ""
            lines.append(f"{entry.deadline.isoformat()}  {entry.label}{suffix}")
        lines.append("")

    if issue.quiet_month:
        lines.append("SEARCH LOG (why we are confident this was a quiet month)")
        lines.append("-" * 72)
        for entry in sorted(issue.search_log, key=lambda e: e.checked_at):
            url = f" ({entry.source_url})" if entry.source_url else ""
            result = f" — {entry.result}" if entry.result else ""
            lines.append(
                f"{entry.checked_at.isoformat()}  {entry.source_name}{url}{result}"
            )
        lines.append("")

    lines.append("-" * 72)
    lines.extend(
        _wrap(
            "You are receiving this because you subscribed to The Compliance "
            "Chronicle. This briefing is information, not legal advice. To stop "
            "receiving it, use the unsubscribe link in your email platform."
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def render_html(issue: Issue) -> str:
    """Render the same issue as simple, email-safe HTML."""

    def esc(text: str) -> str:
        return html.escape(text, quote=True)

    def link(url: str, label: str = "") -> str:
        if not url:
            return ""
        shown = label or url
        return f'<a href="{esc(url)}">{esc(shown)}</a>'

    parts: List[str] = []
    parts.append("<html><head><meta charset=\"utf-8\">")
    parts.append(
        f"<title>The Compliance Chronicle — Issue #{issue.issue_number}</title></head><body>"
    )
    parts.append("<h1>The Compliance Chronicle</h1>")
    parts.append("<p><strong>Texas Cottage-Food Operators Edition</strong><br>")
    parts.append(
        f"Issue #{issue.issue_number} — covering {esc(issue.period_label)} — "
        f"published {issue.publish_date.isoformat()}</p>"
    )
    parts.append(
        '<div style="border:2px solid #000;padding:0.8em;background:#fff8dc;">'
        f"<strong>IMPORTANT — PLEASE READ:</strong> {esc(issue.disclaimer)}</div>"
    )
    if issue.verification_failure_declared:
        parts.append(
            '<div style="border:2px solid #b00;padding:0.8em;background:#ffe4e4;">'
            "<strong>VERIFICATION WARNING FOR THIS ISSUE:</strong> most items "
            "surfaced this month could not be verified against an authoritative "
            "source. Treat this issue as a watch list, not as confirmed "
            "regulatory change.</div>"
        )
    if issue.intro:
        parts.append(f"<p>{esc(issue.intro)}</p>")

    if issue.quiet_month:
        parts.append(f"<h2>{QUIET_CONFIRMATION}</h2>")
        parts.append(
            "<p>We searched the authoritative Texas cottage-food sources for this "
            "period and found no changes that affect your operation. The search "
            "log below shows exactly which sources were checked and when.</p>"
        )
    else:
        parts.append(f"<h2>What changed ({len(issue.items)} item(s))</h2>")
        parts.append("<ol>")
        for item in issue.items:
            parts.append(f"<li><strong>{esc(item.title)}</strong><br>")
            if item.status == STATUS_VERIFIED:
                parts.append(f"{esc(item.summary)}<br>")
                if item.effective_date:
                    parts.append(f"Effective: {item.effective_date.isoformat()}<br>")
                if item.citation:
                    parts.append(f"Citation: {esc(item.citation.reference)}<br>")
                    parts.append(f"Source: {link(item.citation.url)}<br>")
                if item.action:
                    parts.append(f"Action: {esc(item.action.description)}<br>")
                    parts.append(f"Deadline: {item.action.deadline.isoformat()}<br>")
                    parts.append(f"File at: {link(item.action.portal_url)}")
            else:
                parts.append("<strong>WE COULD NOT VERIFY THIS ITEM.</strong><br>")
                parts.append(esc(item.unverified_reason))
                if item.citation and item.citation.url:
                    parts.append(f"<br>Lead source (unverified): {link(item.citation.url)}")
            parts.append("</li>")
        parts.append("</ol>")
        parts.append(f"<p><em>{esc(ACTION_LIST_NOTE)}</em></p>")

    ledger = build_ledger(issue)
    parts.append("<h2>Verification ledger</h2>")
    if ledger.rows:
        parts.append("<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\">")
        parts.append(
            "<tr><th>Status</th><th>Item</th><th>Citation / reason</th></tr>"
        )
        for row in ledger.rows:
            status = "VERIFIED" if row.status == STATUS_VERIFIED else "UNVERIFIED"
            detail = (
                esc(row.citation_reference)
                if row.status == STATUS_VERIFIED
                else esc(row.unverified_reason)
            )
            parts.append(
                f"<tr><td>{status}</td><td>{esc(row.item_id)} — {esc(row.title)}</td>"
                f"<td>{detail}</td></tr>"
            )
        parts.append("</table>")
        parts.append(
            f"<p>Totals: {ledger.verified_count} verified, "
            f"{ledger.unverified_count} unverified.</p>"
        )
    else:
        parts.append("<p>No regulatory claims were surfaced for this period.</p>")

    if issue.calendar:
        parts.append("<h2>Forward deadline calendar</h2><ul>")
        for entry in sorted(issue.calendar, key=lambda e: e.deadline):
            suffix = f" — {link(entry.url)}" if entry.url else ""
            parts.append(
                f"<li>{entry.deadline.isoformat()} — {esc(entry.label)}{suffix}</li>"
            )
        parts.append("</ul>")

    if issue.quiet_month:
        parts.append("<h2>Search log (why we are confident this was a quiet month)</h2>")
        parts.append("<ul>")
        for entry in sorted(issue.search_log, key=lambda e: e.checked_at):
            url = f" ({link(entry.source_url)})" if entry.source_url else ""
            result = f" — {esc(entry.result)}" if entry.result else ""
            parts.append(
                f"<li>{entry.checked_at.isoformat()} — {esc(entry.source_name)}{url}{result}</li>"
            )
        parts.append("</ul>")

    parts.append("<hr>")
    parts.append(
        "<p><small>You are receiving this because you subscribed to The Compliance "
        "Chronicle. This briefing is information, not legal advice. To stop "
        "receiving it, use the unsubscribe link in your email platform.</small></p>"
    )
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"
