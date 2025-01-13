"""This module is used to manage **KIMkit** metadata.

Metadata is stored along with every **KIMkit** item in a file named kimspec.edn, which is organized
as a dict of key-value pairs. A copy of each KIMkit item's metadata is also maintained in a 
collection in a mongodb database to allow for efficient sorting and querying of subsets of KIMkit
items.

Some keys are required for specific item types, while others are optional,
and the types of data stored as the relevant values vary. The metadata standards specifying 
value types and key requirements are stored in KIMkit/settings/metadata_config.edn. 
The specific metadata fields that are required or optional for each **KIMkit** item
type may be viewed by calling ``get_metadata_template_for_item_type()``. The returned
template will specify what data types each field should be, as well as whether a 
required key is actually contitionally-required, meaning that a default value will be
assigned by KIMkit if none is supplied by the user.

When importing a new item, a dictionary of metadata is required to be passed in with the item's
conent, which gets passed to ``create_metadata()``. This metadata must specify all fields 
which are required for the given item type, and may specify any metadata fields which are
listed as optional for that item type. This dict of metadata is checked by ``validate_metadata()``,
which checks that all required metadata fields are set, and then calls ``check_metadata_types()``
to verify that all metadata values are of the correct type and data structure.
If no exceptions are raised, the metadata is written to a file called kimspec.edn, which is stored
along with the item's content. This file is then read into the item's database entry to enable 
subsets of items to be quickly found via mongodb queries.

The metadata of existing **KIMkit** items can be modified directly, without updating the item's
source code, by first loading the relevant ``metadata.MetaData`` object into memory by invoking
the class with the repository and kimcode, and then calling the class methods
``MetaData.edit_metadata_value()`` or ``MetaData.delete_metadata_field()``,
although this will create a new entry in the item's kimprovenance.edn file that tracks the
history of updates to the item.

::

        test_metadata = metadata.MetaData(
            repository=cf.LOCAL_REPOSITORY_PATH,
            kimcode="example_model__MO_123456789101_000",
        )

        test_metadata.edit_metadata_value(
            "description",
            "updated description string.",
            provenance_comments="edited description",
        )

When creating a new **KIMkit** item from an existing item's content, either via
``models.version_update()`` or ``models.fork()``, the new item's metadata will be populated based
on the metadata of the existing item via ``create_new_metadata_from_existing()``. This function 
performs the same checks for structure and type as ``create_metadata()``, but also takes an 
optional dictionary of metadata values, which will either be set or overwritten for the new item
if they are different from its parent item.

Finally, this module implements several functions to allow **KIMkit** Editors to configure the 
global metadata standard for this installation of **KIMkit**. There are two types of metadata 
fields: Required, which all items of a given type must have set, and Optional, which items of
a given type may specify. 

The rationale of the functions managing the metadata standard is that **KIMkit** item types
may have new Optional metadata fields specified via ``add_optional_metadata_key()``.
If every item of a given type has an Optional metadata field set, the Optional field may be made 
Required via ``make_optional_key_required()``. Similarly, ``make_required_key_optional()`` 
can demote a Required metadata field to Optional, and finally ``delete_optional_metadata_key()`` 
can remove an optional field completely.

Required keys are not set or deleted directly, but must be made Optional first to avoid the issue
where previously imported items may not have the new Required key set,
or similarly when deleting a Required key, needing to remove that metadata field from all items 
immediately. By passing through Optional first, **KIMkit** Editors can perform metadata updates to
add/remove keys as needed while items are allowed to specify the key, but not required to.

NOTE: metadata fields that are neither Required or Optional are simply ignored, and not recorded,
so if an optional key is deleted it may still be set for some items, but the next time their 
metadata is updated it will be unset.
"""

import datetime
from pytz import timezone
import os
import warnings
import kim_edn
import stat
from collections import OrderedDict

from . import users
from . import models
from .src import provenance
from .src import config as cf
from .src import logger
from .src.logger import logging
from .src import mongodb
from . import kimcodes

central = timezone("US/Central")

logger = logging.getLogger("KIMkit")


