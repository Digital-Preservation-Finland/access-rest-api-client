"""
Client module to utilize National Digital Preservation Services REST API 3.0.
"""
import os
from requests.auth import HTTPBasicAuth
from tusclient import client
from tusclient.storage import filestorage
from ..base import BaseClient


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
        auth = HTTPBasicAuth(username=self.session.auth[0],
                             password=self.session.auth[1])
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

    def uploader(self, file_path, chunk_size=None, store_url=False):
        """Create TUS Uploader object tailored for Digital Preservation
        Service.

        :param file_path: String path to the file that will be uploaded.
        :param chunk_size: Integer value on how big of a bytes each chunk
            should be when uploading. None for no limit.
        :param store_url: Boolean whether to cache the URLs for given file
            to later try and resume. Defaulted to False due to current
            buggy issue: https://github.com/tus/tus-py-client/issues/103.
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
            storage = filestorage.FileStorage("access_rest_api_client_storage")
            kwargs["store_url"] = True
            kwargs["url_storage"] = storage

        uploader = self.tus_client.uploader(file_path=file_path, **kwargs)
        return uploader
