import datetime as dt

from compliance_chronicle.models import Issue, SearchLogEntry
from compliance_chronicle.verification import build_ledger, quiet_month_missing_sources

from conftest import make_search_log, make_unverified_item, make_verified_item


class TestLedger:
    def test_ledger_counts(self):
        issue = Issue(
            issue_number=1,
            period_label="2026-08",
            publish_date=dt.date(2026, 9, 1),
            items=[make_verified_item("A"), make_unverified_item("B")],
        )
        ledger = build_ledger(issue)
        assert ledger.total == 2
        assert ledger.verified_count == 1
        assert ledger.unverified_count == 1
        assert ledger.majority_unverified is False

    def test_ledger_rows_carry_evidence(self):
        issue = Issue(
            issue_number=1,
            period_label="2026-08",
            publish_date=dt.date(2026, 9, 1),
            items=[make_verified_item("A"), make_unverified_item("B")],
        )
        rows = {r.item_id: r for r in build_ledger(issue).rows}
        assert rows["A"].citation_reference == "Tex. Health & Safety Code ch. 437"
        assert "could not verify" in rows["B"].unverified_reason.lower()

    def test_empty_issue_ledger(self, quiet_issue):
        ledger = build_ledger(quiet_issue)
        assert ledger.total == 0 and not ledger.majority_unverified

    def test_to_dict_shape(self):
        issue = Issue(
            issue_number=1, period_label="p", publish_date=dt.date(2026, 9, 1),
            items=[make_verified_item("A")],
        )
        data = build_ledger(issue).to_dict()
        assert data["verified_count"] == 1 and len(data["rows"]) == 1


class TestQuietMonthSources:
    def test_full_coverage(self, quiet_issue):
        assert quiet_month_missing_sources(quiet_issue) == set()

    def test_missing_class_named(self, quiet_issue):
        quiet_issue.search_log = [
            e for e in quiet_issue.search_log if e.source_class != "fee_schedule"
        ]
        assert quiet_month_missing_sources(quiet_issue) == {"fee_schedule"}

    def test_empty_log(self, quiet_issue):
        quiet_issue.search_log = []
        missing = quiet_month_missing_sources(quiet_issue)
        assert "state_statute" in missing and "fee_schedule" in missing

    def test_unknown_class_does_not_count(self, quiet_issue):
        quiet_issue.search_log.append(
            SearchLogEntry(
                source_name="blog", source_class="secondary_press",
                checked_at=dt.date(2026, 9, 28),
            )
        )
        # still complete because the required four are present; press adds nothing
        assert quiet_month_missing_sources(quiet_issue) == set()
