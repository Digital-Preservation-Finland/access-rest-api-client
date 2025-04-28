"""
dpres_access_rest_api_client.cli tests
"""

import json
from urllib.parse import urlencode

import pytest

import dpres_access_rest_api_client.cli


def test_help(cli_runner):
    """
    Test that `--help` prints the help output
    """
    result = cli_runner(["--help"])

    # Commands are listed in the help output
    commands = ["dip", "ingest-report", "search", "upload", "write-config"]
    for command in commands:
        assert command in result.output


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


def test_search(cli_runner, access_rest_api_host, requests_mock):
    """
    Test that a search can be performed
    """
    qs_encoded = urlencode(
        {
            "page": 1,
            "limit": 1000,
            # Default search query if user didn't provide one
            "q": "pkg_type:AIP",
        }
    )

    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
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
                        "pkg_type": "AIP",
                    },
                    {
                        "location": (
                            "/api/2.0/urn:uuid:fake_contract_id/preserved/"
                            "eggs"
                        ),
                        "createdate": "2021-08-02T09:01:58Z",
                        "lastmoddate": "2021-08-03T09:01:58Z",
                        "id": "eggs",
                        "pkg_type": "AIP",
                    },
                ],
                "links": {"self": "/"},
            },
        },
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


def test_search_query(cli_runner, access_rest_api_host, requests_mock):
    """
    Test performing a search with a custom query
    """
    qs_encoded = urlencode({"page": 1, "limit": 1000, "q": "mets_OBJID:eggs"})

    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
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
                        "pkg_type": "AIP",
                    }
                ],
                "links": {"self": "/"},
            },
        },
    )

    result = cli_runner(["search", "--query", "mets_OBJID:eggs"])
    output = result.output

    assert "eggs" in output
    assert "spam" not in output


def test_download(cli_runner, access_rest_api_host, requests_mock, testpath):
    """
    Test downloading a DIP using the `download` command
    """
    requests_mock.post(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "preserved/spam/disseminate",
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

    download_dir = testpath / "download"
    download_dir.mkdir()

    download_path = download_dir / "spam.zip"

    result = cli_runner(
        ["dip", "download", "--path", str(download_path), "spam"]
    )
    output = result.output

    assert f"downloading to {download_path}" in output

    # File size shown during download
    assert "Downloading (46 Bytes)" in output

    assert download_path.is_file()
    expected_bytes = b"This is a complete DIP in a ZIP sent in a blip"
    assert download_path.read_bytes() == expected_bytes

    # DIP deletion should default to True
    assert "delete" in output


def test_delete_dip_query(cli_runner, access_rest_api_host, requests_mock):
    """
    Test performing DIP deletion with both a successful deletion
    and an unsuccessful deletion.
    """
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
    requests_mock.delete(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/not_found_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "false",
            },
        },
    )

    # Successful deletion
    result = cli_runner(["dip", "delete", "spam_dip"])
    output = result.output
    assert "Proceeding to delete" in output

    # Unsuccessful deletion
    result = cli_runner(["dip", "delete", "not_found_dip"])
    output = result.output
    assert "Proceeding to delete" in output
    assert "DIP could not be deleted" in output


def test_list_ingest_reports(cli_runner, access_rest_api_host, requests_mock):
    """
    Test listing available ingest reports with 'ingest-report list' command.
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

    result = cli_runner(["ingest-report", "list", "doi:fake_id"])
    output = result.output

    assert "2022-01-01 00:00:00+00:00" in output
    assert "2022-01-02 00:00:00+00:00" in output
    assert "accepted" in output
    assert "rejected" in output
    assert "fake_transfer_id_1" in output
    assert "fake_transfer_id_2" in output


def test_no_ingest_reports(cli_runner, access_rest_api_host, requests_mock):
    """
    Test that CLI gives a sensible message when there are no ingest reports
    available.
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id",
        status_code=404,
    )

    result = cli_runner(["ingest-report", "list", "doi:fake_id"])
    output = result.output

    assert output == "No ingest reports found for SIP id 'doi:fake_id'\n"


def test_no_ingest_report(cli_runner, access_rest_api_host, requests_mock):
    """
    Test that CLI gives a sensible message when a spesified ingest report is
    not available.
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id?type=html",
        status_code=404,
    )

    result = cli_runner(
        [
            "ingest-report",
            "get",
            "doi:fake_id",
            "--transfer-id",
            "fake_transfer_id",
            "--file-type",
            "html",
        ]
    )

    assert result.output == (
        "No ingest report was found with given " "parameters\n"
    )


def test_get_ingest_report_with_correct_file_type(
    cli_runner, access_rest_api_host, requests_mock
):
    """
    Test getting an ingest report with the correct file type.
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

    html_report = cli_runner(
        [
            "ingest-report",
            "get",
            "doi:fake_id",
            "--transfer-id",
            "fake_transfer_id",
            "--file-type",
            "html",
        ]
    )
    assert html_report.output == "html ingest report\n"

    xml_report = cli_runner(
        [
            "ingest-report",
            "get",
            "doi:fake_id",
            "--transfer-id",
            "fake_transfer_id",
            "--file-type",
            "xml",
        ]
    )
    assert xml_report.output == "xml ingest report\n"


def test_get_ingest_report_without_specifying_report(cli_runner):
    """
    Test that calling 'ingest-report get' without setting --latest or
    --transfer-id leads to an error.
    """
    result = cli_runner(["ingest-report", "get", "sip_id"])
    assert "report has to be specified with either --latest" in result.output
    assert result.exit_code != 0