class MetaData:
    "Metadata class for KIMkit items"

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

        dest_file = os.path.join(dest_path, cf.CONFIG_FILE)

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
        if users.is_user(username=this_user):
            UUID = users.get_user_info(username=this_user)["uuid"]
        else:
            raise cf.KIMkitUserNotFoundError(
                "Only KIMkit users can edit metadata of items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
            )

        (
            kimspec_order,
            kimspec_strings,
            kimspec_uuid_fields,
            kimspec_arrays,
            kimspec_arrays_dicts,
            KIMkit_item_type_key_requirements,
        ) = _read_metadata_config()

        if key not in kimspec_order:
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
            metadata_dict[key] = new_value

            _write_metadata_to_file(
                metadata_dict["extended-id"], metadata_dict, self.repository
            )
            event_type = "metadata-update"

            dest_dir = kimcodes.kimcode_to_file_path(
                metadata_dict["extended-id"], self.repository
            )

            provenance.add_kimprovenance_entry(
                dest_dir,
                user_id=UUID,
                event_type=event_type,
                comment=provenance_comments,
            )
            logger.info(
                f"User {UUID} updated metadata field '{key}' of item {kimcode} in repository {self.repository} from '{metadata_dict[key]}' to '{new_value}'"
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
        if users.is_user(username=this_user):
            UUID = users.get_user_info(username=this_user)["uuid"]
        else:
            raise cf.KIMkitUserNotFoundError(
                "Only KIMkit users can edit metadata of items. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
            )

        (
            kimspec_order,
            kimspec_strings,
            kimspec_uuid_fields,
            kimspec_arrays,
            kimspec_arrays_dicts,
            KIMkit_item_type_key_requirements,
        ) = _read_metadata_config()

        if field not in kimspec_order:
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
            removed_val = metadata_dict.pop(field, None)

            if removed_val == None:
                warnings.warn(
                    f"Metadata field {field} not specified for this item"
                    + getattr(self, "extended-id")
                    + ", ignoring."
                )
                return

            _write_metadata_to_file(
                metadata_dict["extended-id"], metadata_dict, self.repository
            )
            event_type = "metadata-update"

            dest_dir = kimcodes.kimcode_to_file_path(
                metadata_dict["extended-id"], self.repository
            )
            provenance.add_kimprovenance_entry(
                dest_dir,
                user_id=UUID,
                event_type=event_type,
                comment=provenance_comments,
            )
            logger.info(
                f"User {UUID} deleted metadata field '{field}' of item {kimcode} in repository {self.repository}"
            )

        else:
            logger.warning(
                f"User {UUID} attempted to delete metadata field {field} of item {kimcode} in repository {self.repository} without editor privleges"
            )
            raise cf.NotAnEditorError(
                "Only KIMkit Editors may delete metadata fields of items they are not the contributor or maintainer of."
            )


def create_metadata(
    kimcode,
    metadata_dict,
    UUID=None,
    repository=cf.LOCAL_REPOSITORY_PATH,
    external_path=None,
):
    """Create a kimspec.edn metadata file for a new KIMkit item.

    _extended_summary_

    Parameters
    ----------
    kimcode : str
        id code of the item for which metadata is being created
    metadata_dict : dict
        dict of all required and any optional metadata keys
    UUID : str
        id number of the user or entity requesting the item's creation in UUID format
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY

    Returns
    -------
    MetaData
        KIMkit metadata object

    Raises
    ------
    InvalidMetadataError
        If the supplied metadata_dict does not conform to the KIMkit standard
    """

    if not UUID:
        try:
            username = users.whoami()
            user_info = users.get_user_info(username=username)
            UUID = user_info.get("uuid")
        except AttributeError:
            raise (
                cf.KIMkitUserNotFoundError(
                    "Only KIMkit users can create metadata. Please add yourself as a KIMkit user (users.add_self_as_user('Your Name')) before trying again."
                )
            )

    metadata_dict["date"] = datetime.datetime.now(central).strftime("%Y-%m-%d %H:%M:%S")
    if not "contributor-id" in metadata_dict:
        metadata_dict["contributor-id"] = UUID
    if not "maintainer-id" in metadata_dict:
        metadata_dict["maintainer-id"] = UUID
    if not "developer" in metadata_dict:
        metadata_dict["developer"] = [UUID]
    metadata_dict["domain"] = "KIMkit"
    metadata_dict["repository"] = repository

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

    _write_metadata_to_file(
        kimcode, metadata_dict, repository=repository, external_path=external_path
    )

    if not external_path:
        new_metadata = MetaData(repository, kimcode)

        logger.debug(
            f"Metadata created for new item {kimcode} in repository {repository}"
        )

        return new_metadata


def _write_metadata_to_file(
    kimcode,
    metadata_dict,
    repository=cf.LOCAL_REPOSITORY_PATH,
    external_path=None,
):
    """Internal function used to write a KIMkit item's metadata to disk
    once its metadata has been validated and created. Also calls methods
    from mongodb to insert or update the item's metadata in the database.

    Parameters
    ----------
    kimcode : str
        ID code of the item that this metadata is being written for
    metadata_dict : dict
        Dictionary of metadata to be written to disk in a kimspec.edn.
        Assumed to have been previously validated by validate_metadata()
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY

    Raises
    ------
    TypeError
        Data type not compatible with .edn format
    KIMkitItemNotFoundError
        No item with kimcode exists in repository
    """

    metadata_dict_sorted = OrderedDict()

    (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    ) = _read_metadata_config()

    for field in kimspec_order:
        if field in metadata_dict:
            metadata_dict_sorted[field] = metadata_dict[field]

    if external_path:
        dest_path = external_path
        os.makedirs(dest_path, exist_ok=True)
    else:
        dest_path = kimcodes.kimcode_to_file_path(kimcode, repository)

    # ignore any umask the user may have set
    oldumask = os.umask(0)

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
            os.path.join(dest_path, cf.CONFIG_FILE),
        )
        # add group read/write/execute permissions
        os.chmod(
            os.path.join(dest_path, cf.CONFIG_FILE),
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IWGRP
            | stat.S_IXGRP,
        )
        if not external_path:
            mongodb.upsert_item(kimcode)

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
    supported_item_types = (
        "portable-model",
        "simulator-model",
        "model-driver",
        "test",
        "test-driver",
        "verification-check",
    )

    (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    ) = _read_metadata_config()

    try:
        kim_item_type = metadata_dict["kim-item-type"]

    except KeyError as e:
        raise cf.MissingRequiredMetadataFieldError(
            f"Required metadata field 'kim-item-type' not specified."
        ) from e

    if kim_item_type not in supported_item_types:
        raise cf.InvalidItemTypeError(
            f"""Item type {kim_item_type} not recognized.
         Valid options include 'portable-model', 'simulator-model', and 'model-driver'."""
        )

    metadata_requirements = KIMkit_item_type_key_requirements[kim_item_type]

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
        metadata_dict = check_metadata_types(metadata_dict)
    except (
        KeyError,
        cf.InvalidItemTypeError,
        TypeError,
        ValueError,
        cf.MissingRequiredMetadataFieldError,
        cf.KIMkitUserNotFoundError,
    ) as e:
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
    TypeError
        Required metadata field that should be str is not
    TypeError
        Metadata field that should be UUID4 is not
    ValueError
        Metadata field that should refer to a valid KIMkit user's UUID4 does not
    TypeError
        Metadata field that should be list of str is not
    TypeError
        Values inside metadata field of type list are not UUIDs
    cf.KIMkitUserNotFoundError
        UUID in metadata field list not recognized as a KIMkit user
    KeyError
        Required key in metadata field of type dict not specified
    TypeError
        Value associated with required key inside metadata field of dict type is not str
    TypeError
        Value associated with optional key inside metadata field of dict type is not str
    TypeError
        Metadata field that should be dict is not
    """
    supported_item_types = (
        "portable-model",
        "simulator-model",
        "model-driver",
        "test",
        "test-driver",
        "verification-check",
    )
    # prefix to indicate that the uuid came from openkim.org
    # and so should not be checked against the list of kimkit users
    uuid_override = "openkim:"

    (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    ) = _read_metadata_config()

    if not kim_item_type:
        try:
            kim_item_type = metadata_dict["kim-item-type"]

        except KeyError as e:
            raise cf.MissingRequiredMetadataFieldError(
                f"Required metadata field 'kim-item-type' not specified."
            ) from e

    if kim_item_type not in supported_item_types:
        raise cf.InvalidItemTypeError(
            f"""Item type '{kim_item_type}' not recognized.
         Valid options include 'portable-model', 'simulator-model', and 'model-driver'."""
        )

    for field in metadata_dict:
        if field in kimspec_strings:
            if isinstance(metadata_dict[field], str):
                pass
            else:
                raise TypeError(
                    f"Required metadata field '{field}' is of incorrect type, must be str."
                )
            if field in kimspec_uuid_fields:
                try:
                    valid_user = users.is_user(uuid=metadata_dict[field])
                except TypeError as e:
                    raise TypeError(f"Metadata field {field} must be a UUID4") from e
                if not valid_user:
                    raise ValueError(
                        f"Metadtata field {field} requires a KIMkit user id in UUID4 format."
                    )
        elif field in kimspec_arrays:
            if kimspec_arrays[field] == "list":
                if isinstance(metadata_dict[field], list):
                    for item in metadata_dict[field]:
                        if isinstance(item, str):
                            pass
                        else:
                            raise TypeError(
                                f"Metadata field {field} must be list of str."
                            )

                        if field in kimspec_uuid_fields:
                            if item[: len(uuid_override)] != uuid_override:
                                if not kimcodes.is_valid_uuid4(item):
                                    raise TypeError(
                                        f"Metadata Field {field} should be a list of UUID4 strings"
                                    )
                            if item[: len(uuid_override)] != uuid_override:
                                if not users.is_user(uuid=item):
                                    raise cf.KIMkitUserNotFoundError(
                                        f"UUID {item} not recognized as a KIMkit user"
                                    )
                else:
                    raise TypeError(
                        f"Metadata field '{field}' is of invalid type, must be '{kimspec_arrays[field]}'."
                    )

            elif kimspec_arrays[field] == "list-dict":
                if isinstance(metadata_dict[field], list):
                    for item in metadata_dict[field]:
                        if isinstance(item, dict):
                            pass
                        else:
                            raise TypeError(
                                f"Metadata field {field} must be list of dicts."
                            )
                    if field in kimspec_arrays_dicts:
                        if kimspec_arrays_dicts[field] is True:
                            for item in metadata_dict[field]:
                                for key in kimspec_arrays_dicts[field]:
                                    try:
                                        value = item[key]
                                    except KeyError as e:
                                        raise KeyError(
                                            f"Required key {key} in metadata field {field} not found"
                                        ) from e
                                    if value and not isinstance(value, str):
                                        raise TypeError(
                                            f"Required key {key} in metadata field {field} must have str value"
                                        )
                        # optional keys are allowed not to exist
                        else:
                            for item in metadata_dict[field]:
                                for key in kimspec_arrays_dicts[field]:
                                    try:
                                        value = item[key]
                                    except KeyError:
                                        pass
                                    if value and not isinstance(value, str):
                                        raise TypeError(
                                            f"Key {key} in metadata field {field} must have str value"
                                        )
                else:
                    raise TypeError(
                        f"Metadata field '{field}' is of invalid type, must be '{kimspec_arrays[field]}'."
                    )
            elif kimspec_arrays[field] == "dict":

                if isinstance(metadata_dict[field], dict):
                    for key in kimspec_arrays_dicts[field]:
                        if kimspec_arrays_dicts[field][key]:
                            try:
                                value = metadata_dict[field][key]
                            except KeyError as e:
                                raise KeyError(
                                    f"Required key {key} in metadata field {field} not found"
                                ) from e
                            if value and not isinstance(value, str):
                                raise TypeError(
                                    f"Required key {key} in metadata field {field} must have str value"
                                )
                        # optional keys are allowed not to exist
                        else:
                            try:
                                value = metadata_dict[field][key]
                            except KeyError:
                                pass
                            if value and not isinstance(value, str):
                                raise TypeError(
                                    f"Key {key} in metadata field {field} must have str value"
                                )
                else:
                    raise TypeError(
                        f"Metadata field '{field}' is of invalid type, must be '{kimspec_arrays[field]}'."
                    )

                keys_to_remove = []
                for key in metadata_dict[field]:
                    if key not in kimspec_arrays_dicts[field]:
                        keys_to_remove.append(key)
                        warnings.warn(
                            f"Metadata field '{key}' in field {field} not used for kim item type {kim_item_type}, ignoring."
                        )
                for key in keys_to_remove:
                    metadata_dict[field].pop(key, None)

    return metadata_dict


def create_new_metadata_from_existing(
    old_kimcode,
    new_kimcode,
    UUID,
    metadata_update_dict=None,
    repository=cf.LOCAL_REPOSITORY_PATH,
):
    """Create a new metadata object from an existing kimspec.edn, and any modifications

    Reads an existing kimspec.edn, creates a new metadata object for a new item based on it,
    incorporating any edits specified in metadata_dict.

    Parameters
    ----------
    old_kimcode : str
        kimcode of the parent item
    new_kimcode : str
        kimcode of the newly created item
    UUID : str
        id number of the user or entity making the update in UUID4 format
    metadata_update_dict : dict, optional
        dict of any metadata fields to be changed/assigned, by default None
    repository : path-like, optional
        root directory of the KIMkit repo containing the item,
        by default cf.LOCAL_REPOSITORY_DIRECTORY

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

    old_metadata = MetaData(repository, old_kimcode)
    old_metadata_dict = vars(old_metadata)

    # # repository is useful as a Metadata object instance attribute, but isn't a metadata field
    # if "repository" in old_metadata_dict:
    #     del old_metadata_dict["repository"]

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
    _write_metadata_to_file(new_kimcode, valid_metadata, repository=repository)
    new_metadata = MetaData(repository, new_kimcode)
    logger.debug(
        f"Metadata for new item {new_kimcode} created from metadata of {old_kimcode} in {repository}"
    )
    return new_metadata


