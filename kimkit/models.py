"""
This module contains the classes corresponding to the various **KIMkit** items 
(portable-model, simulator-model, model-driver, test, test-driver, and verification-check),
along with functions to manage them.

In general, content is passed in and out of **KIMkit** as tarfile.TarFile objects, so that
automated systems can submit and retrieve KIMkit content without needing to write to disk.

When creating a new item, either importing it into **KIMkit** for the first time, 
or forking an existing item, you should first generate a kimcode for the item by
calling ``kimcodes.generate_kimcode()`` with a human-readable prefix for the item,
its item-type, and the repository it is to be saved in
(to ensure that kimcode is not already in use).

New content may be added by calling ``import_item()`` with a tarfile.TarFile object
containing the item's source code and associated files and a dict of metadata.
The item's content will be unpacked, assigned a directory in the
repository based on its kimcode ID number, the content and structure of its
metadata will be verified and written into the kimspec.edn file that stores metadata
for the item, and a copy of this metadata will be inserted into the KIMkit MongoDB
database for easy querying. Additionally, the initial entry in the item's history file
kimprovenance.edn will be created and stored in the item's directory for record keeping.

New items may be created from existing **KIMkit** items via either the
``version_update()`` or ``fork()`` functions, both of which take the kimcode of an
existing item, and a tarfile.TarFile of new content to do the update, along with
optional dicts of metadata changes and comments about what was updated and why. The major difference
betwen these functions is that ``version_update()`` creates a new version of the same item,
maintained by the same individual, just with its version number incremented, while ``fork()``
copies the item's content into version 000 of a new item, with whoever called ``fork()`` 
set as the maintainer of the new item. This allows the initial contributor
of a given item to retain ownership of it, but all collaborators can use that content
to base their own items on.

Contributors or maintainers of items may modify or delete their own content, 
otherwise a **KIMkit** Editor must run those
functions with ``run_as_editor=True`` to modify content they don't own.

This module also exposes an ``export()`` function that returns an item's content as a 
tarfile.TarFile object for external use."""

import os
import shutil
import tarfile
import re
import warnings
import stat
from subprocess import check_call

from . import metadata
from . import users
from . import kimcodes

from .src import provenance
from .src import logger
from .src.logger import logging
from .src import kimobjects
from .src import config as cf
from .src import mongodb

logger = logging.getLogger("KIMkit")


class PortableModel(kimobjects.Model):
    """Portable Model Class"""

    def __init__(
        self,
        repository,
        kimcode,
        abspath=None,
        *args,
        **kwargs,
    ):
        """Class representing KIMkit portable-models

        Inherits from OpenKIM PortableModel class

        Parameters
        ----------
        repository : path-like
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item
        abspath : path-like, optional
            location of the item on disk, if not specified it is constructed out of the repoistory and kimcode, by default None
        """

        setattr(self, "repository", repository)
        if not abspath:
            abspath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(PortableModel, self).__init__(kimcode, abspath=abspath, *args, **kwargs)


class SimulatorModel(kimobjects.SimulatorModel):
    """Simulator Model Class"""

    def __init__(
        self,
        repository,
        kimcode,
        abspath=None,
        *args,
        **kwargs,
    ):
        """Class representing KIMkit simulator-models

        Inherits from OpenKIM SimulatorModel class

        Parameters
        ----------
        repository : path-like
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item
        abspath : path-like, optional
            location of the item on disk, if not specified it is constructed out of the repoistory and kimcode, by default None
        """

        setattr(self, "repository", repository)
        if not abspath:
            abspath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(SimulatorModel, self).__init__(kimcode, abspath=abspath, *args, **kwargs)


class ModelDriver(kimobjects.ModelDriver):
    "Model Driver Class"

    def __init__(
        self,
        repository,
        kimcode,
        abspath=None,
        *args,
        **kwargs,
    ):
        """Class representing KIMkit model-drivers

        Inherits from OpenKIM ModelDriver class

        Parameters
        ----------
        repository : path-like
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item
        abspath : path-like, optional
            location of the item on disk, if not specified it is constructed out of the repoistory and kimcode, by default None
        """
        setattr(self, "repository", repository)
        if not abspath:
            abspath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(ModelDriver, self).__init__(kimcode, abspath=abspath, *args, **kwargs)


class Test(kimobjects.Test):
    """KIM Test Class"""

    def __init__(
        self,
        repository,
        kimcode,
        abspath=None,
        *args,
        **kwargs,
    ):
        """Class representing KIMkit tests

        Inherits from OpenKIM Test class

        Parameters
        ----------
        repository : path-like
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item
        abspath : path-like, optional
            location of the item on disk, if not specified it is constructed out of the repoistory and kimcode, by default None
        """

        setattr(self, "repository", repository)
        if not abspath:
            abspath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(Test, self).__init__(kimcode, abspath=abspath, *args, **kwargs)


class TestDriver(kimobjects.TestDriver):
    """KIM Test Driver Class"""

    def __init__(
        self,
        repository,
        kimcode,
        abspath=None,
        *args,
        **kwargs,
    ):
        """Class representing KIMkit test-drivers

        Inherits from OpenKIM TestDriver class

        Parameters
        ----------
        repository : path-like
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item
        abspath : path-like, optional
            location of the item on disk, if not specified it is constructed out of the repoistory and kimcode, by default None
        """

        setattr(self, "repository", repository)
        if not abspath:
            abspath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(TestDriver, self).__init__(kimcode, abspath=abspath, *args, **kwargs)


