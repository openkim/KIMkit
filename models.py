import os
import shutil
import tarfile

from . import metadata
from . import provenance
from . import users
from .logger import logging
from . import kimobjects
from . import kimcodes
from . import config as cf


"""
This module contains the classes corresponding to the various KIMkit items (portable-model, simulator-model, and model-driver),
along with functions to manage them.

In general, content is passed in and out of KIMkit as tarfile.TarFile objects, so that
automated systems can submit and retrieve KIMkit content without needing to write to disk.

When creating a new item, either importing it into KIMkit for the first time, or forking an existing item,
you should first generate a kimcode for the item by calling kimcodes.generate_kimcode() with a human-readable prefix
for the item, its item-type, and the repository it is to be saved in (to ensure that kimcode is not already in use).
"""
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


def import_item(tarfile_obj, repository, kimcode, metadata_dict):
    """Create a directory in the selected repository for the item based on its kimcode,
    copy the item's files into it, generate needed metadata and provenance files,
    and store them with the item.

    Expects the item to be passed in as a tarfile.Tarfile object.

    Parameters
    ----------
    tarfile_obj : tarfile.TarFile
        tarfile object containing item files
    repository : path-like
        root directory of collection to install into
    kimcode : str
        id code of the item
    metadata_dict : dict
        dict of all required and any optional metadata key-value pairs

    Raises
    ------
    KIMkitUserNotFoundError
        The user attempting to import the item isn't in the list of KIMkit users.
    KimCodeAlreadyInUseError
        Specified kimcode is already in use by another item in the same repository.
    ValueError
        Metadata does not comply with KIMkit standard.
    AttributeError
        One or more inputs required for import is missing.
    """

    this_user = users.whoami()
    if users.is_user(system_username=this_user):
        UUID = users.get_uuid(system_username=this_user)
    else:
        raise cf.KIMkitUserNotFoundError(
            "Only KIMkit users can import items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
        )

    if not kimcodes.is_kimcode_available(repository, kimcode):
        raise cf.KimCodeAlreadyInUseError(
            f"kimcode {kimcode} is already in use, please select another."
        )

    metadata_dict["extended-id"] = kimcode

    event_type = "initial-creation"
    if all((tarfile_obj, repository, kimcode, metadata_dict)):

        tmp_dir = os.path.join(repository, kimcode)
        tarfile_obj.extractall(path=tmp_dir)
        contents = os.listdir(tmp_dir)
        # if the contents of the item are enclosed in a directory, copy them out
        # then delete the directory
        if len(contents) == 1:
            inner_dir = os.path.join(tmp_dir, contents[0])
            if os.path.isdir(inner_dir):
                inner_contents = os.listdir(inner_dir)
                for item in inner_contents:
                    shutil.copy(os.path.join(inner_dir, item), tmp_dir)
                shutil.rmtree(inner_dir)

        executables = []
        for file in os.listdir(tmp_dir):
            if os.path.isfile(file):
                executable = os.access(file, os.X_OK)
                if executable:
                    executables.append(os.path.split(file)[-1])
        if executables:
            metadata_dict["executables"] = executables

        try:
            metadata_dict = metadata.validate_metadata(metadata_dict)
        except (ValueError, KeyError, TypeError) as e:
            shutil.rmtree(tmp_dir)
            raise ValueError(
                "Supplied dictionary of metadata does not comply with KIMkit standard."
            ) from e

        dest_dir = kimcodes.kimcode_to_file_path(kimcode, repository)

        logger.info(f"User {UUID} imported item {kimcode} into repository {repository}")

        shutil.copytree(tmp_dir, dest_dir)

        new_metadata = metadata.create_metadata(
            repository, kimcode, metadata_dict, UUID
        )

        provenance.Provenance(
            kimcode,
            repository,
            event_type,
            UUID,
            comments=None,
        )
        shutil.rmtree(tmp_dir)
    else:
        raise AttributeError(
            f"""A name, source directory, KIMkit repository,
             and dict of required metadata fields are required to initialize a new item."""
        )


