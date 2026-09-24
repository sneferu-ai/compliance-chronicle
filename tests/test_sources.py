from compliance_chronicle import sources


class TestRegistry:
    def test_known_classes_stable(self):
        assert set(sources.source_class_keys()) == {
            "state_statute",
            "state_admin_code",
            "fee_schedule",
            "state_agency_guidance",
            "county_health",
            "legislative_watch",
            "secondary_press",
        }

    def test_secondary_press_never_authoritative(self):
        assert not sources.is_authoritative("secondary_press")
        assert sources.is_authoritative("state_statute")

    def test_unknown_class_not_authoritative(self):
        assert not sources.is_authoritative("nope")


class TestClassification:
    def test_statutes_host(self):
        url = "https://statutes.capitol.texas.gov/Docs/HS/htm/HS.437.htm"
        assert sources.classify_url(url) == "state_statute"

    def test_dshs_is_agency_guidance(self):
        url = "https://www.dshs.texas.gov/food-manufacturers-wholesalers/cottage-food-industry"
        assert sources.classify_url(url) == "state_agency_guidance"

    def test_unrecognized_url(self):
        assert sources.classify_url("https://example.com/blog") is None
        assert sources.classify_url("") is None


class TestConflictResolution:
    def test_statute_beats_guidance(self):
        assert sources.resolve_conflict("state_statute", "state_agency_guidance") == "state_statute"
        assert sources.resolve_conflict("state_agency_guidance", "state_statute") == "state_statute"

    def test_equal_authority_is_unresolvable(self):
        assert sources.resolve_conflict("state_statute", "state_statute") is None

    def test_unknown_class_loses(self):
        assert sources.resolve_conflict("state_statute", "my_blog") == "state_statute"


class TestExactCitationHeuristic:
    def test_pinpoints_accepted(self):
        assert sources.looks_like_exact_citation("Tex. Health & Safety Code ch. 437")
        assert sources.looks_like_exact_citation("25 Tex. Admin. Code § 229.661")
        assert sources.looks_like_exact_citation("HB 970, 83rd Leg.")
        assert sources.looks_like_exact_citation("Section 437.002")

    def test_vague_rejected(self):
        assert not sources.looks_like_exact_citation("the DSHS website")
        assert not sources.looks_like_exact_citation("")
        assert not sources.looks_like_exact_citation("   ")


class TestQuietMonthRequirements:
    def test_required_classes(self):
        assert "state_statute" in sources.REQUIRED_QUIET_MONTH_SOURCES
        assert "secondary_press" not in sources.REQUIRED_QUIET_MONTH_SOURCES
