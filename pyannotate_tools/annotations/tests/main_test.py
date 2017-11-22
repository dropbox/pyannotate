import contextlib
import tempfile
import textwrap
import unittest

from typing import Iterator, Tuple, IO

from pyannotate_tools.annotations.infer import InferError
from pyannotate_tools.annotations.main import generate_annotations_json


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
        target = tempfile.NamedTemporaryFile(mode='w+')
        with self.temporary_json_file(data) as source:
            generate_annotations_json(source.name, target.name, source_stream=source, target_stream=target)

        target.flush()
        target.seek(0)
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
            with self.temporary_json_file(data) as source:
                generate_annotations_json(source.name, '/dummy', source_stream=source)
        assert str(e.exception) == textwrap.dedent("""\
            Ambiguous argument kinds:
            (List[int], str) -> None
            (List[int], *str) -> None""")

    @contextlib.contextmanager
    def temporary_json_file(self, data):
        # type: (str) -> Iterator[IO[str]]
        with tempfile.NamedTemporaryFile(mode='w+') as source:
            source.write(data)
            source.flush()
            source.seek(0)
            yield source
