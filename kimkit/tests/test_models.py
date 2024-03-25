"""Initial unit testing framework for KIMkit. To run, simply call with test_models().
"""

import pprint
import tarfile
import os
import shutil
import time

import kimkit.models as models
import kimkit.metadata as metadata
import kimkit.users as users
import kimkit.kimcodes as kimcodes
import kimkit.src.config as cf

EXAMPLE_MO_KIMCODE = "EAM_Dynamo_AcklandTichyVitek_1987_Ag__MO_212700056563_005"
EXAMPLE_MD_KIMCODE = "EAM_Dynamo__MD_120291908751_005"


def test_import_item(test_item_type, test_kimcode, previous_name, driver_name=None):

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
    test_tarfile_path = os.path.join(dirname, previous_name + ".txz")

    with tarfile.open(test_tarfile_path) as test_tarfile:
        models.import_item(
            test_tarfile, test_model_metadata, previous_item_name=previous_name
        )


def test_version_update(test_kimcode):
    dirname = os.path.dirname(__file__)
    test_tarfile_path = os.path.join(dirname, EXAMPLE_MO_KIMCODE + ".txz")

    with tarfile.open(test_tarfile_path) as test_tarfile:

        update_dict = {"description": "updated test model version description"}

        comment = "test version update"

        models.version_update(
            test_kimcode,
            test_tarfile,
            metadata_update_dict=update_dict,
            provenance_comments=comment,
        )

        name, leader, num, ver = kimcodes.parse_kim_code(test_kimcode)
        ver = int(ver)
        ver = ver + 1
        ver = str(ver)
        ver = "00" + ver
        new_kimcode = kimcodes.format_kim_code(name, leader, num, ver)

        models.update_makefile_kimcode(EXAMPLE_MO_KIMCODE, new_kimcode)


def test_fork(test_kimcode, new_test_kimcode):
    dirname = os.path.dirname(__file__)
    test_tarfile_path = os.path.join(dirname, EXAMPLE_MO_KIMCODE + ".txz")

    with tarfile.open(test_tarfile_path) as test_tarfile:

        update_dict = {"description": "forked test model description"}

        comment = "test fork"

        models.fork(
            test_kimcode,
            new_test_kimcode,
            test_tarfile,
            metadata_update_dict=update_dict,
            provenance_comments=comment,
        )

        models.update_makefile_kimcode(EXAMPLE_MO_KIMCODE, new_test_kimcode)


def test_delete(test_kimcode):
    models.delete(test_kimcode)


def test_models():
    test_name = "KIMkit_example_Su_2024"

    test_item_type2 = "model-driver"

    test_md_kimcode = kimcodes.generate_kimcode(
        name=test_name, item_type=test_item_type2
    )

    assert kimcodes.isextendedkimid(test_md_kimcode) is True

    test_import_item(
        test_item_type2, test_md_kimcode, "EAM_Dynamo__MD_120291908751_005"
    )

    test_item_type3 = "portable-model"

    test_mo_kimcode = kimcodes.generate_kimcode(
        name=test_name, item_type=test_item_type3
    )

    assert kimcodes.isextendedkimid(test_mo_kimcode) is True

    try:
        test_import_item(
            test_item_type3,
            test_mo_kimcode,
            "EAM_Dynamo_AcklandTichyVitek_1987_Ag__MO_212700056563_005",
            driver_name=test_md_kimcode,
            workflow_tarfile="workflow_test.txz",
        )
    except TypeError:

        test_import_item(
            test_item_type3,
            test_mo_kimcode,
            "EAM_Dynamo_AcklandTichyVitek_1987_Ag__MO_212700056563_005",
            driver_name=test_md_kimcode,
        )

    test_version_update(test_mo_kimcode)

    name, leader, num, __ = kimcodes.parse_kim_code(test_mo_kimcode)
    new_version = "001"

    updated_kimcode = kimcodes.format_kim_code(name, leader, num, new_version)

    fork_kimcode = kimcodes.generate_kimcode(name=test_name, item_type=test_item_type3)

    test_fork(test_mo_kimcode, fork_kimcode)

    models.delete(fork_kimcode)
    models.delete(updated_kimcode)
    models.delete(test_mo_kimcode)
    models.delete(test_md_kimcode)


test_models()