class VerificationCheck(kimobjects.VerificationCheck):
    """KIM Test Class"""

    def __init__(
        self,
        repository,
        kimcode,
        abspath=None,
        *args,
        **kwargs,
    ):
        """Class representing KIMkit verification checks

        Inherits from OpenKIM Test class

        Parameters
        ----------
        repository : path-like
            path to root directory of KIMkit repository
        kimcode : str, optional
            ID code of the item
        abspath : path-like, optional
            location of the item on disk, if not specified it is constructed out of the repoistory and kimcode, by default None
        """

        setattr(self, "repository", repository)
        if not abspath:
            abspath = kimcodes.kimcode_to_file_path(kimcode, self.repository)
        super(VerificationCheck, self).__init__(
            kimcode, abspath=abspath, *args, **kwargs
        )


def import_item(
    tarfile_obj,
    metadata_dict=None,
    previous_item_name=None,
    workflow_tarfile=None,
    repository=cf.LOCAL_REPOSITORY_PATH,
):
    """Create a directory in the selected repository for the item based on its kimcode,
    copy the item's files into it, generate needed metadata and provenance files,
    and store them with the item.

    Expects the item to be passed in as a tarfile.Tarfile object.

    If the item is from openkim.org the user does not need to supply a dict of
    metadata, as it will be automatically generated from the item's kimspec.edn file.

    Parameters
    ----------
    tarfile_obj : tarfile.TarFile
        tarfile object containing item files
    metadata_dict : dict
        dict of all required and any optional metadata key-value pairs
    previous_item_name : str, optional
        Name the item was assigned before being imported into this KIMkit repository, if any.
        May be a kimcode or regular string.
        Used to search through makefiles and attempt to replace with the item's new kimcode.
        If not set, the item's makefiles will need to have their item name manually set to the new kimcode.
        By default None
    workflow_tarfile: tarfile.TarFile, optional
        TarFile object containing all files needed to recreate the workflow that created the item
    repository : path-like, optional
        root directory of collection to install into,
        by default set to cf.LOCAL_REPOSITORY_PATH

    Raises
    ------
    KIMkitUserNotFoundError
        The user attempting to import the item isn't in the list of KIMkit users.
    InvalidItemTypeError
        The leader of the kimcode is invalid.
    InvalidKIMCode
        Item type not consistient with kimcode leader item type
    KimCodeAlreadyInUseError
        Specified kimcode is already in use by another item in the same repository.
    InvalidMetadataError
        Metadata does not comply with KIMkit standard.
    AttributeError
        One or more inputs required for import is missing.
    """

    this_user = users.whoami()
    if users.is_user(username=this_user):
        UUID = users.get_user_info(username=this_user)["uuid"]
    else:
        raise cf.KIMkitUserNotFoundError(
            "Only KIMkit users can import items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
        )
    event_type = "initial-creation"
    can_create_metadata = False
    if not metadata_dict:
        oldumask = os.umask(0)
        tmp_dir = os.path.join(repository, "tmp")
        tarfile_obj.extractall(path=tmp_dir)
        contents = listdir_nohidden(tmp_dir)
        # if the contents of the item are enclosed in a directory, copy them out
        # then delete the directory
        if len(contents) == 1 and os.path.isdir(os.path.join(tmp_dir, contents[0])):
            inner_dir = os.path.join(tmp_dir, contents[0])
            if os.path.isdir(inner_dir):
                inner_contents = listdir_nohidden(inner_dir)
                for item in inner_contents:
                    item_path = os.path.join(inner_dir, item)
                    if os.path.isdir(item_path):
                        shutil.copytree(
                            item_path, os.path.join(tmp_dir, item), dirs_exist_ok=True
                        )
                    else:
                        shutil.copy(os.path.join(inner_dir, item), tmp_dir)
                shutil.rmtree(inner_dir)
        contents = listdir_nohidden(tmp_dir)
        if "kimspec.edn" in contents:
            kimspec_loc = os.path.join(tmp_dir, "kimspec.edn")
            new_metadata_dict = metadata.create_kimkit_metadata_from_openkim_kimspec(
                kimspec_loc, UUID
            )
            can_create_metadata = True
            shutil.rmtree(tmp_dir)
        else:
            shutil.rmtree(tmp_dir)
            raise cf.InvalidMetadataError(
                "No dict of metadata or kimspec.edn file present, aborting import."
            )
        if "kimprovenance.edn" in contents:
            event_type = "fork"
    if can_create_metadata:
        metadata_dict = new_metadata_dict
    kimcode = metadata_dict["extended-id"]
    kim_item_type = metadata_dict["kim-item-type"]

    __, leader, __, __ = kimcodes.parse_kim_code(kimcode)

    if leader == "MO":
        kimcode_item_type = "portable-model"

    elif leader == "SM":
        kimcode_item_type = "simulator-model"

    elif leader == "MD":
        kimcode_item_type = "model-driver"

    elif leader == "TE":
        kimcode_item_type = "test"

    elif leader == "TD":
        kimcode_item_type = "test-driver"

    elif leader == "VC":
        kimcode_item_type = "verification-check"

    else:
        raise cf.InvalidItemTypeError(
            f"Leader of kimcode {kimcode} does not represent a valid item type"
        )

    if kim_item_type != kimcode_item_type:
        raise cf.InvalidKIMCode(
            "Invalid Kimcode: Item type does not match kimcode leader."
        )

    if not kimcodes.is_kimcode_available(kimcode):
        raise cf.KimCodeAlreadyInUseError(
            f"kimcode {kimcode} is already in use, please select another."
        )

    if all((tarfile_obj, repository, kimcode, metadata_dict)):
        # ignore any umask the user may have set
        oldumask = os.umask(0)
        tmp_dir = os.path.join(repository, kimcode)
        tarfile_obj.extractall(path=tmp_dir)
        tarfile_obj.close()
        contents = listdir_nohidden(tmp_dir)
        # if the contents of the item are enclosed in a directory, copy them out
        # then delete the directory
        if len(contents) == 1 and os.path.isdir(os.path.join(tmp_dir, contents[0])):
            inner_dir = os.path.join(tmp_dir, contents[0])
            if os.path.isdir(inner_dir):
                inner_contents = listdir_nohidden(inner_dir)
                for item in inner_contents:
                    item_path = os.path.join(inner_dir, item)
                    if os.path.isdir(item_path):
                        shutil.copytree(
                            item_path, os.path.join(tmp_dir, item), dirs_exist_ok=True
                        )
                    else:
                        shutil.copy(os.path.join(inner_dir, item), tmp_dir)
                shutil.rmtree(inner_dir)

        executables = []
        for file in listdir_nohidden(tmp_dir):
            # add group read/write/execute permissions
            filepath = os.path.join(tmp_dir, file)
            os.chmod(
                filepath,
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IWGRP
                | stat.S_IXGRP,
            )
            if os.path.isfile(file):
                executable = os.access(file, os.X_OK)
                if executable:
                    executables.append(os.path.split(file)[-1])
        if executables:
            metadata_dict["executables"] = executables

        dest_dir = kimcodes.kimcode_to_file_path(kimcode, repository)

        shutil.copytree(tmp_dir, dest_dir)

        if previous_item_name != None:
            update_makefile_kimcode(previous_item_name, kimcode)
        else:
            logger.warning(
                f"Kimcode update not requested when importing item {kimcode}"
            )
            warnings.warn(
                "No previous item name supplied, item name in makefiles may need to be updated to new kimcode"
            )

        if workflow_tarfile:
            _create_workflow_dir(kimcode, workflow_tarfile, repository)

        try:
            new_metadata = metadata.create_metadata(
                repository=repository,
                kimcode=kimcode,
                metadata_dict=metadata_dict,
                UUID=UUID,
            )
        except cf.InvalidMetadataError as e:
            shutil.rmtree(tmp_dir)
            shutil.rmtree(dest_dir)
            try:
                os.removedirs(os.path.split(dest_dir)[0])
            except OSError:
                pass
            raise cf.InvalidMetadataError(
                "Import Failed due to invalid metadata."
            ) from e

        provenance.add_kimprovenance_entry(
            dest_dir,
            user_id=UUID,
            event_type=event_type,
            comment=None,
        )
        shutil.rmtree(tmp_dir)
        logger.info(f"User {UUID} imported item {kimcode} into repository {repository}")
        # return user's original usmask
        os.umask(oldumask)
    else:
        raise AttributeError(
            f"""A name, source directory, KIMkit repository,
             and dict of required metadata fields are required to initialize a new item."""
        )


