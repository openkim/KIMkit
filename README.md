# KIMkit Interatomic Model Management and Storage System

**KIMkit** is a standalone python package implementing an Interatomic Model managment and storage system based upon and intended to be compatible with the standards set out by the [OpenKIM Project](https://openkim.org). **KIMkit** provides methods to store, archive, edit, and track changes to Interatomic Models, which are simulation codes used to compute specific interactions between atoms, e.g. an interatomic potential or force field.

## Requirements

- kim-api

To install `kimpy`, you need [KIM API](https://openkim.org/kim-api). The
easiest option for obtaining the KIM API is to install the `kim-api`
pre-compiled binary package for your preferred operating system or package
manager.

You can
[install](https://openkim.org/doc/usage/obtaining-models#installing_api)
the KIM API from source.

- kimpy

kimpy is a Python interface to the [KIM API](https://openkim.org/kim-api).

- kim-edn

kim-edn is an open source package for reading and writing .edn files,
The **KIM** infrastructure embraces a subset of **edn** as a
[standard data format](https://openkim.org/doc/schema/edn-format). The
primary purpose of this data format choice is to serve as a notational
superset to [**JSON**](https://en.wikipedia.org/wiki/JSON) with the
enhancements being that it (1) allows for comments and (2) treats commas as
whitespace enabling easier templating.

## Post-Install Setup

**KIMkit** allows for a subset of users with elevated privleges, used to manage global configuration settings, and
edits to content contributed by or maintained by other users.

**KIMkit** defines 3 levels of user access: Administrator, Editor, and User.

There is only one Administrator per installation of **KIMkit**. Inside the **KIMkit** package root directory there should be
a file called 'editors.txt' which all users have read access to, but only the Administrator has write access to. editors.txt should contain a sequence of operating-system usernames as returned by getpass.getuser().
If the current user is in editors.txt, **KIMkit** recoggnizes them as an Editor, and allows them certian
elevated permissions (e.g. editing content submitted by other users, adding keys to the metadata standard).
Any user that is neither the Administrator nor listed as an Editor is a regular User by default.

The Administrator should be listed as an Editor for most use cases.

## First Time Using KIMkit

Seperately from editors.txt, there should also be a file named user_uuids.edn, also in the **KIMkit** root directory,
which stores information about all **KIMkit** users. This file contains an .edn dict where the keys are
UUID4s assigned to each user, and the values are an array that contain strings, with the user's personal name,
and optionally their operating system username (if any).

Users attempting to contribute or edit **KIMkit** data will be prompted to add themselves to the approved users list
by calling users.add_self_as_user(), which simply takes their personal name as an input, associates it with their
operating system username, assigns them a UUID4, and adds this to user_uuids.edn.

## Importing New Content

When creating a new item, either importing it into **KIMkit** for the first time, or forking an existing item,
you should first generate a kimcode for the item by calling kimcodes.generate_kimcode() with a human-readable prefix
for the item, its item-type, and the repository it is to be saved in to ensure that kimcode is not already in use.


```py
>>> import KIMkit
>>> example_kimcode = KIMkit.kimcodes.generate_kimcode(
        name="example_model",
        item_type="portable-model",
        repository="/path/to/repository/")
```

A **KIMkit** repository is simply the root directory of a collection of **KIMkit** items on disk. The repository will have 3 subdirectories within it, corresponding to Portable Models, Simulator Models, and Model Drivers. Inside each of these the various **KIMkit** items are organized according to substrings of the 12 digit ID number in the items' kimcodes and their 3 digit version numbers. In general, there can be an arbitrary number of **KIMkit** repositories used with any given installation of **KIMkit**.

Content is passed in and out of **KIMkit** as python tarfile.TarFile objects, so that automated systems can submit and retrieve **KIMkit** content without needing to write to disk. The content of the item should be packaged as a tar archive and read into memory (e.g. by tar = tarfile.open(/path/to/tar_file.txz)), to be passed into **KIMkit**
along with a dictionary of all required and any optional metadata fields.

```py
>>> import KIMkit
>>> tar_file = "/path/to/tar/archive/example_model__MO_123456789101_000.txz"
>>> tar = tarfile.open(tar_file)
>>> model_metadata = {
        "title": "Example Model v000",
        "potential-type": "eam",
        "license": "example license",
        "kim-item-type": "portable-model",
        "kim-api-version": "2.2.1",
        "species": ["Ag"],
        "developer": ["3ef33c20af204d3796fec32fd221023f"],
        "contributor-id": "3ef33c20af204d3796fec32fd221023f",
        "implementer": ["3ef33c20af204d3796fec32fd221023f"],
        "maintainer-id": "3ef33c20af204d3796fec32fd221023f",
        "model-driver": "EAM_Dynamo__MD_120291908751_005",
        "description": "this is an example model"}

>>> KIMkit.models.import_item(
        tarfile_obj=tar,
        repository="/path/to/repository/",
        kimcode="example_model__MO_1234567891011_000",
        metadata_dict=model_metadata)
```

## Creating New Content From Existing KIMkit Items

Users listed as the contributor or maintainer of a **KIMkit** item may create new versions of that item by calling
models.version_update() on the item with a tarfile.TarFile of new content. New versions of the same item will have the same
kimcode, but with the final 3 digit version number incremented by 1.

Additionally, any user can Fork an existing **KIMkit** item by generating a new kimcode for it, and calling models.fork()
on an existing item and a tarfile.TarFile of new content to create a new item with the new kimcode that they are the contributor of.

Updated and forked items copy over the metadata of the item they were based on, but users may optionally pass in a dictionary
containing any additional or changed metadata fields relevant to the new item. Furthermore, whenever an item's content changes on disk, including metadata updates, its history is updated in the kimprovenance.edn file stored in the item's directory, which keeps track of all changes to the item's files, which user performed the changes, and why.

## KIMkit Metadata

All **KIMkit** items have associated metadata stored along with them in a file called kimspec.edn, which contains a dictionary of metadata keys and associated data values. Different **KIMkit** item types have different subsets of metadata fields required or optional to specify for them, and these various metadata fields take different datatypes and/or structures as their values. The current metadata specification is stored in a series of arrays in config.py.

A dictionary of all required and any desired optional metadata fields conforming to the specification for that item type are required when the item is first imported into **KIMkit**. When creating new versions of **KIMkit** items, users may include a dictionary containing any desired edits to the new item's metadata, otherwise it will be created from the existing item's metadata.

Additionally, it is possible to directly edit the metadata of an item without creating a new version/item, although this will create an update in the item's kimprovenance.edn file that tracks changes to item's content on disk.

```py
>>> import KIMkit
>>> example_metadata = KIMkit.metadata.MetaData(
    "path/to/repository/",
    "example_model__MO_123456789101_000")

>>> example_metadata.edit_metadata_value(
        "description",
        "edited example description",
        provenance_comments="edit description")
```
