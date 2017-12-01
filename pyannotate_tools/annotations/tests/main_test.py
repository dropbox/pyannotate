import contextlib
import os
import tempfile
import textwrap
import unittest

from typing import Iterator

from pyannotate_tools.annotations.infer import InferError
from pyannotate_tools.annotations.main import (generate_annotations_json,
                                               generate_annotations_json_string)


class TestMain(unittest.TestCase):
    def test_generation(self):
        # type: () -> None
        data = """
        [
            {
                "path": "pkg/thing.py",
                "line": 422,
                "func_name": "my_function",
                "type_comments": [
                    "(List[int], str) -> None"
                ],
                "samples": 3
            }
        ]
        """
        with self.temporary_file() as target_path:
            with self.temporary_json_file(data) as source_path:
                generate_annotations_json(source_path, target_path)
            with open(target_path) as target:
                actual = target.read()

        actual = actual.replace(' \n', '\n')
        expected = textwrap.dedent("""\
            [
                {
                    "func_name": "my_function",
                    "line": 422,
                    "path": "pkg/thing.py",
                    "samples": 3,
                    "signature": {
                        "arg_types": [
                            "List[int]",
                            "str"
                        ],
                        "return_type": "None"
                    }
                }
            ]""")
        assert actual == expected

    def test_ambiguous_kind(self):
        # type: () -> None
        data = """
        [
            {
                "path": "pkg/thing.py",
                "line": 422,
                "func_name": "my_function",
                "type_comments": [
                    "(List[int], str) -> None",
                    "(List[int], *str) -> None"
                ],
                "samples": 3
            }
        ]
        """
        with self.assertRaises(InferError) as e:
            with self.temporary_json_file(data) as source_path:
                generate_annotations_json(source_path, '/dummy')
        assert str(e.exception) == textwrap.dedent("""\
            Ambiguous argument kinds:
            (List[int], str) -> None
            (List[int], *str) -> None""")

    def test_generate_to_memory(self):
        # type: () -> None
        data = """
        [
            {
                "path": "pkg/thing.py",
                "line": 422,
                "func_name": "my_function",
                "type_comments": [
                    "(List[int], str) -> None"
                ],
                "samples": 3
            }
        ]
        """
        with self.temporary_json_file(data) as source_path:
            output_data = generate_annotations_json_string(source_path)
        assert output_data == [
            {
                "path": "pkg/thing.py",
                "line": 422,
                "func_name": "my_function",
                "signature": {
                    "arg_types": [
                        "List[int]",
                        "str"
                    ],
                    "return_type": "None"
                },
                "samples": 3
            }
        ]

    @contextlib.contextmanager
    def temporary_json_file(self, data):
        # type: (str) -> Iterator[str]
        source = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as source:
                source.write(data)
            yield source.name
        finally:
            if source is not None:
                os.remove(source.name)

    @contextlib.contextmanager
    def temporary_file(self):
        # type: () -> Iterator[str]
        target = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as target:
                pass
            yield target.name
        finally:
            if target is not None:
                os.remove(target.name)
