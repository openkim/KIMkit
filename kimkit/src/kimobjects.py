"""
@@.. module:: models
    :synopsis: Holds the python object models for kim objects

.. moduleauthor:: Alex Alemi <alexalemi@gmail.com>, Matt Bierbaum <mkb72@cornell.com>,
                  Daniel S. Karls <karl0100@umn.edu>, Claire Waters <bwaters@umn.edu>

A pure python object wrapper for KIMkit objects

Has a base ``KIMObject`` class and

 * Portable Model
 * Simulator Model
 * Model Driver
 * Test
 * Test Driver
 * Verification Check


classes, all of which inherit from ``KIMObject`` and aim to know how to handle themselves.
"""

import shutil
import subprocess
import os
import itertools
from contextlib import contextmanager
import kim_edn

from . import config as cf
from .. import kimcodes
from . import kimapi

# import template
from .logger import logging

logger = logging.getLogger("KIMkit")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Base KIMObject
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class KIMObject(object):
    """The base class that all KIM-related objects (Tests, Test Drivers, Models,
    Model Drivers, Verification Checks, Test Results, Verification Results,
    Errors) inherit from

    Attributes:
        kim_code
            The formatted string used to uniquely identify the item
        path
            The absolute path to the directory associated with the object
        parent_dir
            The parent directory of the object, i.e. the full path of the ``te``
            directory inside the local repository if the item is a KIM test
        makeable
            Whether the item is makeable or not
    """

    # Subclasses should override ``kim_type`
    kim_type = None
    makeable = False

    def __init__(self, kim_code, subdir=None, abspath=None, approved=True):
        """Initialize a KIMObject given the kim_code

        Args:
            kim_code (str)
                A full or partial kim_code, i.e. one like:
                 * Human_readable_prefix__TE_000000000000_000
                 * TE_000000000000_000
                 * TE_000000000000_000-and-MO_111111111111-1523572872-tr
            subdir (str)
                In order to point to a directory that does not follow the pattern
                LOCAL_REPOSITORY_PATH/kim_type/kim_code
                this parameter can provide the subdirectory of the parent directory where
                the item exists:
                LOCAL_REPOSITORY_PATH/subdir/KIM_CODE
        """
        # grab the attributes
        self.kim_code = kim_code
        self.approved = approved

        # Determine where this KIMObject sits in the local repository
        if approved:
            self.parent_dir = os.path.join(cf.LOCAL_REPOSITORY_PATH, self.kim_type)
        else:
            self.parent_dir = os.path.join(
                os.path.join(cf.LOCAL_REPOSITORY_PATH, "pending"),
                self.kim_type,
            )

        # Set path
        if abspath is None:
            if subdir is not None:
                path = os.path.join(self.parent_dir, subdir)
            else:
                path = os.path.join(self.parent_dir, self.kim_code)
        else:
            path = abspath

        # Check that the directory exists
        if os.path.isdir(path):
            self.path = path
        else:
            raise IOError(f"Directory {path} not found")

        # Assume the object is not built by default
        self.built = False

    def __str__(self):
        """the string representation is the full kim_code"""
        return self.kim_code

    def __repr__(self):
        """The repr is of the form <KIMObject(kim_code)>"""
        return "<{}({})>".format(self.__class__.__name__, self.kim_code)

    def __hash__(self):
        """The hash is the full kim_code"""
        return hash(self.kim_code)

    def __eq__(self, other):
        """Two KIMObjects are equivalent if their full kim_code is equivalent"""
        if other:
            return str(self) == str(other)
        return False

    @contextmanager
    def in_dir(self):
        """a context manager to do things inside this objects path
        Usage::

            foo = KIMObject(some_code)
            with foo.in_dir():
                # < code block >

        before executing the code block, cd into the path of the kim object
        execute the code and then come back to the directory you were at
        """
        cwd = os.getcwd()
        os.chdir(self.path)
        logger.debug("working directory changed to: {}".format(self.path))

        try:
            yield
        except Exception as e:
            raise e
        finally:
            os.chdir(cwd)

    def make(self, approved=True):
        """Try to build the thing, by executing ``make`` in its directory"""
        # There should be no need to make the driver here.  In the case of a 'run' submission,
        # the driver should already have been submitted before the Test or Model itself. In the
        # case of runpair, we make sure to sync and build the pending driver (if there is one)
        # before the Test or Model itself.
        if self.makeable:
            kimapi.make_object(self, approved=approved)
            self.built = True
        else:
            logger.warning(
                "%r:%r is not makeable", self.__class__.__name__, self.kim_code
            )

    @classmethod
    def all_on_disk(cls, approved_only=True):
        """
        A generator for all items of this KIMObject type that can be found on
        disk in the local repository. If approved_only=True, only approved items
        are included; otherwise, both approved and pending items on disk are
        included (currently not used).
        """
        logger.debug(
            f"Attempting to find all {cls.__name__} on disk in local repository..."
        )
        type_dir = os.path.join(cf.LOCAL_REPOSITORY_PATH, cls.kim_type)

        kim_codes = (
            subpath
            for subpath in os.listdir(type_dir)
            if (
                os.path.isdir(os.path.join(type_dir, subpath))
                and kimcodes.iskimid(subpath)
                and not os.path.islink(os.path.join(type_dir, subpath))
            )
        )

        # If this is being used for a pending, also search the 'pending' local repository
        if not approved_only:
            type_dir_pending = os.path.join(
                os.path.join(cf.LOCAL_REPOSITORY_PATH, "pending"),
                cls.kim_type,
            )
            kim_codes_pending = (
                subpath
                for subpath in os.listdir(type_dir_pending)
                if (
                    os.path.isdir(os.path.join(type_dir_pending, subpath))
                    and kimcodes.iskimid(subpath)
                )
            )
            kim_codes_final = itertools.chain(kim_codes, kim_codes_pending)
        else:
            kim_codes_final = kim_codes

        for x in kim_codes_final:
            try:
                yield cls(x)
            except Exception:
                logger.exception("Exception on formation of kim_code (%s)", x)

    @property
    def kimspec(self):
        specfile = os.path.join(self.path, cf.CONFIG_FILE)
        if not os.path.exists(specfile):
            return None

        spec = {}
        with open(specfile) as f:
            spec = kim_edn.load(f)
        return spec

    @property
    def kim_api_version(self):
        if self.kimspec:
            return self.kimspec.get("kim-api-version")
        return None

    def delete(self):
        """Delete the folder for this object
        .. note::
            Not to be used lightly!
        """
        logger.warning("Deleting item %r from local repository", self)
        shutil.rmtree(self.path)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Items and Results
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class KIMItem(KIMObject):
    """
    Attributes:
        kim_code_name
            the name at the front of the kim_code or None
        kim_code_leader
            the two digit prefix
        kim_code_number
            the 12 digit number as string
        kim_code_version
            the version number as string

    """

    # the required leader to this classes kim_codes
    kim_type = None

    def __init__(self, kim_code, *args, **kwargs):
        super().__init__(kim_code, *args, **kwargs)

        name, leader, num, version = kimcodes.parse_kim_code(self.kim_code)

        # check to see if we have the right leader
        if self.kim_type:
            assert (
                leader.lower() == self.kim_type
            ), f"{kim_code} not a valid KIM code for {self.__class__.__name__}"

        self.kim_code_name = name
        self.kim_code_leader = leader
        self.kim_code_number = num
        self.kim_code_version = version
        self.kim_code_id = kimcodes.strip_name(self.kim_code)
        self.kim_code_short = kimcodes.strip_version(self.kim_code)

    @property
    def driver(self):
        """Default to having no driver"""
        return None

    @classmethod
    def all_fresh_on_disk(cls):
        """
        A generator for all fresh items of this KIMObject type that can be found
        on disk in the local repository.
        """
        logger.debug(
            f"Attempting to find all fresh {cls.__name__} on disk in local repository..."
        )

        # First, get a generator for all KIM Items of this type and convert it to a list
        all_items = list(cls.all_on_disk())

        # Separate the shortnames from the short-ids
        short_names = {}
        short_ids = []

        for item in all_items:
            name, leader, num, version = kimcodes.parse_kim_code(item.kim_code)
            short_id = ("_").join((leader, num, version))
            short_names[short_id] = name
            short_ids.append(short_id)

        # Sort the short-ids descendingly
        short_ids.sort(reverse=True)

        # Iterate through short-ids. Every time a new shortcode is encountered
        # record the item as being fresh
        fresh_items = []

        prev_short_code = ""
        for _, item in enumerate(short_ids):
            short_code = item.split("_")[0:2]
            if short_code != prev_short_code:
                short_name = short_names[item]
                fresh_items.append(short_name + "__" + item)
                prev_short_code = short_code

        return (cls(x) for x in fresh_items)