def create_kimkit_metadata_from_openkim_kimspec(kimspec_file, UUID):

    openkim_metadata = kim_edn.load(kimspec_file)

    kimcode = openkim_metadata["extended-id"]

    leader = kimcodes.get_leader(kimcode)

    if leader == "MO":
        item_type = "portable-model"
    elif leader == "MD":
        item_type = "model-driver"
    elif leader == "SM":
        item_type = "simulator-model"
    elif leader == "TE":
        item_type = "test"
    elif leader == "TD":
        item_type = "test-driver"
    elif leader == "VC":
        item_type = "verification-check"

    openkim_metadata["kim-item-type"] = item_type

    openkim_metadata["contributor-id"] = UUID
    openkim_metadata["maintainer-id"] = UUID

    if "developer" in openkim_metadata:
        for i, uuid in enumerate(openkim_metadata["developer"]):
            new_uuid = "openkim:" + uuid
            openkim_metadata["developer"][i] = new_uuid

    if "implementer" in openkim_metadata:
        for i, uuid in enumerate(openkim_metadata["implementer"]):
            new_uuid = "openkim:" + uuid
            openkim_metadata["implementer"][i] = new_uuid

    return openkim_metadata


def _read_metadata_config():
    """Read in the metadata configuration spec from
    metadata_config.edn, stored in the KIMkit install directory.

    Returns
    -------
    list, list, list, dict, dict, dict
        6 arrays containing metadata configuration information, including:

        kimspec_order: ordering of kimspec keys (currently just alphabetical)
        kimspec_strings: list of string-valued keys
        kimspec_uuid_fields: subset of string-valued keys that must be UUID4 in hex
        kimspec_arrays: dict of array-valued keys, with the values being strings specifying the type of array
        kimspec_arrays_dicts: dict of inner keys in dict-valued metadata fields,
            where the values are booleans specifying whether the inner key is required
        KIMkit_item_type_key_requirements: dict where the top level keys are KIMkit item types,
            under each are 2 inner keys, "required" and "optional", whose values are lists of
            metadata fields that are Required or Optional for the specified item type.
    """

    with open(cf.KIMKIT_METADATA_CONFIG_FILE, "r") as configfile:
        config = kim_edn.load(configfile)
        kimspec_order = config["kimspec-order"]
        kimspec_strings = config["kimspec-strings"]
        kimspec_uuid_fields = config["kimspec-uuid-fields"]
        kimspec_arrays = config["kimspec-arrays"]
        kimspec_arrays_dicts = config["kimspec-arrays-dicts"]
        KIMkit_item_type_key_requirements = config["KIMkit-item-type-key-requirements"]

    return (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    )


