"""_summary_
"""
import pprint
import tarfile
import os
import time

import KIMkit.models as models
import KIMkit.metadata as metadata
import KIMkit.users as users
import KIMkit.kimcodes as kimcodes


def test_import_item(test_item_type, test_kimcode, driver_name=None):
    # TODO: move to user testing
    # try:
    #     assert users.is_user(personal_name="test_user") is True
    #     test_uuid = users.get_user_info(personal_name="test_user")["uuid"]
    #     have_test_user = True
    # except AssertionError:
    #     test_uuid = users.add_person("test_user")
    #     assert users.is_user(personal_name="test_user") is True

    # TODO: move to metadata testing
    # template = metadata.get_metadata_template_for_item_type(test_item_type)

    # required_keys = template["required"]

    # mandatory_keys = {}
    # for key in required_keys:
    #     if "conditionally-required" not in required_keys[key]:
    #         mandatory_keys[key] = required_keys[key]

    test_model_metadata = {}

    # fill keys required by all item types with default values
    test_model_metadata["description"] = "Description of a test model."
    test_model_metadata["extended-id"] = test_kimcode
    test_model_metadata["kim-api-version"] = "2.2"
    test_model_metadata["kim-item-type"] = test_item_type
    test_model_metadata["title"] = "Title of a test model"

    # add metadata required by all model types
    if test_item_type != "model-driver":
        test_model_metadata["potential-type"] = "meam"
        test_model_metadata["species"] = ["Su"]

    if test_item_type == "simulator-model":
        test_model_metadata["simulator-name"] = "LAMMPS"
        test_model_metadata["simulator-potential"] = "meam"

    elif test_item_type == "portable-model":
        test_model_metadata["model-driver"] = str(driver_name)

    dirname = os.path.dirname(__file__)
    test_tarfile_path = os.path.join(dirname, "test_model.txz")

    with tarfile.open(test_tarfile_path) as test_tarfile:
        models.import_item(
            test_tarfile, test_model_metadata, previous_item_name="test_model"
        )


def test_version_update(test_kimcode):
    test_item_path = kimcodes.kimcode_to_file_path(test_kimcode)

    dirname = os.path.dirname(__file__)

    # generate a tarfile of content from the previous version
    # KIMkit doesn't generally inspect file contents so its moot
    # except that version update and fork attempt to edit kimcodes in makefiles and metadata
    with tarfile.open(
        os.path.join(dirname, test_kimcode + ".txz"), "w:xz"
    ) as test_update_tarfile:
        test_update_tarfile.add(test_item_path, arcname=test_kimcode)


def test_fork():
    pass


def test_install():
    pass


def test_delete(test_kimcode):
    models.delete(test_kimcode)


def test_models():
    test_name = "KIMkit_example_Su_2024"
    test_item_type1 = "simulator-model"

    test_sm_kimcode = kimcodes.generate_kimcode(
        name=test_name, item_type=test_item_type1
    )

    assert kimcodes.isextendedkimid(test_sm_kimcode) is True

    test_import_item(test_item_type1, test_sm_kimcode)
    test_delete(test_sm_kimcode)

    test_item_type2 = "model-driver"

    test_md_kimcode = kimcodes.generate_kimcode(
        name=test_name, item_type=test_item_type2
    )

    assert kimcodes.isextendedkimid(test_md_kimcode) is True

    test_import_item(test_item_type2, test_md_kimcode)

    test_item_type3 = "portable-model"

    test_mo_kimcode = kimcodes.generate_kimcode(
        name=test_name, item_type=test_item_type3
    )

    assert kimcodes.isextendedkimid(test_mo_kimcode) is True

    test_import_item(test_item_type3, test_mo_kimcode, driver_name=test_md_kimcode)
