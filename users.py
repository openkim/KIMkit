import uuid
import kim_edn
import os

from logger import logging

logger = logging.getLogger("KIMkit")


def add_user(name):
    """Assign a UUID to a new user and add them to the list of approved users

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

    with open("user_data.edn", "r") as file:
        user_data_dict = kim_edn.load(file)

    user_data_dict[new_uuid_key] = name

    with open("user_data_tmp.edn", "w") as outfile:
        kim_edn.dump(user_data_dict, outfile, indent=4)

    os.rename("user_data_tmp.edn", "user_data.edn")


def delete_user(user_id, name):
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

    with open("user_data.edn", "r") as file:
        user_data_dict = kim_edn.load(file)

    if is_user(user_id):
        if user_data_dict[user_id] == name:
            del user_data_dict[user_id]

        else:
            raise ValueError(
                f"Supplied name {name} does not match name corresponding to {user_id}"
            )
    else:
        raise KeyError(f"UUID {user_id} not found in user data.")

    logger.info(f"User {name} (UUID {user_id}) deleted from KIMkit approved users")

    with open("user_data_tmp.edn", "w") as outfile:
        kim_edn.dump(user_data_dict, outfile, indent=4)

    os.rename("user_data_tmp.edn", "user_data.edn")


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
        with open("user_data.edn", "r") as file:
            user_data_dict = kim_edn.load(file)
            name = user_data_dict[user_id]
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

        with open("user_data.edn", "r") as file:
            user_data_dict = kim_edn.load(file)
        if user_id in user_data_dict:
            return True
        else:
            return False
    else:
        raise TypeError(f"user id {user_id} is not a valid UUID4")
