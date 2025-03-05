"""Module that tests dpres_access_rest_api_client.v3.client"""

import pytest


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload(client_v3, uploadable_file_path_obj):
    """Test that we can upload without issue.

    The store_url is intentionally set to False so that we won't trigger
    tuspy's implementation of file storage cache.
    """
    uploader = client_v3.create_uploader(
        file_path=str(uploadable_file_path_obj), chunk_size=3, store_url=False
    )
    uploader.upload_chunk()
    uploader.upload()
