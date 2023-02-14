import uuid
import kim_edn
import os
import getpass

import config as cf
from logger import logging

""" This module contains utility functions used to manager users and permissions in KIMkit.

KIMkit defines 3 levels of user access: Administrator, Editor, and User.

There is only one Administrator per installation of KIMkit. Inside the KIMkit package directory there should be
a file called 'editors.txt' which all users have read access to, but only the Administrator has write access to.
Indeed, KIMkit determines whether a given user is the Administrator by checking whether the operating system grants
them write access to editors.txt. Therefore only the Administrator can elevate Users to Editors,
or perfom certian other potenitally destructive actions (e.g. removing a required metadata field from all items).

editors.txt should contain a sequence of operating-system usernames as returned by getpass.getuser().
If the current user is in editors.txt, KIMkit recoggnizes them as an Editor, and allows them certian
elevated permissions (e.g. editing content submitted by other users). Any user that is neither the Administrator nor
listed as an Editor is a regular User by default. The Administrator should be listed as an Editor for most use cases.
"""

logger = logging.getLogger("KIMkit")


def whoami():
    identity = getpass.getuser()
    return identity


def is_administrator():
    """Check whether this user has write permissions from the operating system for the editors file,
    if so, this user is the administrator.

    Returns
    -------
    is_admin : bool
        whether this user is the administrator or not
    """

    try:
        # attempt to write an empty string to check if user has write permissions to the editors file
        with open(os.path.join(cf.KIMKIT_DATA_DIRECTORY, "editors.txt"), "a") as test:
            test.write("")
        is_admin = True
    except PermissionError:
        is_admin = False

    return is_admin


def is_editor():
    """Read the editors.txt file to check if the current user is present,
    if so, the current user is an editor, and is_editor() returns True.

    Returns
    -------
    editor : bool
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


def add_editor(editor_name):
    """A function for the Administrator to add users to the set of approved KIMkit Editors

    Parameters
    ----------
    username : str
        username to be added to the set of approved Editors
    """

    if is_administrator():
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
        raise PermissionError(
            "You are not the Administrator, and do not have access rights to add Editors."
        )


def add_user(name):
    """Assign a UUID to a new user and add them to the list of approved users

    Parameters
    ----------
    name : str
        name of the user
    """

    system_username = whoami()

    new_uuid = uuid.uuid4()
    new_uuid_key = str(new_uuid)

    logger.info(
        f"New user {name} assigned UUID {new_uuid} and added to list of approved KIMkit users"
    )

    with open("user_uuids.edn", "r") as file:
        user_data_dict = kim_edn.load(file)

    user_data_dict[new_uuid_key] = {
        "personal-name": name,
        "system-username": system_username,
    }

    with open("user_data_tmp.edn", "w") as outfile:
        kim_edn.dump(user_data_dict, outfile, indent=4)

    os.rename("user_data_tmp.edn", "user_uuids.edn")


def add_person(name):
    """Assign a UUID to a person without a user account on the system running KIMkit for attribution,
    and add them to the list of approved users

    Parameters
    ----------
    name : str
        name of the user
    """

    new_uuid = uuid.uuid4()
    new_uuid_key = str(new_uuid)

    logger.info(
        f"New user {name} assigned UUID {new_uuid} and added to list of approved KIMkit users"
    )

    with open("user_uuids.edn", "r") as file:
        user_data_dict = kim_edn.load(file)

    user_data_dict[new_uuid_key] = {"personal-name": name}

    with open("user_data_tmp.edn", "w") as outfile:
        kim_edn.dump(user_data_dict, outfile, indent=4)

    os.rename("user_data_tmp.edn", "user_uuids.edn")


def delete_user(user_id):
    """Remove a user from the list of approved users

    Parameters
    ----------
    user_id : str or UUID
        UUID of the user to be deleted
    name : str
        name of the user to be deleted,
        must correspond to the UUID

    Raises
    ------
    ValueError
        if the name supplied does not correspond to the uuid
    KeyError
        if the uuid is not in the list of recognized uuids
    """
    if not is_valid_uuid4(user_id):
        raise ValueError("user id is not a valid UUID4")

    if is_editor():

        with open("user_uuids.edn", "r") as file:
            user_data_dict = kim_edn.load(file)

        if is_user(user_id):
            del user_data_dict[user_id]

        else:
            raise KeyError(f"UUID {user_id} not found in user data.")

        logger.info(f"User {user_id}) deleted from KIMkit approved users")

        with open("user_data_tmp.edn", "w") as outfile:
            kim_edn.dump(user_data_dict, outfile, indent=4)

        os.rename("user_data_tmp.edn", "user_uuids.edn")


def get_name_of_user(user_id):
    """get the name of a user from their uuid

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
    ValueError
        if the user_id is not a valid UUID4
    KeyError
        if the uuid is not in the user file
    """
    if not is_valid_uuid4(user_id):
        raise ValueError("user id is not a valid UUID4")

    if is_user(user_id):
        with open("user_uuids.edn", "r") as file:
            user_data_dict = kim_edn.load(file)
            name = user_data_dict[user_id]["personal-name"]
            return name

    else:
        raise KeyError(f"uuid {user_id} not in authorized users")


def get_system_username_of_user(user_id):
    """get the name of a user from their uuid

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
    ValueError
        if the user_id is not a valid UUID4
    KeyError
        if the uuid is not in the user file
    """
    if not is_valid_uuid4(user_id):
        raise ValueError("user id is not a valid UUID4")

    if is_user(user_id):
        with open("user_uuids.edn", "r") as file:
            user_data_dict = kim_edn.load(file)
            name = user_data_dict[user_id]["system-username"]
            return name

    else:
        raise KeyError(f"uuid {user_id} not in authorized users")


def is_valid_uuid4(user_id):

    # Verify this is a valid uuid4
    try:
        assert user_id.replace("-", "") == uuid.UUID(user_id, version=4).hex
        return True
    except AssertionError as e:
        return False


def is_user(user_id):
    """return True if the user_id is in the list of approved users
    stored in the user data file.

    Parameters
    ----------
    user_id : str
        uuid of the user to be verified

    Returns
    ----------
    True if the uuid is in the list of verified users
    """

    if is_valid_uuid4(user_id):

        with open("user_uuids.edn", "r") as file:
            user_data_dict = kim_edn.load(file)
        if user_id in user_data_dict:
            return True
        else:
            return False
    else:
        raise TypeError(f"user id {user_id} is not a valid UUID4")
