"""
Methods that deal with the KIM API directly.  Currently these are methods
that build the libraries and use the Python interface kimpy
to test if tests and models match.
"""

import os
from subprocess import check_call, CalledProcessError
from contextlib import contextmanager
import packaging.specifiers, packaging.version

from . import config as cf
from .logger import logging

logger = logging.getLogger("KIMkit")

# ======================================
# API build utilities
# ======================================
MAKE_LOG = os.path.join(cf.LOG_DIR, "make.log")


@contextmanager
def in_dir(path):
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    except Exception as e:
        raise e
    finally:
        os.chdir(cwd)


def make_object(obj, approved=True):
    """
    If this object is a Model Driver, Model, or Simulator Model, simply call
    the kim-api-collections-management util with the 'install' subcommand.
    This will install the item in the default user collection, where it will be
    accessible to all Tests/Verification Checks.

    If this object is a Test Driver or runner (Test or Verification Check):
      1. Go into its directory in ~/openkim-repository/[td, te, vc]
      2. Check if there is a file named CMakeLists.txt.  If so, do
           a. mkdir build && cd build
           b. cmake ..
           c. make
           d. copy build and lib to obj dir and delete 'build' subdir???
         and copy the required runner/libs back up into the object's directory
      3. If there is not a CMakeLists.txt file, check if there's a Makefile
         present. If so, simply execute `make`
      4. If there isn't a CMakeLists.txt file or a Makefile, forgo building the
         item
    """
    logger.debug(
        "%r: in function kim_api.make_object with approved=%r" % (obj, approved)
    )

    # First, check if we've already built & installed this item
    if os.path.isfile(os.path.join(obj.path, "built-by-%s" % cf.UUID)):
        logger.debug("%r: File 'built-by-%s' found, skipping 'make'" % (obj, cf.UUID))
        return

    if not packaging.version.Version(
        obj.kim_api_version
    ) in packaging.specifiers.SpecifierSet(cf.__kim_api_version_support_spec__):
        errmsg = (
            "%r: Currently installed KIM API version (%s) is not compatible with object's (%s)"
            % (obj, cf.__kim_api_version__, obj.kim_api_version)
        )
        logger.error(errmsg)
        raise cf.UnsupportedKIMAPIversion(errmsg)

    leader = obj.kim_code_leader.lower()

    with obj.in_dir():
        with open(MAKE_LOG, "a") as log:
            # using `echo` command to ensure proper log write stream sequence,
            # was getting out-of-order stream with object info coming after
            # calling 'make' when using:
            #
            #     log.write("%r\n" % obj)
            #
            check_call(["echo", "%r" % obj], stdout=log, stderr=log)

            try:
                check_call(
                    [
                        "kim-api-collections-management",
                        "install",
                        "environment",
                        obj.path,
                    ],
                    stdout=log,
                    stderr=log,
                ),

                check_call(["touch", "built-by-%s" % cf.UUID], stdout=log, stderr=log)

            except CalledProcessError:
                logger.exception("Could not build %r, check %s" % (obj, MAKE_LOG))
                raise cf.KIMBuildError("Could not build %r, check %s" % (obj, MAKE_LOG))