def delete(kimcode, run_as_editor=False, repository=cf.LOCAL_REPOSITORY_PATH):
    """Delete an item from the repository and all of its content

    Users may delete items if they are the contributor or maintainer of that item.
    Otherwise, a KIMkit editor must delete the item, by specifying run_as_editor=True.

    If all versions of the item have been deleted, delete its enclosing directory as well.

    Parameters
    ----------
    kimcode : str
        ID code the item, must refer to a valid item in repository
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions,
        and delete items they are neither the contributor nor maintainer of, by default False
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY

    Raises
    ------
    KIMkitUserNotFoundError
        A non KIMkit user attempted to delete an item.
    KIMkitItemNotFoundError
        No item with kimcode exists in repository.
    NotRunAsEditorError
        A user with Editor permissions attempted to delete the item, but did not specify run_as_editor=True
    NotAnEditorError
        A user without Editor permissions attempted to delete an item they are not the contributor or maintainer of.
    """

    this_user = users.whoami()
    if users.is_user(username=this_user):
        UUID = users.get_user_info(username=this_user)["uuid"]
    else:
        raise cf.KIMkitUserNotFoundError(
            "Only KIMkit users can delete items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
        )

    del_path = kimcodes.kimcode_to_file_path(kimcode, repository)
    needs_deleted_from_repository = True

    if not os.path.exists(del_path):
        needs_deleted_from_repository = False

    __, leader, num, __ = kimcodes.parse_kim_code(kimcode)

    if leader == "MO":
        item = PortableModel(kimcode=kimcode, repository=repository)

    elif leader == "SM":
        item = SimulatorModel(kimcode=kimcode, repository=repository)

    elif leader == "MD":
        item = ModelDriver(kimcode=kimcode, repository=repository)

    elif leader == "TE":
        item = Test(kimcode=kimcode, repository=repository)

    elif leader == "TD":
        item = TestDriver(kimcode=kimcode, repository=repository)

    elif leader == "VC":
        item = VerificationCheck(kimcode=kimcode, repository=repository)

    spec = item.kimspec

    contributor = spec["contributor-id"]
    maintainer = spec["maintainer-id"]

    can_edit = False
    test_model_prefix = "Test_Model"

    if UUID == contributor or UUID == maintainer:
        can_edit = True

    elif users.is_editor():
        if run_as_editor:
            can_edit = True
        else:
            raise cf.NotRunAsEditorError(
                "Did you mean to edit this item? If you are an Editor run again with run_as_editor=True"
            )
    elif kimcode[:10] == test_model_prefix:
        can_edit = True

    current_item = mongodb.find_item_by_kimcode(kimcode)

    previous_items = mongodb.db.items.find_one(
        {"content-origin": kimcode}, projection={"kimcode": 1, "_id": 0}
    )
    if previous_items is not None:
        can_edit = False
        dependent_kimcode = previous_items["kimcode"]
        msg = f"This item is part of the legacy of item {dependent_kimcode} (and possibly others), do not delete."
        warnings.warn(msg)
        return

    if can_edit:
        if needs_deleted_from_repository:
            shutil.rmtree(del_path)
        if current_item != None:
            mongodb.delete_one_database_entry(kimcode, run_as_editor=run_as_editor)

        logger.info(
            f"User {this_user} deleted item {kimcode} from repository {repository}"
        )

        try:
            empty_dirs_path = os.path.split(del_path)[0]
            os.removedirs(empty_dirs_path)
        except OSError:
            pass
    else:
        logger.warning(
            f"User {this_user} attempted to deleted item {kimcode} from repository {repository}, but is neither the contributor of the item nor an editor"
        )
        raise cf.NotAnEditorError(
            "Only KIMkit Editors or the Administrator may delete items belonging to other users."
        )

    mongodb.set_latest_version_object(num)


