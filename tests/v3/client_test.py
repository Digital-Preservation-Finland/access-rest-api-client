"""Module that tests dpres_access_rest_api_client.v3.client"""

import pytest
from requests.exceptions import HTTPError


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload(client_v3, uploadable_file_fx):
    """Test that we can upload without issue.

    The store_url is intentionally set to False so that we won't trigger
    tuspy's implementation of file storage cache.
    """
    uploader = client_v3.create_uploader(
        file_path=str(uploadable_file_fx), chunk_size=3, store_url=False
    )
    uploader.upload_chunk()
    uploader.upload()


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-00000000-0000-0000-0000-000000000002", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Get transfer",
         "Get transfer in progress",
         "Unauthorized access attempt"],
)
def test_get_transfer(client_v3, transfer_id, transfer_exists):
    """Test that we can get specific transfer and status is readable."""
    if transfer_exists:
        transfer = client_v3.get_transfer(transfer_id)
        assert transfer
        assert transfer["status"]
    else:
        with pytest.raises(HTTPError):
            client_v3.get_transfer(transfer_id)


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "report_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Get report", "Unauthorized access attempt"],
)
def test_get_validation_report(client_v3, transfer_id, report_exists):
    """Test that we can get specific transfer's report to download."""
    if report_exists:
        report = client_v3.get_validation_report(transfer_id)
        assert report
    else:
        with pytest.raises(HTTPError):
            client_v3.get_validation_report(transfer_id)


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "expected_success"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Delete transfer", "Unauthorized deletion attempt"],
)
def test_delete_transfer(client_v3, transfer_id, expected_success):
    """Test that we can delete the transfer information and their reports."""
    success = client_v3.delete_transfer(transfer_id)
    assert success is expected_success


@pytest.mark.usefixtures("mock_access_rest_api_v3_list_endpoint")
@pytest.mark.parametrize(
    ("status", "page", "limit", "expected_count", "has_prev", "has_next"),
    [
        (None, None, None, 20, False, False),
        (None, None, "5", 5, False, True),
        (None, "2", "5", 5, True, True),
        ("accepted", "1", "20", 5, False, False),
    ],
    ids=["Normal listing", "Limited listing", "Page 2", "Status filtered"],
)
def test_list_transfers(
    client_v3, status, page, limit, expected_count, has_prev, has_next
):
    """Test that we can get list of recent transfers."""
    search_result = client_v3.list_transfers(
        status=status, page=page, limit=limit
    )

    assert len(search_result.results) == expected_count
    if has_prev:
        assert search_result.prev_url
    else:
        assert not search_result.prev_url

    if has_next:
        assert search_result.next_url
    else:
        assert not search_result.next_url