def get_metadata_template_for_item_type(item_type):
    """Return a template for the metadata fields needed
    to create a KIMkit item of a given type.

    Item types may be specified with their full name,
    or their 2 letter leader code found in their kimcode.

    Args:
        item_type (str): type of KIMkit item to generate
        metadata template for
    Returns:
        dict of required/optional metadata fields for the item type.
        Top level keys are "required" and "optional"
        under each key are subkeys for the various metadata
        fields. The values associated with these are lists of strings specifying
        what data types they should be, and for certain conditionally required keys
        that are added by KIMkit if they are not specifed at item creation.
    """

    item_type = item_type.lower()

    (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    ) = _read_metadata_config()

    all_item_types = KIMkit_item_type_key_requirements.keys()

    if item_type not in all_item_types:
        # include item type short codes
        item_type_short_codes = ["mo", "sm", "md", "te", "td", "vc"]

        if item_type in item_type_short_codes:
            if item_type == "mo":
                item_type = "portable-model"
            elif item_type == "sm":
                item_type = "simulator-model"
            elif item_type == "md":
                item_type = "model-driver"
            elif item_type == "te":
                item_type = "test"
            elif item_type == "td":
                item_type = "test"
            elif item_type == "vc":
                item_type = "verification-check"
        else:
            raise cf.InvalidItemTypeError(
                f"Item type {item_type} not recognized, aborting."
            )

    metadata_template = KIMkit_item_type_key_requirements[item_type]

    extended_metadata_template = {}

    automatically_added_fields = [
        "developer",
        "contributor-id",
        "maintainer-id",
        "date",
        "domain",
        "repository",
    ]

    for key in metadata_template:
        extended_metadata_template[key] = {}
        for subkey in metadata_template[key]:
            type_value = []
            if subkey in kimspec_strings:
                type_value.append("str")

            elif subkey in kimspec_arrays:
                type_value.append(kimspec_arrays[subkey])

            if subkey in kimspec_uuid_fields:
                type_value.append("UUID4")

            if subkey in automatically_added_fields:
                type_value.append("conditionally-required")

            extended_metadata_template[key][subkey] = type_value

    return extended_metadata_template


