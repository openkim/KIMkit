"""
This module is intended to handle anything related to KIM IDs, uuids, or jobids.

Copyright 2014-2021 Alex Alemi, Matt Bierbaum, Woosong Choi, Daniel S. Karls, James P. Sethna

Please do not distribute this code.
"""
import re
import os
import random

import config as cf
from logger import logging

logger = logging.getLogger("pipeline").getChild("kimcodes")

RE_KIMID = r"^(?:([_a-zA-Z][_a-zA-Z0-9]*?)__)?([A-Z]{2})_([0-9]{12})(?:_([0-9]{3}))?$"
RE_EXTENDEDKIMID = (
    r"^(?:([_a-zA-Z][_a-zA-Z0-9]*?)__)?([A-Z]{2})_([0-9]{12})(?:_([0-9]{3}))$"
)
RE_JOBID = (
    r"^([A-Z]{2}_[0-9]{12}_[0-9]{3})-and-([A-Z]{2}_[0-9]{12}_[0-9]{3})-([0-9]{5,})$"
)
RE_UUID = r"^([A-Z]{2}_[0-9]{12}_[0-9]{3})-and-([A-Z]{2}_[0-9]{12}_[0-9]{3})-([0-9]{5,})-([tve]r)$"
RE_TESTRESULT = r"^([A-Z]{2}_[0-9]{12}_[0-9]{3})-and-([A-Z]{2}_[0-9]{12}_[0-9]{3})-([0-9]{5,})-(tr)$"
RE_VERIFICATIONRESULT = r"^([A-Z]{2}_[0-9]{12}_[0-9]{3})-and-([A-Z]{2}_[0-9]{12}_[0-9]{3})-([0-9]{5,})-(vr)$"
RE_ERROR = r"^([A-Z]{2}_[0-9]{12}_[0-9]{3})-and-([A-Z]{2}_[0-9]{12}_[0-9]{3})-([0-9]{5,})-(er)$"


def parse_kim_code(kim_code):
    """Parse a kim code into it's pieces,
    returns a tuple (name,leader,num,version)"""
    rekimid = re.match(RE_KIMID, kim_code)
    rejobid = re.match(RE_JOBID, kim_code)
    reuuid = re.match(RE_UUID, kim_code)

    if rekimid:
        return rekimid.groups()
    elif rejobid:
        return rejobid.groups()
    elif reuuid:
        return reuuid.groups()
    else:
        raise cf.InvalidKIMCode(
            "{} is not a valid KIM ID, job id, or uuid".format(kim_code)
        )


def get_leader(kimid):
    """NOTE: This function is only to be used with KIM IDs, not UUIDs."""
    rekimid = re.match(RE_KIMID, kimid)

    if rekimid:
        return rekimid.groups()[1]
    else:
        raise cf.InvalidKIMCode("{} is not a valid KIM ID".format(kimid))


def get_short_id(kim_code):
    rekimid = re.match(RE_EXTENDEDKIMID, kim_code)

    if rekimid:
        _, leader, num, ver = rekimid.groups()
        return ("_").join((leader, num, ver))
    else:
        raise ValueError(
            "Supplied KIM ID does not contain the information "
            "necessary to form a short ID"
        )


def format_kim_code(name, leader, num, version):
    """Format a KIM id into its proper form, assuming the form

    {name}__{leader}_{number}_{version}
    """
    # Cast num and version to strings in case they are passed in as ints
    name = str(name)
    version = str(version)

    assert leader, "A leader is required to format a kimcode"
    assert num, "A number is required to format a kimcode"
    assert version, "A version is required to format a kimcode"

    if name:
        if version:
            version = stringify_version(version)
            return "{}__{}_{}_{}".format(name, leader, num, version)
        else:
            return "{}__{}_{}".format(name, leader, num)
    else:
        version = stringify_version(version)
        return "{}_{}_{}".format(leader, num, version)


