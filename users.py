import uuid
import kim_edn
import os
import getpass

from . import config as cf
from .logger import logging

""" This module contains utility functions used to manager users and permissions in KIMkit.

KIMkit defines 3 levels of user access: Administrator, Editor, and User.

There is only one Administrator per installation of KIMkit. Inside the KIMkit package root directory there should be
a file called 'editors.txt' which all users have read access to, but only the Administrator has write access to.
Indeed, KIMkit determines whether a given user is the Administrator by checking whether the operating system grants
them write access to editors.txt. Therefore only the Administrator can elevate Users to Editors,
or perfom certian other potenitally destructive actions (e.g. removing a required metadata field from all items).

editors.txt should contain a sequence of operating-system usernames as returned by getpass.getuser().
If the current user is in editors.txt, KIMkit recoggnizes them as an Editor, and allows them certian
elevated permissions (e.g. editing content submitted by other users, adding keys to the metadata standard).
Any user that is neither the Administrator nor listed as an Editor is a regular User by default.

The Administrator should be listed as an Editor for most use cases.

Seperately from editors.txt, there should also be a file named user_uuids.edn, also in the KIMkit root directory,
which stores information about all KIMkit users. This file contains an .edn dict where the keys are
UUID4s assigned to each user, and the values are an array that contain strings, with the user's personal name,
and optionally their operating system username (if any).
"""

logger = logging.getLogger("KIMkit")


def whoami():
    """
    Returns
    -------
    str
        operating system username of the current user
    """
    identity = getpass.getuser()
    return identity


def is_administrator():
    """Check whether this user has write permissions from the operating system for the editors file,
    if so, this user is the administrator.

    Returns
    -------
    bool
        whether this user is the administrator or not
    """

    try:
        # attempt to append an empty string to editors.txt to check if user has write permissions to the editors file
        with open(os.path.join(cf.KIMKIT_DATA_DIRECTORY, "editors.txt"), "a") as test:
            test.write("")
        is_admin = True
    except PermissionError:
        is_admin = False

    return is_admin


def is_editor():
    """Read the editors.txt file to check if the current user's
    operating system username is present, if so, the current user is an editor,
    and is_editor() returns True.

    Returns
    -------
    bool
        whether this user is an editor
    """

    identity = whoami()

    with open(
        os.path.join(cf.KIMKIT_DATA_DIRECTORY, "editors.txt"), "r"
    ) as editor_file:
        if identity in editor_file.read():
            editor = True
        else:
            editor = False
    return editor


def add_editor(editor_name, run_as_administrator=False):
    """A function for the Administrator to add users to the set of approved KIMkit Editors

    Requires Administrator Priveleges.

    Parameters
    ----------
    editor_name : str
        operating system username of the editor to be added
    run_as_administrator : bool, optional
        A flag to be used by the KIMkit Administrator to run with elevated permissions, by default False

    Raises
    ------
    NotRunAsAdministratorError
        This user is the Administrator, but did not specify run_as_administrator=True
    NotAdministratorError
        A user who is not the administrator attempted to add an editor.
    """

    can_edit = False

    if is_administrator():
        if run_as_administrator:
            can_edit = True
        else:
            raise cf.NotRunAsAdministratorError(
                "Did you mean to add an editor? If you are The Administrator run again with run_as_administrator=True"
            )

    if can_edit:
        with open(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "editors.txt"), "a"
        ) as editor_file:
            editor_file.write(editor_name + "\n")
        logger.info(f"The Administrator added {editor_name} as a KIMkit editor.")
    else:
        username = whoami()
        logger.warning(
            f"User {username} attempted to add {editor_name} as an Editor with insufficient privileges."
        )
        raise cf.NotAdministratorError(
            "You are not the Administrator, and do not have access rights to add Editors."
        )


