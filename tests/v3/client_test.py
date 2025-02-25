"""Module that tests dpres_access_rest_api_client.v3.client"""

import pytest


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload(client_v3, uploadable_file_path_obj):
    uploader = client_v3.uploader(file_path=str(uploadable_file_path_obj),
                                  chunk_size=3)
    uploader.upload_chunk()
    uploader.upload()