def add_optional_metadata_key(
    key_name,
    item_types,
    value_type,
    is_uuid=False,
    dict_key_requirements=None,
    run_as_editor=False,
):
    """Add a new, Optional, metadata field for one or more KIMkit item types

    Requires Editor privleges.

    Parameters
    ----------
    key_name : str
        name of the new metadata key
    item_types : list of str
        types of KIMkit items this key can be set for, valid options include
        "portable-model", "simulator-model", and "model-driver"
    value_type : str
       type of the new key, valid options include:
        "str","list",and "dict"
    is_uuid : bool, optional
        if the metadata field's value_type is "str", is this field also a UUID?, by default False
    dict_key_requirements : dict, optional
        if the metadata field's value_type is "dict", you must provide a dict
        who's keys are the keys of the new metadata field,
        and who's values are bools specifying whether a given key is required,
        by default None
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions,
        and edit the metadata spec, by default False
    """

    def _verify_dict_key_requirements(req_dict):
        """Verify the inner structure of the dict
        of key requirements for dict-valued metadata fields

        Parameters
        ----------
        req_dict : dict
            dictwho's keys are the keys of the new metadata field,
        and who's values are bools specifying whether a given key is required

        Raises
        ------
        TypeError
            If types of values are not bool
        TypeError
            If req_dict itself is not a dict
        """
        if isinstance(req_dict, dict):
            for key in req_dict:
                if not isinstance(req_dict[key], bool):
                    raise TypeError("Values must be bool")
        else:
            raise TypeError("Item Must be a dict")

    if users.is_editor():
        if not run_as_editor:
            raise cf.NotRunAsEditorError(
                "Did you mean to edit the metadata config? If you are an Editor run again with run_as_editor=True"
            )
        (
            kimspec_order,
            kimspec_strings,
            kimspec_uuid_fields,
            kimspec_arrays,
            kimspec_arrays_dicts,
            KIMkit_item_type_key_requirements,
        ) = _read_metadata_config()

        all_item_types = KIMkit_item_type_key_requirements.keys()

        for item in item_types:
            if item not in all_item_types:
                raise cf.InvalidItemTypeError(
                    f"Item type {item} not recognized, aborting."
                )

        if value_type == "dict":
            if not dict_key_requirements:
                raise ValueError(
                    """When adding a new metadata field of type 'dict',you must provide a dict
        who's keys are the keys of the new metadata field,
        and who's values are bools specifying whether a given key is required"""
                )
            _verify_dict_key_requirements(dict_key_requirements)

            kimspec_arrays[key_name] = "dict"
            kimspec_arrays_dicts[key_name] = dict_key_requirements

        elif value_type == "list":
            kimspec_arrays[key_name] = "list"

        elif value_type == "str":
            kimspec_strings.append(key_name)
            if is_uuid:
                kimspec_uuid_fields.append(key_name)

        kimspec_order.append(key_name)
        kimspec_order.sort()

        for item in item_types:
            KIMkit_item_type_key_requirements[item]["optional"].append(key_name)

        final_dict = {
            "kimspec-order": kimspec_order,
            "kimspec-strings": kimspec_strings,
            "kimspec-uuid-fields": kimspec_uuid_fields,
            "kimspec-arrays": kimspec_arrays,
            "kimspec-arrays-dicts": kimspec_arrays_dicts,
            "KIMkit-item-type-key-requirements": KIMkit_item_type_key_requirements,
        }

        tmp_dest_file = os.path.join(
            cf.KIMKIT_SETTINGS_DIRECTORY, "tmp_metadata_config.edn"
        )
        # ignore any umask the user may have set
        oldumask = os.umask(0)
        with open(tmp_dest_file, "w") as outfile:
            comment = _return_metadata_config_preamble()
            outfile.writelines(comment)
            kim_edn.dump(final_dict, outfile, indent=4)

        dest_file = cf.KIMKIT_METADATA_CONFIG_FILE
        os.rename(tmp_dest_file, dest_file)
        # add group read/write/execute permissions
        os.chmod(
            dest_file,
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IWGRP
            | stat.S_IXGRP,
        )
        id = users.whoami()
        logger.info(
            f"User {id} added field {key_name} as an Optional key of type {value_type} to {item_types}"
        )
        # return user's original usmask
        os.umask(oldumask)

    else:
        id = users.whoami()
        logger.warning(
            f"User {id} attempted to add a new metadata key without editor privleges."
        )
        raise cf.NotAnEditorError(
            "Only KIMkit Editors may change metadata configuration settings"
        )


