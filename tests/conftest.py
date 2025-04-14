import json
from configparser import ConfigParser
from itertools import cycle
from pathlib import Path
from uuid import uuid4, UUID
import pytest
import requests_mock
from click.testing import CliRunner

from dpres_access_rest_api_client.cli import cli, Context
from dpres_access_rest_api_client.v2.client import AccessClient as ClientV2
from dpres_access_rest_api_client.v3.client import AccessClient as ClientV3


@pytest.fixture(scope="function")
def testpath(tmpdir):
    """
    Create a temporary test directory
    """
    # TODO: Replace `testpath` with built-in `tmp_path` in pytest 3.9.0+
    return Path(str(tmpdir))


@pytest.fixture(scope="function")
def home_config_path(testpath, monkeypatch):
    """
    Path to the user's configuration file in a mocked home directory
    """
    home_dir = testpath / "home" / "testuser"
    monkeypatch.setenv("HOME", str(home_dir))

    config_dir = home_dir / ".config" / "dpres_access_rest_api_client"
    config_dir.mkdir(parents=True)
    return config_dir / "config.conf"


@pytest.fixture(scope="function", autouse=True)
def mock_config(
    monkeypatch, access_rest_api_host, contract_id, home_config_path
):
    """
    Create a mock configuration file by mocking the user's home directory
    and placing a configuration file in the expected place
    """
    home_config_path.write_text(
        "[dpres]\n"
        f"contract_id={contract_id}\n"
        "username=fakeuser\n"
        "password=fakepassword\n"
        "verify_ssl=true\n"
        f"api_host={access_rest_api_host}/"
    )

    config = ConfigParser()
    config.read(str(home_config_path))

    monkeypatch.setattr("dpres_access_rest_api_client.base.CONFIG", config)

    return config


