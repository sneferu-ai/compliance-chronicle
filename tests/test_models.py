import datetime as dt

from compliance_chronicle.models import (
    DISCLAIMER,
    Action,
    ChangeItem,
    Citation,
    Issue,
)

from conftest import make_action, make_citation, make_unverified_item, make_verified_item


class TestCitation:
    def test_valid_citation_passes(self):
        assert make_citation().validate() == []

    def test_missing_reference_fails(self):
        errors = make_citation(reference="").validate()
        assert any("exact citation" in e for e in errors)

    def test_vague_reference_fails(self):
        errors = make_citation(reference="see the DSHS website").validate()
        assert any("pinpoint" in e for e in errors)

    def test_missing_url_fails(self):
        errors = make_citation(url="").validate()
        assert any("source URL" in e for e in errors)

    def test_non_url_fails(self):
        errors = make_citation(url="the internet").validate()
        assert any("not a URL" in e for e in errors)

    def test_unknown_source_class_fails(self):
        errors = make_citation(source_class="my_blog").validate()
        assert any("unknown source class" in e for e in errors)

    def test_non_authoritative_class_fails(self):
        errors = make_citation(source_class="secondary_press").validate()
        assert any("not authoritative" in e for e in errors)

    def test_roundtrip(self):
        citation = make_citation(accessed=dt.date(2026, 8, 28))
        assert Citation.from_dict(citation.to_dict()) == citation


class TestAction:
    def test_valid_action_passes(self):
        assert make_action().validate() == []

    def test_missing_deadline_fails(self):
        errors = make_action(deadline="").validate()
        assert any("deadline" in e for e in errors)

    def test_missing_portal_fails(self):
        errors = make_action(portal_url="").validate()
        assert any("portal" in e for e in errors)


class TestChangeItem:
    def test_verified_item_complete_passes(self, verified_item):
        assert verified_item.validate() == []

    def test_verified_without_citation_fails(self):
        item = make_verified_item(citation=None)
        assert any("no citation" in e for e in item.validate())

    def test_verified_without_action_fails(self):
        item = make_verified_item(action=None)
        assert any("no action" in e for e in item.validate())

    def test_verified_without_summary_fails(self):
        item = make_verified_item(summary="")
        assert any("summary" in e for e in item.validate())

    def test_unverified_with_reason_passes(self, unverified_item):
        assert unverified_item.validate() == []

    def test_unverified_without_reason_fails(self):
        item = make_unverified_item(unverified_reason="")
        assert any("could not be verified" in e or "could not verify" in e for e in item.validate())

    def test_bad_status_fails(self):
        item = make_verified_item(status="probably")
        assert any("status" in e for e in item.validate())

    def test_roundtrip(self, verified_item):
        assert ChangeItem.from_dict(verified_item.to_dict()) == verified_item


class TestIssue:
    def test_valid_issue_passes(self, sample_issue):
        assert sample_issue.validate() == []

    def test_disclaimer_must_ship_verbatim(self, sample_issue):
        sample_issue.disclaimer = "tl;dr don't sue us"
        assert any("disclaimer" in e for e in sample_issue.validate())

    def test_quiet_month_with_items_fails(self, sample_issue):
        sample_issue.quiet_month = True
        assert any("quiet" in e for e in sample_issue.validate())

    def test_duplicate_item_ids_fail(self, sample_issue):
        sample_issue.items.append(make_verified_item("CHG-001"))
        assert any("duplicate" in e for e in sample_issue.validate())

    def test_majority_unverified_math(self):
        issue = Issue(
            issue_number=3,
            period_label="2026-08",
            publish_date=dt.date(2026, 9, 1),
            items=[
                make_verified_item("A"),
                make_unverified_item("B"),
                make_unverified_item("C"),
            ],
        )
        assert issue.majority_unverified is True
        issue.items = [make_verified_item("A"), make_unverified_item("B")]
        assert issue.majority_unverified is False  # exactly half is not a majority
        issue.items = []
        assert issue.majority_unverified is False

    def test_earliest_deadline_spans_items_and_calendar(self, sample_issue):
        sample_issue.calendar = []
        assert sample_issue.earliest_deadline() == dt.date(2026, 10, 1)
        sample_issue.calendar = []
        sample_issue.items[0].action = make_action(deadline=dt.date(2026, 9, 20))
        assert sample_issue.earliest_deadline() == dt.date(2026, 9, 20)

    def test_roundtrip(self, quiet_issue):
        assert Issue.from_dict(quiet_issue.to_dict()) == quiet_issue
