import datetime
from pytz import timezone
import os
import warnings
import kim_edn
from collections import OrderedDict

from . import users
from . import provenance
from . import config as cf
from .logger import logging
from . import kimcodes

central = timezone("US/Central")

logger = logging.getLogger("KIMkit")

"""Module used to manage KIMkit metadata.

Metadata is stored along with every KIMkit item in a file named kimspec.edn, which is organized
as a dict of key-value pairs. Some keys are required for specific item types, while others are optional,
and the types of data stored as the relevant values vary. The metadata standards specifying value types
and key requirements are stored in config.py"""


class MetaData:
    def __init__(self, repository, kimcode):
        """Metadata class for KIMkit items, reads metadata from kimspec.edn stored
        in the item's directory. Newly imported items should have a kimspec.edn created
        for them via the create_metadata() function.


        Parameters
        ----------
        repository: path-like
            repository where the item is saved
        kimcode : str
            kimcode ID string of the item

        Raises
        ------
        FileNotFoundError
            No kimspec.edn found in the item's directory.
        """
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

    def edit_metadata_value(
        self, key, new_value, provenance_comments=None, run_as_editor=False
    ):
        """Edit a key-value pair corresponding to a metadata field of a KIMkit item
        from that item's kimspec.edn

        Parameters
        ----------
        key : str
            name of the metadata field to be updated
        new_value : str/list/dict
            new value to be set for the metadata field,
            see metadata_config for types and data structure
            requirements for specific metadata fields
        provenance_comments : str, optional
            any comments about how/why the item was edited, by default None
        run_as_editor : bool, optional
            flag to be used by KIMkit Editors to run with elevated permissions,
            and edit metadata of items they are neither the contributor nor maintainer of, by default False

        Raises
        ------
        KIMkitUserNotFoundError
            A non KIMkit user attempted to edit metadata of an item.
        InvalidMetadataFieldError
            Metadata field not in the KIMkit metdata standard
        NotRunAsEditorError
            A user with Editor permissions attempted to edit metadata of the item,
            but did not specify run_as_editor=True
        NotAnEditorError
            A user without Editor permissions attempted to edit metadata
            of an item they are not the contributor or maintainer of.
        """
        this_user = users.whoami()
        if users.is_user(system_username=this_user):
            UUID = users.get_uuid(system_username=this_user)
        else:
            raise cf.KIMkitUserNotFoundError(
                "Only KIMkit users can edit metadata of items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
            )

        if key not in cf.kimspec_order:
            raise cf.InvalidMetadataFieldError(
                f"metadata field {key} not recognized, aborting."
            )
        metadata_dict = vars(self)
        kimcode = metadata_dict["extended-id"]

        contributor = metadata_dict["contributor-id"]
        maintainer = metadata_dict["maintainer-id"]

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

        else:
            logger.warning(
                f"User {UUID} attempted to edit metadata field {key} of item {kimcode} in repository {self.repository} without editor privleges"
            )
            raise cf.NotAnEditorError(
                "Only KIMkit Editors may edit metadata of items they are not the contributor or maintainer of."
            )

    def delete_metadata_field(
        self, field, provenance_comments=None, run_as_editor=False
    ):
        """Delete a key-value pair corresponding to a metadata field of a KIMkit item
        from that item's kimspec.edn

        Parameters
        ----------
        field : str
            name of the metadata field to be deleted
        provenance_comments : str, optional
            any comments about how/why the item was deleted, by default None
        run_as_editor : bool, optional
            flag to be used by KIMkit Editors to run with elevated permissions,
            and delete metadata fields of items they are neither
            the contributor nor maintainer of, by default False

        Raises
        ------
        KIMkitUserNotFoundError
            A non KIMkit user attempted to delete metadata of an item.
        InvalidMetadataFieldError
            Metadata field not in the KIMkit metdata standard
        NotRunAsEditorError
            A user with Editor permissions attempted to delete metadata of the item,
            but did not specify run_as_editor=True
        NotAnEditorError
            A user without Editor permissions attempted to delete metadata of an item
            they are not the contributor or maintainer of.
        """
        this_user = users.whoami()
        if users.is_user(system_username=this_user):
            UUID = users.get_uuid(system_username=this_user)
        else:
            raise cf.KIMkitUserNotFoundError(
                "Only KIMkit users can edit metadata of items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
            )

        if field not in cf.kimspec_order:
            raise cf.InvalidMetadataFieldError(
                f"metadata field {field} not recognized, aborting."
            )
        metadata_dict = vars(self)
        kimcode = metadata_dict["extended-id"]

        contributor = metadata_dict["contributor-id"]
        maintainer = metadata_dict["maintainer-id"]

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
                f"User {UUID} deleted metadata field {field} of item {kimcode} in repository {self.repository}"
            )

            del metadata_dict[field]

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

        else:
            logger.warning(
                f"User {UUID} attempted to delete metadata field {field} of item {kimcode} in repository {self.repository} without editor privleges"
            )
            raise cf.NotAnEditorError(
                "Only KIMkit Editors may delete metadata fields of items they are not the contributor or maintainer of."
            )


