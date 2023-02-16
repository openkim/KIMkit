"""
Copyright 2014-2021 Alex Alemi, Matt Bierbaum, Woosong Choi, Daniel S. Karls, James P. Sethna

Please do not distribute this code.
"""
import os
import edn_format
import json
import subprocess
import pathlib
import tarfile
import shutil
import re
from functools import partial

import config as cf


ImmutableList = edn_format.immutable_list.ImmutableList
ImmutableDict = edn_format.immutable_dict.ImmutableDict

jedns = partial(json.dumps, separators=(" ", " "), indent=4)


def replace_nones(o):
    if isinstance(o, list):
        return [replace_nones(i) for i in o]
    elif isinstance(o, dict):
        return {k: replace_nones(v) for k, v in o.items()}
    else:
        return o if o is not None else ""


def loadedn(f):
    """Load a file, filename, or string containing valid EDN into a dict.
    For whatever, reason, the 'edn_format' module always returns (nested)
    structures of its own internally defined types, ImmutableList and
    ImmutableDict.  Since we generally need to take the content we load
    from an EDN file and do something like json.dumps with it, this
    presents a problem.  Therefore, we recurse through them, converting all
    ImmutableList instances to regular python lists and all ImmutableDict
    instances to regular python dicts.

    NOTE: This function assumes that the content being loaded is always
    contained (at least at the uppermost level) in a dict or list, i.e. {}
    or [] brackets.  If not, we cowardly raise an exception."""

    def convert_immutablelist_to_list(l):
        """Go through all of the elements of this edn_format.ImmutableList
        object and convert them to either list or dict as appropriate"""
        if isinstance(l, ImmutableList):
            l = list(l)
            for ind, entry in enumerate(l):
                if isinstance(entry, ImmutableList):
                    l[ind] = convert_immutablelist_to_list(entry)
                elif isinstance(entry, ImmutableDict):
                    l[ind] = convert_immutabledict_to_dict(entry)
        return l

    def convert_immutabledict_to_dict(d):
        """Go through all of they key-value pairs  of this edn_format
        ImmutableDict object and convert the values to either list or dict as
        appropriate"""
        if isinstance(d, ImmutableDict):
            d = dict(d)
            for key, val in d.items():
                if isinstance(val, ImmutableList):
                    d[key] = convert_immutablelist_to_list(val)
                elif isinstance(val, ImmutableDict):
                    d[key] = convert_immutabledict_to_dict(val)
        return d

    if isinstance(f, str):
        try:
            # See if this is a file name
            with open(f, encoding="utf-8") as fo:
                c = fo.read()
                content = edn_format.loads(c, write_ply_tables=False)
        except IOError:
            # Assume it's a valid EDN-formatted string
            content = edn_format.loads(f, write_ply_tables=False)
    else:
        c = f.read()
        content = edn_format.loads(c, write_ply_tables=False)

    if isinstance(content, ImmutableList):
        content = convert_immutablelist_to_list(content)
    elif isinstance(content, ImmutableDict):
        content = convert_immutabledict_to_dict(content)
    else:
        raise cf.PipelineInvalidEDN(
            "Loaded EDN file or object {}, but it is "
            "not a list or dict.  Only lists or dicts are allowed.".format(f)
        )

    return content


def dumpedn(o, f, allow_nils=True):
    if not allow_nils:
        o = replace_nones(o)
    o = jedns(o)

    if isinstance(f, str):
        with open(f, "w", encoding="utf-8") as fi:
            fi.write(o)
            fi.write("\n")
    else:
        f.write(o)
        f.write("\n")


def mkdir_ext(p):
    if not os.path.exists(p):
        subprocess.check_call(["mkdir", "-p", p])


def flatten(o):
    if isinstance(o, dict):
        out = {}
        for key, value in o.items():
            c = flatten(value)
            if isinstance(c, dict):
                out.update({key + "." + subkey: subval for subkey, subval in c.items()})
            else:
                out.update({key: c})
        return out

    elif not isinstance(o, (str, bytes)) and hasattr(o, "__iter__"):
        return [flatten(item) for item in o]
    else:
        return o


