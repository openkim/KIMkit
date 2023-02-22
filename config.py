import os
import re
import subprocess
import uuid


def tostr(cls):
    return ".".join(map(str, cls))


# First, record the current version of the pipeline and KIM API installed
__kim_api_version__ = "2.2.1"

# The following clauses specify what kim-api-versions that the KIM API currently installed
# on the pipeline Directors/Workers can actually compile and use.
#
__kim_api_version_support_clauses__ = [(1, 6, 0), (1, 9, 0), (2, 0, 0)]

__kim_api_version_support_spec__ = ">= " + tostr(__kim_api_version_support_clauses__[2])

# =============================================================================
# the environment parsing equipment
# =============================================================================
ENVIRONMENT_FILE_NAME = "KIMkit-env"
ENVIRONMENT_LOCATIONS = [
    os.environ.get("KIMKIT_ENVIRONMENT_FILE", ""),
    os.path.join("./", ENVIRONMENT_FILE_NAME),
    os.path.join(os.path.expanduser("~"), ENVIRONMENT_FILE_NAME),
    os.path.join("/KIMkit", ENVIRONMENT_FILE_NAME),
]


def transform(val):
    # try to interpret the value as an int or float as well
    try:
        val = int(val)
    except ValueError:
        try:
            val = float(val)
        except ValueError:
            pass
    if val == "False":
        val = False
    if val == "True":
        val = True
    return val


def read_environment_file(filename):
    """
    Return a dictionary of key, value pairs from an environment file of the form:

        # comments begin like Python comments
        # no spaces in the preceding lines
        SOMETHING=value1
        SOMETHING_ELSE=12
        BOOLEAN_VALUE=True

        # can also reference other values with $VARIABLE
        NEW_VARIABLE=/path/to/$FILENAME
    """
    conf = {}
    with open(filename) as f:
        lines = f.readlines()
        for line in lines:
            if not re.match(r"^[A-Za-z0-9\_]+\=.", line):
                continue

            # if we have a good line, grab the values
            var, val = line.strip().split("=")
            search = re.search(r"(\$[A-Za-z0-9\_]+)", val)
            if search:
                for rpl in search.groups():
                    val = val.replace(rpl, conf[rpl[1:]])

            conf[var] = transform(val)

    return conf


def machine_id():
    """Get a UUID for this particular machine"""
    s = ""
    files = ["/var/lib/dbus/machine-id", "/etc/machine-id"]
    for f in files:
        if os.path.isfile(f):
            with open(f) as fl:
                s = fl.read()

    if not s:
        s = str(uuid.uuid4())
    else:
        # transform the big string into a uuid-looking thing
        q = (0, 8, 12, 16, 20, None)
        s = "-".join([s[q[i] : q[i + 1]] for i in range(5)])
    return s.strip()


def ensure_repository_structure(local_repository_path):
    for fldr in ["portable-models", "simulator-models", "model-drivers"]:
        p = os.path.join(local_repository_path, fldr)
        subprocess.check_call(["mkdir", "-p", p])


class Configuration(object):
    def __init__(self):
        """
        Load the environment for this KIMkit instance.  First, load the default
        values from the Python package and then modify then using any local
        variables found in standard locations (see ENVIRONMENT_LOCATIONS)
        """
        # read in the default environment
        here = os.path.dirname(os.path.realpath(__file__))
        envf = os.path.join(here, "default-environment")
        conf = read_environment_file(envf)

        # supplement it with the default location's extra file
        for loc in ENVIRONMENT_LOCATIONS:
            if os.path.isfile(loc):
                conf.update(read_environment_file(loc))
                break

        # then take variables from the shell environment
        for k, v in list(conf.items()):
            tempval = os.environ.get(k, None)
            if tempval is not None:
                conf.update({k: tempval})

        # add any supplemental variables that should exist internally
        # in the KIMkit code

        # Simulators that we support through ASE
        # ** NB: These should all be in lower case **
        conf.update({"ASE_SUPPORTED_SIMULATORS": ["lammps", "asap"]})

        self.conf = conf

        if not self.conf.get("UUID"):
            self.conf["UUID"] = machine_id()

    def get(self, var, default=None):
        return self.conf.get(var, default)

    def variables(self):
        o = self.conf.keys()
        o.sort()
        return o


