"""
Methods that deal with the KIM API directly.  Currently these are methods
that build the libraries and use the Python interface kimpy
to test if tests and models match.

Copyright 2014-2021 Alex Alemi, Matt Bierbaum, Woosong Choi, Daniel S. Karls, James P. Sethna

Please do not distribute this code.
"""
import os
from subprocess import check_call, CalledProcessError
from contextlib import contextmanager
import packaging.specifiers, packaging.version

from . import config as cf
from .logger import logging

logger = logging.getLogger("pipeline").getChild("kimapi")

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
                if leader in ["md", "mo", "sm"]:
                    if approved:
                        check_call(
                            [
                                "kim-api-collections-management",
                                "install",
                                "user",
                                obj.path,
                            ],
                            stdout=log,
                            stderr=log,
                        ),
                    else:
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

                elif leader in ["td", "te", "vc"]:

                    # First, check for a makefile
                    possible_makefile_names = ["GNUmakefile", "makefile", "Makefile"]

                    found_makefile = False
                    for makefile_name in possible_makefile_names:
                        if os.path.isfile(os.path.join(obj.path, makefile_name)):
                            found_makefile = True
                            break

                    if found_makefile:
                        check_call(["make"], stdout=log, stderr=log)

                    else:
                        # Try to build with cmake in test directory (since
                        # nothing from runners gets installed anywhere
                        # specifically)
                        check_call(
                            [
                                "cmake",
                                obj.path,
                                "-DCMAKE_BUILD_TYPE=" + cf.CMAKE_BUILD_TYPE,
                            ],
                            cwd=obj.path,
                            stdout=log,
                            stderr=log,
                        )
                        check_call(["make"], cwd=obj.path, stdout=log, stderr=log)

                check_call(["touch", "built-by-%s" % cf.UUID], stdout=log, stderr=log)

            except CalledProcessError:
                driver = obj.driver
                if (not approved) and driver:
                    # Here, we perform an extra check to see if the compilation
                    # of this item failed simply because it's a pending item
                    # with a pending driver and the driver wasn't found during
                    # the build attempt. This doesn't apply to Models because
                    # we store pending drivers in the environment variable
                    # collection (just as we do for pending Models). Since VCs
                    # cannot have drivers, this means we only need to proceed
                    # if this item is a pending Test that uses a driver.
                    if leader != "te":
                        pass
                    else:
                        # If we are attempting to build a Test whose driver is only
                        # present in the local 'pending' directory of the Director, create
                        # a temporary symlink where the driver would sit in the
                        # LOCAL_REPOSITORY_PATH to where it sits in the 'pending' directory
                        src = []
                        symlink_path = []
                        src.append(
                            os.path.join(
                                cf.LOCAL_REPOSITORY_PATH, "pending", "td", driver
                            )
                        )
                        symlink_path.append(
                            os.path.join(cf.LOCAL_REPOSITORY_PATH, "td", driver)
                        )

                        try:
                            for s, l in zip(src, symlink_path):
                                os.symlink(s, l)
                        except CalledProcessError:
                            logger.exception(
                                "Failed to create driver symlink for build of pending item %r"
                                % obj
                            )
                            logger.exception(
                                "Could not build %r, check %s" % (obj, MAKE_LOG)
                            )
                            raise cf.KIMBuildError(
                                "Could not build %r, check %s" % (obj, MAKE_LOG)
                            )

                        # Now try to build one more time before giving up
                        try:
                            # TODO: Need to check for CMakeLists.txt and act accordingly
                            #        (can we just do a `make install`?)
                            check_call(["make"], stdout=log, stderr=log)
                            check_call(
                                ["touch", "built-by-%s" % cf.UUID],
                                stdout=log,
                                stderr=log,
                            )
                        except CalledProcessError:
                            logger.exception(
                                "Could not build %r, check %s" % (obj, MAKE_LOG)
                            )
                            raise cf.KIMBuildError(
                                "Could not build %r, check %s" % (obj, MAKE_LOG)
                            )

                        # Delete symlinks
                        for l in symlink_path:
                            os.remove(l)
                else:
                    logger.exception("Could not build %r, check %s" % (obj, MAKE_LOG))
                    raise cf.KIMBuildError(
                        "Could not build %r, check %s" % (obj, MAKE_LOG)
                    )