def create_metadata(repository, kimcode, metadata_dict, UUID):
    """Create a kimspec.edn metadata file for a new KIMkit item.

    _extended_summary_

    Parameters
    ----------
    repository : path-like
        root directory of the KIMkit repository where the item is to be stored
    kimcode : str
        id code of the item for which metadata is being created
    metadata_dict : dict
        dict of all required and any optional metadata keys
    UUID : str
        id number of the user or entity requesting the item's creation in UUID format

    Returns
    -------
    MetaData
        KIMkit metadata object

    Raises
    ------
    InvalidMetadataError
        If the supplied metadata_dict does not conform to the KIMkit standard
    """

    metadata_dict["date"] = datetime.datetime.now(central).strftime("%Y-%m-%d %H:%M:%S")
    metadata_dict["contributor-id"] = UUID
    if not "maintainer-id" in metadata_dict:
        metadata_dict["maintainer-id"] = UUID
    metadata_dict["domain"] = "KIMkit"

    # TODO: assign DOI?

    try:
        metadata_dict = validate_metadata(metadata_dict)

    except (
        cf.MissingRequiredMetadataFieldError,
        cf.InvalidItemTypeError,
        cf.InvalidMetadataTypesError,
    ) as e:
        raise cf.InvalidMetadataError(
            "Supplied metadata dict does not conform to the KIMkit metadata standard."
        ) from e

    _write_metadata_to_file(repository, kimcode, metadata_dict)

    new_metadata = MetaData(repository, kimcode)

    logger.debug(f"Metadata created for new item {kimcode} in repository {repository}")

    return new_metadata


