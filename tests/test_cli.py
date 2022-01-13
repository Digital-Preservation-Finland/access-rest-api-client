"""
dpres_access_rest_api_client.cli tests
"""
from urllib.parse import urlencode


def test_help(cli_runner):
    """
    Test that `--help` prints the help output
    """
    result = cli_runner(["--help"])

    # Commands are listed in the help output
    assert "Download a preserved package" in result.output
    assert "List and search for" in result.output


def test_write_config(cli_runner, home_config_path):
    """
    Test that `write-config` creates the configuration file
    """
    # Remove the existing file and ensure it is regenerated
    home_config_path.unlink()

    result = cli_runner(["write-config"])

    assert f"Configuration file written to {home_config_path}" in result.output
    assert home_config_path.is_file()
    assert "[dpres]" in home_config_path.read_text()

    home_config_path.write_text("overwritten config")

    # If the file exists, nothing is written at all
    result = cli_runner(["write-config"])
    assert "Configuration file already exists" in result.output
    assert home_config_path.read_text() == "overwritten config"


def test_search(cli_runner, requests_mock):
    """
    Test that a search can be performed
    """
    qs_encoded = urlencode({
        "page": 1,
        "limit": 1000,
        # Default search query if user didn't provide one
        "q": "pkg_type:AIP"
    })

    requests_mock.get(
        f"http://fakeapi/api/2.0/urn:uuid:fake_contract_id/"
        f"search?{qs_encoded}",
        json={
            "status": "success",
            "data": {
                "results": [
                    {
                        "location": (
                            "/api/2.0/urn:uuid:fake_contract_id/preserved/"
                            "spam"
                        ),
                        "createdate": "2021-08-01T08:59:05Z",
                        "id": "spam",
                        "pkg_type": "AIP"
                    },
                    {
                        "location": (
                            "/api/2.0/urn:uuid:fake_contract_id/preserved/"
                            "eggs"
                        ),
                        "createdate": "2021-08-02T09:01:58Z",
                        "lastmoddate": "2021-08-03T09:01:58Z",
                        "id": "eggs",
                        "pkg_type": "AIP"
                    }
                ],
                "links": {
                    "self": "/"
                }
            }
        }
    )

    result = cli_runner(["search"])
    output = result.output

    assert "Displaying page 1 with 2 results" in output

    assert "spam" in output
    assert "2021-08-01T08:59:05Z" in output
    assert "N/A" in output

    # ID, package type, creation date and modification date
    # are shown in that order
    assert output.index("AIP") > output.index("spam")
    assert output.index("2021-08-01T08:59:05Z") > output.index("AIP")
    assert output.index("N/A") > output.index("2021-08-01T08:59:05Z")

    assert "eggs" in output


def test_search_query(cli_runner, requests_mock):
    """
    Test performing a search with a custom query
    """
    qs_encoded = urlencode({"page": 1, "limit": 1000, "q": "mets_OBJID:eggs"})

    requests_mock.get(
        f"http://fakeapi/api/2.0/urn:uuid:fake_contract_id/"
        f"search?{qs_encoded}",
        json={
            "status": "success",
            "data": {
                "results": [
                    {
                        "location": (
                            "/api/2.0/urn:uuid:fake_contract_id/preserved/"
                            "eggs"
                        ),
                        "createdate": "2021-08-02T09:01:58Z",
                        "lastmoddate": "2021-08-03T09:01:58Z",
                        "id": "eggs",
                        "pkg_type": "AIP"
                    }
                ],
                "links": {
                    "self": "/"
                }
            }
        }
    )

    result = cli_runner(["search", "--query", "mets_OBJID:eggs"])
    output = result.output

    assert "eggs" in output
    assert "spam" not in output


def test_download(cli_runner, requests_mock, testpath):
    """
    Test downloading a DIP using the `download` command
    """
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
    requests_mock.delete(
        "http://fakeapi/api/2.0/urn:uuid:fake_contract_id/disseminated/"
        "spam_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "true",
            }
        }
    )

    download_dir = testpath / "download"
    download_dir.mkdir()

    download_path = download_dir / "spam.zip"

    result = cli_runner([
        "download", "--path", str(download_path), "spam"
    ])
    output = result.output

    assert f"downloading to {download_path}" in output

    # File size shown during download
    assert "Downloading (46 Bytes)" in output

    assert download_path.is_file()
    assert download_path.read_bytes() == \
        b"This is a complete DIP in a ZIP sent in a blip"

    # DIP deletion should default to True
    assert 'delete' in output


def test_delete_dip_query(cli_runner, requests_mock):
    """
    Test performing DIP deletion with both a successful deletion
    and an unsuccessful deletion.
    """
    requests_mock.delete(
        "http://fakeapi/api/2.0/urn:uuid:fake_contract_id/disseminated/"
        "spam_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "true",
            }
        }
    )
    requests_mock.delete(
        "http://fakeapi/api/2.0/urn:uuid:fake_contract_id/disseminated/"
        "not_found_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "false",
            }
        },
    )

    # Successful deletion
    result = cli_runner(["delete", "spam_dip"])
    output = result.output
    assert "Proceeding to delete" in output

    # Unsuccessful deletion
    result = cli_runner(["delete", "not_found_dip"])
    output = result.output
    assert "Proceeding to delete" in output
    assert "DIP could not be deleted" in output
