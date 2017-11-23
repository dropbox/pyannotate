from __future__ import print_function

import argparse
import logging

from lib2to3.main import StdoutRefactoringTool

from typing import Any, Dict, List, Optional

from pyannotate_tools.annotations.main import generate_annotations_json_string
from pyannotate_tools.fixes.fix_annotate_json import FixAnnotateJson

parser = argparse.ArgumentParser()
parser.add_argument('--type-info', default='type_info.json', metavar="FILE",
                    help="JSON input file (default type_info.json)")
parser.add_argument('-p', '--print-function', action='store_true',
                    help="Assume print is a function")
parser.add_argument('-w', '--write', action='store_true',
                    help="Write output files")
parser.add_argument('-j', '--processes', type=int, default=1, metavar="N",
                    help="Use N parallel processes (default no parallelism)")
parser.add_argument('-v', '--verbose', action='store_true',
                    help="More verbose output")
parser.add_argument('-q', '--quiet', action='store_true',
                    help="Don't show diffs")
parser.add_argument('files', nargs='*',
                    help="Files and directories to update with annotations")


def main(args_override=None):
    # type: (Optional[List[str]]) -> None
    # Parse command line.
    args = parser.parse_args(args_override)
    if not args.files:
        parser.error("At least one file/directory is required")

    # Set up logging handler.
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format='%(message)s', level=level)

    # Run pass 2 with output into a variable.
    infile = args.type_info
    data = generate_annotations_json_string(infile)  # type: List[Any]

    # Run pass 3 with input from that variable.
    FixAnnotateJson.init_stub_json_from_data(data, args.files[0])
    fixers = ['pyannotate_tools.fixes.fix_annotate_json']
    flags = {'print_function': args.print_function}
    rt = StdoutRefactoringTool(
        fixers=fixers,
        options=flags,
        explicit=fixers,
        nobackups=True,
        show_diffs=not args.quiet)
    if not rt.errors:
        rt.refactor(args.files, write=args.write, num_processes=args.processes)
        if args.processes == 1:
            rt.summarize()
        else:
            logging.info("(In multi-process per-file warnings are lost)")
    if not args.write:
        logging.info("NOTE: this was a dry run; use -w to write files")


if __name__ == '__main__':
    main()
