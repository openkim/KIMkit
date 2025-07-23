"""Methods for managing KIMkit metadata and user data stored in a MongoDB database.

KIMkit uses two main collections in the database, "items" and "users". "users" only
stores personal names, operating system usernames, and a UUID4 that is the unique
ID for each user.

"items" stores all metadata fields associated with KIMkit items, to enable users
to easily query for subsets of items with various properties.
    """

import pymongo
import os
import datetime
import re
import kim_edn
import numpy as np

from . import kimobjects
from . import config as cf
from .logger import logging

from .. import kimcodes
from .. import users
from .. import models

logger = logging.getLogger("KIMkit")

client = pymongo.MongoClient(host=cf.MONGODB_HOSTNAME)
db = client[cf.MONGODB_DATABASE]

BADKEYS = {"kimspec", "profiling", "inserted_on", "latest"}


def kimcode_to_dict(kimcode, repository=cf.LOCAL_REPOSITORY_PATH):
    """Read metadata from an item's kimspec.edn, and createa a
    dictionary from it with the correct formatting to be inserted
    into mongodb.

    Parameters
    ----------
    kimcode : str
        id code of the item
    repository : path like, optional
        root of path on disk where the item is stored, by default cf.LOCAL_REPOSITORY_PATH

    Returns
    -------
    dict
        key-value pairs in the order and formatting specified by the metadata standard.

    Raises
    ------
    cf.InvalidKIMCode
        supplied kimcode does not conform to the standard
    """
    if kimcodes.isextendedkimid(kimcode):
        name, leader, num, version = kimcodes.parse_kim_code(kimcode)
    else:
        raise cf.InvalidKIMCode(
            "Received {} for insertion into mongo db. Only full extended KIM "
            "IDs (with version) are supported".format(kimcode)
        )

    extended_id = None
    short_id = None
    m = re.search("(.+)__([A-Z]{2}_\\{12}_\\{3})$", kimcode)
    if m:
        extended_id = kimcode
        short_id = m.group(2)
    else:
        short_id = kimcode

    foo = {}
    if extended_id:
        foo["extended-id"] = extended_id
    foo["short-id"] = short_id
    if extended_id:
        foo["kimid-prefix"] = name
    foo["kimid-typecode"] = leader.lower()
    foo["kimid-number"] = num
    foo["kimid-version"] = version
    foo["kimid-version-as-integer"] = int(version)
    foo["name"] = name
    foo["type"] = leader.lower()
    foo["kimnum"] = num
    foo["version"] = int(version)
    foo["shortcode"] = "_".join((leader.upper(), num))
    foo["kimcode"] = kimcode
    foo["_id"] = kimcode
    foo["inserted_on"] = str(datetime.datetime.utcnow())
    foo["latest"] = True
    foo["repository"] = repository

    if foo["type"] in ("te", "mo", "sm", "td", "md", "vc"):
        foo["makeable"] = True
    if foo["type"] in ("te", "vc"):
        foo["runner"] = True
    if foo["type"] in ("sm", "mo"):
        foo["subject"] = True
    if foo["type"] in ("md", "td"):
        foo["driver"] = True
    else:
        foo["driver"] = False

    src_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    specpath = os.path.join(src_dir, cf.CONFIG_FILE)
    with open(specpath, "r") as specfile:
        spec = kim_edn.load(specfile)

    if foo["type"] == "te":
        # Fetch Test Driver, if any, from kimspec dict we loaded
        testresult = spec.get("test-driver", None)
        if testresult:
            foo["driver"] = rmbadkeys(kimcode_to_dict(testresult))

        # Fetch list of Tests in dependencies.edn, if it exists
        kobj = models.Test(repository=repository, kimcode=kimcode)
        foo["dependencies"] = kobj.runtime_dependencies()

    if foo["type"] == "mo":
        modeldriver = spec.get("model-driver", None)
        if modeldriver:
            # handle portable models without drivers
            if kimcodes.iskimid(modeldriver):
                foo["driver"] = rmbadkeys(kimcode_to_dict(modeldriver))
            else:
                foo["driver"] = modeldriver

    foo.update(spec)
    return foo


