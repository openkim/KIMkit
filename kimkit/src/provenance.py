"""This module contains methods for managing KIMkit item history, which is tracked via a file
stored along with each item called kimprovenance.edn. This file is automatically created when
a new item is imported into KIMkit, and updated whenever the item's content changes on disk.

In general, users should not call any of the functions in this module directly,
nor edit kimprovenance.edn for any KIMkit items."""

import os
import datetime
import subprocess
import hashlib
import codecs
import re
import stat
from collections import OrderedDict
from pytz import timezone
import kim_edn

from .. import users
from .logger import logging
from . import config as cf

logger = logging.getLogger("KIMkit")

central = timezone("US/Central")

CHECKSUMS_MATCH = re.compile(
    r"""
  (\"checksums\"\s\{$\n
    .*?$\n
  \s*\})
  """,
    flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
)

CHECKSUMS_LINE_MATCH = re.compile(
    r"""
    \s*\"(.*?)\"\s*\"([a-z0-9]+)\"\s*$
    """,
    flags=re.VERBOSE,
)


kimprovenance_order = [
    "checksums",
    "comments",
    "event-type",
    "extended-id",
    "timestamp",
    "user-id",
]


def add_kimprovenance_entry(
    path,
    comment,
    event_type=None,
    user_id=None,
):
    """Create a new kimprovenance.edn entry for a new instance of an item

    Attempt to read the previous kimprovenance.edn (if any),
    create a new entry for the new version of the item, and append it to the
    existing entries, and write the result as a kimprovenance.edn in the
    updated item's directory.

    The kimprovenance.edn file of an item stores a list of dicts,
    where each dict corresponds to a single version of the item.
    The first entry in each is itself a dict of shasum hash values
    of all the files in the item's directory
    (except for kimprovenace.edn itself),
    followed by metadata specifying what kind of update happened,
    who performed the update, and why.

    Parameters
    ----------
    path : path-like
        location of the item on disk
    user_id : str
        ID code of the user or entity modifying the item, in UUID4 format
    event_type : str
        reason for the update, valid options include:
        "initial-creation", "version-update", "metadata-update", "fork", and "discontinued"
    comment : str
        Any comments about how the item was updated and/or why, by default None

    Raises
    ------
    RuntimeError
        Encountered object that appears to be neither a file nor a directory
        when attempting to hash the item's files/dirs
    """
    if not user_id:
        try:
            username = users.whoami()
            user_info = users.get_user_info(username=username)
            user_id = user_info.get("uuid")
        except AttributeError:
            raise (
                cf.KIMkitUserNotFoundError(
                    "Only KIMkit users can create metadata. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
                )
            )

    if not event_type:
        existing_provenance = os.path.join(path, "kimprovenance.edn")
        if os.path.isfile(existing_provenance):
            event_type = "revised-version-creation"
        else:
            event_type = "initial-creation"

    assert event_type in [
        "initial-creation",
        "metadata-update",
        "fork",
        "discontinued",
        "revised-version-creation",
    ]

    # Read kimspec.edn to get extended id
    with open(os.path.join(path, "kimspec.edn")) as f:
        kimspec = kim_edn.load(f)

    extended_id = kimspec["extended-id"]

    logger.debug(
        f"Provenance update {event_type} to item {extended_id} triggered by user {user_id}"
    )

    if event_type != "initial-creation":
        with open(os.path.join(path, "kimprovenance.edn")) as f:
            kimprovenance_current = kim_edn.load(f)

        kimprovenance_current_ordered = []
        for entry in kimprovenance_current:
            tmp = OrderedDict([])
            # Now transfer over the 'checksums' key, sorting the filenames alphanumerically in the process
            tmp["checksums"] = OrderedDict([])
            for filesum in sorted(entry["checksums"]):
                tmp["checksums"][filesum] = entry["checksums"][filesum]
            # Now transfer over keys other than 'checksums'
            for key in kimprovenance_order[1:]:
                if key in entry:
                    tmp[key] = entry[key]
            # Append this entry to the new kimprovenance we're making
            kimprovenance_current_ordered.append(tmp)

    # Finally, make a kimprovenance.edn entry for this update
    this_kimprovenance_entry = OrderedDict([])
    this_kimprovenance_entry["checksums"] = OrderedDict([])
    if comment != None:
        this_kimprovenance_entry["comments"] = comment
    this_kimprovenance_entry["event-type"] = event_type
    this_kimprovenance_entry["extended-id"] = extended_id
    this_kimprovenance_entry["timestamp"] = datetime.datetime.now(central).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    this_kimprovenance_entry["user-id"] = user_id

    # Get a list of all files and subdirs in this Test
    absolute_files_and_subdirs = []
    relative_files_and_subdirs = []
    prefix = path

    for tmppath, subdirs, files in os.walk(path):
        for filename in sorted(subdirs + files):
            if os.path.isdir(os.path.join(tmppath, filename)):
                continue

            # Exclude kimprovenance or hidden files
            if filename == "kimprovenance.edn" or filename[0] == ".":
                pass
            else:
                absolute_files_and_subdirs.append(os.path.join(tmppath, filename))
                splitbyprefix = tmppath.split(prefix)[1]
                if splitbyprefix:
                    relative_files_and_subdirs.append(
                        os.path.join(splitbyprefix[1:], filename)
                    )
                else:
                    relative_files_and_subdirs.append(filename)

    for ind, fl in enumerate(relative_files_and_subdirs):
        abs_loc = absolute_files_and_subdirs[ind]
        if os.path.isfile(abs_loc):
            with open(abs_loc, "rb") as f:
                this_kimprovenance_entry["checksums"][fl] = hashlib.sha1(
                    f.read()
                ).hexdigest()

        elif os.path.isdir(abs_loc):
            out = subprocess.run(
                ["shasum", abs_loc], stdout=subprocess.PIPE, check=True
            )
            out = out.stdout.decode("utf-8").split()[0]
            this_kimprovenance_entry["checksums"][fl] = out
        else:
            raise RuntimeError(
                "Encountered object {} that appears to be neither a file nor "
                "a directory ".format(fl)
            )

    # Add this entry to kimprovenance and write it to disk
    if event_type == "initial-creation":
        kimprovenance_new = [this_kimprovenance_entry]
    else:
        kimprovenance_new = [this_kimprovenance_entry] + kimprovenance_current_ordered

    with open(os.path.join(path, "kimprovenance.edn"), "w", encoding="utf-8") as ff:
        write_provenance(kimprovenance_new, ff, path)


