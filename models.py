import sys
import os
import shutil

import metadata
import provenance

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from kim_utils import kimobjects, kimcodes, util

""" Base class items for KIMkit.

Each must be initialized with either a dict of required metadata
if the item is being newly initialized,
XOR its kimcode if the item already exists in KIMkit.
"""


class PortableModel(kimobjects.Model):
    """Portable Model Class"""

    def __init__(
        self,
        repository,
        kimcode=None,
        name=None,
        source_dir=None,
        parameter_files=None,
        metadata_dict=None,
        provenance_comments=None,
        *args,
        **kwargs,
    ):
        """Portable Model Class

        Repository is always required in KIMkit.

        Items can be initialized with just a kimcode if the item is already installed in a KIMkit repository.

        If no kimcode is supplied, a new model can be installed with a name, a list of parameter files,
        a source_dir where the item's files are located, and dict of metadata fields.

        Parameters
        ----------
        repository : str
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item. If not supplied assumne a new item is being imported,
            generate a new kimcode and assign it to the new item


        name : str, optional
            Name of the item, required if importing a new item, by default None
        source_dir : path like, optional
            location of the item on disk, required if importing a new item, by default None
        parameter_files : list of str, optional
           names of files containing parameters for the PM, required if importing a new item, by default None
        metadata_dict : dict, optional
            dict of all required and any optional metadata fields, required if importing a new item, by default None
        provenance_comments : str, optional
            any comments for why the model was created, by default None

        Raises
        ------
        AttributeError
            _description_
        """

        # if no kimcode is supplied, assign a new one to the item
        #  and initialize its directory in the selected repository
        if not kimcode:
            if all((metadata_dict, name, source_dir, parameter_files)):
                kimcode = prepare_install_dir(
                    name,
                    metadata_dict["kim-item-type"],
                    source_dir,
                    repository,
                    metadata_dict,
                    provenance_comments,
                )
            else:
                raise AttributeError(
                    f"A name, source directory, list of parameter files, and dict of metadata are required to initialize a new item."
                )
        setattr(self, "repository", repository)
        kimcode_without_subversion = kimcodes.strip_subversion(kimcode)

        diskPath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(PortableModel, self).__init__(
            kimcode_without_subversion, abspath=diskPath, *args, **kwargs
        )

    def export(self, dest_dir, name=None):
        """Export as a tar archive, with all needed dependancies for it to run

        Parameters
        ----------
        dest_dir : path like
            where to place the exported model
        """
        src_dir = kimcodes.kimcode_to_file_path(self.kim_code, self.repository)
        driver = self.model_driver
        ModelDriver(self.repository, kimcode=self.driver).export(dest_dir)
        util.create_tarball(src_dir, dest_dir, arcname=name)


class SimulatorModel(kimobjects.SimulatorModel):
    """Simulator Model Class"""

    def __init__(
        self,
        repository,
        kimcode=None,
        name=None,
        source_dir=None,
        parameter_files=None,
        metadata_dict=None,
        provenance_comments=None,
        *args,
        **kwargs,
    ):
        """Simulator Model Class

        Repository is always required in KIMkit.

        Items can be initialized with just a kimcode if the item is already installed in a KIMkit repository.

        If no kimcode is supplied, a new model can be installed with a name, a list of parameter files,
        a source_dir where the item's files are located, and dict of metadata fields.

        Parameters
        ----------
        repository : str
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item. If not supplied assumne a new item is being imported,
            generate a new kimcode and assign it to the new item


        name : str, optional
            Name of the item, required if importing a new item, by default None
        source_dir : path like, optional
            location of the item on disk, required if importing a new item, by default None
        parameter_files : list of str, optional
           names of files containing parameters for the PM, required if importing a new item, by default None
        metadata_dict : dict, optional
            dict of all required and any optional metadata fields, required if importing a new item, by default None
        provenance_comments : str, optional
            any comments for why the model was created, by default None

        Raises
        ------
        AttributeError
            _description_
        """

        # if no kimcode is supplied, assign a new one to the item
        #  and initialize its directory in the selected repository
        if not kimcode:
            if all((metadata_dict, name, source_dir, parameter_files)):
                kimcode = prepare_install_dir(
                    name,
                    metadata_dict["kim-item-type"],
                    source_dir,
                    repository,
                    metadata_dict,
                    provenance_comments,
                )
            else:
                raise AttributeError(
                    f"A name, source directory, list of parameter files, and dict of metadata are required to initialize a new item."
                )
        setattr(self, "repository", repository)
        kimcode_without_subversion = kimcodes.strip_subversion(kimcode)
        diskPath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(SimulatorModel, self).__init__(
            kimcode_without_subversion, abspath=diskPath, *args, **kwargs
        )

    def export(self, dest_dir, name=None):
        """Export as a tar archive, with all needed dependancies for it to run

        Parameters
        ----------
        dest_dir : path like
            where to place the exported model
        """
        src_dir = kimcodes.kimcode_to_file_path(self.kim_code)
        util.create_tarball(src_dir, dest_dir, arcname=name)


