from pathlib import Path

from configparser import ConfigParser

import pytest


@pytest.fixture(scope="function")
def testpath(tmpdir):
    """
    Create a temporary test directory
    """
    # TODO: Replace `testpath` with built-in `tmp_path` in pytest 3.9.0+
    return Path(str(tmpdir))


@pytest.fixture(scope="function", autouse=True)
def mock_config(monkeypatch, testpath):
    """
    Create a mock configuration file by mocking the user's home directory
    and placing a configuration file in the expected place
    """
    home_dir = (testpath / "home" / "testuser")
    config_dir = home_dir / ".config" / "dpres_access_rest_client"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "config.conf"
    config_path.write_text(
        "[dpres]\n"
        "contract_id=urn:uuid:fake_contract_id\n"
        "username=fakeuser\n"
        "password=fakepassword\n"
        "api_host=http://fakeapi/"
    )

    config = ConfigParser()
    config.read(str(config_path))

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(
        "dpres_access_rest_api_client.client.CONFIG", config
    )

    return config


@pytest.fixture(scope="function")
def cli_runner(mock_config):
    """
    Run the CLI entrypoint using the provided arguments and return the
    result
    """
    from click.testing import CliRunner
    from dpres_access_rest_api_client.cli import cli, Context

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
def client(mock_config):
    """
    AccessClient instance
    """
    from dpres_access_rest_api_client.client import AccessClient

    client = AccessClient(config=mock_config)

    return client
