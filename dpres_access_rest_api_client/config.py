"""
dpres-access-rest-api-client configuration handling
"""
import configparser
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


def get_config():
    """
    Retrieve the configuration data as a dict. The following sources
    will be checked in order.

    1. `/etc/dpres_access_rest_client/config.conf'
    2. Local configuration directory as determined by `click.get_app_dir()`.
       This follows the XDG spec and usually corresponds
       to `~/.config/dpres_access_rest_client/config.conf`

    If neither source exists, the default configuration file will be written
    to 2 and used instead.
    """
    def get_etc_config_text():
        """
        Get config content from /etc, if any
        """
        path = Path("/etc") / "dpres_access_rest_client" / "config.conf"

        try:
            return path.read_text()
        except FileNotFoundError:
            return None

    def get_user_config_text():
        """
        Get user config content from app config directory, if any
        """
        path = \
            Path(click.get_app_dir("dpres_access_rest_client")) / "config.conf"

        try:
            return path.read_text()
        except FileNotFoundError:
            return None

    def get_default_config_text():
        """
        Get default config text and create the configuration file if it doesn't
        exist
        """
        path = \
            Path(click.get_app_dir("dpres_access_rest_client")) / "config.conf"
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(DEFAULT_CONFIG)

        return DEFAULT_CONFIG

    # Try config sources in order until the first matching one
    config_text = get_etc_config_text()

    if not config_text:
        config_text = get_user_config_text()

    if not config_text:
        config_text = get_default_config_text()

    # Parse the config
    config = configparser.ConfigParser()
    config.read_string(config_text)

    return config


CONFIG = get_config()
