"""Every falsification criterion in the spec, planted and caught."""

import datetime as dt

from compliance_chronicle import gates
from compliance_chronicle.gates import SEVERITY_FAIL, SEVERITY_WARN
from compliance_chronicle.models import Issue

from conftest import make_unverified_item, make_verified_item


def gate(results, gate_id):
    for result in results:
        if result.gate_id == gate_id:
            return result
    raise AssertionError(f"gate {gate_id} not run; got {[r.gate_id for r in results]}")


class TestHappyPath:
    def test_sample_issue_is_shippable(self, sample_issue):
        results = gates.validate_issue(sample_issue)
        assert gates.is_shippable(results), [r.message for r in results if not r.passed]

    def test_quiet_issue_is_shippable(self, quiet_issue):
        results = gates.validate_issue(quiet_issue)
        assert gates.is_shippable(results), [r.message for r in results if not r.passed]

    def test_assert_shippable_returns_results(self, sample_issue):
        assert gates.assert_shippable(sample_issue)


class TestCitationCoverage:
    """Falsification (1): any claim without citation or unverifiable marker fails."""

    def test_verified_item_without_citation_fails(self, sample_issue):
        sample_issue.items[0].citation = None
        result = gate(gates.validate_issue(sample_issue), "model-validation")
        assert not result.passed and result.severity == SEVERITY_FAIL

    def test_unverified_item_without_reason_fails(self, sample_issue):
        sample_issue.items = [make_unverified_item(unverified_reason="")]
        result = gate(gates.validate_issue(sample_issue), "model-validation")
        assert not result.passed


class TestReadTime:
    """Falsification (2): read time over ten minutes fails."""

    def test_overlong_issue_fails(self, sample_issue):
        sample_issue.intro = "word " * 2100  # > 10 min at 200 wpm
        result = gate(gates.validate_issue(sample_issue), "read-time")
        assert not result.passed and result.severity == SEVERITY_FAIL

    def test_normal_issue_passes(self, sample_issue):
        assert gate(gates.validate_issue(sample_issue), "read-time").passed


class TestLeadTime:
    """Falsification (4): an issue arriving after the earliest deadline it reports fails."""

    def test_publish_after_deadline_fails(self, sample_issue):
        sample_issue.publish_date = dt.date(2026, 10, 2)  # deadline is 2026-10-01
        result = gate(gates.validate_issue(sample_issue), "lead-time")
        assert not result.passed and result.severity == SEVERITY_FAIL
        assert "after" in result.message

    def test_publish_on_deadline_fails(self, sample_issue):
        sample_issue.publish_date = dt.date(2026, 10, 1)
        result = gate(gates.validate_issue(sample_issue), "lead-time")
        assert not result.passed

    def test_short_lead_warns_but_does_not_block(self, sample_issue):
        sample_issue.publish_date = dt.date(2026, 9, 28)  # 3 days before deadline
        results = gates.validate_issue(sample_issue)
        result = gate(results, "lead-time")
        assert not result.passed and result.severity == SEVERITY_WARN
        assert gates.is_shippable(results)  # warnings never block

    def test_calendar_deadline_counts(self, sample_issue):
        sample_issue.items = []
        sample_issue.calendar[0].deadline = dt.date(2026, 8, 15)
        result = gate(gates.validate_issue(sample_issue), "lead-time")
        assert not result.passed


class TestQuietMonth:
    """Falsification (5): quiet month without an auditable search log fails."""

    def test_empty_search_log_fails(self, quiet_issue):
        quiet_issue.search_log = []
        result = gate(gates.validate_issue(quiet_issue), "quiet-search-log")
        assert not result.passed and result.severity == SEVERITY_FAIL

    def test_missing_required_source_class_fails(self, quiet_issue):
        quiet_issue.search_log = quiet_issue.search_log[:3]  # drop fee_schedule
        result = gate(gates.validate_issue(quiet_issue), "quiet-search-log")
        assert not result.passed and "fee_schedule" in result.message

    def test_future_dated_search_entry_fails(self, quiet_issue):
        quiet_issue.search_log[0].checked_at = dt.date(2026, 12, 1)
        result = gate(gates.validate_issue(quiet_issue), "quiet-search-log")
        assert not result.passed

    def test_quiet_month_without_calendar_fails(self, quiet_issue):
        quiet_issue.calendar = []
        result = gate(gates.validate_issue(quiet_issue), "quiet-calendar")
        assert not result.passed and result.severity == SEVERITY_FAIL

    def test_quiet_month_with_items_fails_model_validation(self, quiet_issue):
        quiet_issue.items = [make_verified_item("X")]
        result = gate(gates.validate_issue(quiet_issue), "model-validation")
        assert not result.passed


class TestVerificationMajority:
    """Falsification (6): silently shipping a majority-unverifiable issue fails."""

    def _majority_unverified_issue(self, declared: bool) -> Issue:
        return Issue(
            issue_number=4,
            period_label="2026-08",
            publish_date=dt.date(2026, 9, 1),
            items=[
                make_verified_item("A"),
                make_unverified_item("B"),
                make_unverified_item("C"),
            ],
            verification_failure_declared=declared,
        )

    def test_silent_majority_unverified_fails(self):
        result = gate(gates.validate_issue(self._majority_unverified_issue(False)), "verification-majority")
        assert not result.passed and result.severity == SEVERITY_FAIL
        assert "silently" in result.message

    def test_declared_majority_unverified_passes(self):
        issue = self._majority_unverified_issue(True)
        results = gates.validate_issue(issue)
        assert gate(results, "verification-majority").passed
        assert gates.is_shippable(results)

    def test_minority_unverified_passes_without_declaration(self, sample_issue):
        sample_issue.items.append(make_unverified_item("B"))
        assert gate(gates.validate_issue(sample_issue), "verification-majority").passed


class TestAssertShippable:
    def test_raises_with_gate_details(self, sample_issue):
        sample_issue.items[0].citation = None
        try:
            gates.assert_shippable(sample_issue)
        except gates.IssueNotShippable as exc:
            assert "model-validation" in str(exc)
            assert exc.results
        else:
            raise AssertionError("expected IssueNotShippable")
