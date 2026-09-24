from compliance_chronicle import render_email
from compliance_chronicle.models import ACTION_LIST_NOTE, DISCLAIMER


def unwrapped(text: str) -> str:
    """Collapse newlines so wrapping never defeats a verbatim-content check."""
    return " ".join(text.split())


class TestPlainText:
    def test_header_and_disclaimer(self, sample_issue):
        text = render_email.render_plain(sample_issue)
        assert "THE COMPLIANCE CHRONICLE" in text
        assert "Issue #1" in text
        assert "2026-08" in text
        assert DISCLAIMER in unwrapped(text)

    def test_verified_item_shows_citation_and_action(self, sample_issue):
        text = render_email.render_plain(sample_issue)
        assert "Tex. Health & Safety Code ch. 437" in text
        assert "statutes.capitol.texas.gov" in text
        assert "Action:" in text and "Deadline: 2026-10-01" in text
        assert "File at:" in text
        assert ACTION_LIST_NOTE in unwrapped(text)

    def test_unverified_item_is_explicit(self, sample_issue, unverified_item):
        sample_issue.items.append(unverified_item)
        text = render_email.render_plain(sample_issue)
        assert "WE COULD NOT VERIFY THIS ITEM" in text

    def test_ledger_present_with_totals(self, sample_issue):
        text = render_email.render_plain(sample_issue)
        assert "VERIFICATION LEDGER" in text
        assert "[VERIFIED]" in text
        assert "1 verified, 0 unverified" in text

    def test_calendar_present(self, sample_issue):
        text = render_email.render_plain(sample_issue)
        assert "FORWARD DEADLINE CALENDAR" in text
        assert "2026-11-30" in text

    def test_quiet_month_shape(self, quiet_issue):
        text = render_email.render_plain(quiet_issue)
        assert "NO MATERIAL CHANGES THIS MONTH" in text
        assert "SEARCH LOG" in text
        assert "25 TAC 229.661" in text
        assert "FORWARD DEADLINE CALENDAR" in text

    def test_verification_failure_banner(self, sample_issue):
        sample_issue.verification_failure_declared = True
        text = render_email.render_plain(sample_issue)
        assert "VERIFICATION WARNING FOR THIS ISSUE" in text

    def test_footer_disclaimer_repeats(self, sample_issue):
        text = render_email.render_plain(sample_issue)
        assert "information, not legal advice" in text


class TestReadTime:
    def test_read_minutes_math(self):
        assert render_email.read_minutes(" ".join(["w"] * 400)) == 2.0

    def test_sample_issue_under_ten_minutes(self, sample_issue):
        assert render_email.read_minutes(render_email.render_plain(sample_issue)) < 10


class TestHtml:
    def test_html_escapes_and_links(self, sample_issue):
        sample_issue.items[0].title = "Labels & <inspections>"
        out = render_email.render_html(sample_issue)
        assert "Labels &amp; &lt;inspections&gt;" in out
        assert '<a href="https://statutes.capitol.texas.gov/' in out
        assert "VERIFIED" in out
        assert "not legal advice" in out

    def test_html_quiet_month(self, quiet_issue):
        out = render_email.render_html(quiet_issue)
        assert "No material changes this month." in out
        assert "Search log" in out
