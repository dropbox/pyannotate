# flake8: noqa
# Our flake extension misfires on type comments in strings below.

import json
import os
import tempfile

from lib2to3.tests.test_fixers import FixerTestCase

from pyannotate_tools.fixes.fix_annotate_json import FixAnnotateJson


class TestFixAnnotateJson(FixerTestCase):

    def setUp(self):
        super(TestFixAnnotateJson, self).setUp(
            fix_list=["annotate_json"],
            fixer_pkg="pyannotate_tools",
        )
        # See https://bugs.python.org/issue14243 for details
        self.tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
        FixAnnotateJson.stub_json_file = self.tf.name
        FixAnnotateJson.stub_json = None

    def tearDown(self):
        FixAnnotateJson.stub_json = None
        FixAnnotateJson.stub_json_file = None
        self.tf.close()
        os.remove(self.tf.name)
        super(TestFixAnnotateJson, self).tearDown()

    def setTestData(self, data):
        json.dump(data, self.tf)
        self.tf.close()
        self.filename = data[0]["path"]

    def test_basic(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["Foo", "Bar"],
                  "return_type": "Any"},
              }])
        a = """\
            class Foo: pass
            class Bar: pass
            def nop(foo, bar):
                return 42
            """
        b = """\
            from typing import Any
            class Foo: pass
            class Bar: pass
            def nop(foo, bar):
                # type: (Foo, Bar) -> Any
                return 42
            """
        self.check(a, b)

    def test_keyword_only_argument(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["Foo", "Bar"],
                  "return_type": "Any"},
              }])
        a = """\
            class Foo: pass
            class Bar: pass
            def nop(foo, *, bar):
                return 42
            """
        b = """\
            from typing import Any
            class Foo: pass
            class Bar: pass
            def nop(foo, *, bar):
                # type: (Foo, Bar) -> Any
                return 42
            """
        self.check(a, b)

    def test_add_typing_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              # Check with and without 'typing.' prefix
              "signature": {
                  "arg_types": ["List[typing.AnyStr]", "Callable[[], int]"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, bar):
                return 42
            """
        b = """\
            from typing import AnyStr
            from typing import Callable
            from typing import List
            def nop(foo, bar):
                # type: (List[AnyStr], Callable[[], int]) -> object
                return 42
            """
        self.check(a, b)

    def test_add_other_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass", "mod2.OtherClass"],
                  "return_type": "mod3.AnotherClass"},
              }])
        a = """\
            def nop(foo, bar):
                return AnotherClass()
            class MyClass: pass
            """
        b = """\
            from mod2 import OtherClass
            from mod3 import AnotherClass
            def nop(foo, bar):
                # type: (MyClass, OtherClass) -> AnotherClass
                return AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_add_kwds(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, **kwds):
                return 42
            """
        b = """\
            from typing import Any
            def nop(foo, **kwds):
                # type: (int, **Any) -> object
                return 42
            """
        self.check(a, b)

    def test_dont_add_kwds(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int", "**AnyStr"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, **kwds):
                return 42
            """
        b = """\
            from typing import AnyStr
            def nop(foo, **kwds):
                # type: (int, **AnyStr) -> object
                return 42
            """
        self.check(a, b)

    def test_add_varargs(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, *args):
                return 42
            """
        b = """\
            from typing import Any
            def nop(foo, *args):
                # type: (int, *Any) -> object
                return 42
            """
        self.check(a, b)

    def test_dont_add_varargs(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int", "*int"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, *args):
                return 42
            """
        b = """\
            def nop(foo, *args):
                # type: (int, *int) -> object
                return 42
            """
        self.check(a, b)

    def test_return_expr_not_none(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "None"},
              }])
        a = """\
            def nop():
                return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            def nop():
                # type: () -> Optional[Any]
                return 0
            """
        self.check(a, b)

    def test_return_expr_none(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "None"},
              }])
        a = """\
            def nop():
                return
            """
        b = """\
            def nop():
                # type: () -> None
                return
            """
        self.check(a, b)

    def test_generator_optional(self):
        self.setTestData(
            [{"func_name": "gen",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "Optional[int]"},
              }])
        a = """\
            def gen():
                yield 42
            """
        b = """\
            from typing import Iterator
            def gen():
                # type: () -> Iterator[int]
                yield 42
            """
        self.check(a, b)

    def test_generator_plain(self):
        self.setTestData(
            [{"func_name": "gen",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def gen():
                yield 42
            """
        b = """\
            from typing import Iterator
            def gen():
                # type: () -> Iterator[int]
                yield 42
            """
        self.check(a, b)

    def test_not_generator(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop():
                def gen():
                    yield 42
            """
        b = """\
            def nop():
                # type: () -> int
                def gen():
                    yield 42
            """
        self.check(a, b)

    def test_add_self(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop(self):
                pass
            """
        b = """\
            from typing import Any
            def nop(self):
                # type: (Any) -> int
                pass
            """
        self.check(a, b)

    def test_dont_add_self(self):
        self.setTestData(
            [{"func_name": "C.nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            class C:
                def nop(self):
                    pass
            """
        b = """\
            class C:
                def nop(self):
                    # type: () -> int
                    pass
            """
        self.check(a, b)

    def test_too_many_types(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"},
              }])
        a = """\
            def nop():
                pass
            """
        self.warns(a, a, "source has 0 args, annotation has 1 -- skipping", unchanged=True)

    def test_too_few_types(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a):
                pass
            """
        self.warns(a, a, "source has 1 args, annotation has 0 -- skipping", unchanged=True)

    def test_line_number_drift(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 10,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a):
                pass
            """
        self.warns(a, a, "signature from line 10 too far away -- skipping", unchanged=True)

    def test_classmethod(self):
        # Class method names currently are returned without class name
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"}
              }])
        a = """\
            class C:
                @classmethod
                def nop(cls, a):
                    return a
            """
        b = """\
            class C:
                @classmethod
                def nop(cls, a):
                    # type: (int) -> int
                    return a
            """
        self.check(a, b)

    def test_staticmethod(self):
        # Static method names currently are returned without class name
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"}
              }])
        a = """\
            class C:
                @staticmethod
                def nop(a):
                    return a
            """
        b = """\
            class C:
                @staticmethod
                def nop(a):
                    # type: (int) -> int
                    return a
            """
        self.check(a, b)

    def test_long_form(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]", "*Any"],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a, b, c,  # some comment
                    d, e, f,  # multi-line
                              # comment
                    g=None, h=0, *args):
                return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            from typing import Union
            def nop(a,  # type: int
                    b,  # type: int
                    c,  # type: int  # some comment
                    d,  # type: str
                    e,  # type: str
                    f,  # type: str  # multi-line
                              # comment
                    g=None,  # type: Optional[bool]
                    h=0,  # type: Union[int, str]
                    *args  # type: Any
                    ):
                # type: (...) -> int
                return 0
            """
        self.check(a, b)

    def test_long_form_method(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "C.nop",
              "path": "<string>",
              "line": 2,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]", "*Any"],
                  "return_type": "int"},
              }])
        a = """\
            class C:
                def nop(self, a, b, c,  # some comment
                              d, e, f,  # multi-line
                                        # comment
                              g=None, h=0, *args):
                    return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            from typing import Union
            class C:
                def nop(self,
                        a,  # type: int
                        b,  # type: int
                        c,  # type: int  # some comment
                        d,  # type: str
                        e,  # type: str
                        f,  # type: str  # multi-line
                                        # comment
                        g=None,  # type: Optional[bool]
                        h=0,  # type: Union[int, str]
                        *args  # type: Any
                        ):
                    # type: (...) -> int
                    return 0
            """
        self.check(a, b)

    def test_long_form_classmethod(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]", "*Any"],
                  "return_type": "int"},
              }])
        a = """\
            class C:
                @classmethod
                def nop(cls, a, b, c,  # some comment
                        d, e, f,
                        g=None, h=0, *args):
                    return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            from typing import Union
            class C:
                @classmethod
                def nop(cls,
                        a,  # type: int
                        b,  # type: int
                        c,  # type: int  # some comment
                        d,  # type: str
                        e,  # type: str
                        f,  # type: str
                        g=None,  # type: Optional[bool]
                        h=0,  # type: Union[int, str]
                        *args  # type: Any
                        ):
                    # type: (...) -> int
                    return 0
            """
        self.check(a, b)
        # Do the same test for staticmethod
        a = a.replace('classmethod', 'staticmethod')
        b = b.replace('classmethod', 'staticmethod')
        self.check(a, b)

    def test_long_form_trailing_comma(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]"],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a, b, c,  # some comment
                    d, e, f,
                    g=None, h=0):
                return 0
            """
        b = """\
            from typing import Optional
            from typing import Union
            def nop(a,  # type: int
                    b,  # type: int
                    c,  # type: int  # some comment
                    d,  # type: str
                    e,  # type: str
                    f,  # type: str
                    g=None,  # type: Optional[bool]
                    h=0,  # type: Union[int, str]
                    ):
                # type: (...) -> int
                return 0
            """
        self.check(a, b)

    def test_one_liner(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a):   return a
            """
        b = """\
            def nop(a):
                # type: (int) -> int
                return a
            """
        self.check(a, b)
