import datetime
from pytz import timezone
import sys
import os
import warnings
import kim_edn

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from kim_utils import util, kimcodes

import users
import metadata_config as cfg

central = timezone("US/Central")


class MetaData:
    def __init__(self, repository, kimcode, metadata_dict=None):
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
        setattr(
            self, "date", datetime.datetime.now(central).strftime("%Y-%m-%d %H:%M:%S")
        )

        dest_path = kimcodes.kimcode_to_file_path(kimcode, repository)

        dest_file = os.path.join(dest_path, "kimspec.edn")

        # read current metadata from kimspec.edn if it exists
        if os.path.isfile(dest_file):
            existing_metadata = kim_edn.load(dest_file)
            for key in existing_metadata:
                setattr(self, key, existing_metadata[key])

        # update metadata with any new fields provided
        if metadata_dict:
            for field in metadata_dict:
                setattr(self, field, metadata_dict[field])

            # write a kimspec.edn if any metadata fields have been modified
            self._write_metadata_to_file(kimcode, repository)

    def add_metadata_key(self, key, value):
        pass

    def delete_metadata_key(self, key):
        pass

    def edit_metadata_value(self, key, new_value):
        pass

    def _fork_metadata(self, existing_kimcode, new_kimcode):
        pass

    def _update_provenance_after_metadata_change(self, kimcode):
        pass

    def _write_metadata_to_file(self, kimcode, repository):
        """generate and write the kimspec.edn metadata file for a new KIM item

        Parameters
        ----------
        kimcode : str

        repository : pathlike
            repository the item is stored within
        """

        dest_path = kimcodes.kimcode_to_file_path(kimcode, repository)

        if os.path.exists(dest_path):
            dest_file = os.path.join(dest_path, "kimspec.edn")
            with open(dest_file, "w") as outfile:
                kim_edn.dump(vars(self), outfile, indent=4)

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

    metadata_requirements = cfg.KIMkit_item_type_key_requirements[kim_item_type]

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
        if field in cfg.kimspec_strings:
            if isinstance(metadata_dict[field], str):
                pass
            else:
                raise TypeError(
                    f"Required metadata field '{field}' is of incorrect type, must be str."
                )
        elif field in cfg.kimspec_arrays:
            for item in metadata_dict[field]:
                if isinstance(item, cfg.kimspec_arrays[field]):
                    if cfg.kimspec_arrays[field] == dict:
                        key_requirements = cfg.kimspec_arrays_dicts[field]
                        for key in key_requirements:
                            if key and isinstance(metadata_dict[field][key], str):
                                pass
                            else:
                                raise KeyError(
                                    f"Missing required key '{key}' in metadata field '{field}'."
                                )
                    # Not really needed, written for clarity, type already checked above
                    elif cfg.kimspec_arrays[field] == str:
                        pass
                else:
                    raise TypeError(
                        f"Metadata field '{field}' is of invalid type, must be '{cfg.kimspec_arrays[field]}'."
                    )


def create_new_metadata_from_existing(
    repository, old_kimcode, new_kimcode, metadata_update_dict=None
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
    metadata_update_dict : dict, optional
        dict of any metadata fields to be changed/assigned, by default None
    """

    old_metadata = MetaData(repository, old_kimcode)
    old_metadata_dict = vars(old_metadata)

    new_metadata_dict = {}

    for key in old_metadata_dict:
        new_metadata_dict[key] = old_metadata_dict[key]

    if metadata_update_dict:
        for key in metadata_update_dict:
            new_metadata_dict[key] = metadata_update_dict[key]

    validate_metadata(new_metadata_dict)
    new_metadata = MetaData(repository, new_kimcode, metadata_dict=new_metadata_dict)
    return new_metadata