class ModelDriver(kimobjects.ModelDriver):
    def __init__(
        self,
        repository,
        kimcode=None,
        name=None,
        source_dir=None,
        metadata_dict=None,
        provenance_comments=None,
        *args,
        **kwargs,
    ):
        """Model Driver Class

        Repository is always required in KIMkit.

        Items can be initialized with just a kimcode if the item is already installed in a KIMkit repository.

        If no kimcode is supplied, a new model can be installed with a name, a list of parameter files,
        a source_dir where the item's files are located, and dict of metadata fields.

        Parameters
        ----------
        repository : str
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item. If not supplied assumne a new item is being imported,
            generate a new kimcode and assign it to the new item


        name : str, optional
            Name of the item, required if importing a new item, by default None
        source_dir : path like, optional
            location of the item on disk, required if importing a new item, by default None
        metadata_dict : dict, optional
            dict of all required and any optional metadata fields, required if importing a new item, by default None
        provenance_comments : str, optional
            any comments for why the model was created, by default None

        Raises
        ------
        AttributeError
            _description_
        """

        # if no kimcode is supplied, assign a new one to the item
        #  and initialize its directory in the selected repository
        if not kimcode:
            if all((metadata_dict, name, source_dir)):
                kimcode = prepare_install_dir(
                    name,
                    metadata_dict["kim-item-type"],
                    source_dir,
                    repository,
                    metadata_dict,
                    provenance_comments,
                )
            else:
                raise AttributeError(
                    f"A name, source directory, and dict of metadata are required to initialize a new Driver."
                )
        setattr(self, "repository", repository)
        kimcode_without_subversion = kimcodes.strip_subversion(kimcode)
        diskPath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(ModelDriver, self).__init__(
            kimcode_without_subversion, abspath=diskPath, *args, **kwargs
        )

    def export(self, dest_dir, name=None):
        """Export as a tar archive, with all needed dependancies for it to run

        Parameters
        ----------
        dest_dir : path like
            where to place the exported model
        name : str, optional
            name of the resulting .tar archive,
        """
        src_dir = kimcodes.kimcode_to_file_path(self.kim_code, self.repository)
        util.create_tarball(src_dir, dest_dir, arcname=name)


def prepare_install_dir(
    name,
    item_type,
    source_dir,
    repository,
    metadata_dict,
    provenance_comments=None,
    event_type="initial-creation",
    kimcode=None,
):
    """Assign the item a kimcode, create a directory in the selected repository for
    the item based on that kimcode, copy the item's files into it,
    generate needed metadata and provenance files, and store them with the item.

    If updating or forking an existing item, call this function with the kimcode to
    create the new version/item's directory

    If no new items/directories need to be created, returns the kimcode and exits.

    Parameters
    ----------
    name : str
        a human-readable name prefix for the item
    item_type : str
        options include "simulator-model", "portable-model", and "model-driver"
    source_dir : path like
        location of the item's files on disk
    repository : path like
        path to collection to install into
    metadata_dict : dict
        dict of all required and any optional metadata key-value pairs
    provenance_comments : str, optional
        any comments on how/why the item was created, by default None
    event_type : str
        reason for provenance update
        valid options include:"initial-creation", "version-update", "metadata-update", "fork", and "discontinued"
    kimcode : str
        id code of the item, if this is a new item a new kimcode will be assigned,
        if performing a version-update the existing kimcode will have its version incremented
        if performing a fork

    Returns
    -------
    new_kimcode : str
        ID code of the item in KIMkit
    """
    if not kimcode:
        valid_kimcode = False
        while valid_kimcode == False:
            new_kimcode = kimcodes.generate_kimcode(
                name, item_type, include_subversion=True
            )
            tmp_path = kimcodes.kimcode_to_file_path(new_kimcode, repository)
            # if the directory exists, an item of this type has already been assigned this ID number
            # generate a new random ID number and check again to avoid collisions
            if not os.path.exists(tmp_path):
                valid_kimcode = True
    else:
        # increment version of current kimcode for version update
        if event_type == "version-update":
            # TODO increment kimcode in new version format
            # TODO copy metadta and provenance to new item
            pass
        # assign version 0 of a new kimcode to the forked item
        elif event_type == "fork":
            valid_kimcode = False
            while valid_kimcode == False:
                new_kimcode = kimcodes.generate_kimcode(
                    name, item_type, include_subversion=True
                )
                tmp_path = kimcodes.kimcode_to_file_path(new_kimcode, repository)
                # if the directory exists, an item of this type has already been assigned this ID number
                # generate a new random ID number and check again to avoid collisions
                if not os.path.exists(tmp_path):
                    valid_kimcode = True
            # TODO copy metadta and provenance to new item
            # no new items need to be created, do nothing
        else:
            new_kimcode = kimcode
            return new_kimcode

    # TODO adjust logic for fork/update to copy when needed
    save_to_repository(source_dir, new_kimcode, repository)

    metadata.MetaData(repository, new_kimcode, metadata_dict)

    provenance.Provenance(
        new_kimcode,
        repository,
        event_type,
        metadata_dict["contributor"][0],  # TODO parse list of UUIDs
        comments=provenance_comments,
    )
    return new_kimcode


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