def delete(repository, kimcode, run_as_editor=False):
    """Delete an item from the repository and all of its content

    Users may delete items if they are the contributor or maintainer of that item.
    Otherwise, a KIMkit editor must delete the item, by specifying run_as_editor=True.

    If all versions of the item have been deleted, delete its enclosing directory as well.

    Parameters
    ----------
    repository : path-like
        root directory of the KIMkit repo containing the item
    kimcode : str
        ID code the item, must refer to a valid item in repository
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions,
        and delete items they are neither the contributor nor maintainer of, by default False

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
    if users.is_user(system_username=this_user):
        UUID = users.get_uuid(system_username=this_user)
    else:
        raise cf.KIMkitUserNotFoundError(
            "Only KIMkit users can delete items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
        )

    del_path = kimcodes.kimcode_to_file_path(kimcode, repository)

    if not os.path.exists(del_path):
        raise cf.KIMkitItemNotFoundError(
            f"No item {kimcode} found in repository {repository}"
        )

    __, leader, __, __ = kimcodes.parse_kim_code(kimcode)

    if leader == "MO":
        item = PortableModel(kimcode=kimcode, repository=repository)

    elif leader == "SM":
        item = SimulatorModel(kimcode=kimcode, repository=repository)

    elif leader == "MD":
        item = ModelDriver(kimcode=kimcode, repository=repository)

    spec = item.kimspec

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

        logger.info(
            f"User {this_user} deleted item {kimcode} from repository {repository}"
        )

        shutil.rmtree(del_path)

        # if all versions of the item have been deleted, delete its enclosing directory
        outer_dir = os.path.split(del_path)[0]  # one level up in the directory
        with os.scandir(outer_dir) as it:
            if not any(it):  # empty directory
                shutil.rmtree(outer_dir)
                kimcode_without_version = kimcodes.strip_version(kimcode)

                logger.info(
                    f"All versions of {kimcode_without_version} deleted, deleting the item."
                )
    else:
        logger.warning(
            f"User {this_user} attempted to deleted item {kimcode} from repository {repository}, but is neither the contributor of the item nor an editor"
        )
        raise cf.NotAnEditorError(
            "Only KIMkit Editors or the Administrator may delete items belonging to other users."
        )


def version_update(
    repository,
    kimcode,
    tarfile_obj,
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
    repository : path-like
        root directory of the KIMkit repository containing the item
    kimcode : str
        ID code of the item to be updated
    tarfile_obj : tarfile.Tarfile
        tarfile object containing the new version's content
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
    ValueError
        A more recent version of the item exists, so the older one should not be updated
    NotRunAsEditorError
        A user with Editor permissions attempted to update the item, but did not specify run_as_editor=True
    ValueError
        The metadata_update_dict does not comply with the KIMkit standard
    NotAnEditorError
        A user without Editor permissions attempted to update an item they are not the contributor or maintainer of.
    """

    this_user = users.whoami()
    if users.is_user(system_username=this_user):
        UUID = users.get_uuid(system_username=this_user)
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
    versions = os.listdir(outer_dir)
    most_recent_version = max(versions)

    most_recent_dir = os.path.join(outer_dir, most_recent_version)

    if not os.path.samefile(current_dir, most_recent_dir):
        raise ValueError(
            f"{kimcode} is not the most recent version of this item. Most recent version {most_recent_version} should be used as a base for updating."
        )

    event_type = "revised-version-creation"
    name, leader, num, old_version = kimcodes.parse_kim_code(kimcode)
    if leader == "MO":
        this_item = PortableModel(kimcode=kimcode, repository=repository)
        kim_item_type = "portable-model"
    elif leader == "SM":
        this_item = SimulatorModel(kimcode=kimcode, repository=repository)
        kim_item_type = "simulator-model"
    elif leader == "MD":
        this_item = ModelDriver(kimcode=kimcode, repository=repository)
        kim_item_type = "model-driver"

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

        logger.info(
            f"User {UUID} has requested a version update of item {kimcode} in repository {repository}"
        )
        new_version = str(int(old_version) + 1)
        new_kimcode = kimcodes.format_kim_code(name, leader, num, new_version)
        tmp_dir = os.path.join(repository, new_kimcode)
        tarfile_obj.extractall(path=tmp_dir)
        contents = os.listdir(tmp_dir)
        # if the contents of the item are enclosed in a directory, copy them out
        # then delete the directory
        if len(contents) == 1:
            inner_dir = os.path.join(tmp_dir, contents[0])
            if os.path.isdir(inner_dir):
                inner_contents = os.listdir(inner_dir)
                for item in inner_contents:
                    shutil.copy(os.path.join(inner_dir, item), tmp_dir)
                shutil.rmtree(inner_dir)

        executables = []
        for file in os.listdir(tmp_dir):
            if os.path.isfile(file):
                executable = os.access(file, os.X_OK)
                if executable:
                    executables.append(os.path.split(file)[-1])
        if executables:
            if metadata_update_dict:
                metadata_update_dict["executables"] = executables
        dest_dir = kimcodes.kimcode_to_file_path(new_kimcode, repository)
        shutil.copytree(tmp_dir, dest_dir)
        try:
            metadata.create_new_metadata_from_existing(
                repository,
                kimcode,
                new_kimcode,
                UUID,
                metadata_update_dict=metadata_update_dict,
            )
        except (KeyError, ValueError, TypeError) as e:
            shutil.rmtree(dest_dir)
            shutil.rmtree(tmp_dir)
            raise ValueError(
                f"Metadata associated with item {new_kimcode} is invalid."
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

    else:

        logger.warning(
            f"User {this_user} requested a verion update of item {kimcode} in repository {repository}, but is neither the owner of the item nor an Editor."
        )
        raise cf.NotAnEditorError(
            "Only KIMkit Editors or the Administrator may create updated versions of items belonging to other users."
        )


def fork(
    repository,
    kimcode,
    new_kimcode,
    tarfile_obj,
    metadata_update_dict=None,
    provenance_comments=None,
):
    """Create a new item, based off a fork of an existing one,
    with new content and possibly new metadata

    Expects the content of the new version of the item to be passed in as a tarfile.Tarfile object.

    Parameters
    ----------
    repository : path-like
        root directory of the KIMkit repository containing the item
    kimcode : str
        ID code of the item to be forked
    new_kimcode : str
        id code the new item will be assigned
    tarfile_obj : tarfile.Tarfile
        tarfile object containing the new version's content
    metadata_update_dict : dict, optional
        dict of any metadata keys to be changed in the new version, by default None
    provenance_comments : str, optional
        any comments about how/why this version was created, by default None

    Raises
    ------
    KIMkitUserNotFoundError
        A non KIMkit user attempted to update an item.
    KIMkitItemNotFoundError
        No item with kimcode exists in repository
    KimCodeAlreadyInUseError
        New kimcode is already assigned to an item in this repository
    ValueError
        The metadata_update_dict does not comply with the KIMkit standard
    """

    this_user = users.whoami()
    if users.is_user(system_username=this_user):
        UUID = users.get_uuid(system_username=this_user)
    else:
        raise cf.KIMkitUserNotFoundError(
            "Only KIMkit users can fork items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
        )

    current_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    if not os.path.exists(current_dir):
        raise cf.KIMkitItemNotFoundError(
            f"No item with kimcode {kimcode} exists, aborting."
        )

    if not kimcodes.is_kimcode_available(repository, new_kimcode):
        raise cf.KimCodeAlreadyInUseError(
            f"kimcode {new_kimcode} is already in use, please select another."
        )

    logger.info(
        f"User {UUID} has forked item {new_kimcode} based on {kimcode} in repository {repository}"
    )
    event_type = "fork"
    name, leader, __, __ = kimcodes.parse_kim_code(kimcode)
    if leader == "MO":
        kim_item_type = "portable-model"
    elif leader == "SM":
        kim_item_type = "simulator-model"
    elif leader == "MD":
        kim_item_type = "model-driver"

    tmp_dir = os.path.join(repository, new_kimcode)
    tarfile_obj.extractall(path=tmp_dir)
    contents = os.listdir(tmp_dir)
    # if the contents of the item are enclosed in a directory, copy them out
    # then delete the directory
    if len(contents) == 1:
        inner_dir = os.path.join(tmp_dir, contents[0])
        if os.path.isdir(inner_dir):
            inner_contents = os.listdir(inner_dir)
            for item in inner_contents:
                shutil.copy(os.path.join(inner_dir, item), tmp_dir)
            shutil.rmtree(inner_dir)

    executables = []
    for file in os.listdir(tmp_dir):
        if os.path.isfile(file):
            executable = os.access(file, os.X_OK)
            if executable:
                executables.append(os.path.split(file)[-1])
    if executables:
        if metadata_update_dict:
            metadata_update_dict["executables"] = executables
    dest_dir = kimcodes.kimcode_to_file_path(new_kimcode, repository)
    shutil.copytree(tmp_dir, dest_dir)
    try:
        metadata.create_new_metadata_from_existing(
            repository,
            kimcode,
            new_kimcode,
            UUID,
            metadata_update_dict=metadata_update_dict,
        )
    except (KeyError, ValueError, TypeError) as e:
        shutil.rmtree(dest_dir)
        shutil.rmtree(tmp_dir)
        raise ValueError(
            f"Metadata associated with item {new_kimcode} is invalid."
        ) from e
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


def export(repository, kimcode):
    """Export an item as a tarfile.TarFile object, with any dependancies (e.g. model-drivers) needed for it to run

    Parameters
    ----------
    repository : path-like
        root directory of the KIMkit repository containing the item
    kimcode: str
        id code of the item

    Returns
    -------
    list of tarfile.TarFile objects
        list of object(s) containing all of the item's content,
        and any dependancies (e.g. model-drivers) needed for it to run

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
        req_driver = this_item.driver
        with tarfile.open(os.path.join(src_dir, req_driver + ".txz"), "w:xz") as tar:
            tar.add(src_dir, arcname=req_driver)
    with tarfile.open(os.path.join(src_dir, kimcode + ".txz"), "w:xz") as tar:
        tar.add(src_dir, arcname=kimcode)
    contents = os.listdir(src_dir)
    tarfile_objs = []
    for item in contents:
        if ".txz" in item:
            tarfile_obj = tarfile.open(os.path.join(src_dir, item))
            tarfile_objs.append(tarfile_obj)
            os.remove(os.path.join(src_dir, item))
    return tarfile_objs


def install(repository, kimcode, install_dir):
    """Export the item, and also install it into a collection managed by the kim-api-collections-manager

    Requires the install location to be accessible on the same filesystem as the KIMkit repository,
    and for the kim-api to be installed there.

    Parameters
    ----------
    repository : path-like
        root directory of the KIMkit repository containing the item
    kimcode: str
        id code of the item
    install_dir : path-like
        location on disk to install the item to
    """

    tarfile_objs = export(kimcode, repository)

    # extract the item from its tar archive, along with any dependencies (e.g. drivers)
    for tar in tarfile_objs:
        tar.extractall(path=install_dir)
        tar.close()

    # go into the extracted archives, create relevant objects in memory, and call their make methods
    for file in os.listdir(install_dir):
        d = os.path.join(install_dir, file)
        if os.path.isdir(d):
            obj_kimcode = os.path.basename(d)
            __, leader, __, __ = kimcodes.parse_kim_code(obj_kimcode)
            if leader == "MO":
                obj = PortableModel(
                    repository=None,
                    kimcode=obj_kimcode,
                    abspath=os.path.join(install_dir, kimcode),
                )
            elif leader == "SM":
                obj = SimulatorModel(
                    repository=None,
                    kimcode=obj_kimcode,
                    abspath=os.path.join(install_dir, kimcode),
                )
            elif leader == "MD":
                obj = ModelDriver(
                    repository=None,
                    kimcode=obj_kimcode,
                    abspath=os.path.join(install_dir, kimcode),
                )

            logger.debug(
                f"Item {kimcode} from repository {repository} installed into kim-api-collection in directory {install_dir}"
            )

            obj.make()
