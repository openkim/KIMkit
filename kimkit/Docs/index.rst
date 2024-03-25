.. KIMkit documentation master file, created by
   sphinx-quickstart on Tue Apr 18 11:19:08 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

KIMkit Interatomic Model Management and Storage System
=========================================================
**KIMkit** is a standalone python package implementing an Interatomic Model management and storage system based upon
and intended to be compatible with the standards set out by the `OpenKIM Project <https://openkim.org>`_ .
**KIMkit** provides methods to store, archive, edit, and track changes to Interatomic Models, which are simulation codes used to compute specific interactions between atoms, e.g. an interatomic potential or force field.

Package Contents
----------------

Python Files:

   ``models.py``

      Contains functions for managing the main **KIMkit** item types: Portable Models, Simulator Models, and Model Drivers.

   ``metadata.py``

      Contains functions used to validate and set metadata associated with **KIMkit** items.
      Additonally, contains utility functions allowing **KIMkit** Editors to modify the metadata standard configured in ``metadata_config.edn``.

   ``users.py``

      Contains functions used to manage **KIMkit** users, validate user identities, and control which users have elevated access privleges as **KIMkit** Editors.

   ``kimcodes.py``

      Contains a number of utility functions for creating, validating, parsing, and managing the kimcode identification strings used to identify **KIMkit** items.

Configuration Files:


   ``default-environment``

      Contains default file paths and environment variables used to configure various global behaviors of **KIMkit**. 

   ``settings/editors.txt``

      Should be created inside KIMkit/settings by the system administrator after **KIMkit** is installed. ``editors.txt`` should only be writable by the **KIMkit** Administrator, and contain a list of operating system usernames to be granted Editor privleges.

   ``settings/metadata_config.edn``

      Contains several arrays specifying which metadata fields are required or optional for each **KIMkit** item type, and their internal data structures. Users should not modify ``metadata_config.edn`` directly, but **KIMkit** Editors can adjust the default metadata settings via the utility functions in ``metadata.py``

Important Directories:

   These paths can be configured inside ``default-environment``

   ``KIMKIT_DATA_DIRECTORY``

      Unset by default, should be set to point to the root path of the **KIMkit** installation.

Documentation Contents
=======================
.. toctree::
   :maxdepth: 1

   installation
   quick_start
   models
   metadata
   users
   kimcodes

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`