def delete_optional_metadata_key(
    key_name,
    item_types,
    repository=cf.LOCAL_REPOSITORY_PATH,
    run_as_editor=False,
    inline_delete=False,
):
    """Delete an optional metadata key from the spec

    Requires Editor privleges.

    NOTE: Deleting a key from the metadata spec won't immediately
    delete it out of all item's kimspec.edn, but when those items are
    subsequently edited or updated, keys not in the specification will
    be ignored and not copied to descendant items.

    Parameters
    ----------
    key_name : str
        name of the new metadata key
    item_types : list of str
        types of KIMkit items to delete this key from, valid options include
        "portable-model", "simulator-model", and "model-driver"
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions,
        and edit the metadata spec, by default False
    inline_delete : bool, optional
        flag to immediately delete depricated keys from items with them set,
        by default False

    Returns
    --------
    list
        list of kimcodes with depricated keys, which either had them deleted
        if inline_delete=True, or need to have them deleted otherwise.
    """
    (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    ) = _read_metadata_config()

    if key_name not in kimspec_order:
        raise cf.InvalidMetadataFieldError(
            f"Field {key_name} not recognized as a part of the KIMkit metadata standard, aborting."
        )

    all_item_types = KIMkit_item_type_key_requirements.keys()

    for item in item_types:
        if item not in all_item_types:
            raise cf.InvalidItemTypeError(f"Item type {item} not recognized, aborting.")

    id = users.whoami()
    UUID = users.get_user_info(username=id)["uuid"]

    if users.is_editor():
        if not run_as_editor:
            raise cf.NotRunAsEditorError(
                "Did you mean to edit the metadata config? If you are an Editor run again with run_as_editor=True"
            )
        # remove this key from the optional key list for the specified item types
        for item in item_types:
            KIMkit_item_type_key_requirements[item]["optional"].remove(key_name)

        id = users.whoami()
        logger.info(
            f"Editor {id} deleted optional metadata field {key_name} from item types {item_types}."
        )

        # check whether any item types still have this key specified
        key_set = False

        for item in all_item_types:
            if key_name in KIMkit_item_type_key_requirements[item]["optional"]:
                key_set = True

            # safety check, shouldn't be possible
            elif key_name in KIMkit_item_type_key_requirements[item]["required"]:
                key_set = True

        # if this key is not set for any item, delete it from the metadata standard completely
        if key_set == False:
            lists = [kimspec_order, kimspec_strings, kimspec_uuid_fields]
            dicts = [kimspec_arrays, kimspec_arrays_dicts]

            for l in lists:
                if key_name in l:
                    l.remove(key_name)

            for d in dicts:
                d.pop(key_name, None)

            logger.info(
                f"Optional metadata field {key_name} not set for any item types, deleting from the standard."
            )

        final_dict = {
            "kimspec-order": kimspec_order,
            "kimspec-strings": kimspec_strings,
            "kimspec-uuid-fields": kimspec_uuid_fields,
            "kimspec-arrays": kimspec_arrays,
            "kimspec-arrays-dicts": kimspec_arrays_dicts,
            "KIMkit-item-type-key-requirements": KIMkit_item_type_key_requirements,
        }

        tmp_dest_file = os.path.join(
            cf.KIMKIT_SETTINGS_DIRECTORY, "tmp_metadata_config.edn"
        )
        # ignore any umask the user may have set
        oldumask = os.umask(0)
        with open(tmp_dest_file, "w") as outfile:
            comment = _return_metadata_config_preamble()
            outfile.writelines(comment)
            kim_edn.dump(final_dict, outfile, indent=4)

        dest_file = cf.KIMKIT_METADATA_CONFIG_FILE
        os.rename(tmp_dest_file, dest_file)

        # add group read/write/execute permissions
        os.chmod(
            dest_file,
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IWGRP
            | stat.S_IXGRP,
        )
        # return user's original usmask
        os.umask(oldumask)
        # run a query to retrieve any current items without the specified key set.
        query_results = []
        for item_type in item_types:
            res = mongodb.query_item_database(
                {key_name: {"$exists": True}, "kim-item-type": item_type},
                projection={"extended-id": 1, "_id": 0},
            )
            query_results.extend(res)

        items_needing_delete = []
        for i in query_results:
            items_needing_delete.append(i.get("extended-id", None))

        if inline_delete:

            for kimcode in items_needing_delete:
                create_new_metadata_from_existing(kimcode, kimcode, UUID)

                logger.info(
                    f"user {id} deleted metadata field {key_name} from item {kimcode}"
                )

        return items_needing_delete

    else:
        logger.warning(
            f"User {id} attempted to delete metadata field {key_name} without editor privleges."
        )
        raise cf.NotAnEditorError(
            "Only KIMkit Editors may change metadata configuration settings"
        )


