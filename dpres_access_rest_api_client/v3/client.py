"""
Client module to utilize National Digital Preservation Services REST API 3.0.
"""

import os
from typing import Union
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from tusclient import client
from tusclient.storage import filestorage
from tusclient.uploader import Uploader
from ..base import BaseClient, SearchResult


class AccessClient(BaseClient):
    """
    Client for accessing the Digital Preservation Service REST API
    """

    def __init__(self, config=None):
        """
        Create the AccessClient instance
        """
        super().__init__(api="3.0", config=config)
        # TUS endpoint is a bit special in DPS that contract ID is not provided
        # in the URL.
        self._tus_endpoint = f"{self.host}/api/{self.api_version}/transfers"
        self._tus_client = None

    def _create_tus_client(self):
        """Creates and returns a tus client instance tailored for
        Digital Preservation Service.

        :return: TusClient object.
        """
        tus_client = client.TusClient(self.tus_endpoint)
        auth = HTTPBasicAuth(
            username=self.session.auth[0], password=self.session.auth[1]
        )
        tus_client.headers["User-Agent"] = self.session.headers["User-Agent"]
        tus_client = auth(tus_client)
        return tus_client

    @property
    def tus_client(self):
        """Returns TusClient object.

        :return: TusClient object.
        """
        if self._tus_client is None:
            self._tus_client = self._create_tus_client()
        return self._tus_client

    @property
    def tus_endpoint(self):
        """Returns TUS endpoint of Digital Preservation Service.

        :return: TUS endpoint in string.
        """
        return self._tus_endpoint

    def create_uploader(
        self,
        file_path: str,
        chunk_size: Union[int, None] = None,
        store_url: bool = False,
        cache_file: str = "dpres_access_rest_api_client_tus_storage",
    ) -> Uploader:
        """Create TUS Uploader object tailored for Digital Preservation
        Service.

        :param file_path: String path to the file that will be uploaded.
        :param chunk_size: Integer value on how big of a bytes each chunk
            should be when uploading. None for no limit.
        :param store_url: Boolean whether to cache the URLs for given file
            to later try and resume. Defaulted to False due to current
            buggy issue: https://github.com/tus/tus-py-client/issues/103.
        :param cache_file: Which file to use to cache TUS storage for
            resumable usage. This is only utilized when store_url is True.
        :return: TUS Uploader-instance.
        """
        kwargs = {
            "metadata": {
                "contract_id": self.contract_id,
                "filename": os.path.basename(file_path),
            }
        }
        if chunk_size:
            kwargs["chunk_size"] = chunk_size
        if self.session.verify is False:
            kwargs["verify_tls_cert"] = False

        if store_url:
            storage = filestorage.FileStorage(cache_file)
            kwargs["store_url"] = True
            kwargs["url_storage"] = storage

        uploader = self.tus_client.uploader(file_path=file_path, **kwargs)
        return uploader

    def get_transfer(self, transfer_id):
        """Get transfer information from Digital Preservation Service.

        :param transfer_id: Transfer ID to fetch the information for.
        :return: JSON data from successful response.
        :raises HTTPError: When response code is within 400 - 500 range.
        """

        url = f"{self.base_url}/transfers/{transfer_id}"
        response = self.session.get(url)
        return response.json()["data"]

    def get_validation_report(self, transfer_id, report_type="xml"):
        """Get validation report for given transfer.

        :param transfer_id: Transfer ID to fetch the report for.
        :param report_type: Report type to download, either "xml" or "html"
            (default: xml).
        :return: Content data in bytes from successful response.
        :raises HTTPError: When response code is within 400 - 500 range.
        """

        url = f"{self.base_url}/transfers/{transfer_id}/report"
        params = {"type": report_type}
        response = self.session.get(url, params=params)
        return response.content

    def delete_transfer(self, transfer_id):
        """Delete the given transfer information. This will make it so
        that future call to get transfer information or report is no
        longer possible.

        :param transfer_id: Transfer ID to delete.
        :return: True on success, otherwise False.
        """
        url = f"{self.base_url}/transfers/{transfer_id}"
        try:
            self.session.delete(url)
            return True
        except HTTPError:
            return False

    def list_transfers(self, status=None, page=1, limit=20):
        """Get list of recent transfers from Digital Preservation Service.

        :param status: Filter the result down to given status in string.
        :param page: Which page number to view in integer.
        :param limit: Limit to how many results in integer.
        :return: JSON data from successful response.
        :raises HTTPError: When response code is within 400 - 500 range.
        """

        url = f"{self.base_url}/transfers"
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        response = self.session.get(url, params=params)
        data = response.json()["data"]

        prev_url = None
        if data["links"].get("previous"):
            links_prev_url = data["links"]["previous"].lstrip("/")
            prev_url = f"{self.host}/{links_prev_url}"

        next_url = None
        if data["links"].get("next"):
            links_next_url = data["links"]["next"].lstrip("/")
            next_url = f"{self.host}/{links_next_url}"

        return SearchResult(
            results=data["results"], prev_url=prev_url, next_url=next_url
        )