def insert_item(kimcode):
    """Create a mongodb entry for a new KIMkit item
    by reading its metadata from its kimspec.edn,
    and insert it into the database.

    Parameters
    ----------
    kimcode : str
        id code of the item
    """
    logger.info("Inserting item %s into mongodb", kimcode)

    info = kimcode_to_dict(kimcode)

    try:
        db.items.insert_one(info)
        set_latest_version_object(info["kimid-number"])
    except:
        logger.error("Already have %s", kimcode)


def update_item(kimcode):
    """Update the db entry of this item with
    new metadata read from disc.

    Additionally, if the item being updated is a driver,
    update all the items that use the driver, since they
    have a copy of the driver's db entry in their own entries.

    Parameters
    ----------
    kimcode : str
        id code of the item
    """
    logger.info("Updating metadata of item %s", kimcode)

    info = rmbadkeys(kimcode_to_dict(kimcode))

    info.pop("_id", None)

    __, __, num, __ = kimcodes.parse_kim_code(kimcode)

    try:
        db.items.replace_one({"kimcode": kimcode}, info)
        set_latest_version_object(num)
    except:
        logger.error("Error updating db entry of item %s", kimcode)

    __, leader, __, __ = kimcodes.parse_kim_code(kimcode)

    if leader == "MD":
        # if this item is a driver, update the db entries
        # of all the items that use this driver
        # since they contain a copy of its information

        data = query_item_database(
            filter={"driver.kimcode": kimcode}, projection={"kimcode": 1, "_id": 0}
        )
        for item in data:
            item_kimcode = item["kimcode"]
            db.items.update_one({"kimcode": item_kimcode}, {"$set": {"driver": info}})
            logger.info("Updating metadata of item %s", item_kimcode)


def upsert_item(kimcode):
    """Wrapper method to help with managing metadata in the database.
    Attempts to insert or update the metadata information
    in the mongodb database for an item.

    If the item does not already have a database entry,
    create one for it and insert it. If the item does already
    have a database entry, read the most current metadata from
    the kimspec.edn in the item's directory, create a new db
    entry from that metadata, and overwrite its existing one.

    Parameters
    ----------
    kimcode : str
        id code of the item
    """
    data = find_item_by_kimcode(kimcode)

    if not data:
        insert_item(kimcode)

    else:
        update_item(kimcode)


def insert_user(uuid, name, username=None):
    """Backend method to add user to database

    Args:
        uuid (str): UUID4 unique to the user
        name (str): personal name of the user
        username (str, optional): operating system username of the user.
                                 Defaults to None.
    """
    user_entry = {"uuid": uuid, "personal-name": name}

    if username:
        user_entry["operating-system-username"] = username

    db.users.insert_one(user_entry)


def update_user(uuid, name, username=None):
    """Backend method to update user's database entry

    Args:
        uuid (str): UUID4 unique to the user
        name (str): personal name of the user
        username (str, optional): operating system username of the user.
                                 Defaults to None.
    """
    user_entry = {"uuid": uuid, "personal-name": name}

    if username:
        user_entry["operating-system-username"] = username

    db.users.replace_one({"uuid": uuid}, user_entry)


def drop_tables(ask=True, run_as_editor=False):
    """DO NOT CALL IN PRODUCTION!

    backend method to clear the database,
    requires editor privleges.

    Args:
        ask (bool, optional): whether to prompt for confirmation.
                              Defaults to True.
        run_as_editor (bool,optional): flag for editors to run with elevated privleges
    """

    if users.is_editor():
        if run_as_editor:
            if ask:
                check = eval(input("Are you sure? [y/n] "))
            else:
                check = "y"

        else:
            raise cf.NotRunAsEditorError(
                "Did you mean to drop all tables? If you are an Editor run again with run_as_editor=True"
            )
    else:
        this_user = users.whoami()
        logger.warning(
            f"User {this_user} attempted to drop all tables from the database, but is not an editor"
        )
        raise cf.NotAnEditorError("Only KIMkit editors can delete database entries")

    if check == "y":
        db["items"].drop()
        db["users"].drop()


