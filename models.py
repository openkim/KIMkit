import sys
import os
import shutil

import metadata
import provenance

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from kim_utils import kimobjects, kimcodes, util

"""
Base class items for KIMkit.
"""


class PortableModel(kimobjects.Model):
    """Portable Model Class"""

    def __init__(
        self,
        repository,
        kimcode,
        *args,
        **kwargs,
    ):
        """Portable Model Class

        Repository is always required in KIMkit.

        Items can be initialized with just a kimcode if the item is already installed in a KIMkit repository.

        Parameters
        ----------
        repository : str
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item. If not supplied assumne a new item is being imported,
            generate a new kimcode and assign it to the new item
        """

        setattr(self, "repository", repository)
        diskPath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(PortableModel, self).__init__(kimcode, abspath=diskPath, *args, **kwargs)


class SimulatorModel(kimobjects.SimulatorModel):
    """Simulator Model Class"""

    def __init__(self, repository, kimcode, *args, **kwargs):
        """Simulator Model Class

        Repository is always required in KIMkit.

        Items can be initialized with just a kimcode if the item is already installed in a KIMkit repository.

        Parameters
        ----------
        repository : str
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item. If not supplied assumne a new item is being imported,
            generate a new kimcode and assign it to the new item
        """

        setattr(self, "repository", repository)
        diskPath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(SimulatorModel, self).__init__(kimcode, abspath=diskPath, *args, **kwargs)


class ModelDriver(kimobjects.ModelDriver):
    def __init__(
        self,
        repository,
        kimcode=None,
        name=None,
        source_dir=None,
        metadata_dict=None,
        *args,
        **kwargs,
    ):
        """Model Driver Class

        Repository is always required in KIMkit.

        Items can be initialized with just a kimcode if the item is already installed in a KIMkit repository.

        Parameters
        ----------
        repository : str
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item. If not supplied assumne a new item is being imported,
            generate a new kimcode and assign it to the new item
        """
        setattr(self, "repository", repository)
        diskPath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(ModelDriver, self).__init__(kimcode, abspath=diskPath, *args, **kwargs)


def import_item(name, source_dir, repository, metadata_dict):
    """Assign the item a kimcode, create a directory in the selected repository for
    the item based on that kimcode, copy the item's files into it,
    generate needed metadata and provenance files, and store them with the item.

    By default, when importing a new item it will be assigned major version 000.

    If updating or forking an existing item, call this function with the kimcode to
    create the new version/item's directory

    If no new items/directories need to be created, returns the kimcode and exits.

    Parameters
    ----------
    name : str
        a human-readable name prefix for the item
    source_dir : path like
        location of the item's files on disk
    repository : path like
        path to collection to install into
    metadata_dict : dict
        dict of all required and any optional metadata key-value pairs

    Returns
    -------
    new_kimcode : str
        ID code of the item in KIMkit
    """

    # TODO validate metadata before importing
    item_type = metadata_dict["kim-item-type"]
    event_type = "initial-creation"
    if all((name, item_type, source_dir, repository, metadata_dict)):
        new_kimcode = kimcodes.generate_kimcode(name, item_type, repository)
        save_to_repository(source_dir, new_kimcode, repository)

        metadata.MetaData(repository, new_kimcode, metadata_dict)

        provenance.Provenance(
            new_kimcode,
            repository,
            event_type,
            metadata_dict["contributor"][0],  # TODO parse list of UUIDs
            comments=None,
        )
        return new_kimcode
    else:
        raise AttributeError(
            f"""A name, source directory, KIMkit repository,
             and dict of required metadata fields are required to initialize a new item."""
        )


def save_to_repository(source_dir, kimcode, repository):
    """Take an item that's been imported and had a kimcode
    generated and save it in the relevant repository.

    Parameters
    ----------
    source_dir : str or path
        directory where the item is currently stored
    kimcode : str
        kimcode of the item
    repository : str or path
        repository in which to save the item
    """

    if os.path.isdir(source_dir):
        dest_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
        shutil.copytree(source_dir, dest_dir)

    else:
        raise FileNotFoundError(f"Source Directory {source_dir} Not Found")


def delete(kimcode, repository):
    """delete an item from the repository and all of its content

    Parameters
    ----------
    kimcode : str
        kimcode of the item, must match self.kim_code for the item to be deleted
    repository : path like
        root directory of the KIMkit repo containing the item
    """
    # TODO handle UUIDs
    del_path = kimcodes.kimcode_to_file_path(kimcode, repository)
    shutil.rmtree(del_path)

    # if all versions of the item have been deleted, delete its enclosing directory
    outer_dir = os.path.split(del_path)[0]  # one level up in the directory
    with os.scandir(outer_dir) as it:
        if not any(it):  # empty directory
            shutil.rmtree(outer_dir)


def export(dest_dir, kimcode, repository):
    """Export as a tar archive, with all needed dependancies for it to run

    Parameters
    ----------
    dest_dir : path like
        where to place the exported model
    kimcode: str
        id code of the item
    repository : path like
        root directory of the KIMkit repository containing the item
    """
    src_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    name, leader, num, version = kimcodes.parse_kim_code(kimcode)

    if leader == "MO":  # portable model
        this_item = PortableModel(repository, kimcode=kimcode)
        req_driver = this_item.driver
        export(dest_dir, req_driver, repository)
    util.create_tarball(src_dir, dest_dir, arcname=kimcode)
