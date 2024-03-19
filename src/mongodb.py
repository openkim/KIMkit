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

from . import config as cf
from .logger import logging

from .. import kimcodes
from .. import users

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
    m = re.search("(.+)__([A-Z]{2}_\d{12}_\d{3})$", kimcode)
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
    foo["path"] = os.path.join(leader.lower(), kimcode)
    foo["_id"] = kimcode
    foo["inserted_on"] = str(datetime.datetime.utcnow())
    foo["latest"] = True

    if foo["type"] in ("mo", "sm", "md"):
        foo["makeable"] = True
    if foo["type"] in ("sm", "mo"):
        foo["subject"] = True
    if foo["type"] in ("md"):
        foo["driver"] = True
    else:
        foo["driver"] = False

    if leader == "MO":
        item_type = "portable-models"
    elif leader == "SM":
        item_type = "simulator-models"
    elif leader == "MD":
        item_type = "model-drivers"

    src_dir = kimcodes.kimcode_to_file_path(kimcode, repository)
    specpath = os.path.join(src_dir, cf.CONFIG_FILE)
    with open(specpath, "r") as specfile:
        spec = kim_edn.load(specfile)

    if foo["type"] == "mo":
        modeldriver = spec.get("model-driver", None)
        if modeldriver:
            foo["driver"] = rmbadkeys(kimcode_to_dict(modeldriver))

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


def drop_tables(ask=True,run_as_editor=False):
    """DO NOT CALL IN PRODUCTION!

    backend method to clear the database,
    requires editor privleges.

    Args:
        ask (bool, optional): whether to prompt for confirmation.
                              Defaults to True.
        run_as_editor (bool,optional): flag for editors to run with elevated privleges
    """

    if users.is_editor() and run_as_editor:
        if ask:
            check = eval(input("Are you sure? [y/n] "))
        else:
            check = "y"

        if check == "y":
            db["items"].drop()
            db["users"].drop()


def delete_one_database_entry(id_code, run_as_editor=False):
    """Backend method to delete an item's/user's database entry

    Args:
        id_code (str): kimcode or UUID4 to be deleted
    """

    if users.is_editor() and run_as_editor:
        db.items.delete_one({"kimcode": id_code})
        db.users.delete_one({"uuid": id_code})


def find_item_by_kimcode(kimcode):
    """Do a query to find a single item with the given kimcode

    Args:
        kimcode (str): ID code of the item

    Raises:
        InvalidKIMCode: Invalid kimcode

    Returns:
        dict: metadata of the item matching the kimcode
    """
    if kimcodes.iskimid(kimcode):
        data = db.items.find_one({"kimcode": kimcode})
    else:
        raise cf.InvalidKIMCode("Invalid KIMkit ID code.")

    return data

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
        __,__,num,__=kimcodes.parse_kim_code(kimcode)
        data = db.items.find_one({"kimnum":num})
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
