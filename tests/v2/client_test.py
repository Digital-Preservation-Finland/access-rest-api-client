"""
dpres_access_rest_api_client.v2.client tests
"""

import math
from datetime import datetime, timezone

import pytest

import dpres_access_rest_api_client.v2.client


def test_dip_request(testpath, access_rest_api_host, client_v2, requests_mock):
    """
    Test downloading a DIP using the AccessClient methods
    """
    download_path = testpath / "spam.zip"
    requests_mock.post(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/preserved/"
        "spam/disseminate",
        json={
            "status": "success",
            "data": {
                "disseminated": (
                    "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                    "spam_dip"
                )
            },
        },
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {"complete": "false", "actions": {}},
        },
    )
    requests_mock.delete(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "true",
            },
        },
    )

    dip_request = client_v2.create_dip_request("spam", archive_format="zip")

    # Perform the first poll request; DIP is not yet ready
    assert not dip_request.check_status()
    assert not dip_request.ready

    with pytest.raises(ValueError) as exc:
        dip_request.download(download_path)
    assert str(exc.value) == "DIP is not ready for download yet"

    # Perform delete DIP request; DIP cannot be deleted yet
    with pytest.raises(ValueError) as exc:
        dip_request.delete()
    assert str(exc.value) == "DIP is not ready for deletion"

    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {
                "complete": "true",
                "actions": {
                    "download": (
                        "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                        "spam_dip/download"
                    )
                },
            },
        },
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip/download",
        content=b"This is a complete DIP in a ZIP sent in a blip",
        headers={
            # requests-mock does not generate a Content-Length header
            # automatically
            "Content-Length": "46"
        },
    )

    # Second poll reuest; DIP is now ready
    assert dip_request.check_status()
    dip_request.download(download_path)

    assert download_path.is_file()
    expected_bytes = b"This is a complete DIP in a ZIP sent in a blip"
    assert download_path.read_bytes() == expected_bytes

    # DIP deletion should now return True
    delete_request = dip_request.delete()
    assert delete_request is True


def test_host_change(client_v2):
    """Test that host can not be changed."""
    with pytest.raises(Exception):
        client_v2.host = "new_host"


def test_poll_interval_iter():
    """
    Test that poll interval iterator returns poll intervals in the expected
    range
    """
    poll_interval_iter = (
        dpres_access_rest_api_client.v2.client.get_poll_interval_iter()
    )

    for _ in range(0, 5):
        # First five are 3 seconds with 0.5s of jitter
        assert math.isclose(next(poll_interval_iter), 3, abs_tol=0.5)

    for _ in range(0, 5):
        # Second five are 10 seconds...
        assert math.isclose(next(poll_interval_iter), 10, abs_tol=0.5)

    for _ in range(0, 10):
        # ..and the last value of 60 seconds is repeated forever
        assert math.isclose(next(poll_interval_iter), 60, abs_tol=0.5)


def test_get_ingest_report_entries(
    access_rest_api_host, client_v2, requests_mock
):
    """
    Test that list of ingest report entries are returned for given sip_id
    in correctly modified form: download key is removed, date converted
    to datetime and reports are sorted by date, newest report being the first
    in the list.
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id",
        json={
            "status": "success",
            "data": {
                "results": [
                    {
                        "date": "2022-01-01T00:00:00Z",
                        "download": {
                            "html": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_1?type=html"
                            ),
                            "xml": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_1?type=xml"
                            ),
                        },
                        "id": "fake_transfer_id_1",
                        "status": "accepted",
                    },
                    {
                        "date": "2022-01-02T00:00:00Z",
                        "download": {
                            "html": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_2?type=html"
                            ),
                            "xml": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_2?type=xml"
                            ),
                        },
                        "id": "fake_transfer_id_2",
                        "status": "rejected",
                    },
                ]
            },
        },
    )
    correct_result = [
        {
            "date": datetime(2022, 1, 2, tzinfo=timezone.utc),
            "transfer_id": "fake_transfer_id_2",
            "status": "rejected",
        },
        {
            "date": datetime(2022, 1, 1, tzinfo=timezone.utc),
            "transfer_id": "fake_transfer_id_1",
            "status": "accepted",
        },
    ]

    received_entries = client_v2.get_ingest_report_entries("doi:fake_id")
    assert received_entries == correct_result


def test_get_ingest_report(access_rest_api_host, client_v2, requests_mock):
    """
    Test that ingest report is returned for given id with correct file type
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id?type=html",
        content=b"html ingest report",
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id?type=xml",
        content=b"xml ingest report",
    )

    html_report = client_v2.get_ingest_report(
        "doi:fake_id", "fake_transfer_id", "html"
    )
    xml_report = client_v2.get_ingest_report(
        "doi:fake_id", "fake_transfer_id", "xml"
    )

    assert html_report == b"html ingest report"
    assert xml_report == b"xml ingest report"