class KIMJobResult(KIMObject):
    """Represents a Test Result, Verification Result, or Error"""

    kim_type = None
    makeable = False

    def __init__(self, kim_code, *args, **kwargs):
        super().__init__(kim_code, *args, **kwargs)


# ============================================================
# Runner & Subject
# ============================================================


class Runner(KIMItem):
    """
    An executable KIM Item.  This may be a Test or Verification Check.  The
    corresponding subject will be a Model.

    NOTE: Technically we could do away with the terminology of "runner" and "subject"
          now that we've eliminated the idea of Test Verifications, but since "runner"
          can still be a TE or VC, I'm keeping it in place.
    """

    makeable = True
    result_leader = "tr"

    def __init__(self, kim_code, *args, **kwargs):
        super(Runner, self).__init__(kim_code, *args, **kwargs)
        self.executable = os.path.join(self.path, cf.TEST_EXECUTABLE)
        self.infile_path = os.path.join(self.path, cf.INPUT_FILE)
        self.depfile_path = os.path.join(self.path, cf.DEPENDENCY_FILE)

    def __call__(self, *args, **kwargs):
        """Calling a runner object executes its executable in
        its own directory.  args and kwargs are passed to ``subprocess.check_call``."""
        with self.in_dir():
            subprocess.check_call(self.executable, *args, **kwargs)

    @property
    def _reversed_out_dict(self):
        """Reverses the out_dict"""
        return {value: key for key, value in self.out_dict.items()}

    @property
    def infile(self):
        """return a file object for the INPUT_FILE"""
        return open(self.infile_path)

    @property
    def depfile(self):
        """return a file object for DEPENDENCY_FILE"""
        if os.path.isfile(self.depfile_path):
            return open(self.depfile_path)
        return None

    # def processed_infile(self, subject, add_history=False):
    #     """Process the input file, with template, and return a file object to the result"""
    #     template.process(self.infile_path, subject, self, add_history=add_history)
    #     return open(os.path.join(self.path, cf.OUTPUT_DIR, cf.TEMP_INPUT_FILE))

    # @property
    # def template(self):
    #     return template.template_environment.get_template(
    #         os.path.join(self.path, cf.OUTPUT_DIR, cf.TEMPLATE_FILE)
    #     )

    @property
    def children_on_disk(self):
        return None

    @property
    def fresh_children_on_disk(self):
        return None

    @property
    def simulator_potential(self):
        if not self.kimspec:
            return None
        else:
            return self.kimspec.get("simulator-potential")