@pytest.fixture(scope="function")
def cli_runner(mock_config):
    """
    Run the CLI entrypoint using the provided arguments and return the
    result
    """

    def wrapper(args, **kwargs):
        """
        Run the CLI entrypoint using provided arguments and return
        the result.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli, args, obj=Context(), catch_exceptions=False, **kwargs
        )
        return result

    return wrapper


@pytest.fixture(scope="function")
def client_v2(mock_config):
    """
    AccessClient instance
    """

    client = ClientV2(config=mock_config)

    return client


@pytest.fixture(scope="function")
def client_v3(mock_config):
    """
    AccessClient instance
    """

    client = ClientV3(config=mock_config)

    return client


@pytest.fixture(scope="session")
def contract_id():
    """Set fixed contract URN UUID for testing purposes."""
    return "urn:uuid:fake_contract_id"


@pytest.fixture(scope="session")
def access_rest_api_host():
    """Set fixed host for testing purposes."""
    return "http://fakeapi.test"


@pytest.fixture(scope="session")
def transfer_id():
    """Set fixed transfer UUID for TUS endpoint testing purposes."""
    return str(uuid4())


@pytest.fixture(scope="function")
def uploadable_file_fx(tmp_path):
    """Generate a temporary file that could be used to test uploading."""
    uploadable_file = tmp_path / "upload_me.tar"
    uploadable_file.write_text("Hadouken!")
    return uploadable_file


@pytest.fixture(scope="function")
def empty_file_fx(tmp_path):
    """Generate empty file."""
    uploadable_file = tmp_path / "upload_me.tar"
    uploadable_file.write_text("")
    return uploadable_file


@pytest.fixture(scope="function")
def wrong_file_ending_fx(tmp_path):
    """Generate file with wrong file ending."""
    uploadable_file = tmp_path / "upload_me.txt"
    uploadable_file.write_text("Hadouken!")
    return uploadable_file


@pytest.fixture(scope="function")
def mock_tus_endpoints(access_rest_api_host, transfer_id):
    """Mock TUS endpoints by having dynamic responses."""
    tus_url = f"{access_rest_api_host}/api/3.0/transfers"
    transfer_exists = False
    chunks_uploaded = 0
    upload_length = 0
    upload_metadata = ""
    tus_supported_extensions = ["creation", "termination"]
    tus_version = "1.0.0"
    tus_supported_version = ["1.0.0"]
    options_headers = {
        "Tus-Extension": ",".join(tus_supported_extensions),
        "Tus-Resumable": tus_version,
        "Tus-Version": ",".join(tus_supported_version),
    }

    def head_response(request, context):
        if not transfer_exists:
            context.status_code = 404
            context.headers = {"Tus-Resumable": tus_version}
            return ""

        context.headers = {
            "Cache-Control": "no-store",
            "Tus-Resumable": tus_version,
            "Upload-Offset": str(chunks_uploaded),
            "Upload-Metadata": upload_metadata,
            "Upload-Length": str(upload_length),
        }
        return ""

    def patch_response(request, context):
        if not transfer_exists:
            context.status_code = 404
            context.headers = {"Tus-Resumable": tus_version}
            return ""

        nonlocal chunks_uploaded
        content_length = int(request.headers["Content-Length"])
        chunks_uploaded += content_length
        if chunks_uploaded > upload_length:
            chunks_uploaded = upload_length
        context.headers = {
            "Tus-Resumable": tus_version,
            "Upload-Offset": str(chunks_uploaded),
        }
        return ""

    def post_response(request, context):
        nonlocal transfer_exists
        nonlocal upload_metadata
        nonlocal upload_length
        transfer_exists = True
        upload_metadata = request.headers["Upload-Metadata"]
        upload_length = int(request.headers["Upload-Length"])

        context.headers = {
            "Location": f"{tus_url}/{transfer_id}",
            "Tus-Resumable": tus_version,
        }
        return ""

    with requests_mock.Mocker() as mock:
        mock.options(
            f"{tus_url}", text="", headers=options_headers, status_code=204
        )
        mock.head(
            f"{tus_url}/{transfer_id}", text=head_response, status_code=204
        )
        mock.patch(
            f"{tus_url}/{transfer_id}", text=patch_response, status_code=204
        )
        mock.post(f"{tus_url}", text=post_response, status_code=201)
        yield


@pytest.fixture(scope="function")
def mock_access_rest_api_v3_endpoints(access_rest_api_host, contract_id):
    # We'll use fixed transfer_id.
    transfer_ids = {
        "accepted": "sip.tar-00000000-0000-0000-0000-000000000001",
        "in_progress": "sip.tar-00000000-0000-0000-0000-000000000002",
        "failure": "sip.tar-99999999-9999-9999-9999-999999999999",
    }
    xml_content = '<?xml version="1.0" encoding="utf-8" ?>\n<root>Whee</root>'
    with requests_mock.Mocker() as mock:
        for key, transfer_id in transfer_ids.items():
            if key == "accepted":
                get_transfer_response = json.dumps(
                    {
                        "data": {
                            "actions": {
                                "report": (
                                    f"/api/3.0/{contract_id}/transfers/"
                                    f"{transfer_id}/report"
                                ),
                            },
                            "filename": "accepted_package.tar.gz",
                            "sip": {
                                "sip_id": "accepted-package",
                                "sip_size": 1,
                            },
                            "status": "accepted",
                            "timestamp": "Fri, 07 Mar 2025 13:46:44 GMT",
                            "transfer_id": f"{transfer_id}",
                        },
                        "status": "success",
                    }
                )
                get_transfer_status_code = 200
                get_transfer_report_response = xml_content
                get_transfer_report_status_code = 200
                delete_transfer_response = ""
                delete_transfer_status_code = 204
            if key == "in_progress":
                get_transfer_response = json.dumps(
                    {
                        "data": {
                            "actions": {},
                            "filename": "accepted_package.tar.gz",
                            "sip": {},
                            "status": "in_progress",
                            "timestamp": "Fri, 07 Mar 2025 13:46:44 GMT",
                            "transfer_id": f"{transfer_id}",
                        },
                        "status": "success",
                    }
                )
                get_transfer_status_code = 200
                get_transfer_report_response = xml_content
                get_transfer_report_status_code = 200
                delete_transfer_response = ""
                delete_transfer_status_code = 204
            elif key == "failure":
                get_transfer_response = json.dumps(
                    {
                        "message": "No transfer!",
                        "status": "fail",
                    }
                )
                get_transfer_status_code = 404
                get_transfer_report_response = json.dumps(
                    {
                        "message": "No report!",
                        "status": "fail",
                    }
                )
                get_transfer_report_status_code = 404
                delete_transfer_response = json.dumps(
                    {
                        "message": "No delete!",
                        "status": "fail",
                    }
                )
                delete_transfer_status_code = 404

            mock.get(
                f"{access_rest_api_host}/api/3.0/{contract_id}/transfers/"
                f"{transfer_id}",
                text=get_transfer_response,
                status_code=get_transfer_status_code,
            )
            mock.get(
                f"{access_rest_api_host}/api/3.0/{contract_id}/transfers/"
                f"{transfer_id}/report",
                text=get_transfer_report_response,
                status_code=get_transfer_report_status_code,
            )
            mock.delete(
                f"{access_rest_api_host}/api/3.0/{contract_id}/transfers/"
                f"{transfer_id}",
                text=delete_transfer_response,
                status_code=delete_transfer_status_code,
            )
        yield


@pytest.fixture(scope="function")
def mock_access_rest_api_v3_endpoints_interactive(access_rest_api_host,
                                                  contract_id):
    """Mock access-rest-api v3 endpoints by having dynamic responses.
    This mock is tailored for the test where whole cycle has to be conducted.
    """
    report_exists = False
    transfer_exists = True
    transfer_id = "sip.tar-00000000-0000-0000-0000-000000000001"
    transfer_id_fail = "sip.tar-99999999-9999-9999-9999-999999999999"
    times_polled = 0
    times_need_to_poll = 5
    xml_content = '<?xml version="1.0" encoding="utf-8" ?>\n<root>Whee</root>'

    def get_transfer_response(request, context):
        """Have to poll at least X amount of times before report starts
        to exist.
        """
        nonlocal report_exists
        nonlocal times_polled
        times_polled += 1
        if times_polled >= times_need_to_poll:
            actions = {
                "report": (
                    f"/api/3.0/{contract_id}/transfers/"
                    f"{transfer_id}/report"
                ),
            }
            status = "accepted"
            report_exists = True
        else:
            actions = {}
            status = "in_progress"
        if not transfer_exists:
            context.status_code = 404
            report_exists = False
        return json.dumps(
            {
                "data": {
                    "actions": actions,
                    "filename": "accepted_package.tar.gz",
                    "sip": {
                        "sip_id": f"{status}-package",
                        "sip_size": 1,
                    },
                    "status": f"{status}",
                    "timestamp": "Fri, 07 Mar 2025 13:46:44 GMT",
                    "transfer_id": f"{transfer_id}",
                },
                "status": "success",
            }
        )

    def get_transfer_report_response(request, context):
        if not report_exists:
            context.status_code = 404
        return xml_content

    def delete_transfer_response(request, context):
        """Mark as transfer to no longer exist after this is called."""
        nonlocal report_exists
        nonlocal transfer_exists
        if transfer_exists:
            report_exists = False
            transfer_exists = False
        else:
            context.status_code = 404

    with requests_mock.Mocker() as mock:
        mock.get(
            f"{access_rest_api_host}/api/3.0/{contract_id}/transfers/"
            f"{transfer_id}",
            text=get_transfer_response,
            status_code=200,
        )
        mock.get(
            f"{access_rest_api_host}/api/3.0/{contract_id}/transfers/"
            f"{transfer_id_fail}",
            json={"status": "fail"},
            status_code=404,
        )
        mock.get(
            f"{access_rest_api_host}/api/3.0/{contract_id}/transfers/"
            f"{transfer_id}/report",
            text=get_transfer_report_response,
            status_code=200,
        )
        mock.delete(
            f"{access_rest_api_host}/api/3.0/{contract_id}/transfers/"
            f"{transfer_id}",
            text=delete_transfer_response,
            status_code=204,
        )
        yield


@pytest.fixture(scope="function")
def mock_access_rest_api_v3_list_endpoint(access_rest_api_host, contract_id):
    # We'll use fixed transfer_id.
    transfers = []
    valid_statuses = ["accepted", "in_progress", "rejected", "uploading"]
    statuses = cycle(valid_statuses)
    processed_statuses = ["accepted", "rejected"]
    for i in range(1, 21):
        transfer_id = str(UUID(int=i))
        status = next(statuses)
        if status in processed_statuses:
            actions = {
                "report": (
                    f"/api/3.0/{contract_id}/transfers/"
                    f"{transfer_id}/report"
                ),
            }
        else:
            actions = {}
        transfers.append(
            {
                "actions": actions,
                "filename": f"{status}_{i}_package.tar.gz",
                "sip": {
                    "sip_id": f"{status}-{i}-package",
                    "sip_size": 1,
                },
                "status": f"{status}",
                "timestamp": "Fri, 11 Mar 2025 12:06:44 GMT",
                "transfer_id": f"{transfer_id}",
            }
        )

    def list_transfer_response(request, context):
        limit_filter = request.qs.get("limit", [""])[0]
        page_filter = request.qs.get("page", [""])[0]
        status_filter = request.qs.get("status", [""])[0]
        if status_filter in valid_statuses:
            results = [x for x in transfers if x["status"] == status_filter]
        else:
            results = transfers[:]
        if not limit_filter:
            limit_filter = "20"
        if not page_filter:
            page_filter = "1"
        start_index = int(limit_filter) * (int(page_filter) - 1)
        end_index = int(limit_filter) * (int(page_filter))
        filtered_results = results[start_index:end_index]
        links = {
            "self": "self",
            "previous": "previous" if start_index > 0 else "",
            "next": "next" if end_index < len(results) else "",
        }
        response = json.dumps(
            {
                "data": {"links": links, "results": filtered_results},
                "status": "success",
            }
        )
        return response

    with requests_mock.Mocker() as mock:
        mock.get(
            f"{access_rest_api_host}/api/3.0/{contract_id}/transfers",
            text=list_transfer_response,
            status_code=200,
        )
        yield
