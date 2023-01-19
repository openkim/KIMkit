import datetime
import sys
import os
import re
import json
from functools import partial
from collections import OrderedDict
import codecs

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from kim_utils import util, kimcodes

import users

SOURCE_CITATIONS_MATCH = re.compile(
    r"""
  \"source-citations\"\s\[($\n
    .*?$\n
  \s*)\]\s*\n
  """,
    flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
)

SIMULATOR_POTENTIAL_COMPATIBILITY_MATCH = re.compile(
    r"""
  \"simulator-potential-compatibility\"\s\[($\n
    .*?$\n
  \s*)\]\s*\n
  """,
    flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
)

FUNDING_MATCH = re.compile(
    r"""
  \"funding\"\s\[($\n
    .*?$\n
  \s*)\]\s*\n
  """,
    flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
)

DEVELOPER_MATCH = re.compile(
    r"""
  \"developer\"\s\[($\n
    .*?$\n
  \s*)\]\s*\n
  """,
    flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
)

IMPLEMENTER_MATCH = re.compile(
    r"""
  \"implementer\"\s\[($\n
    .*?$\n
  \s*)\]\s*\n
  """,
    flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
)

SPECIES_MATCH = re.compile(
    r"""
  \"species\"\s\[($\n
    .*?$\n
  \s*)\]\s*\n
  """,
    flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
)

jedns = partial(json.dumps, separators=(" ", " "), indent=1, ensure_ascii=False)
jedns_kimprov = partial(json.dumps, separators=(" ", " "), indent=2, ensure_ascii=False)

kimspec_order = [
    "extended-id",
    "title",
    "potential-type",
    "license",
    "kim-item-type",
    "kim-api-version",
    "species",
    "developer",
    "contributor",
    "maintainer",
    "model-driver",
    "simulator",
    "description",
    "funding",
    "doi",
    "disclaimer",
    "content-origin",
    "training",
    "source-citations",
    "content-other-locations",
    "date",
]