def _write_metadata_to_file(repository, kimcode, metadata_dict):
    """Internal function used to write a KIMkit item's metadata to disk
    once its metadata has been validated and created.

    Parameters
    ----------
    repository : path-like
        Root directory of the KIMkit repository the item is stored within
    kimcode : str
        ID code of the item that this metadata is being written for
    metadata_dict : dict
        Dictionary of metadata to be written to disk in a kimspec.edn.
        Assumed to have been previously validated by validate_metadata()

    Raises
    ------
    e
        Data type not compatible with .edn format
    KIMkitItemNotFoundError
        No item with kimcode exists in repository
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
        raise cf.KIMkitItemNotFoundError(
            f"KIM item does not appear to exist in the selected repository {repository}"
        )


def validate_metadata(metadata_dict):
    """Check that all required metadata fields have valid entries.

    Further, call check_metadata_types to ensure all metadata fields
    are of valid type and structure.

    Parameters
    ----------
    metadata_dict : dict
        dictionary of all required and any optional metadata fields

    Returns
    -------
    dict
        dictionary of validated metadata

    Raises
    ------
    MissingRequiredMetadataFieldError
        kim-item-type not specified.
        Prevents further validation because the metdata standard depends on item type.
    InvalidItemTypeError
        kim-item-type is invalid.
        Valid options include 'portable-model', 'simulator-model', and 'model-driver'.
    MissingRequiredMetadataFieldError
        A required metadata field is not specified.
    InvalidMetadataTypesError
        Validating metadata types failed
    """
    supported_item_types = ("portable-model", "simulator-model", "model-driver")

    try:
        kim_item_type = metadata_dict["kim-item-type"]

    except (KeyError) as e:
        raise cf.MissingRequiredMetadataFieldError(
            f"Required metadata field 'kim-item-type' not specified."
        ) from e

    if kim_item_type not in supported_item_types:
        raise cf.InvalidItemTypeError(
            f"""Item type {kim_item_type} not recognized.
         Valid options include 'portable-model', 'simulator-model', and 'model-driver'."""
        )

    metadata_requirements = cf.KIMkit_item_type_key_requirements[kim_item_type]

    required_fields = metadata_requirements["required"]
    optional_fields = metadata_requirements["optional"]

    for field in required_fields:
        try:
            metadata_dict[field]
        except KeyError as e:
            raise cf.MissingRequiredMetadataFieldError(
                f"Required metadata field '{field}' not specified, aborting"
            ) from e
    fields_to_remove = []
    for field in metadata_dict:
        if field not in required_fields and field not in optional_fields:
            fields_to_remove.append(field)
            warnings.warn(
                f"Metadata field '{field}' not used for kim item type {kim_item_type}, ignoring."
            )
    for field in fields_to_remove:
        metadata_dict.pop(field, None)

    try:
        check_metadata_types(metadata_dict)
    except (KeyError, cf.InvalidItemTypeError, TypeError, ValueError) as e:
        raise cf.InvalidMetadataTypesError(
            "Types of one or more metadata fields are invalid"
        ) from e
    return metadata_dict


def check_metadata_types(metadata_dict, kim_item_type=None):
    """Check that all required and optional metadata fields are of the correct
    type and structure.

    Parameters
    ----------
    metadata_dict : dict
        dict of any metadata fields
    kim_item_type : str, optional
        can pass in kim_item_type as a parameter if not included in the metadata dict, by default None
        Valid options include 'portable-model', 'simulator-model', and 'model-driver'.

    Raises
    ------
    KeyError
        kim-item-type not specified.
        Prevents further validation because the metdata standard depends on item type.
    InvalidItemTypeError
        kim-item-type is invalid.
        Valid options include 'portable-model', 'simulator-model', and 'model-driver'.
    TypeError
        Required metadata field that should be str is not
    ValueError
        Metadata field that should be UUID4 is not
    KeyError
        Metadata field of type dict is missing a required key
    ValueError
        Metadata field that should be UUID4 is not
    TypeError
        General error for metadata field of incorrect type
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
        raise cf.InvalidItemTypeError(
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
            if field in cf.kimspec_uuid_fields:
                if not users.is_user(user_id=metadata_dict[field]):
                    raise ValueError(
                        f"Metadtata field {field} requires a KIMkit user id in UUID4 format."
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
                    elif cf.kimspec_arrays[field] == str:
                        if field in cf.kimspec_uuid_fields:
                            if not users.is_user(user_id=item):
                                raise ValueError(
                                    f"Metadtata field {field} requires a KIMkit user id in UUID4 format."
                                )
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
    repository : path-like
        root directory of the KIMkit repository containing the item
    old_kimcode : str
        kimcode of the parent item
    new_kimcode : str
        kimcode of the newly created item
    UUID : str
        id number of the user or entity making the update in UUID4 format
    metadata_update_dict : dict, optional
        dict of any metadata fields to be changed/assigned, by default None

    Returns
    -------
    MetaData
        KIMkit metadata object for the new item

    Raises
    ------
    InvalidMetadataError
        If the metadata of the new item does not conform to the standard,
        most likely the metadata_update_dict has errors.
    """

    logger.debug(
        f"Metadata for new item {new_kimcode} created from metadata of {old_kimcode} in {repository}"
    )

    old_metadata = MetaData(repository, old_kimcode)
    old_metadata_dict = vars(old_metadata)

    # repository is useful as a Metadata object instance attribute, but isn't a metadata field
    if "repository" in old_metadata_dict:
        del old_metadata_dict["repository"]

    new_metadata_dict = {}

    for key in old_metadata_dict:
        new_metadata_dict[key] = old_metadata_dict[key]

    new_metadata_dict["extended-id"] = new_kimcode
    new_metadata_dict["contributor-id"] = UUID

    if metadata_update_dict:
        for key in metadata_update_dict:
            new_metadata_dict[key] = metadata_update_dict[key]

    try:
        valid_metadata = validate_metadata(new_metadata_dict)
    except (
        cf.MissingRequiredMetadataFieldError,
        cf.InvalidItemTypeError,
        cf.InvalidMetadataTypesError,
    ) as e:
        raise cf.InvalidMetadataError("Validating metadata failed.") from e
    _write_metadata_to_file(repository, new_kimcode, valid_metadata)
    new_metadata = MetaData(repository, new_kimcode)
    return new_metadata


def add_metadata_key(self, key, value):
    pass


def delete_metadata_key(self, key):
    pass
