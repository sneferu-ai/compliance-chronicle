"""Render issues as text-selectable PDFs and maintain the archive.

The archive contract: every past issue as a text-selectable PDF, with
an index so a subscriber can find an issue by number, period, or date.
PDFs are rendered from the same logical structure as the email so the
two artifacts can never silently diverge in content.
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import os
from typing import List, Sequence

from .models import STATUS_VERIFIED, Issue
from .pdf import Line, build_pdf, write_pdf
from .verification import build_ledger


def issue_to_lines(issue: Issue) -> List[Line]:
    lines: List[Line] = []
    lines.append(Line("The Compliance Chronicle", size=18, bold=True, space_after=2))
    lines.append(Line("Texas Cottage-Food Operators Edition", size=12, space_after=2))
    lines.append(
        Line(
            f"Issue #{issue.issue_number} — covering {issue.period_label} — "
            f"published {issue.publish_date.isoformat()}",
            size=10,
            space_after=8,
        )
    )
    lines.append(Line("IMPORTANT — PLEASE READ", bold=True))
    lines.append(Line(issue.disclaimer, space_after=6))

    if issue.verification_failure_declared:
        lines.append(Line("VERIFICATION WARNING FOR THIS ISSUE", bold=True))
        lines.append(
            Line(
                "Most items surfaced this month could not be verified against an "
                "authoritative source. Treat this issue as a watch list, not as "
                "confirmed regulatory change.",
                space_after=6,
            )
        )

    if issue.intro:
        lines.append(Line(issue.intro, space_after=6))

    if issue.quiet_month:
        lines.append(Line("NO MATERIAL CHANGES THIS MONTH", size=13, bold=True))
        lines.append(
            Line(
                "We searched the authoritative Texas cottage-food sources for this "
                "period and found no changes that affect your operation. The search "
                "log below shows exactly which sources were checked and when.",
                space_after=6,
            )
        )
    else:
        lines.append(
            Line(f"WHAT CHANGED ({len(issue.items)} item(s))", size=13, bold=True, space_after=4)
        )
        for index, item in enumerate(issue.items, start=1):
            lines.append(Line(f"{index}. {item.title}", bold=True, space_after=2))
            if item.status == STATUS_VERIFIED:
                lines.append(Line(item.summary, indent=12))
                if item.effective_date:
                    lines.append(
                        Line(f"Effective: {item.effective_date.isoformat()}", indent=12)
                    )
                if item.citation:
                    lines.append(Line(f"Citation: {item.citation.reference}", indent=12))
                    lines.append(Line(f"Source: {item.citation.url}", indent=12))
                if item.action:
                    lines.append(Line(f"Action: {item.action.description}", indent=12))
                    lines.append(
                        Line(f"Deadline: {item.action.deadline.isoformat()}", indent=12)
                    )
                    lines.append(Line(f"File at: {item.action.portal_url}", indent=12))
            else:
                lines.append(Line("WE COULD NOT VERIFY THIS ITEM.", bold=True, indent=12))
                lines.append(Line(item.unverified_reason, indent=12))
                if item.citation and item.citation.url:
                    lines.append(
                        Line(f"Lead source (unverified): {item.citation.url}", indent=12)
                    )
            lines.append(Line("", space_after=4))
        lines.append(
            Line(
                "Action items identify what changed, the published deadline, and the "
                "official portal or form. They are pointers to the authorities, not "
                "instructions for completing a filing.",
                space_after=6,
            )
        )

    ledger = build_ledger(issue)
    lines.append(Line("VERIFICATION LEDGER", size=13, bold=True, space_after=4))
    if ledger.rows:
        for row in ledger.rows:
            marker = "VERIFIED" if row.status == STATUS_VERIFIED else "UNVERIFIED"
            lines.append(Line(f"[{marker}] {row.item_id} — {row.title}"))
            detail = (
                row.citation_reference
                if row.status == STATUS_VERIFIED
                else row.unverified_reason
            )
            if detail:
                lines.append(Line(detail, indent=12))
        lines.append(
            Line(
                f"Totals: {ledger.verified_count} verified, "
                f"{ledger.unverified_count} unverified.",
                space_after=6,
            )
        )
    else:
        lines.append(Line("No regulatory claims were surfaced for this period.", space_after=6))

    if issue.calendar:
        lines.append(Line("FORWARD DEADLINE CALENDAR", size=13, bold=True, space_after=4))
        for entry in sorted(issue.calendar, key=lambda e: e.deadline):
            suffix = f" — {entry.url}" if entry.url else ""
            lines.append(Line(f"{entry.deadline.isoformat()}  {entry.label}{suffix}"))
        lines.append(Line("", space_after=6))

    if issue.quiet_month:
        lines.append(
            Line(
                "SEARCH LOG (why we are confident this was a quiet month)",
                size=13,
                bold=True,
                space_after=4,
            )
        )
        for entry in sorted(issue.search_log, key=lambda e: e.checked_at):
            url = f" ({entry.source_url})" if entry.source_url else ""
            result = f" — {entry.result}" if entry.result else ""
            lines.append(Line(f"{entry.checked_at.isoformat()}  {entry.source_name}{url}{result}"))
        lines.append(Line("", space_after=6))

    lines.append(
        Line(
            "This briefing is information, not legal advice.",
            size=9,
            space_after=0,
        )
    )
    return lines


def render_issue_pdf_bytes(issue: Issue) -> bytes:
    title = f"The Compliance Chronicle — Issue #{issue.issue_number} ({issue.period_label})"
    return build_pdf(title, issue_to_lines(issue))


def render_issue_pdf(issue: Issue, out_path: str) -> str:
    title = f"The Compliance Chronicle — Issue #{issue.issue_number} ({issue.period_label})"
    write_pdf(title, issue_to_lines(issue), out_path)
    return out_path


def build_archive(issues: Sequence[Issue], out_dir: str) -> str:
    """Write one text-selectable PDF per issue plus an index.

    Returns the path of the archive index. The index is regenerated
    from the issues actually present, so it can never point at an
    issue that was not written.
    """

    os.makedirs(out_dir, exist_ok=True)
    ordered = sorted(issues, key=lambda i: i.issue_number)
    index_rows = []
    for issue in ordered:
        filename = f"{issue.slug()}.pdf"
        render_issue_pdf(issue, os.path.join(out_dir, filename))
        index_rows.append(
            {
                "issue_number": issue.issue_number,
                "period_label": issue.period_label,
                "publish_date": issue.publish_date.isoformat(),
                "file": filename,
                "items": len(issue.items),
                "quiet_month": issue.quiet_month,
            }
        )

    generated = _dt.date.today().isoformat()
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {"schema": "compliance_chronicle.archive/v1", "generated": generated, "issues": index_rows},
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")

    def esc(text: str) -> str:
        return html.escape(text, quote=True)

    html_rows = "\n".join(
        "<tr>"
        f"<td>#{row['issue_number']}</td>"
        f"<td>{esc(row['period_label'])}</td>"
        f"<td>{esc(row['publish_date'])}</td>"
        f"<td>{'quiet month' if row['quiet_month'] else str(row['items']) + ' item(s)'}</td>"
        f"<td><a href=\"{esc(row['file'])}\">PDF</a></td>"
        "</tr>"
        for row in index_rows
    )
    index_html = (
        "<html><head><meta charset=\"utf-8\">"
        "<title>The Compliance Chronicle — Issue Archive</title></head><body>"
        "<h1>The Compliance Chronicle — Issue Archive</h1>"
        "<p>Every past issue as a text-selectable PDF. "
        "This briefing is information, not legal advice.</p>"
        "<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\">"
        "<tr><th>Issue</th><th>Period</th><th>Published</th><th>Contents</th><th>PDF</th></tr>"
        f"{html_rows}"
        "</table>"
        f"<p><small>Archive generated {esc(generated)}.</small></p>"
        "</body></html>\n"
    )
    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as handle:
        handle.write(index_html)
    return index_path
