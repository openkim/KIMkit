import os
import sys
import datetime
import subprocess
import hashlib
import codecs
import re
from collections import OrderedDict
from pytz import timezone
import kim_edn
import users

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from kim_utils import util, kimcodes

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


class Provenance:
    def __init__(
        self,
        kimcode,
        repository,
        event_type,
        UUID,
        comments=None,
    ):
        """provenance object used to track item history

        The provenance file of an item stores a list of dicts,
        where each dict corresponds to a single version of the item.
        The first entry in each is itself a dict of hash values of all the files
        in the item's directory, followed by metadata specifying who performed the
        update and why.

        None of the methods of the provenance item are meant to be called directly,
        they will be invoked by updates to other KIMkit items which update their
        own provenance automatically.

        Parameters
        ----------
        kimcode : int
            kimcode of target item
        event_type : str
            valid options include:"initial-creation", "version-update", "metadata-update", "fork", and "discontinued"
        UUID : list of str
            UUID of the user(s) making the change to provenance
        comments : str, optional
            comments about why and how the item was updated, by default None
        """
        if not users.is_user(UUID):
            raise ValueError(f"UUID {UUID} not recognized as a KIMkit user.")
        self.kimcode = kimcode
        self.event_type = event_type
        self.UUID = UUID
        self.comments = comments if comments is not None else None

        path = kimcodes.kimcode_to_file_path(kimcode, repository)

        add_kimprovenance_entry(path, self.UUID, self.event_type, self.comments)


def add_kimprovenance_entry(path, user_id, event_type, comment):
    """Create a new kimprovenance.edn entry for a new instance of an item

    _extended_summary_

    Parameters
    ----------
    path : str
        location of the item on disk
    user_id : str
        UUID of the user making the edit
    event_type : str
        reason for the update, valid options include:"initial-creation", "version-update", "metadata-update", "fork", and "discontinued"
    comment : str
        any comments about what changes were made and why

    Raises
    ------
    e
    RuntimeError
    """
    if not users.is_user(user_id):
        raise ValueError(f"UUID {user_id} not recognized as a KIMkit user.")

    assert event_type in [
        "initial-creation",
        "metadata-update",
        "fork",
        "discontinued",
        "revised-version-creation",
    ]

    # Read kimspec.edn to get extended id
    with open(os.path.join(path, "kimspec.edn")) as f:
        kimspec = util.loadedn(f)

    extended_id = kimspec["extended-id"]

    if event_type != "initial-creation":

        with open(os.path.join(path, "kimprovenance.edn")) as f:
            kimprovenance_current = util.loadedn(f)

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
        write_provenance(kimprovenance_new, ff)


def write_provenance(o, f, allow_nils=True):
    if not allow_nils:
        o = util.replace_nones(o)

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


def format_kimprovenance(kimprov_as_str):
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
