from __future__ import print_function

import argparse
import json
import logging
import os
import sys

from lib2to3.main import StdoutRefactoringTool

from typing import Any, Dict, List, Optional

from pyannotate_tools.annotations.main import generate_annotations_json_string, unify_type_comments
from pyannotate_tools.fixes.fix_annotate_json import FixAnnotateJson

parser = argparse.ArgumentParser()
parser.add_argument('--type-info', default='type_info.json', metavar="FILE",
                    help="JSON input file (default type_info.json)")
parser.add_argument('--uses-signature', action='store_true',
                    help="JSON input uses a signature format")
parser.add_argument('-p', '--print-function', action='store_true',
                    help="Assume print is a function")
parser.add_argument('-w', '--write', action='store_true',
                    help="Write output files")
parser.add_argument('-j', '--processes', type=int, default=1, metavar="N",
                    help="Use N parallel processes (default no parallelism)")
parser.add_argument('--max-line-drift', type=int, default=5, metavar="N",
                    help="Maximum allowed line drift when inserting annotation"
                         " (can be useful for custom codecs)")
parser.add_argument('-v', '--verbose', action='store_true',
                    help="More verbose output")
parser.add_argument('-q', '--quiet', action='store_true',
                    help="Don't show diffs")
parser.add_argument('-d', '--dump', action='store_true',
                    help="Dump raw type annotations (filter by files, default all)")
parser.add_argument('-a', '--auto-any', action='store_true',
                    help="Annotate everything with 'Any', without reading type_info.json")
parser.add_argument('files', nargs='*', metavar="FILE",
                    help="Files and directories to update with annotations")
parser.add_argument('-s', '--only-simple', action='store_true',
                    help="Only annotate functions with trivial types")
parser.add_argument('--python-version', action='store', default='2', choices=['2', '3'],
                    help="Choose annotation style, 2 for Python 2 with comments (the "
                         "default), 3 for Python 3 with annotation syntax" )
parser.add_argument('--py2', '-2', action='store_const', dest='python_version', const='2',
                    help="Annotate for Python 2 with comments (default)")
parser.add_argument('--py3', '-3', action='store_const', dest='python_version', const='3',
                    help="Annotate for Python 3 with argument and return value annotations")


class ModifiedRefactoringTool(StdoutRefactoringTool):
    """Class that gives a nicer error message for bad encodings."""

    def refactor_file(self, filename, write=False, doctests_only=False):
        try:
            super(ModifiedRefactoringTool, self).refactor_file(
                filename, write=write, doctests_only=doctests_only)
        except SyntaxError as err:
            if str(err).startswith("unknown encoding:"):
                self.log_error("Can't parse %s: %s", filename, err)
            else:
                raise


def dump_annotations(type_info, files):
    """Dump annotations out of type_info, filtered by files.

    If files is non-empty, only dump items either if the path in the
    item matches one of the files exactly, or else if one of the files
    is a path prefix of the path.
    """
    with open(type_info) as f:
        data = json.load(f)
    for item in data:
        path, line, func_name = item['path'], item['line'], item['func_name']
        if files and path not in files:
            for f in files:
                if path.startswith(os.path.join(f, '')):
                    break
            else:
                continue  # Outer loop
        print("%s:%d: in %s:" % (path, line, func_name))
        type_comments = item['type_comments']
        signature = unify_type_comments(type_comments)
        arg_types = signature['arg_types']
        return_type = signature['return_type']
        print("    # type: (%s) -> %s" % (", ".join(arg_types), return_type))


def main(args_override=None):
    # type: (Optional[List[str]]) -> None

    # Parse command line.
    args = parser.parse_args(args_override)
    if not args.files and not args.dump:
        parser.error("At least one file/directory is required")

    if args.python_version not in ('2', '3'):
        sys.exit('--python-version must be 2 or 3')

    annotation_style = 'py' + args.python_version

    # Set up logging handler.
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format='%(message)s', level=level)

    if args.dump:
        dump_annotations(args.type_info, args.files)
        return

    if args.auto_any:
        fixers = ['pyannotate_tools.fixes.fix_annotate']
    else:
        # Produce nice error message if type_info.json not found.
        try:
            with open(args.type_info) as f:
                contents = f.read()
        except IOError as err:
            sys.exit("Can't open type info file: %s" % err)

        # Run pass 2 with output into a variable.
        if args.uses_signature:
            data = json.loads(contents)  # type: List[Any]
        else:
            data = generate_annotations_json_string(
                args.type_info,
                only_simple=args.only_simple)

        # Run pass 3 with input from that variable.
        FixAnnotateJson.init_stub_json_from_data(data, args.files[0])
        fixers = ['pyannotate_tools.fixes.fix_annotate_json']

    flags = {'print_function': args.print_function,
             'annotation_style': annotation_style}
    rt = ModifiedRefactoringTool(
        fixers=fixers,
        options=flags,
        explicit=fixers,
        nobackups=True,
        show_diffs=not args.quiet)
    if not rt.errors:
        with FixAnnotateJson.max_line_drift_set(args.max_line_drift):
            rt.refactor(args.files, write=args.write, num_processes=args.processes)
        if args.processes == 1:
            rt.summarize()
        else:
            logging.info("(In multi-process per-file warnings are lost)")
    if not args.write:
        logging.info("NOTE: this was a dry run; use -w to write files")


if __name__ == '__main__':
    main()