def delete_one_database_entry(id_code, run_as_editor=False):
    """Backend method to delete an item's/user's database entry

    Args:
        id_code (str): kimcode or UUID4 to be deleted
    """

    can_delete = False

    this_username = users.whoami()

    this_user_uuid = find_user(username=this_username)["uuid"]
    if not kimcodes.is_valid_uuid4(id_code):
        query_results = query_item_database(
            {"kimcode": id_code},
            projection={"contributor-id": 1, "maintainer-id": 1, "_id": 0},
            include_old_versions=True,
        )
        this_entry = query_results[0]
        contributor = this_entry["contributor-id"]
        maintainer = this_entry["maintainer-id"]
        
    if this_user_uuid == contributor or this_user_uuid == maintainer:
            can_delete = True

    if users.is_editor() and can_delete==False:
        if run_as_editor:
            can_delete = True
        else:
            raise cf.NotRunAsEditorError(
                "Did you mean to delete this entry? If you are an Editor run again with run_as_editor=True"
            )

    if can_delete:
        db.items.delete_one({"kimcode": id_code})
        db.users.delete_one({"uuid": id_code})

    else:
        logger.warning(
            f"User {this_username} attempted to deleted item {id_code} from the database, but is neither the contributor of the item nor an editor"
        )
        raise cf.NotAnEditorError("Only KIMkit editors can delete database entries")


def find_item_by_kimcode(kimcode):
    """Do a query to find a single item with the given kimcode

    Args:
        kimcode (str): ID code of the item

    Raises:
        InvalidKIMCode: Invalid kimcode

    Returns:
        dict: metadata of the item matching the kimcode
    """
    name, leader, num, version = kimcodes.parse_kim_code(kimcode)
    shortcode = leader + "_" + num
    if kimcodes.isextendedkimid(kimcode):
        if name:
            data = db.items.find_one({"kimcode": kimcode})
        else:
            data = db.items.find_one({"shortcode": shortcode, "kimid-version": version})
    elif kimcodes.iskimid(kimcode):
        data = db.items.find_one({"shortcode": shortcode, "latest": True})
    else:
        raise cf.InvalidKIMCode("Invalid KIMkit ID code.")

    return data


def list_potentials():
    """List the kimcodes of all potentials currently in this kimkit repository

    Returns:
        list of kimcodes
    """

    data = db.items.find(
        filter={"kim-item-type": {"$in": ["portable-model", "simulator-model"]}},
        projection={"kimcode": 1, "_id": 0},
    )

    potentials = []
    for doc in data:
        potentials.append(doc["kimcode"])

    return potentials


def list_drivers():
    """List the kimcodes of all drivers currently in this kimkit repository

    Returns:
        list of kimcodes
    """

    data = db.items.find(
        filter={"kim-item-type": {"$in": ["model-driver", "test-driver"]}},
        projection={"kimcode": 1, "_id": 0},
    )

    drivers = []
    for doc in data:
        drivers.append(doc["kimcode"])

    return drivers

def list_model_drivers():
    """List the kimcodes of all model drivers currently in this kimkit repository

    Returns:
        list of kimcodes
    """

    data = db.items.find(
        filter={"kim-item-type": "model-driver"},
        projection={"kimcode": 1, "_id": 0},
    )

    drivers = []
    for doc in data:
        drivers.append(doc["kimcode"])

    return drivers

