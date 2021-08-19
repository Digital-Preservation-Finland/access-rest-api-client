dpres-access-rest-api-client
============================

dpres-access-rest-api-client is a command-line utility and Python library for
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

After you have installed the application, you can test that the application
is working by running

```
$ access-client --help
```

When the command-line application is launched for the first time, a
configuration file will be created in the user's configuration directory;
this is usually `~/.config/dpres-access-rest-api-client/config.conf`. Edit the
configuration file with the necessary credentials.

To search for packages to download, run

```
$ access-client search
```

An optional search query can be passed using the `--query`. See the
[API documentation](https://digitalpreservation.fi/files/Interfaces-2.2.0-en.pdf)
for details such as syntax and accepted field names.

To download a package, copy the AIP ID from the previous command and then
run

```
$ access-client download <AIP-ID>
```
