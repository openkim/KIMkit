import datetime
from pytz import timezone
import sys
import os
import warnings
import kim_edn
from collections import OrderedDict

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from kim_utils import kimcodes

import users
import provenance
import config as cf
from logger import logging

central = timezone("US/Central")

logger = logging.getLogger("KIMkit")


class MetaData:
    def __init__(self, repository, kimcode):
        """Default metadata class for KIMkit items

        _extended_summary_

        Parameters
        ----------
        kimcode : str
            kimcode ID string of the item
        repository: path like
            repository where the item is saved
        metadata_dict: dict, optional
            Dictionary of any metadata values to be added or modified.
            All required fields for the item type must be specified to initialize metadata for a new item.
            If not suppied, metadata information is read from existing kimspec.edn
        """
        # setattr(
        #     self, "date", datetime.datetime.now(central).strftime("%Y-%m-%d %H:%M:%S")
        # )
        setattr(self, "repository", repository)
        dest_path = kimcodes.kimcode_to_file_path(kimcode, repository)

        dest_file = os.path.join(dest_path, "kimspec.edn")

        # read current metadata from kimspec.edn if it exists
        if os.path.isfile(dest_file):
            existing_metadata = kim_edn.load(dest_file)
            for key in existing_metadata:
                setattr(self, key, existing_metadata[key])
        else:
            raise FileNotFoundError(f"No kimspec.edn found at {dest_path}")

    def get_metadata_fields(self):
        metadata_dict = vars(self)
        return metadata_dict

    def edit_metadata_value(self, key, new_value, UUID, provenance_comments=None):
        """edit a metadata field of an existing item

        Parameters
        ----------
        key : str
            name of the metadata field to be updated
        new_value : str, array, see metadata_config
            new value to be set for the metadata field
        provenance_comments : str, optional
            any comments about how/why the item was edited, by default None

        Raises
        ------
        KeyError
            if the metadata key is not specified in metadata_config
        """
        # TODO: fix user check
        # if not users.is_user(UUID):
        #     raise ValueError(f"UUID {UUID} not recognized as a KIMkit user.")

        if key not in cf.kimspec_order:
            raise KeyError(f"metadata field {key} not recognized, aborting.")
        metadata_dict = vars(self)
        kimcode = metadata_dict["extended-id"]
        logger.info(
            f"User {UUID} updated metadata field {key} of item {kimcode} in repository {self.repository} from {metadata_dict[key]} to {new_value}"
        )

        metadata_dict[key] = new_value

        _write_metadata_to_file(
            self.repository, metadata_dict["extended-id"], metadata_dict
        )
        event_type = "metadata-update"
        provenance.Provenance(
            metadata_dict["extended-id"],
            self.repository,
            event_type,
            UUID,
            comments=provenance_comments,
        )


def create_metadata(repository, kimcode, metadata_dict, UUID):
    """Create a kimspec.edn metadata file for an item without one.


    Parameters
    ----------
    repository : path like
        root directory of the KIMkit repository where the item is stored
    kimcode : str
        id code of the item for which metadata is being created
    metadata_dict : dict
        dict of all required and any optional metadata keys
    UUID : str
        id number of the entity requesting the item's creation
    """

    logger.debug(f"Metadata created for new item {kimcode} in repository {repository}")

    metadata_dict["date"] = datetime.datetime.now(central).strftime("%Y-%m-%d %H:%M:%S")
    metadata_dict["contributor-id"] = UUID
    if not "maintainer-id" in metadata_dict:
        metadata_dict["maintainer-id"] = UUID
    metadata_dict["domain"] = "KIMkit"

    # TODO: assign DOI?

    _write_metadata_to_file(repository, kimcode, metadata_dict)

    new_metadata = MetaData(repository, kimcode)

    return new_metadata


def _write_metadata_to_file(repository, kimcode, metadata_dict):
    """generate and write the kimspec.edn metadata file for a new KIM item

    Parameters
    ----------
    kimcode : str
        id code of the item associated with this metadata
    repository : pathlike
        root directory of the KIMkit repository the item is stored within
    """

    metadata_dict_sorted = OrderedDict()

    for field in cf.kimspec_order:
        if field in metadata_dict:
            metadata_dict_sorted[field] = metadata_dict[field]

    dest_path = kimcodes.kimcode_to_file_path(kimcode, repository)

    if os.path.exists(dest_path):
        dest_file = os.path.join(dest_path, "kimspec_tmp.edn")
        with open(dest_file, "w") as outfile:
            try:
                kim_edn.dump(metadata_dict_sorted, outfile, indent=4)
            except TypeError as e:
                os.remove(os.path.join(dest_path, dest_file))
                raise e

        os.rename(
            os.path.join(dest_path, "kimspec_tmp.edn"),
            os.path.join(dest_path, "kimspec.edn"),
        )

    else:
        raise FileNotFoundError(
            f"KIM item does not appear to exist in the selected repository {repository}"
        )