def make_optional_metadata_key_required(key_name, item_types, run_as_editor=False):
    """Promote an optional metadata field from Optional to Required
    for a certian class of items

    Requires Editor privleges.

    NOTE: Can only promote a metadata field to Required if all relevant
    items already have that field specified, or items may be left
    with invalid metadata. If items without a field are present, this function will
    do nothing and return a list of their kimcodes.

    Parameters
    ----------
    key_name : str
        name of the new metadata key
    item_types : list of str
        types of KIMkit items to make this key required for for, valid options include
        "portable-model", "simulator-model", and "model-driver"
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions,
        and edit the metadata spec, by default False

    Returns
    -------
    list
        list of kimcodes of items without the key to be made required
    """
    (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    ) = _read_metadata_config()

    if key_name not in kimspec_order:
        raise cf.InvalidMetadataFieldError(
            f"Field {key_name} not recognized as a part of the KIMkit metadata standard, aborting."
        )

    all_item_types = KIMkit_item_type_key_requirements.keys()

    for item in item_types:
        if item not in all_item_types:
            raise cf.InvalidItemTypeError(f"Item type {item} not recognized, aborting.")

    # run a query to retrieve any current items without the specified key set.
    query_results = []
    for item_type in item_types:
        res = mongodb.query_item_database(
            {key_name: {"$exists": False}, "kim-item-type": item_type},
            projection={"extended-id": 1, "_id": 0},
        )
        query_results.extend(res)

    if len(query_results) == 0:
        if users.is_editor():
            if not run_as_editor:
                raise cf.NotRunAsEditorError(
                    "Did you mean to edit the metadata config? If you are an Editor run again with run_as_editor=True"
                )

            for item in item_types:
                KIMkit_item_type_key_requirements[item]["optional"].remove(key_name)
                KIMkit_item_type_key_requirements[item]["required"].append(key_name)

            final_dict = {
                "kimspec-order": kimspec_order,
                "kimspec-strings": kimspec_strings,
                "kimspec-uuid-fields": kimspec_uuid_fields,
                "kimspec-arrays": kimspec_arrays,
                "kimspec-arrays-dicts": kimspec_arrays_dicts,
                "KIMkit-item-type-key-requirements": KIMkit_item_type_key_requirements,
            }
            # ignore any umask the user may have set
            oldumask = os.umask(0)
            tmp_dest_file = os.path.join(
                cf.KIMKIT_SETTINGS_DIRECTORY, "tmp_metadata_config.edn"
            )

            with open(tmp_dest_file, "w") as outfile:
                comment = _return_metadata_config_preamble()
                outfile.writelines(comment)
                kim_edn.dump(final_dict, outfile, indent=4)

            dest_file = cf.KIMKIT_METADATA_CONFIG_FILE
            os.rename(tmp_dest_file, dest_file)

            # add group read/write/execute permissions
            os.chmod(
                dest_file,
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IWGRP
                | stat.S_IXGRP,
            )
            # return user's original usmask
            os.umask(oldumask)
            id = users.whoami()
            logger.info(
                f"User {id} modified metadata field {key_name} to be Required instead of Optional for types {item_types}"
            )

            return []

        else:
            id = users.whoami()
            logger.warning(
                f"User {id} attempted to make {key_name} Required without editor privleges."
            )
            raise cf.NotAnEditorError(
                "Only KIMkit Editors may change metadata configuration settings"
            )

    else:
        warnings.warn(f"Items missing key {key_name}, cannot make required:")
        items_needing_key = []
        for i in query_results:
            items_needing_key.append(i.get("extended-id", None))
        return items_needing_key


