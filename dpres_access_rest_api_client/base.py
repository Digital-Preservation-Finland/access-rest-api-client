"""Module that provides base client to setup HTTP requests."""

import collections
import functools
import random
import warnings
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

import requests
from requests.adapters import HTTPAdapter

from .config import CONFIG

SearchResult = collections.namedtuple(
    "SearchResult", ("results", "prev_url", "next_url")
)


class BaseClient:
    """
    Client for accessing the Digital Preservation Service REST API
    """

    def __init__(self, api="2.0", config=None):
        """
        Create the BaseClient instance
        """
        if not config:
            config = CONFIG

        self._api_version = api
        self._contract_id = config["dpres"]["contract_id"]
        # Normalize host by removing the trailing slash. Host is
        # read-only attribute, since changing the host while polling a
        # DIP would cause problems.
        self._host = config["dpres"]["api_host"].rstrip("/")
        self.base_url = (
            f"{self.host}/api/{self.api_version}/{self.contract_id}"
        )

        self.session = self._create_session(config=config)

    @property
    def api_version(self):
        """Return the API version."""
        return self._api_version

    @property
    def contract_id(self):
        """Return the contract id."""
        return self._contract_id

    @property
    def host(self):
        """Return API host."""
        return self._host

    @classmethod
    def _create_session(cls, config=None):
        """
        Create self.session based on the provided configuration
        """
        from dpres_access_rest_api_client import __version__

        if not config:
            config = CONFIG

        session = requests.Session()

        session.auth = (
            config["dpres"]["username"],
            config["dpres"]["password"],
        )

        # Disable SSL verification depending on user config
        session.verify = config["dpres"].getboolean(
            "verify_ssl", fallback=True
        )

        if not session.verify:
            warnings.warn(
                "SSL verification has been *DISABLED* for access-rest-api-"
                "client.",
                InsecureRequestWarning,
            )
            # Disable warnings or otherwise every single request
            # will end up printing a lot of noise
            disable_warnings(category=InsecureRequestWarning)

        # Automatically run 'raise_for_status' for each response
        def check_status(resp, **_):
            """Check status for each response"""
            resp.raise_for_status()

        session.hooks["response"] = [check_status]

        # Set a timeout of 10 seconds for every request by shimming the
        # 'request' method
        session.request = functools.partial(session.request, timeout=10)

        session.headers["User-Agent"] = (
            f"dpres-access-rest-api-client/{__version__} "
            f"(github.com/Digital-Preservation-Finland/"
            f"access-rest-api-client)"
        )

        retry = Retry(
            # Retry a total of 5 times
            total=5,
            # Backoff factor of 1, meaning each retry will have a doubled delay
            backoff_factor=1,
            # Server-side errors will result in retries
            status_forcelist=[500, 502, 503, 504],
        )

        # Setup retry policy only for API calls
        session.mount(
            config["dpres"]["api_host"], HTTPAdapter(max_retries=retry)
        )

        return session


def get_poll_interval_iter():
    """
    Return an iterator that can be iterated for poll intervals. This takes
    care of ramping up the poll interval for longer dissemination tasks.
    """
    # First five requests use 3s intervals,
    # second five use 10s intervals,
    # and all subsequent intervals are 60s
    intervals = sorted([3, 10, 60] * 5)
    intervals.reverse()

    last_interval = 0

    while True:
        if intervals:
            last_interval = intervals.pop()

        # Return interval with some additional jitter to ensure multiple
        # requests are not sent at the same time
        # (aka the thundering herd problem).
        yield last_interval + (random.random() * 0.5)  # nosec
