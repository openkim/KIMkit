""" This module contains utility functions used to manager users and permissions in **KIMkit**.

**KIMkit** defines 3 levels of user access: Administrator, Editor, and User.

There is only one Administrator per installation of **KIMkit**. Inside the KIMkit/settings/ directory the
system administrator should create a file called 'editors.txt' which all users have read access to,
but only the Administrator has write access to.
Indeed, **KIMkit** determines whether a given user is the Administrator by checking whether the operating system grants
them write access to editors.txt. Therefore only the Administrator can elevate Users to Editors,
or perfom certian other potenitally destructive actions.

editors.txt should contain a sequence of operating-system usernames as returned by ``getpass.getuser()``.
If the current user is in editors.txt, **KIMkit** recoggnizes them as an Editor, and allows them certian
elevated permissions (e.g. editing content submitted by other users, adding keys to the metadata standard).
Any user that is neither the Administrator nor listed as an Editor is a regular User by default.

The Administrator should be listed as an Editor for most use cases.

Seperately from editors.txt, there is also a "users" collection in the KIMkit mongodb database,
which stores information about all **KIMkit** users. This collection stores UUID4s assigned to each user,
the user's personal name, and optionally their operating system username (if any).

These UUID4s define the identities of **KIMkit** users, and
whenever a user tries to modify content on disk, **KIMkit** will check if their operating system username is assigned
to a UUID4 in the database, and if not the operation will fail with an exception that prompts the user to add themselves
to the user list and be assigned a UUID4 by calling ``add_self_as_user()`` on their personal name. This is needed to track
contributors, developers, maintainers, etc. which are stored as UUID4s in the metadata file kimspec.edn associated with
each **KIMkit** item. If someone without a login on the system running **KIMkit** has contributed to an item, a user may
assign them a UUID4 by calling ``add_person()`` on their personal name so that their contributions can be tracked and credited.
"""

import uuid
import kim_edn
import os
import getpass

from .src import config as cf
from .src import logger
from .src import mongodb
from .src.logger import logging
from . import kimcodes

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
        with open(cf.KIMKIT_EDITORS_FILE, "a") as test:
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

    with open(cf.KIMKIT_EDITORS_FILE, "r") as editor_file:
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
        with open(cf.KIMKIT_EDITORS_FILE, "a") as editor_file:
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

    if is_user(personal_name=name):
        user_data = get_user_info(personal_name=name)
        print(user_data)
        existing_uuid = user_data["uuid"]
        raise RuntimeError(
            f"User {name} already has a KIMkit UUID: {existing_uuid}, aborting."
        )

    mongodb.insert_user(new_uuid_key, name, username=system_username)

    logger.info(
        f"New user {name} (system username {system_username}) assigned UUID {new_uuid_key} and added to list of approved KIMkit users"
    )


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

    if is_user(personal_name=name):
        user_data = mongodb.find_user(personal_name=name)
        existing_uuid = user_data["uuid"]
        raise RuntimeError(
            f"User {name} already has a KIMkit UUID: {existing_uuid}, aborting."
        )

    mongodb.insert_user(new_uuid_key, name)

    logger.info(
        f"New user {name} assigned UUID {new_uuid_key} and added to list of approved KIMkit users"
    )


def add_own_username(uuid):
    """Intened for users who have been added to the
    KIMkit users database before they had an account
    on the system KIMkit is running on. Such users may
    call this function to have their username added
    to their entry in the users collection the before the
    first time they run a KIMkit command that requires a UUID.

    Parameters
    ----------
    uuid : uuid4 as str
        id code of the user
    """

    if not is_user(uuid=uuid):
        raise RuntimeError("UUID4 not recognized as a KIMkit user.")

    username = whoami()

    user_info = get_user_info(uuid=uuid)

    name = user_info["personal-name"]

    mongodb.update_user(uuid, name, username=username)


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
    if not kimcodes.is_valid_uuid4(user_id):
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
        if is_user(uuid=user_id):
            mongodb.delete_one_database_entry(user_id)

        else:
            raise cf.KIMkitUserNotFoundError(f"UUID {user_id} not found in user data.")

        logger.info(f"User {user_id} deleted from KIMkit approved users")

    else:
        username = whoami()
        logger.warning(
            f"User {username} attempted to delete user {user_id} without editor priveleges"
        )
        raise cf.NotAnEditorError(
            "Editor permissions are required to delete users from KIMkit."
        )


def get_user_info(uuid=None, username=None, personal_name=None):
    if uuid:
        if not kimcodes.is_valid_uuid4(uuid):
            raise (cf.InvalidKIMCode("Invalid UUID"))

    data = mongodb.find_user(uuid=uuid, username=username, personal_name=personal_name)

    return data


def is_user(uuid=None, username=None, personal_name=None):
    """Return True if the user currently logged in is in the list of approved users
    stored in the user data file.

    It is possible to search for users matching any of a specified uuid4,
    personal name, or operating system username.

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
    if uuid:
        if not kimcodes.is_valid_uuid4(uuid):
            raise (cf.InvalidKIMCode("Invalid UUID"))

    data = mongodb.find_user(uuid=uuid, username=username, personal_name=personal_name)
    if data:
        found_user = True
    return found_user
