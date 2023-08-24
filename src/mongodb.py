import pymongo
import os
import datetime
import re
import kim_edn

from . import config as cf
from .logger import logging

from .. import kimcodes

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
        # TODO: add set_latest_version_object() equivalent once querys work
    except:
        logger.error("Already have %s", kimcode)


def update_item(kimcode):
    """Update the db entry of this item with
    new metadata read from disc.

    Parameters
    ----------
    kimcode : str
        id code of the item
    """
    logger.info("Updating metadata of item %s", kimcode)

    info = kimcode_to_dict(kimcode)

    info.pop("_id", None)

    try:
        db.items.replace_one({"kimcode": kimcode}, info)
        # TODO: add set_latest_version_object() equivalent once querys work
    except:
        logger.error("Error updating db entry of item %s", kimcode)


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
    user_entry = {"uuid": uuid, "personal-name": name}

    if username:
        user_entry["operating-system-username"] = username

    db.users.insert_one(user_entry)


def update_user(uuid, name, username=None):
    user_entry = {"uuid": uuid, "personal-name": name}

    if username:
        user_entry["operating-system-username"] = username

    db.users.replace_one({"uuid": uuid}, user_entry)


def drop_tables(ask=True):
    if ask:
        check = eval(input("Are you sure? [y/n] "))
    else:
        check = "y"

    if check == "y":
        db["items"].drop()
        db["users"].drop()


def delete_one_database_entry(id_code):
    db.items.delete_one({"kimcode": id_code})
    db.users.delete_one({"uuid": id_code})


def find_item_by_kimcode(kimcode):
    if kimcodes.iskimid(kimcode):
        data = db.items.find_one({"kimcode": kimcode})
    else:
        raise ValueError("Invalid KIMkit ID code.")

    return data


def find_user(uuid=None, personal_name=None, username=None):
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
    return {k: v for k, v in list(dd.items()) if k not in BADKEYS}