def version_update(
    kimcode,
    tarfile_obj,
    workflow_tarfile=None,
    repository=cf.LOCAL_REPOSITORY_PATH,
    metadata_update_dict=None,
    provenance_comments=None,
    run_as_editor=False,
):
    """Create a new version of the item with new content and possibly new metadata

    Expects the content of the new version of the item to be passed in as a tarfile.Tarfile object.

    Users may update items if they are the contributor or maintainer of that item.
    Otherwise, a KIMkit editor must update the item, by specifying run_as_editor=True.

    Parameters
    ----------
    kimcode : str
        ID code of the item to be updated
    tarfile_obj : tarfile.Tarfile
        tarfile object containing the new version's content
    workflow_tarfile: tarfile.TarFile, optional
        TarFile object containing all files needed to recreate the workflow that created the item
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY
    metadata_update_dict : dict, optional
        dict of any metadata keys to be changed in the new version, by default None
    provenance_comments : str, optional
        any comments about how/why this version was created, by default None
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions,
        and update items they are neither the contributor nor maintainer of, by default False

    Raises
    ------
    KIMkitUserNotFoundError
        A non KIMkit user attempted to update an item.
    KIMkitItemNotFoundError
        No item with kimcode exists in repository
    NotMostRecentVersionError
        A more recent version of the item exists, so the older one should not be updated
    NotRunAsEditorError
        A user with Editor permissions attempted to update the item, but did not specify run_as_editor=True
    InvalidMetadataError
        The metadata_update_dict does not comply with the KIMkit standard
    NotAnEditorError
        A user without Editor permissions attempted to update an item they are not the contributor or maintainer of.
    """

    this_user = users.whoami()
    if users.is_user(username=this_user):
        UUID = users.get_user_info(username=this_user)["uuid"]
    else:
        raise cf.KIMkitUserNotFoundError(
            "Only KIMkit users can update items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
        )

    current_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    if not os.path.exists(current_dir):
        raise cf.KIMkitItemNotFoundError(
            f"No item with kimcode {kimcode} exists, aborting."
        )

    outer_dir = os.path.split(current_dir)[0]
    versions = listdir_nohidden(outer_dir)
    most_recent_version = max(versions)

    most_recent_dir = os.path.join(outer_dir, most_recent_version)

    if not os.path.samefile(current_dir, most_recent_dir):
        raise cf.NotMostRecentVersionError(
            f"{kimcode} is not the most recent version of this item. Most recent version {most_recent_version} should be used as a base for updating."
        )

    event_type = "revised-version-creation"
    name, leader, num, old_version = kimcodes.parse_kim_code(kimcode)
    if leader == "MO":
        this_item = PortableModel(kimcode=kimcode, repository=repository)

    elif leader == "SM":
        this_item = SimulatorModel(kimcode=kimcode, repository=repository)

    elif leader == "MD":
        this_item = ModelDriver(kimcode=kimcode, repository=repository)

    elif leader == "TE":
        this_item = Test(kimcode=kimcode, repository=repository)

    elif leader == "TD":
        this_item = TestDriver(kimcode=kimcode, repository=repository)

    elif leader == "VC":
        this_item = VerificationCheck(kimcode=kimcode, repository=repository)

    spec = this_item.kimspec

    contributor = spec["contributor-id"]
    maintainer = spec["maintainer-id"]

    can_edit = False

    if UUID == contributor or UUID == maintainer:
        can_edit = True

    elif users.is_editor():
        if run_as_editor:
            can_edit = True
        else:
            raise cf.NotRunAsEditorError(
                "Did you mean to edit this item? If you are an Editor run again with run_as_editor=True"
            )

    if can_edit:
        # ignore any umask the user may have set
        oldumask = os.umask(0)
        new_version = str(int(old_version) + 1)
        new_kimcode = kimcodes.format_kim_code(name, leader, num, new_version)
        tmp_dir = os.path.join(repository, new_kimcode)
        tarfile_obj.extractall(path=tmp_dir)
        tarfile_obj.close()
        contents = listdir_nohidden(tmp_dir)
        # if the contents of the item are enclosed in a directory, copy them out
        # then delete the directory
        if len(contents) == 1 and os.path.isdir(os.path.join(tmp_dir, contents[0])):
            inner_dir = os.path.join(tmp_dir, contents[0])
            if os.path.isdir(inner_dir):
                inner_contents = listdir_nohidden(inner_dir)
                for item in inner_contents:
                    item_path = os.path.join(inner_dir, item)
                    if os.path.isdir(item_path):
                        shutil.copytree(
                            item_path, os.path.join(tmp_dir, item), dirs_exist_ok=True
                        )
                    else:
                        shutil.copy(os.path.join(inner_dir, item), tmp_dir)
                shutil.rmtree(inner_dir)

        executables = []
        for file in listdir_nohidden(tmp_dir):
            # add group read/write/execute permissions
            filepath = os.path.join(tmp_dir, file)
            os.chmod(
                filepath,
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IWGRP
                | stat.S_IXGRP,
            )
            if os.path.isfile(file):
                executable = os.access(file, os.X_OK)
                if executable:
                    executables.append(os.path.split(file)[-1])
        if executables:
            if metadata_update_dict:
                metadata_update_dict["executables"] = executables
            else:
                metadata_update_dict = {"executables": executables}

        if metadata_update_dict:
            metadata_update_dict["content-origin"] = kimcode
        else:
            metadata_update_dict = {"content-origin": kimcode}

        dest_dir = kimcodes.kimcode_to_file_path(new_kimcode, repository)
        shutil.copytree(tmp_dir, dest_dir)

        update_makefile_kimcode(kimcode, new_kimcode, repository=repository)

        if workflow_tarfile:
            _create_workflow_dir(new_kimcode, workflow_tarfile, repository)

        else:
            # copy the previous version's workflow, if any, if no new workflow supplied
            old_workflow_path = os.path.join(current_dir, "workflow")
            if os.path.isdir(old_workflow_path):
                workflow_tar = export_workflow(kimcode, repository)
                _create_workflow_dir(new_kimcode, workflow_tar, repository)
                new_workflow_dir = os.path.join(dest_dir, "workflow")
                with open(
                    os.path.join(new_workflow_dir, "previous.txt"), "w"
                ) as witness_file:
                    witness_file.write(kimcode)
                logger.info(
                    f"Copying existing workflow from previous version {kimcode}"
                )

        try:
            metadata.create_new_metadata_from_existing(
                kimcode,
                new_kimcode,
                UUID,
                metadata_update_dict=metadata_update_dict,
                repository=repository,
            )
        except cf.InvalidMetadataError as e:
            shutil.rmtree(dest_dir)
            shutil.rmtree(tmp_dir)
            try:
                os.removedirs(os.path.split(dest_dir)[0])
            except OSError:
                pass
            raise cf.InvalidMetadataError(
                f"Update failed due to invalid metadata."
            ) from e
        old_provenance = os.path.join(
            kimcodes.kimcode_to_file_path(kimcode, repository), "kimprovenance.edn"
        )
        new_dir = kimcodes.kimcode_to_file_path(new_kimcode, repository)
        shutil.copy(old_provenance, new_dir)

        provenance.add_kimprovenance_entry(
            new_dir,
            user_id=UUID,
            event_type=event_type,
            comment=provenance_comments,
        )

        shutil.rmtree(tmp_dir)
        logger.info(
            f"User {UUID} has requested a version update of item {kimcode} in repository {repository}"
        )
        # return user's original usmask
        os.umask(oldumask)

    else:
        logger.warning(
            f"User {this_user} requested a verion update of item {kimcode} in repository {repository}, but is neither the owner of the item nor an Editor."
        )
        raise cf.NotAnEditorError(
            "Only KIMkit Editors or the Administrator may create updated versions of items belonging to other users."
        )