def list_test_drivers():
    """List the kimcodes of all test drivers currently in this kimkit repository

    Returns:
        list of kimcodes
    """

    data = db.items.find(
        filter={"kim-item-type":"test-driver"},
        projection={"kimcode": 1, "_id": 0},
    )

    drivers = []
    for doc in data:
        drivers.append(doc["kimcode"])

    return drivers

def list_runners():
    """List the kimcodes of all runners currently in this kimkit repository

    Returns:
        list of kimcodes
    """
    data = db.items.find(
        filter={"kim-item-type": {"$in": ["test", "verification-check"]}},
        projection={"kimcode": 1, "_id": 0},
    )

    drivers = []
    for doc in data:
        drivers.append(doc["kimcode"])


def list_all_items():
    """List the kimcodes of all items in this database

    Returns:
        list: list of kimcodes
    """

    data = db.items.find(
        filter={},
        projection={"kimcode": 1, "_id": 0},
    )

    items = []
    for doc in data:
        items.append(doc["kimcode"])

    return items


def _find_db_entries_missing_repository_items(repository=cf.LOCAL_REPOSITORY_PATH):
    """Return a list of items that have metadata in the database, but are missing
    corresponding files in the local repository.

    Args:
        repository (path-like, optional): Root path of the local repository.
                                             Defaults to cf.LOCAL_REPOSITORY_PATH.

    Returns:
        list: list of kimcodes of items that are missing files
    """

    all_items = list_all_items()
    missing_items = []

    for kimcode in all_items:

        item_path = kimcodes.kimcode_to_file_path(kimcode, repository=repository)

        target_metadata_file = os.path.join(repository, item_path, cf.CONFIG_FILE)
        # item is missing/has missing metadata
        if not os.path.isfile(target_metadata_file):
            missing_items.append(kimcode)

    return missing_items


def _insert_missing_db_entries_from_repository_if_possible(
    repository=cf.LOCAL_REPOSITORY_PATH,
):
    """Determine which items in the local repository do not have entries in the
    database, and read their metadata and insert them if possible. Otherwise, return
    a list of kimcodes of items that failed to insert.

    Args:
        repository (_type_, optional): _description_. Defaults to cf.LOCAL_REPOSITORY_PATH.
    """

    failed_to_insert = []

    all_items_in_database = list_all_items()

    all_items_in_repository = models.enumerate_repository(repository=repository)

    all_items_in_database = np.asarray(all_items_in_database)
    all_items_in_repository = np.asarray(all_items_in_repository)

    # subtract the set of the items in the database from the items in the repository
    # the remainder if any are items that are missing from the database
    missing_db_entries = np.setdiff1d(all_items_in_repository, all_items_in_database)

    for kimcode in missing_db_entries:

        try:
            # if the item is intact and has a valid kimspec.edn, simply insert it into the db
            upsert_item(kimcode)
        except:
            # catch all errors and simply report them as failures to insert
            # too hard to predict all failure modes, will require human intervention
            failed_to_insert.append(kimcode)

    return failed_to_insert


def sychronize_database_with_local_repository_and_report_failures(
    repository=cf.LOCAL_REPOSITORY_PATH,
):
    """Attempt to synchronize the information in the local repository
    on disk with the metadata stored in the database. Items missing from the
    repository are simply reported, as there is no way to generate metadata
    for them. However, attempt to insert items missing from the database but
    present in the repository by reading their kimspec.edn metadata files, also
    reporting failures if they occur.

    Args:
        repository (path-like, optional): Root directory of the local repository.
                                             Defaults to cf.LOCAL_REPOSITORY_PATH.

    Returns:
        dict: dict with 2 keys, 'missing-database-entries', and
        'missing-repository-files', each associated with a list of
        kimcodes of the missing items that were not able to be
        automatically inserted.
    """

    missing_database_items = _insert_missing_db_entries_from_repository_if_possible(
        repository=repository
    )

    missing_repository_items = _find_db_entries_missing_repository_items(
        repository=repository
    )

    missing_items = {
        "missing-database-entries": missing_database_items,
        "missing-repository-files": missing_repository_items,
    }

    return missing_items