def add_self_as_user(name):
    """Function to be used when a new user uses KIMkit for the first time,
    to assign themselves a UUID4 and adds them to the list of approved KIMkit users.

    Checks if this user has already been added to the user file.

    Parameters
    ----------
    name : str
        personal name of the user adding themselves

    Raises
    ------
    RuntimeError
        This user already has a UUID4 associated with their personal name,
        or operating system username.
    """

    system_username = whoami()

    new_uuid = uuid.uuid4()
    new_uuid_key = new_uuid.hex

    logger.info(
        f"New user {name} (system username {system_username}) assigned UUID {new_uuid} and added to list of approved KIMkit users"
    )

    try:
        with open(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"), "r"
        ) as file:
            user_data_dict = kim_edn.load(file)

        existing_uuid = get_uuid(system_username=system_username, personal_name=name)

        if existing_uuid != None:
            raise RuntimeError(
                f"User {name} already has a KIMkit UUID: {existing_uuid}, aborting."
            )

    except FileNotFoundError:
        user_data_dict = {}

    user_data_dict[new_uuid_key] = {
        "personal-name": name,
        "system-username": system_username,
    }

    with open("user_data_tmp.edn", "w") as outfile:
        kim_edn.dump(user_data_dict, outfile, indent=4)

    os.rename("user_data_tmp.edn", "user_uuids.edn")


def add_person(name):
    """Assign a UUID to a person without a user account on the system running KIMkit for attribution,
    and add them to the list of approved users.

    This function is intended to allow individuals who contributed to content in KIMkit,
    but who do not have user accounts on the system running KIMkit, to be credited for their contributions
    by assigning them a UUID4 and associating it to ther personal name.

    Parameters
    ----------
    name : str
        personal name of the individual to be added

    Raises
    ------
    RuntimeError
        This individual already has a UUID4 associated with their personal name.
    """

    new_uuid = uuid.uuid4()
    new_uuid_key = new_uuid.hex

    logger.info(
        f"New user {name} assigned UUID {new_uuid} and added to list of approved KIMkit users"
    )

    try:
        with open(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"), "r"
        ) as file:
            user_data_dict = kim_edn.load(file)

        existing_uuid = get_uuid(personal_name=name)

        if existing_uuid != None:
            raise RuntimeError(
                f"User {name} already has a KIMkit UUID: {existing_uuid}, aborting."
            )
    except FileNotFoundError:
        user_data_dict = {}

    user_data_dict[new_uuid_key] = {"personal-name": name}

    with open(
        os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_data_tmp.edn"), "w"
    ) as outfile:
        kim_edn.dump(user_data_dict, outfile, indent=4)

    os.rename(
        os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_data_tmp.edn"),
        os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"),
    )


def delete_user(user_id, run_as_editor=False):
    """Remove a user from the list of approved users.

    Requires editor privleges.

    Parameters
    ----------
    user_id : str or UUID
        UUID of the user to be deleted
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions and delete users, by default False

    Raises
    ------
    TypeError
        Invalid UUID4
    NotRunAsEditorError
        This user is a KIMkit Editor, but did not specify run_as_editor=True
    KIMkitUserNotFoundError
        Specified user_id not found in the user data file
    NotAnEditorError
        A user who is not a KIMkit editor attempted to delete a user
    """
    if not is_valid_uuid4(user_id):
        raise TypeError("user id is not a valid UUID4")

    can_edit = False

    if is_editor():
        if run_as_editor:
            can_edit = True
        else:
            raise cf.NotRunAsEditorError(
                "Did you mean to delete this user? If you are an Editor run again with run_as_editor=True"
            )

    if can_edit:

        with open(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"), "r"
        ) as file:
            user_data_dict = kim_edn.load(file)

        if is_user(user_id=user_id):
            del user_data_dict[user_id]

        else:
            raise cf.KIMkitUserNotFoundError(f"UUID {user_id} not found in user data.")

        logger.info(f"User {user_id}) deleted from KIMkit approved users")

        with open(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_data_tmp.edn"), "w"
        ) as outfile:
            kim_edn.dump(user_data_dict, outfile, indent=4)

        os.rename(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_data_tmp.edn"),
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"),
        )

    else:
        username = whoami()
        logger.warning(
            f"User {username} attempted to delete user {user_id} without editor priveleges"
        )
        raise cf.NotAnEditorError(
            "Editor permissions are required to delete users from KIMkit."
        )