def make_required_metadata_key_optional(key_name, item_types, run_as_editor=False):
    """Demote a metadata field from Required to Optional for one or more KIMkit item types

    Requires Editor privleges.

    Parameters
    ----------
    key_name : str
        name of the new metadata key
    item_types : list of str
        types of KIMkit items to make this key optional for, valid options include
        "portable-model", "simulator-model", and "model-driver"
    run_as_editor : bool, optional
        flag to be used by KIMkit Editors to run with elevated permissions,
        and edit the metadata spec, by default False
    """

    (
        kimspec_order,
        kimspec_strings,
        kimspec_uuid_fields,
        kimspec_arrays,
        kimspec_arrays_dicts,
        KIMkit_item_type_key_requirements,
    ) = _read_metadata_config()

    if key_name not in kimspec_order:
        raise cf.InvalidMetadataFieldError(
            f"Field {key_name} not recognized as a part of the KIMkit metadata standard, aborting."
        )

    all_item_types = KIMkit_item_type_key_requirements.keys()

    for item in item_types:
        if item not in all_item_types:
            raise cf.InvalidItemTypeError(f"Item type {item} not recognized, aborting.")

    if users.is_editor():
        if not run_as_editor:
            raise cf.NotRunAsEditorError(
                "Did you mean to edit the metadata config? If you are an Editor run again with run_as_editor=True"
            )

        for item in item_types:
            KIMkit_item_type_key_requirements[item]["required"].remove(key_name)
            KIMkit_item_type_key_requirements[item]["optional"].append(key_name)

        final_dict = {
            "kimspec-order": kimspec_order,
            "kimspec-strings": kimspec_strings,
            "kimspec-uuid-fields": kimspec_uuid_fields,
            "kimspec-arrays": kimspec_arrays,
            "kimspec-arrays-dicts": kimspec_arrays_dicts,
            "KIMkit-item-type-key-requirements": KIMkit_item_type_key_requirements,
        }
        # ignore any umask the user may have set
        oldumask = os.umask(0)
        tmp_dest_file = os.path.join(
            cf.KIMKIT_SETTINGS_DIRECTORY, "tmp_metadata_config.edn"
        )

        with open(tmp_dest_file, "w") as outfile:
            comment = _return_metadata_config_preamble()
            outfile.writelines(comment)
            kim_edn.dump(final_dict, outfile, indent=4)

        dest_file = cf.KIMKIT_METADATA_CONFIG_FILE
        os.rename(tmp_dest_file, dest_file)
        # add group read/write/execute permissions
        os.chmod(
            dest_file,
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IWGRP
            | stat.S_IXGRP,
        )
        # return user's original usmask
        os.umask(oldumask)
        id = users.whoami()
        logger.info(
            f"User {id} modified metadata field {key_name} to be Optional instead of Required for types {item_types}"
        )

    else:
        id = users.whoami()
        logger.warning(
            f"User {id} attempted to make {key_name} Optional without editor privleges."
        )
        raise cf.NotAnEditorError(
            "Only KIMkit Editors may change metadata configuration settings"
        )


def _return_metadata_config_preamble():
    """Helper function to write the preamble comment to settings/metadata_config.edn"""

    preamble_comment = """; 
; This file contains arrays specifying the metadata standard for this installation of KIMkit. 
;
; The metadata standard may be changed by editing this file, or through the functions 
; add_optional_metadata_key(), delete_optional_metadata_key(), make_optional_metadata_key_required(),
; and make_required_metadata_key_optional() defined in metadata.py. Using the helper functions is preferred,
; as it will check existing items for compliance.
;
; kimspec-order defines the order of metadata fields, alphabetical by default.
; 
; kimspec-strings lists the metadata fields that should be string-valued.
;
; kimspec-uuid-fields lists the subset of string-valued metadata fields that should be UUID4.hex strings.
;
; kimspec-arrays is a dict who's keys are metadata fields that should be array-valued,
;     and its values define which type of array object that field should be.
;
; kimspec-arrays-dicts is a dict of dicts who's top-level keys are metadata fields that should be dict-valued,
;    and who's inner keys are keys those fields may have, and their values are booleans specifying whether
;    they're required or not.
;
; KIMkit-item-type-key-requirements is a dict of dicts who's top level keys are KIMkit item types,
;    the values of each is another dict, who's inner keys of each are "required" and "optional",
;    and the values of those inner dicts list which metadata fields are required or optional
;    for the KIMkit item type.
"""

    return preamble_comment