def fork(
    kimcode,
    new_kimcode,
    tarfile_obj=None,
    workflow_tarfile=None,
    repository=cf.LOCAL_REPOSITORY_PATH,
    metadata_update_dict=None,
    provenance_comments=None,
):
    """Create a new item, based off a fork of an existing one,
    with new content and possibly new metadata

    Expects the content of the new version of the item to be passed in as a tarfile.Tarfile object.

    Parameters
    ----------
    kimcode : str
        ID code of the item to be forked
    new_kimcode : str
        id code the new item will be assigned
    tarfile_obj : tarfile.Tarfile, optional
        tarfile object containing the new version's content
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY
    metadata_update_dict : dict, optional
        dict of any metadata keys to be changed in the new version, by default None
    provenance_comments : str, optional
        any comments about how/why this version was created, by default None

    Raises
    ------
    KIMkitUserNotFoundError
        A non KIMkit user attempted to update an item.
    InvalidItemTypeError
        Leader of new kimcode is invalid.
    KIMkitItemNotFoundError
        No item with kimcode exists in repository
    KimCodeAlreadyInUseError
        New kimcode is already assigned to an item in this repository
    InvalidMetadataError
        The metadata_update_dict does not comply with the KIMkit standard
    """

    this_user = users.whoami()
    if users.is_user(username=this_user):
        UUID = users.get_user_info(username=this_user)["uuid"]
    else:
        raise cf.KIMkitUserNotFoundError(
            "Only KIMkit users can fork items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
        )

    __, new_leader, __, __ = kimcodes.parse_kim_code(new_kimcode)

    if new_leader not in ["MO", "SM", "MD", "TE", "TD", "VC"]:
        raise cf.InvalidItemTypeError(
            f"Leader of new kimcode {new_kimcode} does not refer to a valid kim item type"
        )

    current_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    if not os.path.exists(current_dir):
        raise cf.KIMkitItemNotFoundError(
            f"No item with kimcode {kimcode} exists, aborting."
        )

    if not kimcodes.is_kimcode_available(new_kimcode):
        raise cf.KimCodeAlreadyInUseError(
            f"kimcode {new_kimcode} is already in use, please select another."
        )
    # ignore any umask the user may have set
    oldumask = os.umask(0)
    event_type = "fork"

    tmp_dir = os.path.join(repository, new_kimcode)
    if tarfile_obj:
        tarfile_obj.extractall(path=tmp_dir)
        tarfile_obj.close()
    else:
        # copy the existing item without editing it
        # if no new content supplied
        old_tarfile_obj = export(kimcode)
        for item in old_tarfile_obj:
            if kimcode in item.getnames():
                item.extractall(path=tmp_dir)
                item.close()
    contents = listdir_nohidden(tmp_dir)
    # if the contents of the item are enclosed in a directory, copy them out
    # then delete the directory
    if len(contents) == 1 and os.path.isdir(os.path.join(tmp_dir, contents[0])):
        inner_dir = os.path.join(tmp_dir, contents[0])
        if os.path.isdir(inner_dir):
            inner_contents = listdir_nohidden(inner_dir)
            for item in inner_contents:
                item_path = os.path.join(inner_dir, item)
                if os.path.isdir(item_path):
                    shutil.copytree(
                        item_path, os.path.join(tmp_dir, item), dirs_exist_ok=True
                    )
                else:
                    shutil.copy(os.path.join(inner_dir, item), tmp_dir)
            shutil.rmtree(inner_dir)

    executables = []
    for file in listdir_nohidden(tmp_dir):
        # add group read/write/execute permissions
        filepath = os.path.join(tmp_dir, file)
        os.chmod(
            filepath,
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IWGRP
            | stat.S_IXGRP,
        )
        if os.path.isfile(file):
            executable = os.access(file, os.X_OK)
            if executable:
                executables.append(os.path.split(file)[-1])
    if executables:
        if metadata_update_dict:
            metadata_update_dict["executables"] = executables
        else:
            metadata_update_dict = {"executables": executables}

    if metadata_update_dict:
        metadata_update_dict["content-origin"] = kimcode
    else:
        metadata_update_dict = {"content-origin": kimcode}

    dest_dir = kimcodes.kimcode_to_file_path(new_kimcode, repository)
    shutil.copytree(tmp_dir, dest_dir)

    if workflow_tarfile:
        _create_workflow_dir(new_kimcode, workflow_tarfile, repository)

    else:
        if not tarfile_obj:
            # if the previous item had a workflow dir it was already copied
            # when the old item's contents were copied
            # just add a witness file with the old item's kimcode
            # if there was a workflow to copy
            new_workflow_dir = os.path.join(dest_dir, "workflow")

            if os.path.isdir(new_workflow_dir):
                with open(
                    os.path.join(new_workflow_dir, "previous.txt"), "w"
                ) as witness_file:
                    witness_file.write(kimcode)
                logger.info(
                    f"Copying existing workflow from previous version {kimcode}"
                )

    update_makefile_kimcode(kimcode, new_kimcode, repository=repository)

    try:
        metadata.create_new_metadata_from_existing(
            kimcode,
            new_kimcode,
            UUID,
            metadata_update_dict=metadata_update_dict,
            repository=repository,
        )
    except cf.InvalidMetadataError as e:
        shutil.rmtree(dest_dir)
        shutil.rmtree(tmp_dir)
        try:
            os.removedirs(os.path.split(dest_dir)[0])
        except OSError:
            pass
        raise cf.InvalidMetadataError(f"Forking failed due to invalid metadata.") from e
    old_provenance = os.path.join(
        kimcodes.kimcode_to_file_path(kimcode, repository), "kimprovenance.edn"
    )
    shutil.copy(old_provenance, dest_dir)

    provenance.add_kimprovenance_entry(
        dest_dir,
        user_id=UUID,
        event_type=event_type,
        comment=provenance_comments,
    )

    shutil.rmtree(tmp_dir)
    logger.info(
        f"User {UUID} has forked item {new_kimcode} based on {kimcode} in repository {repository}"
    )
    # return user's original usmask
    os.umask(oldumask)


