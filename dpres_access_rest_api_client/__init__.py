"""
dpres-access-rest-api-client default imports
"""

from pkg_resources import DistributionNotFound, get_distribution

# flake8: noqa
from .v2.client import AccessClient, DIPRequest

try:
    # pylint: disable=no-member
    __version__ = get_distribution("access_rest_api_client").version
except DistributionNotFound:
    __version__ = "unknown"