def find_legacy(kimcode):
    """Do a query to find if any items with a given
    12 digit id in their kimcode exist.

    Args:
        kimcode (str): ID code of the item

    Raises:
        InvalidKIMCode: Invalid kimcode

    Returns:
        dict: metadata of the item matching the kimcode
    """
    if kimcodes.iskimid(kimcode):
        __, __, num, __ = kimcodes.parse_kim_code(kimcode)
        data = db.items.find_one({"kimnum": num})
    else:
        raise cf.InvalidKIMCode("Invalid KIMkit ID code.")

    return data


def query_item_database(
    filter, projection=None, skip=0, limit=0, sort=None, include_old_versions=False
):
    """Pass a query to the KIMkit items database via pymongo.find()

    Args:
        filter (dict): filter to query for matching documents

        projection (dict, optional): dict specifying which fields to return,
            {field:1} returns that field, {field:0} Defaults to None.

        skip (int, optional): how many documents to skip. Defaults to 0.

        limit (int, optional): limit how many results to return.
            Defaults to 0, which returns all

        sort (list, optional): a list of (key, direction) pairs specifying the sort order for this query.
            Defaults to None.

        include_old_versions: bool, optional, if True return all matching items, not
            just the item with the highest version number

    Returns: dict
    """

    # by default, only return most recent versions of items
    if not include_old_versions:
        filter["latest"] = True

    data = db.items.find(
        filter, projection=projection, skip=skip, limit=limit, sort=sort
    )
    results = []
    for result in data:
        results.append(result)

    return results


def rebuild_latest_tags():
    """
    Build the latest: True/False tags for all test results in the database
    by finding the latest versions of all results
    """
    logger.info("Updating all object latest...")
    objs = db.items.find({"type": {"$in": ["mo", "md", "sm"]}}, {"kimid-number": 1})
    objs = set([o.get("kimid-number") for o in objs if "kimid-number" in o])
    for o in objs:
        set_latest_version_object(o)


def set_latest_version_object(id_num):
    """
    Sets KIM Objects with the highest version in their lineage to have 'latest'=True,
    and the rest to have 'latest'=False
    """
    query = {"kimid-number": id_num}
    fields = {"kimid-version": 1, "extended-id": 1}
    sort = [("kimid-version", -1)]

    objs = list(db.items.find(query, fields, sort=sort))

    if len(objs) == 0:
        logger.debug(
            "Object %r not found in database, skipping `latest` update" % id_num
        )
        return

    objids = [i["extended-id"] for i in objs if "extended-id" in i]

    db.items.update_many(
        {"extended-id": {"$in": objids}},
        {"$set": {"latest": False}},
    )
    db.items.update_many(
        {"extended-id": objids[0]},
        {"$set": {"latest": True}},
    )


def find_user(uuid=None, personal_name=None, username=None):
    """Query the database for a user matching the input

    Can query based on personal name, operating system username,
    or UUID.

    Args:
        uuid (str, optional): UUID4 assigned to the user. Defaults to None.
        personal_name (str, optional): User's name. Defaults to None.
        username (str, optional): User's operating system username. Defaults to None.

    Returns:
        dict: matching user information
    """
    if uuid:
        if kimcodes.is_valid_uuid4(uuid):
            data = db.users.find_one({"uuid": uuid})

    if personal_name:
        data = db.users.find_one({"personal-name": personal_name})

    if username:
        data = db.users.find_one({"operating-system-username": username})

    if data:
        data.pop("_id", None)

    return data


def rmbadkeys(dd):
    """Helper function to prune keys that shouldn't be frequently updated

    Args:
        dd (dict): mongodb formatted dict of metadata
    Returns:
        dict: the same dict without any keys specified in BADKEYS
    """
    return {k: v for k, v in list(dd.items()) if k not in BADKEYS}
