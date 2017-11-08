import contextlib
import tempfile
import textwrap
import unittest

from typing import Iterator

from addtypes_tools.annotations.infer import InferError
from addtypes_tools.annotations.main import generate_annotations_json


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
        target = tempfile.NamedTemporaryFile(mode='r')
        with self.temporary_json_file(data) as source_path:
            generate_annotations_json(source_path, target.name)

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

    @contextlib.contextmanager
    def temporary_json_file(self, data):
        # type: (str) -> Iterator[str]
        with tempfile.NamedTemporaryFile(mode='w') as source:
            source.write(data)
            source.flush()
            yield source.name