class Subject(KIMItem):
    """
    Something that is run against.  Since we no longer have Test Verifications, a subject
    is always going to be a Model.
    """

    makeable = True

    def __init__(self, kim_code, *args, **kwargs):
        """Initialize the Model, with a kim_code"""
        super(Subject, self).__init__(kim_code, *args, **kwargs)

    @property
    def children_on_disk(self):
        return None

    @property
    def fresh_children_on_disk(self):
        return None

    def delete(self):
        """
        If we are a Director or Dispatcher or Worker, remove the subject by using
        the KIM API collections management utility (this will remove all of the
        associated files). If not, just use shutil to remove the directory.
        """
        logger.warning("Deleting item %r from local repository", self)
        subprocess.call(
            ["kim-api-collections-management", "remove", "--force", self.kim_code]
        )
        shutil.rmtree(self.path, ignore_errors=True)


# ============================================================
# Subject Objs
# ============================================================


# --------------------------------------
# Model
# -------------------------------------
class Model(Subject):
    """A KIM Model, KIMItem with

    Settings:
        kim_type = "mo"
        makeable = True
    """

    kim_type = "mo"
    makeable = True
    subject_name = "model"

    def __init__(self, kim_code, *args, **kwargs):
        """Initialize the Model, with a kim_code"""
        super(Model, self).__init__(kim_code, *args, **kwargs)

    @property
    def model_driver(self):
        """Return the model driver if there is one, otherwise None,
        currently, this tries to parse the kim file for the MODEL_DRIVER_NAME line
        """
        if not self.kimspec or not self.kimspec.get("model-driver"):
            return None
        else:
            return self.kimspec["model-driver"]

    @property
    def driver(self):
        return self.model_driver

    @property
    def species(self):
        if not self.kimspec:
            return None
        else:
            return self.kimspec["species"]


