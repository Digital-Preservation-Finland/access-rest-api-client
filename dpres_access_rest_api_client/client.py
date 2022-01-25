"""
Client module for querying and downloading DIPs using the National Digital
Preservation Services REST API.
"""

import collections
import functools
import random
import time
from urllib.parse import quote
import warnings
from pathlib import Path

import urllib3
from urllib3.exceptions import InsecureRequestWarning

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .config import CONFIG

SearchResult = collections.namedtuple(
    "SearchResult",
    ("results", "prev_url", "next_url")
)


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


class AccessClient:
    """
    Client for accessing the Digital Preservation Service REST API
    """
    def __init__(self, config=None):
        """
        Create the AccessClient instance
        """
        if not config:
            config = CONFIG

        # Normalize host by removing the trailing slash. Host is
        # read-only attribute, since changing the host while polling a
        # DIP would cause problems.
        self._host = config["dpres"]["api_host"].rstrip("/")
        self.base_url = \
            f"{self.host}/api/2.0/{config['dpres']['contract_id']}"

        self.session = self._create_session(config=config)

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
            config["dpres"]["username"], config["dpres"]["password"]
        )

        # Disable SSL verification depending on user config
        session.verify = config['dpres'].getboolean('verify_ssl')

        if not session.verify:
            warnings.warn(
                "SSL verification has been *DISABLED* for access-rest-api-"
                "client.",
                InsecureRequestWarning
            )
            # Disable warnings or otherwise every single request
            # will end up printing a lot of noise
            urllib3.disable_warnings(category=InsecureRequestWarning)

        # Automatically run 'raise_for_status' for each response
        def check_status(resp, **_):
            """Check status for each response"""
            resp.raise_for_status()

        session.hooks["response"] = [check_status]

        # Set a timeout of 10 seconds for every request by shimming the
        # 'request' method
        session.request = functools.partial(
            session.request, timeout=10
        )

        session.headers["User-Agent"] = (
            f"dpres-access-rest-api-client/{__version__} "
            f"(github.com/Digital-Preservation-Finland/"
            f"dpres-access-rest-api-client)"
        )

        retry = Retry(
            # Retry a total of 5 times
            total=5,
            # Backoff factor of 1, meaning each retry will have a doubled delay
            backoff_factor=1,
            # Server-side errors will result in retries
            status_forcelist=[500, 502, 503, 504]
        )

        # Setup retry policy only for API calls
        session.mount(
            config["dpres"]["api_host"], HTTPAdapter(max_retries=retry)
        )

        return session

    def search(self, page=1, limit=1000, query=None):
        """
        Perform a search for packages and return a SearchResult

        :param int page: Search result page.
                         Defaults to 1 (i.e. the first page).
        :param int limit: Maximum amount of search results per page
        :param str query: Search query based on Solr's dialect of the
                          Lucene query syntax.
        """
        params = {
            "page": page,
            "limit": limit
        }

        if query:
            params["q"] = query

        response = self.session.get(
            f"{self.base_url}/search",
            params=params
        )
        data = response.json()["data"]

        prev_url = None
        if data["links"].get("prev"):
            prev_url = f"{self.host}{data['links']['prev']}"

        next_url = None
        if data["links"].get("next"):
            next_url = f"{self.host}{data['links']['next']}"

        return SearchResult(
            results=data["results"], prev_url=prev_url, next_url=next_url
        )

    def create_dip_request(self, aip_id, catalog=None, archive_format=None):
        """
        Start a dissemination request and return a DIPRequest
        object that can be used to poll for the created DIP and eventually
        download it.

        :param str aip_id: Identifier of the AIP to download
        :param str catalog: Optional schema catalog used to disseminate
                            the AIP.
                            Newest available schema catalog is used by default.
        :param str archive_format: Archive format used for the disseminated
                                   DIP. Default is 'zip'.
        """
        dip_request = DIPRequest(
            client=self,
            aip_id=aip_id,
            catalog=catalog,
            archive_format=archive_format
        )
        dip_request.disseminate()

        return dip_request

    def delete_dissemination(self, dip_id):
        """
        Delete a completed DIP from the DPRES service.

        :param dip_id: Identifier of the DIP to delete
        """
        response = self.session.delete(
            f"{self.base_url}/disseminated/{dip_id}"
        )
        data = response.json()["data"]
        return data["deleted"] == "true"

    def get_ingest_report_entries(self, sip_id):
        """
        Get all the ingest report entries created for a package.

        :param sip_id: SIP identifier of the package

        :returns: Entries of all ingest reports created for a package
                  as a list of dicts.
        """
        sip_id = quote(sip_id, safe="")
        url = f"{self.base_url}/ingest/report/{sip_id}"
        response = self.session.get(url)
        return response.json()["data"]["results"]

    def get_ingest_report(self, sip_id, transfer_id, file_type):
        """
        Get the specified ingest report of a package.

        :param sip_id: SIP identifier
        :param transfer_id: Transfer id
        :param file_type: File format to be returned, either "xml" or "html"

        :returns: The ingest report as a byte string
        """
        if file_type not in ["xml", "html"]:
            raise ValueError(f"Invalid file type '{file_type}': Only 'xml' "
                             "and 'html' file formats are accepted")

        sip_id = quote(sip_id, safe="")
        transfer_id = quote(transfer_id, safe="")
        url = (f"{self.base_url}/ingest/report/{sip_id}/{transfer_id}"
               f"?type={file_type}")
        response = self.session.get(url)
        return response.content


