"""Assembly contract: Sneferu report + curation → issue, never dropping a claim."""

import pytest

from compliance_chronicle import assemble, gates


class TestAssembly:
    def test_sample_report_assembles(self, load_sample):
        issue = assemble.assemble_issue(
            load_sample("sample_research_report.json"), load_sample("sample_curation.json")
        )
        assert issue.issue_number == 1
        assert len(issue.items) == 3
        assert [i.status for i in issue.items] == ["verified", "verified", "unverified"]

    def test_uncited_claim_becomes_unverified_never_dropped(self, load_sample):
        report = load_sample("sample_research_report.json")
        issue = assemble.assemble_issue(report, load_sample("sample_curation.json"))
        rumor = next(i for i in issue.items if i.item_id == "CLM-003")
        assert rumor.status == "unverified"
        assert "could not verify" in rumor.unverified_reason.lower()

    def test_non_authoritative_citation_becomes_unverified(self, load_sample):
        report = load_sample("sample_research_report.json")
        report["claims"][0]["citation"]["source_class"] = "secondary_press"
        issue = assemble.assemble_issue(report, load_sample("sample_curation.json"))
        assert issue.items[0].status == "unverified"

    def test_vague_citation_reference_becomes_unverified(self, load_sample):
        report = load_sample("sample_research_report.json")
        report["claims"][0]["citation"]["reference"] = "the statute"
        issue = assemble.assemble_issue(report, load_sample("sample_curation.json"))
        assert issue.items[0].status == "unverified"

    def test_curation_override_replaces_summary(self, load_sample):
        issue = assemble.assemble_issue(
            load_sample("sample_research_report.json"), load_sample("sample_curation.json")
        )
        assert "floor everything else stands on" in issue.items[0].summary

    def test_explicit_drop_is_recorded_not_silent(self, load_sample):
        curation = load_sample("sample_curation.json")
        curation["overrides"]["CLM-001"] = {"drop": True, "drop_reason": "duplicate of CLM-002"}
        issue = assemble.assemble_issue(load_sample("sample_research_report.json"), curation)
        dropped = next(i for i in issue.items if i.item_id == "CLM-001")
        assert dropped.status == "unverified"
        assert "duplicate" in dropped.unverified_reason

    def test_quiet_month_with_claims_is_an_assembly_error(self, load_sample):
        curation = load_sample("sample_curation.json")
        curation["quiet_month"] = True
        with pytest.raises(assemble.AssemblyError):
            assemble.assemble_issue(load_sample("sample_research_report.json"), curation)

    def test_extra_search_log_and_calendar_merge(self, load_sample):
        curation = load_sample("sample_curation.json")
        curation["extra_search_log"] = [
            {
                "source_name": "County health dept",
                "source_class": "county_health",
                "checked_at": "2026-08-29",
            }
        ]
        curation["extra_calendar"] = [{"label": "Extra deadline", "deadline": "2026-12-01"}]
        issue = assemble.assemble_issue(load_sample("sample_research_report.json"), curation)
        assert any(e.source_class == "county_health" for e in issue.search_log)
        assert any(e.label == "Extra deadline" for e in issue.calendar)

    def test_unknown_report_schema_rejected(self, load_sample):
        report = load_sample("sample_research_report.json")
        report["schema"] = "something-else/v9"
        with pytest.raises(assemble.AssemblyError):
            assemble.assemble_issue(report, load_sample("sample_curation.json"))

    def test_url_classification_fallback(self, load_sample):
        report = load_sample("sample_research_report.json")
        report["claims"][0]["citation"]["source_class"] = ""
        issue = assemble.assemble_issue(report, load_sample("sample_curation.json"))
        assert issue.items[0].citation.source_class == "state_statute"
        assert issue.items[0].status == "verified"

    def test_assembled_sample_passes_gates(self, load_sample):
        issue = assemble.assemble_issue(
            load_sample("sample_research_report.json"), load_sample("sample_curation.json")
        )
        results = gates.validate_issue(issue)
        assert gates.is_shippable(results), [r.message for r in results if not r.passed]

    def test_quiet_sample_passes_gates(self, load_sample):
        issue = assemble.assemble_issue(
            load_sample("sample_quiet_report.json"), load_sample("sample_quiet_curation.json")
        )
        assert issue.quiet_month
        results = gates.validate_issue(issue)
        assert gates.is_shippable(results), [r.message for r in results if not r.passed]


class TestRoundTrip:
    def test_issue_json_roundtrip(self, load_sample, tmp_path):
        issue = assemble.assemble_issue(
            load_sample("sample_research_report.json"), load_sample("sample_curation.json")
        )
        path = tmp_path / "issue.json"
        assemble.save_issue(issue, str(path))
        loaded = assemble.load_issue(str(path))
        assert loaded == issue
        # and gates still pass on the reloaded issue
        assert gates.is_shippable(gates.validate_issue(loaded))