def doproject(o, keys):
    if isinstance(o, dict):
        o = flatten(o)
        try:
            out = [o[key] for key in keys]
            if len(out) == 1:
                return out[0]
            return out
        except KeyError:
            return None

    if not isinstance(o, (str, bytes)) and hasattr(o, "__iter__"):
        ll = []
        for item in o:
            a = doproject(item, keys)
            if a is not None:
                ll.append(a)

        if len(ll) == 1:
            return ll[0]
        return ll
    else:
        raise o


def max_run_time_is_valid(max_run_time):
    RE_MAX_RUN_TIME = re.compile("^[0-9]+:[0-9]+:[0-9]+$")
    if RE_MAX_RUN_TIME.match(max_run_time):
        return True
    else:
        return False


def create_tarball(
    src_dir, dst_dir, files_and_dirs=None, arcname=None, remove_files_and_dirs=False
):
    """Create a gzipped tar archive from a directory or a specific list
    of files and directories inside of some directory and place it in a
    destination directory.

    Parameters
    ----------
    src_dir : str
        Absolute path of the directory that is either going to be tarred
        up in its entirety, or contains files and directories that are
        going to be tarred up.
    dst_dir : str
        Absolute path of the directory to place the completed archive in.
    files_and_dirs : tuple or list, optional
        If a non-empty tuple or list of strings, the corresponding files
        and/or directories with the corresponding names that exist inside
        of `src_dir` will be added to the archive, while any remaining
        files/directories in `src_dir` will be ignored. If None, the
        entire src_dir will itself be added to the archive. Default:
        None.
    arcname : str, optional
        Mame for the resulting archive. If None, the archive will be
        named after `src_dir`. Note that this is the archive name itself,
        not the compressed archive file name, and so this should *not*
        include an extension such as ".tgz". A ".tgz" extension will be
        appended automatically. Default: None.
    remove_files_and_dirs : bool, optional
        If `files_and_dirs` is None, delete `src_dir` after creating the
        archive. Otherwise, delete all files/directories in
        `files_and_dirs` after creating the archive. Default: False.

    Raises
    ------
    ValueError
        If `dest_dir` does not exist (caller needs to create directory first).
    ValueError
        If `remove_files_and_dirs`==True and `dst_dir` is equal to or a
        subdirectory of a directory that would be deleted after
        archiving.
    """
    src_dir = pathlib.Path(src_dir)
    dst_dir = pathlib.Path(dst_dir)

    if not dst_dir.is_dir():
        raise ValueError(f"Destination directory {dst_dir} does not exist.")

    dst_dir_would_be_removed = False
    if remove_files_and_dirs:
        dst_dir_parts = dst_dir.parts
        if not files_and_dirs:
            if src_dir.parts <= dst_dir_parts:
                dst_dir_would_be_removed = True
        else:
            for fl_or_dir in files_and_dirs:
                fl_or_dir_path = src_dir / fl_or_dir
                if fl_or_dir_path.is_dir():
                    if fl_or_dir_path.parts <= dst_dir_parts:
                        dst_dir_would_be_removed = True
                        break

    if dst_dir_would_be_removed:
        raise ValueError(
            f"Destination directory {dst_dir} falls under a directory "
            "that you have requested be deleted after the archiving "
            "process. Choose a different destination directory."
            "Exiting..."
        )

    if arcname is None:
        arcname = src_dir.name

    tarball_path = (dst_dir / arcname).with_suffix(".tgz")

    if not files_and_dirs:
        with tarfile.open(tarball_path, mode="w:gz") as tarball:
            tarball.add(src_dir, arcname=arcname)

        if remove_files_and_dirs:
            shutil.rmtree(src_dir)

    else:
        with tarfile.open(tarball_path, mode="w:gz") as tarball:
            for fl_or_dir in files_and_dirs:
                fl_or_dir_path = src_dir / fl_or_dir
                tarball.add(fl_or_dir_path, arcname=fl_or_dir)

                if remove_files_and_dirs:
                    if fl_or_dir_path.is_dir():
                        shutil.rmtree(fl_or_dir_path)
                    else:
                        fl_or_dir_path.unlink()
