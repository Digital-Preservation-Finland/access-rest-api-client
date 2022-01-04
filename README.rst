Access REST API Client
======================

Access REST API Client is a command-line utility and Python library for
searching and downloading packages in the Finnish National Digital Preservation
Service.

Installation
------------

Installation requires Python 3.6 or newer. The software has been tested using
CentOS 7.

You can install the application inside a virtualenv using the following
instructions.

To create a virtualenv, activate it and install dpres-access-rest-api-client, run

```
# Create virtualenv
$ python3 -mvenv venv
# Activate virtualenv
$ source venv/bin/activate
# Install dpres-access-rest-api-client
$ pip install .
```

To deactivate the virtualenv, run `deactivate`. The created virtualenv needs
to be active in order to use dpres-access-rest-api-client.

Usage
-----

After you have installed the application, you can create the configuration
file by running

```
$ access-client write-config
```

Edit the configuration file with necessary credentials.
You can also save the configuration file at `/etc/dpres_access_rest_api_client/config.conf`
or define the path using the environment variable `ACCESS_REST_API_CLIENT_CONF`.

To search for packages to download, run

```
$ access-client search
```

An optional search query can be passed using the `--query`. See the
[API documentation](https://urn.fi/urn:nbn:fi-fe2020100578098)
for details such as syntax and accepted field names.
See `access-client search --help` for the usage of extra parameters.

To download a package, copy the AIP ID from the previous command and then
run

```
$ access-client download <AIP-ID>
```

See `access-client download --help` for the usage of extra parameters.


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
this program.  If not, see <https://www.gnu.org/licenses/>.

