"""Main entry point to mypy annotation inference utility."""

import json

from typing import List
from mypy_extensions import TypedDict

from pyannotate_tools.annotations.types import ARG_STAR, ARG_STARSTAR
from pyannotate_tools.annotations.infer import infer_annotation
from pyannotate_tools.annotations.parse import parse_json


# Schema of a function signature in the output
Signature = TypedDict('Signature', {'arg_types': List[str],
                                    'return_type': str})

# Schema of a function in the output
FunctionData = TypedDict('FunctionData', {'path': str,
                                          'line': int,
                                          'func_name': str,
                                          'signature': Signature,
                                          'samples': int})


def unify_type_comments(type_comments):
    # type: (List[str]) -> Signature
    arg_types, return_type = infer_annotation(type_comments)
    arg_strs = []
    for arg, kind in arg_types:
        arg_str = str(arg)
        if kind == ARG_STAR:
            arg_str = '*%s' % arg_str
        elif kind == ARG_STARSTAR:
            arg_str = '**%s' % arg_str
        arg_strs.append(arg_str)
    return {
        'arg_types': arg_strs,
        'return_type': str(return_type),
    }


def generate_annotations_json_string(source_path):
    # type: (str) -> List[FunctionData]
    """Produce annotation data JSON file from a JSON file with runtime-collected types.

    Data formats:

    * The source JSON is a list of pyannotate_tools.annotations.parse.RawEntry items.
    * The output JSON is a list of FunctionData items.
    """
    items = parse_json(source_path)
    results = []
    for item in items:
        signature = unify_type_comments(item.type_comments)
        data = {
            'path': item.path,
            'line': item.line,
            'func_name': item.func_name,
            'signature': signature,
            'samples': item.samples
        }  # type: FunctionData
        results.append(data)
    return results

def generate_annotations_json(source_path, target_path):
    # type: (str, str) -> None
    """Like generate_annotations_json_string() but writes JSON to a file."""
    results = generate_annotations_json_string(source_path)
    with open(target_path, 'w') as f:
        json.dump(results, f, sort_keys=True, indent=4)
