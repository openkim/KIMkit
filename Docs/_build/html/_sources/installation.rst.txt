.. _installation:

Previous Section: :doc:`index`

KIMkit Installation
====================


Requirements
-------------

- kim-api



To install `kimpy`, you need the `KIM API <https://openkim.org/kim-api>`_. The
easiest option for obtaining the KIM API is to install the `kim-api`
pre-compiled binary package for your preferred operating system or package
manager. You can also `install <https://openkim.org/doc/usage/obtaining-models#installing_api>`_
the KIM API from source.

- kimpy

`kimpy <https://pypi.org/project/kimpy/>`_ is a Python interface to the KIM API, whic can be installed via pip.

- kim-edn

`kim-edn <https://pypi.org/project/kim-edn/>`_ is an open source package for reading and writing .edn files,
The **KIM** infrastructure embraces a subset of **edn** as a
`standard data format <https://openkim.org/doc/schema/edn-format>`_. The
primary purpose of this data format choice is to serve as a notational
superset to `JSON <https://en.wikipedia.org/wiki/JSON>`_ with the
enhancements being that it (1) allows for comments and (2) treats commas as
whitespace enabling easier templating.

Configuring User Privleges
---------------------------

Inside the **KIMkit** package root directory the system administrator should create
a file called 'editors.txt' which all users have read access to, but only one user,
the **KIMkit** Administrator has write access to.

**KIMkit** allows for a subset of users with elevated privleges, used to manage global configuration settings, and
edits to content contributed by or maintained by other users. **KIMkit** defines 3 levels of user access: Administrator, Editor, and User.
There is only one Administrator per installation of **KIMkit**, the user account with write access to editors.txt.

editors.txt should contain a sequence of operating-system usernames (one per line) as returned by getpass.getuser().
If the current user is in editors.txt, **KIMkit** recognizes them as an Editor, and allows them certain
elevated permissions (e.g. editing content submitted by other users, adding keys to the metadata standard).

Any user that is neither the Administrator nor listed as an Editor is a regular User by default.

The Administrator should be listed as an Editor for most use cases.

Configuring Paths
------------------

The default-environment file contains paths and settings to be used as default environment variables for a variety
of **KIMkit** settings. The main path KIMKIT_DATA_DIRECTORY is unset by default, and should be configured to point
to the path where **KIMkit** is installed. These settings can be overridden by a file called KIMkit-env stored
inside KIMKIT_DATA_DIRECTORY to to allow for finer control of settings per installation.


Next Section :doc:`quick_start`