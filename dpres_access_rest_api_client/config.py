"""
dpres-access-rest-api-client configuration handling
"""
import configparser
import os
import warnings
from pathlib import Path

import click

DEFAULT_CONFIG = """
[dpres]
; Contract ID corresponding to your organization.
; REPLACE THIS with your own.
;
; Example:
; contract_id=urn:uuid:12345678-f00d-d00f-a4b7-010a184befdd
contract_id=

; Username and password corresponding to your organization
; REPLACE THESE with your credentials.
;
; Example:
; username=pasi
; password=hunter2
username=
password=

; Host of the DPRES service.
; This usually doesn't need to be changed except for testing purposes.
api_host=https://pas.csc.fi/

; Whether to verify the SSL certificate of the host.
; Do *not* change this except for testing purposes.
verify_ssl=true
"""[1:]  # Skip the first newline


def _get_etc_config_path():
    """
    Get path to the system-wide configuration file
    """
    return Path("/etc") / "dpres_access_rest_api_client" / "config.conf"


def _get_user_config_path():
    """
    Get path to the user configuration file
    """
    return Path(
        click.get_app_dir("dpres_access_rest_api_client")
    ) / "config.conf"


def get_config():
    """
    Retrieve the configuration data as a dict. The following sources
    will be checked in order.

    1. Path defined by environment variable ACCESS_REST_API_CLIENT_CONF
    2. `/etc/dpres_access_rest_api_client/config.conf`
    3. Local configuration directory as determined by `click.get_app_dir()`.
       This follows the XDG spec and usually corresponds
       to `~/.config/dpres_access_rest_api_client/config.conf`

    If neither source exists, the default configuration file will be written
    to 2 and used instead.
    """
    def get_env_config_text():
        """
        Get config content using path from ACCESS_REST_API_CLIENT_CONF
        environment variable, if defined
        """
        if os.environ.get("ACCESS_REST_API_CLIENT_CONF"):
            return Path(os.environ["ACCESS_REST_API_CLIENT_CONF"]).read_text()

        return None

    def get_etc_config_text():
        """
        Get config content from /etc, if any
        """
        try:
            return _get_etc_config_path().read_text()
        except FileNotFoundError:
            return None

    def get_user_config_text():
        """
        Get user config content from app config directory, if any
        """
        try:
            return _get_user_config_path().read_text()
        except FileNotFoundError:
            return None

    # Try config sources in order until the first matching one
    config_text = get_env_config_text()

    if not config_text:
        config_text = get_etc_config_text()

    if not config_text:
        config_text = get_user_config_text()

    if not config_text:
        warnings.warn(
            "Configuration file not found, using defaults.", UserWarning
        )

    # Parse the config
    config = configparser.ConfigParser()
    config.read_string(DEFAULT_CONFIG)

    if config_text:
        config.read_string(config_text)

    return config


def write_default_config():
    """
    Write default config to the user's configuration directory if the file
    does not exist

    :returns: Path to the configuration file if it was written, None otherwise
    """
    user_config_path = _get_user_config_path()

    if user_config_path.is_file():
        return None

    user_config_path.parent.mkdir(parents=True, exist_ok=True)
    user_config_path.write_text(DEFAULT_CONFIG)

    return user_config_path


CONFIG = get_config()
