from scraper.management.commands.prepare_gov_district_url_candidates import suggested_url


def test_suggested_url_uses_reviewed_catalog_ids_not_declined_city_names():
    assert suggested_url(69) == "https://www.gov.pl/web/po-bialystok"
    assert suggested_url(79) == "https://www.gov.pl/web/po-wloclawek"


def test_suggested_url_rejects_another_institution():
    try:
        suggested_url(56)
    except ValueError as exc:
        assert str(exc) == "not_a_reviewed_district_prosecutor"
    else:
        raise AssertionError("non-district institution must not gain a candidate URL")