def test_invalid_ingest_report_file_type(client_v2):
    """
    Test that trying to get ingest report with an invalid file type raises
    ValueError
    """
    with pytest.raises(ValueError) as error:
        client_v2.get_ingest_report(
            "sip_id", "transfer_id", "invalid_file_type"
        )
    assert "Invalid file type 'invalid_file_type'" in str(error.value)


def test_get_latest_ingest_report(
    access_rest_api_host, client_v2, requests_mock
):
    """
    Test that the latest ingest report is returned when there exists many
    ingest reports for a package.
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id",
        json={
            "status": "success",
            "data": {
                "results": [
                    {
                        "date": "1980-01-01T00:00:00Z",
                        "download": {
                            "html": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_1?type=html"
                            ),
                            "xml": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_1?type=xml"
                            ),
                        },
                        "id": "fake_transfer_id_1",
                        "status": "accepted",
                    },
                    {
                        "date": "2000-01-01T00:00:00Z",
                        "download": {
                            "html": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_2?type=html"
                            ),
                            "xml": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_2?type=xml"
                            ),
                        },
                        "id": "fake_transfer_id_2",
                        "status": "rejected",
                    },
                    {
                        "date": "1990-01-01T00:00:00Z",
                        "download": {
                            "html": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_3?type=html"
                            ),
                            "xml": (
                                "/api/2.0/urn:uuid:fake_contract_id"
                                "/ingest/report/doi:fake_id/"
                                "fake_transfer_id_3?type=xml"
                            ),
                        },
                        "id": "fake_transfer_id_3",
                        "status": "accepted",
                    },
                ]
            },
        },
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id_1?type=html",
        content=b"oldest ingest report",
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id_2?type=html",
        content=b"latest ingest report",
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id_3?type=html",
        content=b"old ingest report",
    )

    report = client_v2.get_latest_ingest_report("doi:fake_id", "html")
    assert report == b"latest ingest report"


def test_no_latest_ingest_report(
    access_rest_api_host, client_v2, requests_mock
):
    """
    Test that if there are no ingest reports when trying to get the latest
    report, None is returned.
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id",
        status_code=404,
    )

    report = client_v2.get_latest_ingest_report("doi:fake_id", "html")
    assert report is None


def test_no_ingest_report(access_rest_api_host, client_v2, requests_mock):
    """
    Test that if there is no ingest report with given ids, None is returned.
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id?type=html",
        status_code=404,
    )

    report = client_v2.get_ingest_report(
        "doi:fake_id", "fake_transfer_id", "html"
    )
    assert report is None


def test_no_ingest_reports(access_rest_api_host, client_v2, requests_mock):
    """
    Test that if there are no ingest reports for a SIP, empty list is returned.
    """
    # When there are no available ingest reports, access-rest-api returns 404
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id",
        status_code=404,
    )

    received_entries = client_v2.get_ingest_report_entries("doi:fake_id")
    assert received_entries == []


def test_ssl_verification(mock_config):
    """Test that SSL verification is enabled by default."""
    # Remove 'verify_ssl' parameter from configuration file
    mock_config.remove_option("dpres", "verify_ssl")

    client = dpres_access_rest_api_client.v2.client.AccessClient()
    assert client.session.verify