def generate_kimcode(name, item_type, repository):
    """Generate a kimcode for a new KIMkit item

    kimcodes have format:
    [human-readable-prefix] [2 letter leader code] [12 digit id number] [3 digit version]

    The prefix can only contain alphanumeric characters
    (letters and digits) and underscores, and must begin with a letter.
    Unicode characters are not allowed.

    The leader code referrs to the item_type, and specifies the type of KIMkit item,
    MO == portable-model, SM == simulator-model, MD == model-driver

    The 12 digit ID number is generated pseudo-randomly, and is used to create a
    directory for the item in the KIMkit repository. The repository is specified
    at creation time to allow this function to check for ID number collisions
    within that repository.

    The version of a KIMkit item is a 3 digit integer, which starts at 000 for
    all new items.



    Parameters
    ----------
    name : str
        Human readable prefix for the item
    item_type : str
        type of KIMkit item to generate a kimcode for
        Valid options include 'portable-model', 'simulator-model', and 'model-driver'
    repository : path-like
        root directory of the KIMkit repo containing the item

    Returns
    -------
    str
        kimcode of the item

    Raises
    ------
    ValueError
        invalid item_type
    """

    # generate appropriate leader code for item type
    if item_type == "portable-model":
        leader = "MO"
    elif item_type == "simulator-model":
        leader = "SM"
    elif item_type == "model-driver":
        leader = "MD"
    else:
        raise ValueError(
            "Valid item types include 'portable-model', 'simulator-model', and 'model-driver'"
        )

    # only need to generate a new kimcode for version 0 of a new item
    version = 0

    # generate 12 digit random kim id number as a string
    n = 12
    # check if the kimcode is already in use before returning,
    # generate a new id number if a collision is detected
    # (if there is already a directory assigned to the trial kimcode)
    valid_kimcode = False
    while not valid_kimcode:
        id_number = "".join(["{}".format(random.randint(0, 9)) for num in range(0, n)])
        new_kimcode = format_kim_code(name, leader, id_number, version)
        if is_kimcode_available(repository, new_kimcode):
            kimcode = new_kimcode
            valid_kimcode = True

    return kimcode


def is_kimcode_available(repository, kimcode):
    """Check for kimcode collisions in the specified repository

    _extended_summary_

    Parameters
    ----------
    repository : path-like
        root directory of repo to install into
    kimcode : str
        id code of the item

    Returns
    -------
    bool
        whether the kimcode is unused
    """
    if not os.path.exists(kimcode_to_file_path(kimcode, repository)):
        return True
    else:
        return False


def kimcode_to_file_path(kimcode, repository):
    """Convert a kimcode and repository to a location on disk
    to save the item.

    Items in /repository/ with kimcode 'name_prefix_XXXXYYYYZZZZ_VVV' are stored at path:

    /repository/XXXX/YYYY/ZZZZ/VVV/

    Parameters
    ----------
    kimcode : str
        id code of the item
    repository : path-like
        root directory of repo to begin item's path at

    Returns
    -------
    path-like
        path to save item in repository with kimcode

    Raises
    ------
    ValueError
        Unrecognized KIMkit item type
    """
    parsed_kimcode = parse_kim_code(kimcode)

    # if no subversion specified
    name, leader, id_number, version = parsed_kimcode
    n = 4  # use 4 digit substrings as directories
    subdirs = [id_number[i : i + n] for i in range(0, len(id_number), n)]

    if leader == "MO":
        prefix = "portable-models"
    elif leader == "SM":
        prefix = "simulator-models"
    elif leader == "MD":
        prefix = "model-drivers"
    else:
        raise ValueError("Unrecognized KIMkit item type")

    if repository:
        path = os.path.join(repository, prefix, *subdirs, version)
    else:
        path = os.path.join(prefix, *subdirs, version)

    return path


def strip_version(kimcode):
    name, leader, num, version = parse_kim_code(kimcode)
    return "{}__{}_{}".format(name, leader, num)


def strip_name(kimcode):
    name, leader, num, version = parse_kim_code(kimcode)
    return "{}_{}_{}".format(leader, num, version)


def stringify_version(version):
    return str(version).zfill(3)


def iskimid(kimcode):
    return re.match(RE_KIMID, kimcode) is not None


def isextendedkimid(kimcode):
    return re.match(RE_EXTENDEDKIMID, kimcode) is not None


def isuuid(kimcode):
    return re.match(RE_UUID, kimcode) is not None


def isjobid(kimcode):
    return re.match(RE_JOBID, kimcode) is not None


def istestresult(uuid):
    return re.match(RE_TESTRESULT, uuid) is not None


def isverificationresult(uuid):
    return re.match(RE_VERIFICATIONRESULT, uuid) is not None


def iserror(uuid):
    return re.match(RE_ERROR, uuid) is not None