conf = Configuration()
globals().update(conf.conf)

# Metadata Options
kimspec_order = [
    "content-origin",
    "content-other-locations",
    "contributor-id",
    "date",
    "description",
    "developer",
    "disclaimer",
    "doi",
    "domain",
    "executables",
    "extended-id",
    "funding",
    "implementer",
    "kim-api-version",
    "kim-item-type",
    "license",
    "maintainer-id",
    "model-driver",
    "potential-type",
    "simulator-name",
    "simulator-potential",
    "simulator-potential-compatibility",
    "source-citations",
    "species",
    "title",
    "training",
]

kimspec_uuid_fields = [
    "contributor-id",
    "developer",
    "implementer",
    "maintainer-id",
]

kimspec_strings = [
    "content-origin",
    "content-other-locations",
    "contributor-id",
    "date",
    "description",
    "disclaimer",
    "doi",
    "domain",
    "extended-id",
    "kim-api-version",
    "kim-item-type",
    "license",
    "maintainer-id",
    "model-driver",
    "potential-type",
    "simulator-name",
    "simulator-potential",
    "title",
]

# The type specified in these dicts is what the inner type of the kimspec array should be
kimspec_arrays = {
    "developer": str,
    "execuatbles": str,
    "funding": dict,
    "implementer": str,
    "simulator_potential_compatibility": dict,
    "source-citations": dict,  # BibTex style edn dicts of citations
    "species": str,
    "training": str,
}

kimspec_arrays_dicts = {
    "funding": {
        "funder-name": True,
        "award-number": False,
        "award-uri": False,
        "award-title": False,
    },
    "simulator-potential-compatibility": {
        "simulator-name": True,
        "simulator-potential": True,
        "compatibility": True,
        "compatibility-notes": False,
    },
}
# TODO: copy crossref query from webapp?


KIMkit_item_type_key_requirements = {
    "portable-model": {
        "required": [
            "description",
            "developer",
            "extended-id",
            "implementer",
            "kim-api-version",
            "kim-item-type",
            "license",
            "potential-type",
            "species",
            "title",
        ],
        "optional": [
            "content-origin",
            "content-other-locations",
            "contributor-id",
            "disclaimer",
            "doi",
            "domain",
            "executables",
            "funding",
            "maintainer-id",
            "model-driver",
            "date",
            "source-citations",
            "training",
        ],
    },
    "simulator-model": {
        "required": [
            "description",
            "developer",
            "extended-id",
            "implementer",
            "kim-api-version",
            "kim-item-type",
            "license",
            "potential-type",
            "species",
            "simulator-name",
            "simulator-potential",
            "title",
        ],
        "optional": [
            "content-origin",
            "content-other-locations",
            "contributor-id",
            "disclaimer",
            "doi",
            "domain",
            "executables",
            "funding",
            "maintainer-id",
            "date",
            "source-citations",
            "training",
        ],
    },
    "model-driver": {
        "required": [
            "description",
            "developer",
            "extended-id",
            "implementer",
            "kim-api-version",
            "kim-item-type",
            "license",
            "title",
        ],
        "optional": [
            "content-origin",
            "content-other-locations",
            "contributor-id",
            "disclaimer",
            "doi",
            "domain",
            "executables",
            "funding",
            "maintainer-id",
            "date",
            "simulator-potential-compatibility",
            "source-citations",
        ],
    },
}

# KIMkit custom exception types:


class KIMkitUserNotFoundError(PermissionError):
    """Raised when a user does not have a vaild KIMkit UUID4 assigned in user_uuids.edn"""


class KimCodeAlreadyInUseError(FileExistsError):
    """Raised when attmpting to assign a kimcode to an item that is already assigned to a different item in the same repository"""