class MetaData:
    def __init__(self, repository, kimcode, metadata_dict=None):
        """Default metadata class for KIMkit items

        _extended_summary_

        Parameters
        ----------
        kimcode : str
            kimcode ID string of the item
        repository: path like
            repository where the item is saved
        metadata_dict: dict
            required to initialize metadata for a new item
            if not suppied, metadata information is read from existing kimspec.edn
            raises exception if neither metadata dict nor kimspec.edn for the item is found

            title : str
                human readable title of the item
            species : list of str
                species the item supports
            potential_type : str
                type of IM potential
            developer : list of str
                UUIDs of the item's developers
            contributor : list of str
                UUIDs of the item's contributors
            maintainer : list of str
                UUIDs of the item's maintainers
            license : str
                license the item is released under
            kim_item_type : str
                options include "simulator-model", "portable-model", and "model-driver"
            kim_api_version : str
                version of the kim API the item is compatible with
            description : str, optional
                description of the item, by default None
            funding : list of str, optional
                souces of funding supporting development of the item, by default None
            doi : str, optional
                DOI of the item, by default None
            disclaimer : str, optional
                any disclaimer regarding the item, by default None
            content_other_locations : list of str, optional
                other locations the item is archived, by default None
            content_origin : str, optional
                initial origin of the item, by default None
            source_citation : str, optional
                citation for the origin of the item, by default None
            training : str, optional
                ID of the training dataset associated with the item, by default None
            simulator : str, optional
                simulator used to run an SM, by default None
        """

        required_metadata_fields_strings = [
            "title",
            "license",
            "kim-item-type",
            "kim-api-version",
        ]

        required_metadata_fields_lists = [
            "developer",
            "contributor",
            "maintainer",
        ]

        optional_metadata_fields_strings = [
            "description",
            "funding",
            "doi",
            "disclaimer",
            "content-origin",
            "training",
        ]

        optional_metadata_fields_lists = [
            "source-citations",
            "content-other-locations",
        ]

        def validate_metadata(self, metadata_dict):
            """check that all required metadata fields have valid entries,
            and default optional metadata fields are of valid types

            Parameters
            ----------
            metadata_dict : dict
                dictionary of all required and any optional metadata keys
            """
            setattr(self, "date", str(datetime.datetime.now()))
            setattr(self, "extended-id", kimcode)

            try:
                kim_item_type = metadata_dict["kim-item-type"]

            except (KeyError):
                raise KeyError(
                    f"Required metadata field 'kim-item-type' not specified."
                )

            if kim_item_type == "portable-model":
                required_metadata_fields_strings.append("model-driver")
                required_metadata_fields_strings.append("potential-type")
                required_metadata_fields_lists.append("species")

            elif kim_item_type == "simulator-model":
                required_metadata_fields_strings.append("simulator")
                required_metadata_fields_strings.append("potential-type")
                required_metadata_fields_lists.append("species")

            elif kim_item_type == "model-driver":
                pass  # do nothing for now

            else:
                raise (
                    KeyError(
                        f"""kim-item-type not recognized.
                Valid item types include 'portable-model',
                 'simulator-model', and 'model-driver'"""
                    )
                )

            for field in required_metadata_fields_strings:
                if metadata_dict[field]:

                    if isinstance(metadata_dict[field], str):
                        value = metadata_dict[field]
                        setattr(self, field, value)

                    else:
                        raise (
                            TypeError(
                                f"Required metadata field {field} is of invalid type, must be str."
                            )
                        )

                else:
                    raise (KeyError(f"Required metadata field {field} not specified."))

            for field in required_metadata_fields_lists:
                if metadata_dict[field]:
                    if isinstance(metadata_dict[field], list) and all(
                        isinstance(item, str) for item in metadata_dict[field]
                    ):
                        value = metadata_dict[field]
                        setattr(self, field, value)

                    else:
                        raise (
                            TypeError(
                                f"Required metadata field {field} is of invalid type, must be list of str."
                            )
                        )
                else:
                    raise (KeyError(f"Required metadata field {field} not specified."))

            for field in optional_metadata_fields_strings:
                if field in metadata_dict:
                    if isinstance(metadata_dict[field], str):
                        value = metadata_dict[field]
                        setattr(self, field, value)

                    else:
                        raise (
                            TypeError(
                                f"Metadata field {field} is of invalid type, must be str."
                            )
                        )

            for field in optional_metadata_fields_lists:
                if field in metadata_dict:
                    if isinstance(metadata_dict[field], list) and all(
                        isinstance(item, str) for item in metadata_dict[field]
                    ):
                        value = metadata_dict[field]
                        setattr(self, field, value)

                    else:
                        raise (
                            TypeError(
                                f"Metadata field {field} is of invalid type, must be list of str."
                            )
                        )

        dest_path = kimcodes.kimcode_to_file_path(kimcode, repository)

        dest_file = os.path.join(dest_path, "kimspec.edn")

        if metadata_dict:
            validate_metadata(self, metadata_dict)

            # set any additional, user-specified metadata fields
            for key in metadata_dict:
                if key not in required_metadata_fields_strings:
                    if key not in required_metadata_fields_lists:
                        if key not in optional_metadata_fields_strings:
                            if key not in optional_metadata_fields_lists:
                                setattr(self, key, metadata_dict[key])

        else:
            if os.path.isfile(dest_file):
                existing_metadata = util.loadedn(dest_file)
                for key in existing_metadata:
                    setattr(self, key, existing_metadata[key])
            else:
                raise FileExistsError(
                    f"No metadata supplied and no kimspec.edn found in the directory of item {kimcode}, aborting."
                )

        # write a kimspec.edn if one doesn't already exist for this model
        if not os.path.exists(dest_file):
            self._write_metadata_to_file(kimcode, repository)

    def add_metadata_key(self, key, value):
        pass

    def delete_metadata_key(self, key):
        pass

    def edit_metadata_value(self, key, new_value):
        pass

    def _fork_metadata(self, existing_kimcode, new_kimcode):
        pass

    def _update_provenance_after_metadata_change(self, kimcode):
        pass

    def _write_metadata_to_file(self, kimcode, repository):
        """generate and write the kimspec.edn metadata file for a new KIM item

        Parameters
        ----------
        kimcode : str

        repository : pathlike
            repository the item is stored within
        """

        dest_path = kimcodes.kimcode_to_file_path(kimcode, repository)

        if os.path.exists(dest_path):
            dest_file = os.path.join(dest_path, "kimspec.edn")
            dumpedn_kimspec(vars(self), dest_file)

        else:
            raise FileNotFoundError(
                f"KIM item does not appear to exist in the selected repository {repository}"
            )


def dumpedn_kimspec(o, f, allow_nils=True):
    if not allow_nils:
        o = util.replace_nones(o)

    # If f is a string, create a file object
    if isinstance(f, str):
        flobj = codecs.open(f, "w", encoding="utf-8")
    else:
        flobj = f

    # Reorder keys to kimspec_order if this is a kimspec file
    if "kimspec.edn" in flobj.name:
        kimspec_new = OrderedDict([])
        for key in kimspec_order:
            if key in o:
                kimspec_new[key] = o[key]

        final_object = kimspec_new

        # Dump to string
        final_object_as_string = jedns(final_object)
        final_object_as_string = format_kimspec(final_object_as_string)

    # Remove trailing spaces
    final_object_stripped = ("\n").join(
        [x.rstrip() for x in final_object_as_string.splitlines()]
    )

    flobj.write(final_object_stripped)
    flobj.write("\n")

    flobj.close()


def get_individual_dicts(entries_block):
    # Add newline that's usually picked off by our other regex
    entries_block += "\n"

    ENTRIES_MATCH = re.compile(
        r"""
        \{.*?\}\s*$\n
        """,
        flags=re.VERBOSE | re.MULTILINE | re.DOTALL,
    )
    entries = ENTRIES_MATCH.findall(entries_block)
    if len(entries) == 0:
        raise RuntimeError("Failed to extract any individual dict entries")

    return entries