def write_provenance(o, f, path, allow_nils=True):
    """Write a kimprovenance.edn file

    Parameters
    ----------
    o : list
        content to write
    f : file object or str
        location to write to
    allow_nils : bool, optional
        whether to allow nil-types to be written, by default True

    Raises
    ------
    Exception
        not all kimprovenance objects are lists
    """
    # ignore any umask the user may have set
    oldumask = os.umask(0)
    if not allow_nils:
        o = replace_nones(o)

    # If f is a string, create a file object
    if isinstance(f, str):
        flobj = codecs.open(f, "w", encoding="utf-8")
    else:
        flobj = f

    if not isinstance(o, list):
        raise Exception(
            "Attempted to dump kimprovenance object of type %r. All kimprovenance objects "
            " must be lists." % type(o)
        )

    kimprovenance_new = []
    for entry in o:
        entry_new = OrderedDict([])
        # First sort the entries in 'checksums' and add it to this entry
        entry_new["checksums"] = OrderedDict([])
        for filesum in sorted(entry["checksums"]):
            entry_new["checksums"][filesum] = entry["checksums"][filesum]
        # Now all keys other than 'checksums'
        for key in kimprovenance_order[1:]:
            if key in entry:
                entry_new[key] = entry[key]
        kimprovenance_new.append(entry_new)

    final_object = kimprovenance_new

    # Custom formatting for kimprovenance
    final_object_as_string = kim_edn.dumps(final_object, indent=1)
    final_object_as_string = format_kimprovenance(final_object_as_string)

    # Remove trailing spaces
    final_object_stripped = ("\n").join(
        [x.rstrip() for x in final_object_as_string.splitlines()]
    )

    flobj.write(final_object_stripped)
    flobj.write("\n")

    flobj.close()
    provfile = os.path.join(path, "kimprovenance.edn")
    os.chmod(
        provfile,
        stat.S_IRUSR
        | stat.S_IWUSR
        | stat.S_IXUSR
        | stat.S_IRGRP
        | stat.S_IWGRP
        | stat.S_IXGRP,
    )
    # return user's original usmask
    os.umask(oldumask)


def format_kimprovenance(kimprov_as_str):
    """Organize provenance information into the correct format

    Parameters
    ----------
    kimprov_as_str : str
        kimprovenance content as a string

    Returns
    -------
    str
        correctly formatted kimprovenence string

    Raises
    ------
    Exception
        no checksums in kimprovenance string
    Exception
        no checksums in kimprovenance string
    """
    # First replace the checksums section
    tmp = CHECKSUMS_MATCH.findall(kimprov_as_str)
    if len(tmp) == 0:
        raise Exception("Failed to match any checksums instances!!! Exiting...")

    new_kimprov_as_str = kimprov_as_str

    for checksums_instance in tmp:
        checksums_section = '"checksums" {'

        checksums_lines = checksums_instance.splitlines()

        if len(checksums_lines) == 0:
            raise Exception(
                "Failed to match any lines in checksums instance!!! Exiting..."
            )

        checksums_section += '"{}" "{}"\n'.format(
            *CHECKSUMS_LINE_MATCH.search(checksums_lines[1]).groups()
        )

        for ind, line in enumerate(checksums_lines[2:-2]):
            checksums_section += " " * 15 + '"{}" "{}"\n'.format(
                *CHECKSUMS_LINE_MATCH.search(line).groups()
            )

        checksums_section += " " * 15 + '"{}" "{}"'.format(
            *CHECKSUMS_LINE_MATCH.search(checksums_lines[-2]).groups()
        )
        checksums_section += "}"

        new_kimprov_as_str = new_kimprov_as_str.replace(
            checksums_instance, checksums_section
        )

    # Now fix up the rest of the file
    new_kimprov_as_str = new_kimprov_as_str.replace("[\n  {", "[{")
    new_kimprov_as_str = new_kimprov_as_str.replace(
        '{\n    "checksums"', '{"checksums"'
    )
    new_kimprov_as_str = re.sub(
        '^  {"checksums"', ' {"checksums"', new_kimprov_as_str, flags=re.MULTILINE
    )
    new_kimprov_as_str = re.sub('^    "', '  "', new_kimprov_as_str, flags=re.MULTILINE)
    new_kimprov_as_str = re.sub('"$\n  }', '"}', new_kimprov_as_str, flags=re.MULTILINE)
    new_kimprov_as_str = re.sub("}$\n]", "}]", new_kimprov_as_str, flags=re.MULTILINE)

    return new_kimprov_as_str


def replace_nones(o):
    """Helper function to replace None values in kimprovenance

    Parameters
    ----------
    o : list/dict
        kimprovenance item to have Nones removed from

    Returns
    -------
    list/dict
        object o with nones removed
    """
    if isinstance(o, list):
        return [replace_nones(i) for i in o]
    elif isinstance(o, dict):
        return {k: replace_nones(v) for k, v in o.items()}
    else:
        return o if o is not None else ""
