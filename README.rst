Access REST API Client
======================

Access REST API Client is a command-line utility and Python library for
retrieving information and performing requests on packages in the Finnish
National Digital Preservation Service.

Requirements
------------

Installation and usage requires Python 3.9 or newer.
The software is tested with Python 3.9 on AlmaLinux 9 release.

Installation using RPM packages (preferred)
-------------------------------------------

Installation on Linux distributions is done by using the RPM Package Manager.
See how to `configure the PAS-jakelu RPM repositories`_ to setup necessary software sources.

.. _configure the PAS-jakelu RPM repositories: https://www.digitalpreservation.fi/user_guide/installation_of_tools

After the repository has been added, the package can be installed by running the following command::

    sudo dnf install python3-dpres-access-rest-api-client

Usage
-----

**Write configuration file**

After you have installed the application, you can create the configuration
file by running

::

    $ access-client write-config

Edit the configuration file with necessary credentials.
You can also save the configuration file at ``/etc/dpres_access_rest_api_client/config.conf``
or define the path using the environment variable ``ACCESS_REST_API_CLIENT_CONF``.

**Ingest content to the DPS**

To upload a package, run

::

    $ access-client upload <FILE-PATH>

This command will provide a transfer id for the uploaded package, which is
needed for the usage of the various transfer commands.
See ``access-client upload --help`` for the usage of extra parameters.

To download the SIP validation report for a given transfer, run

::

    $ access-client transfer get-report <TRANSFER-ID>

This command will poll the DPS ingest and download the SIP validation report
when the ingest process is finished.

See ``access-client transfer get-report --help`` for the usage of extra
parameters.

To display information on a specific transfer, run

::

    $ access-client transfer info <TRANSFER-ID>

To delete transfer information and its report, run

::

    $ access-client transfer delete <TRANSFER-ID>

To list recent transfers, run

::

    $ access-client transfer list

This command will also tell the transfer ids of the listed transfers.
See ``access-client transfer list --help`` for the usage of extra parameters.

**Search and dissemination content from the DPS**

To search for packages to download, run

::

    $ access-client search

An optional search query can be passed using the ``--query``. See the
`API documentation <https://urn.fi/urn:nbn:fi-fe2020100578098>`_
for details such as syntax and accepted field names.

See ``access-client search --help`` for the usage of extra parameters.

To download a package, copy the AIP ID from the previous command and then
run

::

    $ access-client dip download <AIP-ID>

See ``access-client dip download --help`` for the usage of extra parameters.

To delete a DIP package, copy the DIP ID from the previous
``access-client search --query pkg_type:DIP`` command and then run

::

    $ access-client dip delete <DIP-ID>


Installation using Python Virtualenv for development purposes
-------------------------------------------------------------

You can install the application inside a virtualenv using the following
instructions.

Create a virtual environment::

    python3 -m venv venv

Run the following to activate the virtual environment::

    source venv/bin/activate

Install the required software with commands::

    pip install --upgrade pip==20.2.4 setuptools
    pip install -r requirements_github.txt
    pip install .

To deactivate the virtual environment, run ``deactivate``.
To reactivate it, run the ``source`` command above.

Using the Python classes
------------------------
This application comes with client class that interacts with Finnish
National Digital Preservation Service's API. More information on available
API can be read in `https://urn.fi/urn:nbn:fi-fe2020100578098 <https://urn.fi/urn:nbn:fi-fe2020100578098>`_.

Configuration
^^^^^^^^^^^^^

Before the client classes can be used, it's recommend to first setup necessary
configuration files.

Creating configuration::

    # Import the configuration creation function
    from dpres_access_rest_api_client.config import write_default_config

    # Create the configuration file. The function returns the location where
    # the configuration is written.
    path = write_default_config()

By default, the path goes to home directory under
``.config/dpres_access_rest_api_client/config.conf``.
Edit the necessary information.

API 2.X
^^^^^^^

Client with implementation that utilizes API 2.X endpoints.

Example of downloading DIP::

    # Import the API 2.X access client class
    from dpres_access_rest_api_client.v2.client import AccessClient

    # Initialize the client
    client = AccessClient()

    # Create a new DIPRequest request instance
    dip_request = client.create_dip_request(<AIP_ID>)

    # Check is DIP ready to download
    is_dip_ready = dip_request.check_status()

    # Download DIP if it is ready
    if is_dip_ready:
        dip_request.download(<download location.tar.gz>)

API 3.X
^^^^^^^

Client with implementation that utilizes API 3.X endpoints.

Example of uploading package with tus.io protocol::

    # Import the API 3.X access client class
    from dpres_access_rest_api_client.v3.client import AccessClient

    # Initialize the client
    client = AccessClient()

    # Create a new TUS Uploader request instance to upload package in
    # 8192 bytes size pieces.
    uploader = client.create_uploader(<filepath to package>, chunk_size=8192)

    # First get information how much of the data needs to be sent.
    upload_length = uploader.get_file_size()

    # Now start uploading using tus.io protocol.
    while uploader.offset < upload_length:
        uploader.upload_chunk()

    # Upload is finished so we can now fetch the transfer ID from the URL.
    transfer_id = uploader.url.split("/")[-1]

More information on tus.io protocols can be read at
`tus.io's website <https://tus.io/protocols/resumable-upload>`_.

Copyright
---------
Copyright (C) 2021 CSC - IT Center for Science Ltd.

This program is free software: you can redistribute it and/or modify it under the terms
of the GNU Lesser General Public License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with
this program.  If not, see https://www.gnu.org/licenses/.