# --------------------------------------
# Simulator Model
# -------------------------------------
class SimulatorModel(Subject):
    """A KIM Model, KIMItem with

    Settings:
        kim_type = "sm"
        makeable = True
    """

    kim_type = "sm"
    makeable = True
    subject_name = "simulator-model"

    def __init__(self, kim_code, *args, **kwargs):
        """Initialize the Simulator Model, with a kim_code"""
        super(SimulatorModel, self).__init__(kim_code, *args, **kwargs)

    @property
    def species(self):
        if not self.kimspec:
            return None
        else:
            return self.kimspec["species"]

    @property
    def simulator(self):
        return self.kimspec["simulator-name"]

    @property
    def simulator_potential(self):
        if not self.kimspec:
            return None
        else:
            return self.kimspec["simulator-potential"]

    @property
    def pm_run_compatible(self):
        """
        Whether the SM can run against regular Tests (that are designed to run
        against portable models) as opposed to Tests that can specifically
        constructed against one or more classes of simulator potentials.
        Defaults to True if not present in kimspec.edn.
        """
        if not self.kimspec:
            return None
        else:
            try:
                return self.kimspec["pm-run-compatible"]
            except KeyError:
                return True


# ============================================================
# Runner Objs
# ============================================================


# ---------------------------------------------
# Test
# ---------------------------------------------
class Test(Runner):
    """A kim test, it is a KIMItem, plus

    Settings:
        kim_type = "te"
        makeable = True

    Attributes:
        executable
            a path to its executable
        outfile_path
            path to its INPUT_FILE
        infile_path
            path to its OUTPUT_FILE
        out_dict
            a dictionary of its output file, mapping strings to
            Property objects
    """

    kim_type = "te"
    makeable = True
    subject_type = Model
    result_leader = "tr"
    runner_name = "test"
    subject_name = "test"

    def __init__(self, kim_code, *args, **kwargs):
        """Initialize the Test, with a kim_code"""
        super(Test, self).__init__(kim_code, *args, **kwargs)

    @property
    def _reversed_out_dict(self):
        """Reverses the out_dict"""
        return {value: key for key, value in self.out_dict.items()}

    @property
    def test_driver(self):
        """Return the Test Driver listed in this Test's kimspec file"""
        if not self.kimspec or not self.kimspec.get("test-driver"):
            return None
        else:
            return self.kimspec["test-driver"]

    @property
    def driver(self):
        return self.test_driver

    @property
    def species(self):
        if not self.kimspec:
            return None
        else:
            return self.kimspec["species"]

    @property
    def simulator(self):
        drv = self.driver
        if drv:
            return kim_obj(drv).simulator
        else:
            return self.kimspec["simulator-name"]

    def runtime_dependencies(self):
        """
        Read the DEPENDENCY_FILE (currently dependencies.edn) for the runner item.
        Note that these will usually be specified without a version number, and also
        that the list returned by this function only contains the Tests listed in the
        dependency file, not tuples containing those Tests with any Models.
        """
        # FIXME: Verify that each item listed in dependencies.edn is at least a partial kimcode for
        #        a Test, i.e. only Tests should be listed in dependencies.edn.
        if self.depfile:
            deps = kim_edn.load(self.depfile)
            if not isinstance(deps, list):
                logger.exception(
                    "Dependencies file of item %r has invalid format (must be a list)"
                    % self.kim_code
                )
                raise TypeError(
                    "Dependencies file of item %r has invalid format (must be a list)"
                    % self.kim_code
                )
            for dep in deps:
                if not isinstance(dep, str):
                    logger.exception(
                        "Dependencies file entry %r of item %r has invalid format (must be a "
                        "string)" % (dep, self.kim_code)
                    )
                    raise TypeError(
                        "Dependencies file entry %r of item %r has invalid "
                        "format (must be a string)" % (dep, self.kim_code)
                    )
            # Cast each entry of deps to str to get rid of any unicode.
            deps = [str(dep) for dep in deps]
            return deps
        return []