def export(
    kimcode,
    destination_path,
    include_dependencies=True,
    repository=cf.LOCAL_REPOSITORY_PATH,
):
    """Export an item as a .txz file, with any dependancies (e.g. model-drivers) needed for it to run,
    and save it to the path specified in destination_path

    Parameters
    ----------
    kimcode: str
        id code of the item
    destination_path: path-like
        location on disk to save the tar archive
    include_dependencies : bool, optional
        Flag to allow exports of KIMkit content without included dependencies,
        e.g. drivers, by default True
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY

    Raises
    ------
    KIMkitItemNotFoundError
        No item with kimcode found in repository
    """
    src_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    if not os.path.isdir(src_dir):
        raise cf.KIMkitItemNotFoundError(
            f"No item with kimcode {kimcode} exists, aborting."
        )

    logger.debug(f"Exporting item {kimcode} from repository {repository}")
    __, leader, __, __ = kimcodes.parse_kim_code(kimcode)
    if leader == "MO":  # portable model
        this_item = PortableModel(repository, kimcode=kimcode)
        if include_dependencies:
            req_driver = this_item.driver
            # some portable models may not have a driver associated/available
            # these will have a string in the model-driver field
            # but it will not be a kimcode
            if kimcodes.iskimid(req_driver):
                driver_src_dir = kimcodes.kimcode_to_file_path(req_driver, repository)
                with tarfile.open(
                    os.path.join(driver_src_dir, req_driver + ".txz"), "w:xz"
                ) as tar:
                    tar.add(driver_src_dir, arcname=req_driver)
                contents = listdir_nohidden(driver_src_dir)
                for item in contents:
                    if ".txz" in item:
                        tarfile_obj = tarfile.open(os.path.join(driver_src_dir, item))
                        tarfile_obj.close()
                        shutil.move(
                            os.path.join(driver_src_dir, item), destination_path
                        )
    elif leader == "TE":  # test
        this_item = Test(repository, kimcode=kimcode)
        if include_dependencies:
            req_driver = this_item.driver
            driver_src_dir = kimcodes.kimcode_to_file_path(req_driver, repository)
            with tarfile.open(
                os.path.join(driver_src_dir, req_driver + ".txz"), "w:xz"
            ) as tar:
                tar.add(driver_src_dir, arcname=req_driver)
            contents = listdir_nohidden(driver_src_dir)
            for item in contents:
                if ".txz" in item:
                    tarfile_obj = tarfile.open(os.path.join(driver_src_dir, item))
                    tarfile_obj.close()
                    shutil.move(os.path.join(driver_src_dir, item), destination_path)
    with tarfile.open(os.path.join(src_dir, kimcode + ".txz"), "w:xz") as tar:
        tar.add(src_dir, arcname=kimcode)
    contents = listdir_nohidden(src_dir)
    for item in contents:
        if ".txz" in item:
            tarfile_obj = tarfile.open(os.path.join(src_dir, item))
            tarfile_obj.close()
            src = os.path.join(src_dir, item)
            dest = os.path.join(destination_path, item)
            check_call(["mv", f"{src}", f"{dest}"])


