"""
dpres_access_rest_api_client.client tests
"""
import math

import pytest

from dpres_access_rest_api_client.client import get_poll_interval_iter


def test_dip_request(testpath, client, requests_mock):
    """
    Test downloading a DIP using the AccessClient methods
    """
    download_path = testpath / "spam.zip"
    requests_mock.post(
        "http://fakeapi/api/2.0/urn:uuid:fake_contract_id/preserved/spam/"
        "disseminate",
        json={
            "status": "success",
            "data": {
                "disseminated": (
                    "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                    "spam_dip"
                )
            }
        }
    )
    requests_mock.get(
        "http://fakeapi/api/2.0/urn:uuid:fake_contract_id/disseminated/"
        "spam_dip",
        json={
            "status": "success",
            "data": {
                "complete": "false",
                "actions": {}
            }
        }
    )

    dip_request = client.create_dip_request("spam", archive_format="zip")

    # Perform the first poll request; DIP is not yet ready
    assert not dip_request.poll()
    assert not dip_request.ready

    with pytest.raises(ValueError) as exc:
        dip_request.download(download_path)

    assert str(exc.value) == "DIP is not ready for download yet"

    requests_mock.get(
        "http://fakeapi/api/2.0/urn:uuid:fake_contract_id/disseminated/"
        "spam_dip",
        json={
            "status": "success",
            "data": {
                "complete": "true",
                "actions": {
                    "download": (
                        "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                        "spam_dip/download"
                    )
                }
            }
        }
    )
    requests_mock.get(
        "http://fakeapi/api/2.0/urn:uuid:fake_contract_id/disseminated/"
        "spam_dip/download",
        content=b"This is a complete DIP in a ZIP sent in a blip",
        headers={
            # requests-mock does not generate a Content-Length header
            # automatically
            "Content-Length": "46"
        }
    )

    # Second poll reuest; DIP is now ready
    assert dip_request.poll()
    dip_request.download(download_path)

    assert download_path.is_file()
    assert download_path.read_bytes() == \
        b"This is a complete DIP in a ZIP sent in a blip"


def test_poll_interval_iter():
    """
    Test that poll interval iterator returns poll intervals in the expected
    range
    """
    poll_interval_iter = get_poll_interval_iter()

    for _ in range(0, 5):
        # First five are 3 seconds with 0.5s of jitter
        assert math.isclose(next(poll_interval_iter), 3, abs_tol=0.5)

    for _ in range(0, 5):
        # Second five are 10 seconds...
        assert math.isclose(next(poll_interval_iter), 10, abs_tol=0.5)

    for _ in range(0, 10):
        # ..and the last value of 60 seconds is repeated forever
        assert math.isclose(next(poll_interval_iter), 60, abs_tol=0.5)