def get_name_of_user(user_id):
    """get the personal name of a user from their uuid

    Parameters
    ----------
    user_id : str
        uuid of the user

    Returns
    -------
    name: str
        name of the user corresponding to the uuid

    Raises
    ------
    TypeError
        Invalid UUID4
    KIMkitUserNotFoundError
        Specified user_id not found in the user data file
    """
    if not is_valid_uuid4(user_id):
        raise TypeError("user id is not a valid UUID4")

    if is_user(user_id=user_id):
        with open(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"), "r"
        ) as file:
            user_data_dict = kim_edn.load(file)
            name = user_data_dict[user_id]["personal-name"]
            return name

    else:
        raise cf.KIMkitUserNotFoundError(f"uuid {user_id} not in authorized users")


def get_system_username_of_user(user_id):
    """get the operating system username of a user from their uuid

    Parameters
    ----------
    user_id : str
        uuid of the user

    Returns
    -------
    name: str
        operating system username of the user corresponding to the uuid

    Raises
    ------
    TypeError
        Invalid UUID4
    KIMkitUserNotFoundError
        Specified user_id not found in the user data file
    """
    if not is_valid_uuid4(user_id):
        raise TypeError("user id is not a valid UUID4")

    if is_user(user_id=user_id):
        with open(
            os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"), "r"
        ) as file:
            user_data_dict = kim_edn.load(file)
            name = user_data_dict[user_id]["system-username"]
            return name

    else:
        raise cf.KIMkitUserNotFoundError(f"uuid {user_id} not in authorized users")


def get_uuid(system_username=None, personal_name=None):
    """Given a personal name or system username, return the associated UUID (if any)

    Parameters
    ----------
    system_username : str, optional
        unix username of the user account, by default None
    personal_name : str, optional
        personal name of a user, by default None

    Returns
    -------
    UUID : str
        unique id assigned to the user in UUID4 format
    """

    with open(os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"), "r") as file:
        user_data_dict = kim_edn.load(file)
        user_data = user_data_dict.items()
        found_user = False
        for item in user_data:
            UUID = item[0]
            names = item[1]

            if system_username:
                if names["system-username"] == system_username:
                    found_user = True
                    break

            if personal_name:
                if names["personal-name"] == personal_name:
                    found_user = True
                    break
        if found_user:
            return UUID
        else:
            return None


def is_valid_uuid4(val):
    """Check whether a given string can be converted
    to a valid UUID4

    Parameters
    ----------
    val : str
        UUID string to be checked

    Returns
    -------
    bool
        whether the val is a valid UUID4
    """
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def is_user(system_username=None, personal_name=None, user_id=None):
    """Return True if the user currently logged in is in the list of approved users
    stored in the user data file.

    Generally, only one of system_username, personal_name, or user_id should be specified.

    Parameters
    ----------
    system_username : str, optional
        operating system username to be searched for, by default None
    personal_name : str, optional
        personal name to be searched for, by default None
    user_id : str, optional
        UUID4 to be searched for, by default None

    Returns
    -------
    bool
        whether the input refers to a recognized KIMkit user

    Raises
    ------
    TypeError
        user_id is not a valid UUID4
    """
    found_user = False
    with open(os.path.join(cf.KIMKIT_DATA_DIRECTORY, "user_uuids.edn"), "r") as file:
        user_data_dict = kim_edn.load(file)

        if user_id:
            if is_valid_uuid4(user_id):
                if user_id in user_data_dict:
                    found_user = True
            else:
                raise TypeError(f"User ID {user_id} is not a valid UUID4.")
        user_data = user_data_dict.items()
        for item in user_data:
            UUID = item[0]
            names = item[1]
            if system_username:
                if names["system-username"] == system_username:
                    found_user = True
                    break
            if personal_name:
                if names["personal-name"] == personal_name:
                    found_user = True
                    break
    return found_user
