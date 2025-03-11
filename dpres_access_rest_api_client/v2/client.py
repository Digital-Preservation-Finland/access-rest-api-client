"""
Client module for querying and downloading DIPs using the National Digital
Preservation Services REST API.
"""

from datetime import datetime, timezone
import functools
import time
from urllib.parse import quote
from pathlib import Path

import requests

from ..base import BaseClient, SearchResult, get_poll_interval_iter


class AccessClient(BaseClient):
    """
    Client for accessing the Digital Preservation Service REST API
    """

    def __init__(self, config=None):
        """
        Create the AccessClient instance
        """
        super().__init__(api="2.0", config=config)

    def search(self, page=1, limit=1000, query=None):
        """
        Perform a search for packages and return a SearchResult

        :param int page: Search result page.
                         Defaults to 1 (i.e. the first page).
        :param int limit: Maximum amount of search results per page
        :param str query: Search query based on Solr's dialect of the
                          Lucene query syntax.
        """
        params = {"page": page, "limit": limit}

        if query:
            params["q"] = query

        response = self.session.get(f"{self.base_url}/search", params=params)
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
            archive_format=archive_format,
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

        :returns: Entries of all ingest reports created for a package as a list
                  of dicts. Returns an empty list if there are no ingest
                  reports available, or if the given SIP id cannot be found.
        """
        sip_id = quote(sip_id, safe="")
        url = f"{self.base_url}/ingest/report/{sip_id}"
        try:
            response = self.session.get(url)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                # Either there are no ingest reports for the SIP or the SIP
                # doesn't even exist. Either case, return an empty list.
                return []
            raise

        entries = response.json()["data"]["results"]

        # Modify entries to be more user-friendly
        for entry in entries:
            entry.pop("download")
            entry["transfer_id"] = entry.pop("id")
            entry["date"] = datetime.strptime(
                entry["date"], "%Y-%m-%dT%H:%M:%SZ"
            )
            entry["date"] = entry["date"].replace(tzinfo=timezone.utc)
        entries = sorted(
            entries, key=lambda entry: entry["date"], reverse=True
        )

        return entries

    def get_ingest_report(self, sip_id, transfer_id, file_type):
        """
        Get the specified ingest report of a package.

        :param sip_id: SIP identifier
        :param transfer_id: Transfer id
        :param file_type: File format to be returned, either "xml" or "html"

        :returns: The ingest report as a byte string. Returns None if no
                  ingest report is found for the given SIP and transfer
                  identifiers or if the identifiers are faulty.
        """
        if file_type not in ["xml", "html"]:
            raise ValueError(
                f"Invalid file type '{file_type}': Only 'xml' "
                "and 'html' file formats are accepted"
            )

        sip_id = quote(sip_id, safe="")
        transfer_id = quote(transfer_id, safe="")
        url = (
            f"{self.base_url}/ingest/report/{sip_id}/{transfer_id}"
            f"?type={file_type}"
        )
        try:
            response = self.session.get(url)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                # Either there is no ingest report for the SIP and transfer id
                # or the ids are faulty. Either case, return None.
                return None
            raise

        return response.content

    def get_latest_ingest_report(self, sip_id, file_type):
        """
        Get the latest ingest report created for a package.

        :param sip_id: SIP identifier
        :param file_type: File format to be returned, either "xml" or "html"

        :returns: The latest ingest report created for the package as a byte
                  string, or None if no reports are found
        """
        report_entries = self.get_ingest_report_entries(sip_id)

        if not report_entries:
            return None

        latest = max(report_entries, key=lambda entry: entry["date"])
        return self.get_ingest_report(sip_id, latest["transfer_id"], file_type)


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
            params=params,
        )
        data = response.json()["data"]

        self.dip_id = data["disseminated"].split("/")[-1]

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