def update_makefile_kimcode(
    old_kimcode, new_kimcode, repository=cf.LOCAL_REPOSITORY_PATH, replace_with=None
):
    """Search through the item's directory for makefiles containing kimcodes matching a previous version of the item,
    and attempt to replace them with the item's new kimcode.

    Parameters
    ----------
    old_kimcode : str
        previous id code of the item that may be lingering in makefiles
    new_kimcode : str
        new id code of the item to be written into makefiles
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY
    replace_with: str
        optional string to replace the old kimcode with, if different
        than the new kimcode.
    """

    item_path = kimcodes.kimcode_to_file_path(new_kimcode, repository)

    # First, check for a makefile
    possible_makefile_names = ["GNUmakefile", "makefile", "Makefile", "CMakeLists.txt"]
    set_new_kimcode = False
    already_changed = None
    for makefile_name in possible_makefile_names:
        makefile = os.path.join(item_path, makefile_name)
        if os.path.isfile(makefile):
            with open(makefile, "r") as flobj:
                makefile_contents = flobj.read()
                # check if the user manually updated the kimcode before this
                already_changed = re.search(
                    r"\b" + new_kimcode + r"\b", makefile_contents
                )
                # attempt to replace the old kimcode
                if not replace_with:
                    updated_makefile_contents = re.sub(
                        r"\b" + old_kimcode + r"\b", new_kimcode, makefile_contents
                    )
                else:
                    updated_makefile_contents = re.sub(
                        r"\b" + old_kimcode + r"\b", replace_with, makefile_contents
                    )
            if updated_makefile_contents != makefile_contents:
                set_new_kimcode = True
                tmp_makefile_name = "tmp_" + makefile_name
                # ignore any umask the user may have set
                oldumask = os.umask(0)
                tmp_makefile = os.path.join(item_path, tmp_makefile_name)
                with open(tmp_makefile, "w") as flobj2:
                    flobj2.write(updated_makefile_contents)
                os.rename(tmp_makefile, makefile)
                os.chmod(
                    makefile,
                    stat.S_IRUSR
                    | stat.S_IWUSR
                    | stat.S_IXUSR
                    | stat.S_IRGRP
                    | stat.S_IWGRP
                    | stat.S_IXGRP,
                )
                logger.info(
                    f"Updated name/kimcode of item {new_kimcode}  makeflile {makefile_name} to match its new kimcode."
                )
                # return user's original usmask
                os.umask(oldumask)

    if set_new_kimcode == False and already_changed == None:
        logger.warning(
            f"No kimcodes replaced in makefiles of item {new_kimcode}, makefiles may be invalid"
        )
        warnings.warn(
            f"""
            No kimcodes replaced in makefiles of item
            {new_kimcode}
            makefiles may refer to outdated kimcode,
            and may require manual editing to be installable by kim_api.

            Please write the kimcode of items explicitly into their makefiles
            so that KIMkit can edit them by regex when managing items."""
        )


