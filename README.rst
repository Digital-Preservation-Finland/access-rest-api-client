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

After you have installed the application, you can create the configuration
file by running

::

    $ access-client write-config

Edit the configuration file with necessary credentials.
You can also save the configuration file at ``/etc/dpres_access_rest_api_client/config.conf``
or define the path using the environment variable ``ACCESS_REST_API_CLIENT_CONF``.

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

    $ access-client download <AIP-ID>

See ``access-client download --help`` for the usage of extra parameters.

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