# ------------------------------------------
# Verification Check
# ------------------------------------------
class VerificationCheck(Test):
    """A kim test, it is a KIMItem, plus

    Settings:
        kim_type = "vc"
        makeable = True

    Attributes:
        executable
            a path to its executable
        outfile_path
            path to its INPUT_FILE
        infile_path
            path to its OUTPUT_FILE
        out_dict
            a dictionary of its output file, mapping strings to
            Property objects
    """

    kim_type = "vc"
    makeable = True
    subject_type = Model
    result_leader = "vr"
    runner_name = "verification-check"

    def __init__(self, kim_code, *args, **kwargs):
        """Initialize the Test, with a kim_code"""
        super(VerificationCheck, self).__init__(kim_code, *args, **kwargs)

    @property
    def simulator(self):
        return self.kimspec["simulator-name"]


# ============================================================
# Drivers
# ============================================================


# ------------------------------------------
# Test Driver
# ------------------------------------------
class TestDriver(KIMItem):
    """A test driver, a KIMItem with,

    Settings:
        kim_type = "td"
        makeable = True

    Attributes:
        executable
            the executable for the TestDriver
    """

    kim_type = "td"
    makeable = True

    def __init__(self, kim_code, *args, **kwargs):
        """Initialize the TestDriver, with a kim_code"""
        super(TestDriver, self).__init__(kim_code, *args, **kwargs)
        self.executable = os.path.join(self.path, cf.TEST_EXECUTABLE)

    def __call__(self, *args, **kwargs):
        """Make the TestDriver callable, executing its executable in its own directory,
        passing args and kwargs to ``subprocess.check_call``
        """
        with self.in_dir():
            subprocess.check_call(self.executable, *args, **kwargs)

    @property
    def children_on_disk(self):
        """
        Return a generator of all of the Tests in the local repository which
        use this Test Driver.  In production, this function is only used as a
        secondary precaution when deleting a Test Driver from the system in
        order to ensure all of their children are indeed deleted. The
        Director's delete() function should already ensure that this secondary
        deletion step is unnecessary.

        This function is also used by the user VM command line utilities.
        """
        return (test for test in Test.all_on_disk() if self.kim_code == test.driver)

    def delete(self):
        """
        Override KIMItem.delete to also delete children from local repository
        """
        logger.warning("Deleting item %r from local repository", self)
        # Delete any children of this driver in the local repository
        for child in self.children_on_disk:
            child.delete()
        shutil.rmtree(self.path)

    @property
    def fresh_children_on_disk(self):
        """
        Same as children_on_disk, but only returns non-stale Tests which use
        this Test Driver.  Also used by the user VM command line utilities.
        """
        return (
            test for test in Test.all_fresh_on_disk() if self.kim_code == test.driver
        )

    @property
    def simulator(self):
        return self.kimspec["simulator-name"]