class DIPRequest:
    """
    Object used to perform a DIP dissemination and download
    """
    def __init__(self, client, aip_id, catalog=None, archive_format="zip"):
        """
        Create a DIPRequest.

        :param str aip_id: Identifier of the AIP to download
        :param str catalog: Optional schema catalog used to disseminate the
                            AIP. Newest available schema catalog is used by
                            default.
        :param str archive_format: Archive format used for the
                                   disseminated DIP.
                                   Default is 'zip'.

        .. note::

            After creating the DIPRequest, start the dissemination request
            by calling `DIPRequest.disseminate()`
        """
        self.client = client
        self.aip_id = aip_id
        self.catalog = catalog
        self.archive_format = archive_format

        self.ready = None
        self.dip_id = None

    @property
    def _poll_url(self):
        if not self.dip_id:
            return None
        return f"{self.base_url}/disseminated/{self.dip_id}"

    @property
    def _download_url(self):
        if not self.dip_id:
            return None
        return f"{self._poll_url}/download"

    @property
    def session(self):
        """
        AccessClient instance
        """
        return self.client.session

    @property
    def host(self):
        """
        Client's hostname
        """
        return self.client.host

    @property
    def base_url(self):
        """
        Client's base URL
        """
        return self.client.base_url

    def disseminate(self):
        """
        Send a dissemination request to the REST API.
        """
        params = {}

        if self.catalog:
            params["catalog"] = self.catalog

        if self.archive_format:
            params["format"] = self.archive_format

        response = self.session.post(
            f"{self.base_url}/preserved/{self.aip_id}/disseminate",
            params=params
        )
        data = response.json()["data"]

        self.dip_id = data['disseminated'].split('/')[-1]

    def check_status(self, poll=False):
        """
        Check if the DIP has been generated and is ready for download.

        :param bool poll: Whether to poll until the DIP is ready for download.
                          Default is False.

        :returns: True if DIP is ready for download, False otherwise
        """
        poll_interval_iter = get_poll_interval_iter()

        while not self.ready:
            response = self.session.get(self._poll_url)
            data = response.json()["data"]

            if data["complete"] == "true":
                self.ready = True
                break

            self.ready = False

            if poll:
                time.sleep(next(poll_interval_iter))
            else:
                break

        return self.ready

    def get_streamed_download_response(self):
        """
        Perform a HTTP request to download the DIP and return a streamable
        requests.Response object
        """
        if not self.ready:
            raise ValueError("DIP is not ready for download yet")

        return self.session.get(self._download_url, stream=True)

    def delete(self):
        """
        Perform a HTTP request to delete the DIP from the DPRES
        service.

        :returns: True if DIP was deleted, False otherwise
        """
        if not self.ready:
            raise ValueError("DIP is not ready for deletion")
        response = self.session.delete(self._poll_url)
        data = response.json()["data"]
        return data["deleted"] == "true"

    @property
    @functools.lru_cache()
    def streamed_download_response(self):
        """
        Return a streamed download response.

        .. note::

            This property is cached, meaning only one response will be
            initiated. If multiple requests are necessary for whatever reason,
            use `get_streamed_download_response()` directly.
        """
        return self.get_streamed_download_response()

    @property
    @functools.lru_cache()
    def download_size(self):
        """
        Return the size of the DIP in bytes
        """
        return int(self.streamed_download_response.headers["Content-Length"])

    @property
    def download_iter(self):
        """
        Return an iterator that returns DIP data in ~1 MB chunks
        """
        return self.streamed_download_response.iter_content(
            chunk_size=1024 * 1024
        )

    def download(self, path):
        """
        Download the DIP to the given path
        """
        path = Path(path).resolve()

        # pylint: disable=no-member
        with path.open("wb", buffering=1024 * 1024) as file_:
            for chunk in self.download_iter:
                file_.write(chunk)