def format_kimspec_dicts(dicts, first_leading_indent):
    new_dicts = []
    dict_counter = 0
    num_dicts = len(dicts)
    for d in dicts:
        d_formatted = ""
        line_counter = 0
        d_split = d.strip().splitlines()
        for ln in d_split:
            # Handle indentation of first line
            if dict_counter == 0 and line_counter == 1:
                d_formatted += "{" + ln.strip() + "\n"
            elif dict_counter > 0 and line_counter == 1:
                d_formatted += " " * first_leading_indent + "{" + ln.strip() + "\n"
            elif line_counter == len(d_split) - 2:
                if dict_counter == num_dicts - 1:
                    d_formatted += " " * (first_leading_indent + 1) + ln.strip() + "}\n"
                else:
                    d_formatted += " " * indent + ln.strip() + "}\n"
            elif line_counter == len(d_split) - 1:
                pass
            elif line_counter > 1:
                indent = first_leading_indent + 1
                d_formatted += " " * indent + ln.strip() + "\n"
            line_counter += 1

        new_dicts.append(d_formatted)

        dict_counter += 1

    return ("").join(new_dicts)


def format_kimspec_array(array_block, first_leading_indent):
    new_block = ""
    line_counter = 0
    array_split = array_block.strip().splitlines()
    num_lines = len(array_split)

    if len(array_split) == 1:
        return array_block.strip()
    else:
        for ln in array_split:
            ln = ln.strip()

            if line_counter == 0:
                new_block += ln + "\n"
            elif line_counter > 0 and line_counter < num_lines - 1:
                new_block += " " * first_leading_indent + ln + "\n"
            elif line_counter == num_lines - 1:
                new_block += " " * first_leading_indent + ln

            line_counter += 1

    return new_block


def format_kimspec_flatten_array(array_block):
    new_block = []
    for ln in array_block.strip().splitlines():
        new_block.append(ln.strip())
    return (" ").join(new_block)


def format_kimspec(kimspec_as_str):

    new_kimspec_as_str = kimspec_as_str

    # First replace the source-citations section, if it exists
    sc = SOURCE_CITATIONS_MATCH.search(kimspec_as_str)
    if sc:
        source_citations_block = sc.group(1)
        source_citations_entries = get_individual_dicts(source_citations_block)

        formatted_source_citations = format_kimspec_dicts(
            source_citations_entries, first_leading_indent=21
        )

        new_kimspec_as_str = new_kimspec_as_str.replace(
            source_citations_block, formatted_source_citations
        )

    # Now replace the simulator-potential-compatibility section, if it exists
    spc = SIMULATOR_POTENTIAL_COMPATIBILITY_MATCH.search(kimspec_as_str)
    if spc:
        simulator_potential_compatibility_block = spc.group(1)
        simulator_potential_compatibility_entries = get_individual_dicts(
            simulator_potential_compatibility_block
        )

        formatted_simulator_potential_compatibility = format_kimspec_dicts(
            simulator_potential_compatibility_entries, first_leading_indent=38
        )

        new_kimspec_as_str = new_kimspec_as_str.replace(
            simulator_potential_compatibility_block,
            formatted_simulator_potential_compatibility,
        )

    # Now replace the funding section, if it exists
    funding = FUNDING_MATCH.search(kimspec_as_str)
    if funding:
        funding_block = funding.group(1)
        funding_entries = get_individual_dicts(funding_block)

        formatted_funding = format_kimspec_dicts(
            funding_entries, first_leading_indent=12
        )

        new_kimspec_as_str = new_kimspec_as_str.replace(
            funding_block,
            formatted_funding,
        )

    # Now replace the developer block
    dev = DEVELOPER_MATCH.search(kimspec_as_str)
    if not dev:
        raise Exception("Failed to match developer block!!! Exiting...")

    developer_block = dev.group(1)

    formatted_developer = format_kimspec_array(developer_block, first_leading_indent=14)

    new_kimspec_as_str = new_kimspec_as_str.replace(
        developer_block, formatted_developer
    )

    # Now replace the implementer block, if it exists
    impl = IMPLEMENTER_MATCH.search(kimspec_as_str)
    if impl:
        implementer_block = impl.group(1)

        formatted_implementer = format_kimspec_array(
            implementer_block, first_leading_indent=16
        )

        new_kimspec_as_str = new_kimspec_as_str.replace(
            implementer_block, formatted_implementer
        )

    # Now replace the species block, if it exists
    sp = SPECIES_MATCH.search(kimspec_as_str)
    if sp:
        species_block = sp.group(1)
        formatted_species = format_kimspec_flatten_array(species_block)
        new_kimspec_as_str = new_kimspec_as_str.replace(
            species_block, formatted_species
        )

    # FIXME: I think we need to handle 'executables' here.  I'm just not sure
    # what convention the web app uses for newlines/spacing

    # Now fix up the rest of the file
    new_kimspec_as_str = re.sub(
        '^{$\n "',
        '{"',
        new_kimspec_as_str,
        flags=re.MULTILINE,
    )
    new_kimspec_as_str = re.sub("}$\n]", "}]", new_kimspec_as_str, flags=re.MULTILINE)
    new_kimspec_as_str = re.sub('"$\n}', '"}', new_kimspec_as_str, flags=re.MULTILINE)

    return new_kimspec_as_str