# ------------------------------------------
# Model Driver
# ------------------------------------------
class ModelDriver(KIMItem):
    """A model driver, a KIMItem with,

    Settings:
        kim_type = "md"
        makeable = True
    """

    kim_type = "md"
    makeable = True

    def __init__(self, kim_code, *args, **kwargs):
        """Initialize the ModelDriver, with a kim_code"""
        super(ModelDriver, self).__init__(kim_code, *args, **kwargs)

    @property
    def children_on_disk(self):
        """
        Return a generator of all of the Models in the local repository which
        use this Model Driver.  In production, this function is only used as a
        secondary precaution when deleting a Model Driver from the system in
        order to ensure all of their children are indeed deleted. The
        Director's delete() function should already ensure that this secondary
        deletion step is unnecessary.

        This function is also used by the user VM command line utilities.
        """
        return (model for model in Model.all_on_disk() if self.kim_code == model.driver)

    def delete(self):
        """
        Override KIMItem.delete to also delete children from local repository
        """
        logger.warning("Deleting item %r from local repository", self)
        # First, remove all of the children
        for child in self.children_on_disk:
            child.delete()

        # Now, remove the Model Driver itself
        subprocess.check_call(
            ["kim-api-collections-management", "remove", "--force", self.kim_code]
        )
        shutil.rmtree(self.path, ignore_errors=True)

    @property
    def fresh_children_on_disk(self):
        """
        Same as children_on_disk, but only returns non-stale Models which use
        this Model Driver.  Also used by the user VM command line utilities.
        """
        return (
            model
            for model in Model.all_fresh_on_disk()
            if self.kim_code == model.driver
        )


# --------------------------------------------
# Helper code
# --------------------------------------------
# two letter codes to the associated class
kim_code_to_class = {
    "mo": Model,
    "md": ModelDriver,
    "sm": SimulatorModel,
    "te": Test,
    "td": TestDriver,
    "vc": VerificationCheck,
}


def kim_obj(kim_code, *args, **kwargs):
    """Basic KIMObject factory. Given a kim code, initialize and return the
    correct type of object.
    """

    def _get_kim_type(kim_code):
        """The type code of the item in lowercase.  Possible return values:

        mo : Model
        sm : Simulator Model
        md : Model Driver

        Raises
        ------
        InvalidKIMCode
            If the kim code does not correspond to one of the types listed
            above.
        """
        if kimcodes.iskimid(kim_code):
            _, kim_type, _, _ = kimcodes.parse_kim_code(kim_code)
        elif kimcodes.isuuid(kim_code):
            _, _, _, kim_type = kimcodes.parse_kim_code(kim_code)
        else:
            raise cf.InvalidKIMCode(
                f"Item {kim_code} is not a KIM item (Model, Simulator Model,Model Driver, Verification Check, Test Result) or job result (Verification Result, or Error)."
            )

        return kim_type.lower()

    kim_type = _get_kim_type(kim_code)

    try:
        cls = kim_code_to_class[kim_type]
    except KeyError:
        raise cf.InvalidKIMCode(
            f"Invalid kim type code {kim_type} in item ID {kim_code}"
        )
    except IOError:
        raise cf.KIMkitItemNotFoundError(
            f"Could not initialize KIMObject for {kim_code}"
        )
    else:
        kobj = cls(kim_code, *args, **kwargs)
        return kobj


def leaders():
    return [i.lower() for i in list(kim_code_to_class.keys())]