def test_get_ingest_report_with_conflicting_report_specification(cli_runner):
    """
    Test that calling 'ingest-report get' with both --latest and --transfer-id
    leads to an error.
    """
    result = cli_runner(
        [
            "ingest-report",
            "get",
            "sip_id",
            "--latest",
            "--transfer-id",
            "transfer_id",
        ]
    )
    assert "Both --latest and --transfer-id provided" in result.output
    assert result.exit_code != 0


def test_getting_latest_ingest_report(
    cli_runner, access_rest_api_host, requests_mock
):
    """
    Test that calling 'ingest-report get' with --latest flag returns
    the latest ingest report out of many options.
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

    result = cli_runner(
        [
            "ingest-report",
            "get",
            "doi:fake_id",
            "--latest",
            "--file-type",
            "html",
        ]
    )
    assert result.output == "latest ingest report\n"


def test_save_ingest_report_to_path(
    cli_runner, access_rest_api_host, requests_mock, testpath
):
    """
    Test that ingest report is saved to the file system when a path is given.
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/ingest/"
        "report/doi%3Afake_id/fake_transfer_id?type=html",
        content=b"html ingest report",
    )

    download_path = testpath / "ingest_report.html"
    result = cli_runner(
        [
            "ingest-report",
            "get",
            "doi:fake_id",
            "--transfer-id",
            "fake_transfer_id",
            "--file-type",
            "html",
            "--path",
            download_path,
        ]
    )

    assert result.output == f"Ingest report saved to {download_path}\n"

    assert download_path.is_file()
    assert download_path.read_bytes() == b"html ingest report"


@pytest.mark.parametrize(
    "enable_resumable",
    [
        False,
        True,
    ],
    ids=["Normal use", "Resumable enabled"],
)
@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload_file(
    cli_runner, transfer_id, uploadable_file_fx, enable_resumable
):
    """Test that the click-application can upload file."""

    commands = ["upload", "--chunk-size", "3", f"{uploadable_file_fx}"]
    if enable_resumable:
        commands.append("--enable-resumable")
    result = cli_runner(commands)
    assert result.exit_code == 0
    assert f"{transfer_id}" in result.output


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload_empty_file(cli_runner, empty_file_fx):
    """Test that the click-application can handle an empty file"""

    commands = ["upload", f"{empty_file_fx}"]
    result = cli_runner(commands)
    assert result.exit_code == 1
    assert "file is empty" in result.output


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload_wrong_file_ending(cli_runner, wrong_file_ending_fx):
    """Test that the click-application can handle a file with invalid suffix"""

    commands = ["upload", f"{wrong_file_ending_fx}"]
    result = cli_runner(commands)
    assert result.exit_code == 1
    assert "format not supported" in result.output


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-00000000-0000-0000-0000-000000000002", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Get transfer", "Get transfer in progress", "No transfer"],
)
def test_transfers_info(cli_runner, transfer_id, transfer_exists):
    """Test that the click-application can get transfer info."""

    commands = ["transfer", "info", f"{transfer_id}"]
    result = cli_runner(commands)
    if transfer_exists:
        assert result.exit_code == 0
        assert f"{transfer_id}" in result.output
    else:
        assert result.exit_code == 1


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists", "output_file"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True, False),
        ("sip.tar-00000000-0000-0000-0000-000000000001", True, True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False, True),
    ],
    ids=["Write to default", "Write to custom", "No report"],
)
def test_transfers_get_report(
    cli_runner, transfer_id, transfer_exists, output_file, tmp_path,
    monkeypatch,
):
    """Test that the click-application can get transfer report."""

    def _mock_resolve(_):
        """Make Path(".").resolve() return tmp_path"""
        return tmp_path

    commands = ["transfer", "get-report", f"{transfer_id}"]
    if output_file:
        report_path = tmp_path / "report.xml"
        commands.append("--path")
        commands.append(f"{report_path}")
    else:
        monkeypatch.setattr(
            dpres_access_rest_api_client.cli.Path, "resolve", _mock_resolve)
        report_path = tmp_path / f"{transfer_id}-report.xml"

    result = cli_runner(commands)
    if not transfer_exists:
        assert result.exit_code == 1
        # Conclude testing here.
        return

    assert result.exit_code == 0

    assert f"{report_path}" in result.output
    assert report_path.is_file()


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Delete transfer", "No transfer"],
)
def test_transfers_delete(cli_runner, transfer_id, transfer_exists):
    """Test that the click-application can get transfer info."""

    commands = ["transfer", "delete", f"{transfer_id}"]
    result = cli_runner(commands)
    if transfer_exists:
        assert result.exit_code == 0
        assert f"{transfer_id}" in result.output
    else:
        assert result.exit_code == 1


@pytest.mark.usefixtures("mock_access_rest_api_v3_list_endpoint")
def test_transfers_list(cli_runner):
    """Test that the click-application can list the transfers."""
    commands = ["transfer", "list"]
    result = cli_runner(commands)
    assert result.exit_code == 0
    assert "accepted" in result.output


@pytest.mark.parametrize(
    "response_text",
    [
        json.dumps(
            {
                "data": {"message": "I'm a teapot in json format",
                         "random_key": "Some message involved with this key"},
                "status": "fail",
            }
        ),
        "I'm a teapot in text format",
    ],
    ids=["Expected response format", "Unexpected response format"],
)
def test_transfers_list_errors(
    cli_runner, access_rest_api_host, contract_id, requests_mock, response_text
):
    """Test that the click-application handles error responses when
    attempting to list transfers.
    """
    commands = ["transfer", "list"]

    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/{contract_id}/transfers",
        text=response_text,
        status_code=418,
    )

    result = cli_runner(commands)
    assert result.exit_code == 1
    assert "Error:" in result.output