def validate_metadata(metadata_dict):
    """check that all required metadata fields have valid entries.

    Parameters
    ----------
    metadata_dict : dict
        dictionary of all required and any optional metadata fields
    """
    supported_item_types = ("portable-model", "simulator-model", "model-driver")

    try:
        kim_item_type = metadata_dict["kim-item-type"]

    except (KeyError):
        raise KeyError(f"Required metadata field 'kim-item-type' not specified.")

    if kim_item_type not in supported_item_types:
        raise ValueError(
            f"""Item type {kim_item_type} not recognized.
         Valid options include 'portable-model', 'simulator-model', and 'model-driver'."""
        )

    metadata_requirements = cf.KIMkit_item_type_key_requirements[kim_item_type]

    required_fields = metadata_requirements["required"]
    optional_fields = metadata_requirements["optional"]

    for field in required_fields:
        try:
            metadata_dict[field]
        except KeyError:
            raise KeyError(
                f"Required metadata field '{field}' not specified, aborting"
            ) from KeyError
    fields_to_remove = []
    for field in metadata_dict:
        if field not in required_fields and field not in optional_fields:
            fields_to_remove.append(field)
            warnings.warn(
                f"Metadata field '{field}' not used for kim item type {kim_item_type}, ignoring."
            )
    for field in fields_to_remove:
        metadata_dict.pop(field, None)

    check_metadata_types(metadata_dict)
    return metadata_dict


def check_metadata_types(metadata_dict, kim_item_type=None):
    """Check that all required and optional metadata fields are of the correct
    type and structure.

    Parameters
    ----------
    metadata_dict : dict
        dict of any metadata fields
    kim_item_type : str, optional
        can pass in kim_item_type as a parameter if not included in the metadata dict
    """
    supported_item_types = ("portable-model", "simulator-model", "model-driver")

    if not kim_item_type:

        try:
            kim_item_type = metadata_dict["kim-item-type"]

        except (KeyError):
            raise KeyError(
                f"Required metadata field 'kim-item-type' not specified."
            ) from KeyError

    if kim_item_type not in supported_item_types:
        raise ValueError(
            f"""Item type '{kim_item_type}' not recognized.
         Valid options include 'portable-model', 'simulator-model', and 'model-driver'."""
        )

    for field in metadata_dict:
        if field in cf.kimspec_strings:
            if isinstance(metadata_dict[field], str):
                pass
            else:
                raise TypeError(
                    f"Required metadata field '{field}' is of incorrect type, must be str."
                )
        elif field in cf.kimspec_arrays:
            for item in metadata_dict[field]:
                if isinstance(item, cf.kimspec_arrays[field]):
                    if cf.kimspec_arrays[field] == dict:
                        key_requirements = cf.kimspec_arrays_dicts[field]
                        for key in key_requirements:
                            if key and isinstance(metadata_dict[field][key], str):
                                pass
                            else:
                                raise KeyError(
                                    f"Missing required key '{key}' in metadata field '{field}'."
                                )
                    # Not really needed, written for clarity, type already checked above
                    elif cf.kimspec_arrays[field] == str:
                        pass
                else:
                    raise TypeError(
                        f"Metadata field '{field}' is of invalid type, must be '{cf.kimspec_arrays[field]}'."
                    )


def create_new_metadata_from_existing(
    repository, old_kimcode, new_kimcode, UUID, metadata_update_dict=None
):
    """Create a new metadata object from an existing kimspec.edn, and any modifications

    Reads an existing kimspec.edn, creates a new metadata object for a new item based on it,
    incorporating any edits specified in metadata_dict.

    Parameters
    ----------
    repository : str
        root directory of the KIMkit repository containing the item
    old_kimcode : str
        kimcode of the parent item
    new_kimcode : str
        kimcode of the newly created item
    UUID : str
        id number of the entity making the update
    metadata_update_dict : dict, optional
        dict of any metadata fields to be changed/assigned, by default None
    """

    logger.debug(
        f"Metadata for new item {new_kimcode} created from metadata of {old_kimcode} in {repository}"
    )

    old_metadata = MetaData(repository, old_kimcode)
    old_metadata_dict = vars(old_metadata)

    new_metadata_dict = {}

    for key in old_metadata_dict:
        new_metadata_dict[key] = old_metadata_dict[key]

    new_metadata_dict["extended-id"] = new_kimcode
    new_metadata_dict["contributor-id"] = UUID

    if metadata_update_dict:
        for key in metadata_update_dict:
            new_metadata_dict[key] = metadata_update_dict[key]

    valid_metadata = validate_metadata(new_metadata_dict)
    _write_metadata_to_file(repository, new_kimcode, valid_metadata)
    new_metadata = MetaData(repository, new_kimcode)
    return new_metadata


def add_metadata_key(self, key, value):
    pass


def delete_metadata_key(self, key):
    pass