def listdir_nohidden(path):
    """List the files and directories in a given path,
    ignoring hiden files/directories.

    Args:
        path (path-like): directory who's conents to list

    Returns:
       list: list of all files and directories in path,
       excluding hidden files/directories
    """

    root_path = cf.KIM_API_PREFIX_DIR

    if not os.path.isdir(root_path):
        os.mkdir(root_path)

    target_dirs = [
        cf.KIM_API_PORTABLE_MODELS_DIR,
        cf.KIM_API_SIMULATOR_MODELS_DIR,
        cf.KIM_API_MODEL_DRIVERS_DIR,
    ]

    for dir in target_dirs:
        if not os.path.isdir(dir):
            os.mkdir(dir)


def _create_workflow_dir(
    kimcode, workflow_tarfile, repository=cf.LOCAL_REPOSITORY_PATH
):
    """Create a "workflow" subdirectory within the item's directory,
    store all workflow-defining files (taining scripts, hyperparameters,
    dependencies, etc.) inside it for future reference.

    Parameters
    ----------
    kimcode : str
        id code of the item
    workflow_tarfile : tarfile.TarFile
        TarFile object containing all the files
        needed to recontstruct the workflow
    repository : path like, optional
        root dir of the kimkit repository storing the item,
        by default cf.LOCAL_REPOSITORY_PATH
    """
    item_path = kimcodes.kimcode_to_file_path(kimcode, repository)

    # ignore any umask the user may have set
    oldumask = os.umask(0)

    workflow_dir = os.path.join(item_path, "workflow")

    tmp_dir = os.path.join(item_path, "tmp")
    workflow_tarfile.extractall(path=tmp_dir)
    workflow_tarfile.close()
    contents = os.listdir(tmp_dir)
    # if the contents of the item are enclosed in a directory, copy them out
    # then delete the directory
    if len(contents) == 1 and os.path.isdir(os.path.join(tmp_dir, contents[0])):
        inner_dir = os.path.join(tmp_dir, contents[0])
        if os.path.isdir(inner_dir):
            inner_contents = os.listdir(inner_dir)
            for item in inner_contents:
                item_path = os.path.join(inner_dir, item)
                if os.path.isdir(item_path):
                    shutil.copytree(
                        item_path, os.path.join(tmp_dir, item), dirs_exist_ok=True
                    )
                else:
                    shutil.copy(os.path.join(inner_dir, item), tmp_dir)
            shutil.rmtree(inner_dir)

    for file in listdir_nohidden(tmp_dir):
        # add group read/write/execute permissions
        filepath = os.path.join(tmp_dir, file)
        os.chmod(
            filepath,
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IWGRP
            | stat.S_IXGRP,
        )

    shutil.copytree(tmp_dir, workflow_dir, dirs_exist_ok=True)
    shutil.rmtree(tmp_dir)
    # return user's original usmask
    os.umask(oldumask)


def export_workflow(kimcode, destination_path, repository=cf.LOCAL_REPOSITORY_PATH):
    """Export the contents of the "workflow" subdirectory for a given item,
    if it exists and save it to the destination_path.

    Parameters
    ----------
    kimcode : str
        id code of the item
    repository : path like, optional
        root directory of the repository containing the item,
        by default cf.LOCAL_REPOSITORY_PATH

    Raises
    ------
    cf.KIMkitItemNotFoundError
        no item with specified kimcode found
    cf.KIMkitItemNotFoundError
        no workflow found associated with specified item
    """
    src_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    if not os.path.isdir(src_dir):
        raise cf.KIMkitItemNotFoundError(
            f"No item with kimcode {kimcode} exists, aborting."
        )

    workflow_dir = os.path.join(src_dir, "workflow")

    if not os.path.isdir(workflow_dir):
        raise cf.KIMkitItemNotFoundError(
            f"No workflow is associated with item {kimcode}, aborting."
        )

    logger.debug(
        f"Exporting workflow used to create item {kimcode} from repository {repository}"
    )

    with tarfile.open(
        os.path.join(workflow_dir, kimcode + "_workflow.txz"), "w:xz"
    ) as tar:
        tar.add(workflow_dir, arcname=kimcode + "_workflow")
    contents = os.listdir(workflow_dir)
    for item in contents:
        if ".txz" in item:
            shutil.move(os.path.join(workflow_dir, item), destination_path)


def listdir_nohidden(path):
    good_files_and_dirs = []
    for f in os.listdir(path):
        if not f.startswith("."):
            good_files_and_dirs.append(f)
    return good_files_and_dirs


def enumerate_repository(repository=cf.LOCAL_REPOSITORY_PATH):
    """Return a list of all items currently saved in the local repository

    Args:
        repository (path-like, optional): root directory of the local repository,
                Defaults to cf.LOCAL_REPOSITORY_PATH.
    """

    repository_kimcodes = []

    subdir_prefixes = [
        "portable-models",
        "model-drivers",
        "simulator-models",
        "tests",
        "test-drivers",
        "verification-checks",
    ]

    # get a list of all subdirectories in the repository
    all_subdirs = [x[0] for x in os.walk(repository)]

    for subdir in all_subdirs:

        # parse the levels of each subdir path
        parts = subdir.split("/")

        # exclude temporary directories, only search in kim item type directories
        for prefix in subdir_prefixes:
            if prefix in parts:

                for part in parts:

                    # check for directory names that are full extended kim ids
                    # those contain items
                    if kimcodes.isextendedkimid(part):
                        repository_kimcodes.append(part)

    # reduce to unique entries
    repository_kimcodes = set(repository_kimcodes)
    repository_kimcodes = list(repository_kimcodes)

    return repository_kimcodes
