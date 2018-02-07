# flake8: noqa
# Our flake extension misfires on type comments in strings below.

from lib2to3.tests.test_fixers import FixerTestCase

# deadcode: fix_annotate is used as part of the fixer_pkg for this test
from pyannotate_tools.fixes import fix_annotate


class TestFixAnnotate(FixerTestCase):

    def setUp(self):
        super(TestFixAnnotate, self).setUp(
            fix_list=["annotate"],
            fixer_pkg="pyannotate_tools",
        )

    def test_no_arg(self):
        a = """\
            def nop():
                return 42
            """
        b = """\
            from typing import Any
            def nop():
                # type: () -> Any
                return 42
            """
        self.check(a, b)

    def test_one_arg(self):
        a = """\
            def incr(arg):
                return arg+1
            """
        b = """\
            from typing import Any
            def incr(arg):
                # type: (Any) -> Any
                return arg+1
            """
        self.check(a, b)

    def test_two_args(self):
        a = """\
            def add(arg1, arg2):
                return arg1+arg2
            """
        b = """\
            from typing import Any
            def add(arg1, arg2):
                # type: (Any, Any) -> Any
                return arg1+arg2
            """
        self.check(a, b)

    def test_defaults(self):
        a = """\
            def foo(iarg=0, farg=0.0, sarg='', uarg=u'', barg=False):
                return 42
            """
        b = """\
            from typing import Any
            def foo(iarg=0, farg=0.0, sarg='', uarg=u'', barg=False):
                # type: (int, float, str, unicode, bool) -> Any
                return 42
            """
        self.check(a, b)

    def test_staticmethod(self):
        a = """\
            class C:
                @staticmethod
                def incr(self):
                    return 42
            """
        b = """\
            from typing import Any
            class C:
                @staticmethod
                def incr(self):
                    # type: (Any) -> Any
                    return 42
            """
        self.check(a, b)

    def test_classmethod(self):
        a = """\
            class C:
                @classmethod
                def incr(cls, arg):
                    return 42
            """
        b = """\
            from typing import Any
            class C:
                @classmethod
                def incr(cls, arg):
                    # type: (Any) -> Any
                    return 42
            """
        self.check(a, b)

    def test_instancemethod(self):
        a = """\
            class C:
                def incr(self, arg):
                    return 42
            """
        b = """\
            from typing import Any
            class C:
                def incr(self, arg):
                    # type: (Any) -> Any
                    return 42
            """
        self.check(a, b)

    def test_fake_self(self):
        a = """\
            def incr(self, arg):
                return 42
            """
        b = """\
            from typing import Any
            def incr(self, arg):
                # type: (Any, Any) -> Any
                return 42
            """
        self.check(a, b)

    def test_nested_fake_self(self):
        a = """\
            class C:
                def outer(self):
                    def inner(self, arg):
                        return 42
            """
        b = """\
            from typing import Any
            class C:
                def outer(self):
                    # type: () -> None
                    def inner(self, arg):
                        # type: (Any, Any) -> Any
                        return 42
            """
        self.check(a, b)

    def test_multiple_decorators(self):
        a = """\
            class C:
                @contextmanager
                @classmethod
                @wrapped('func')
                def incr(cls, arg):
                    return 42
            """
        b = """\
            from typing import Any
            class C:
                @contextmanager
                @classmethod
                @wrapped('func')
                def incr(cls, arg):
                    # type: (Any) -> Any
                    return 42
            """
        self.check(a, b)

    def test_stars(self):
        a = """\
            def stuff(*a, **kw):
                return 4, 2
            """
        b = """\
            from typing import Any
            def stuff(*a, **kw):
                # type: (*Any, **Any) -> Any
                return 4, 2
            """
        self.check(a, b)

    def test_idempotency(self):
        a = """\
            def incr(arg):
                # type: (Any) -> Any
                return arg+1
            """
        self.unchanged(a)

    def test_no_return_expr(self):
        a = """\
            def proc1(arg):
                return
            def proc2(arg):
                pass
            """
        b = """\
            from typing import Any
            def proc1(arg):
                # type: (Any) -> None
                return
            def proc2(arg):
                # type: (Any) -> None
                pass
            """
        self.check(a, b)

    def test_nested_return_expr(self):
        # The 'return expr' in inner() shouldn't affect the return type of outer().
        a = """\
            def outer(arg):
                def inner():
                    return 42
                return
            """
        b = """\
            from typing import Any
            def outer(arg):
                # type: (Any) -> None
                def inner():
                    # type: () -> Any
                    return 42
                return
            """
        self.check(a, b)

    def test_nested_class_return_expr(self):
        # The 'return expr' in class Inner shouldn't affect the return type of outer().
        a = """\
            def outer(arg):
                class Inner:
                    return 42
                return
            """
        b = """\
            from typing import Any
            def outer(arg):
                # type: (Any) -> None
                class Inner:
                    return 42
                return
            """
        self.check(a, b)

    def test_add_import(self):
        a = """\
            import typing
            from typing import Callable

            def incr(arg):
                return 42
            """
        b = """\
            import typing
            from typing import Callable
            from typing import Any

            def incr(arg):
                # type: (Any) -> Any
                return 42
            """
        self.check(a, b)

    def test_dont_add_import(self):
        a = """\
            def nop(arg=0):
                return
            """
        b = """\
            def nop(arg=0):
                # type: (int) -> None
                return
            """
        self.check(a, b)

    def test_long_form(self):
        self.maxDiff = None
        a = """\
            def nop(arg0, arg1, arg2, arg3, arg4,
                    arg5, arg6, arg7, arg8=0, arg9='',
                    *args, **kwds):
                return
            """
        b = """\
            from typing import Any
            def nop(arg0,  # type: Any
                    arg1,  # type: Any
                    arg2,  # type: Any
                    arg3,  # type: Any
                    arg4,  # type: Any
                    arg5,  # type: Any
                    arg6,  # type: Any
                    arg7,  # type: Any
                    arg8=0,  # type: int
                    arg9='',  # type: str
                    *args,  # type: Any
                    **kwds  # type: Any
                    ):
                # type: (...) -> None
                return
            """
        self.check(a, b)

    def test_long_form_trailing_comma(self):
        self.maxDiff = None
        a = """\
            def nop(arg0, arg1, arg2, arg3, arg4, arg5, arg6,
                    arg7=None, arg8=0, arg9='', arg10=False,):
                return
            """
        b = """\
            from typing import Any
            def nop(arg0,  # type: Any
                    arg1,  # type: Any
                    arg2,  # type: Any
                    arg3,  # type: Any
                    arg4,  # type: Any
                    arg5,  # type: Any
                    arg6,  # type: Any
                    arg7=None,  # type: Any
                    arg8=0,  # type: int
                    arg9='',  # type: str
                    arg10=False,  # type: bool
                    ):
                # type: (...) -> None
                return
            """
        self.check(a, b)

    def test_one_liner(self):
        a = """\
            class C:
                def nop(self, a): a = a; return a
                # Something
            # More
            pass
            """
        b = """\
            from typing import Any
            class C:
                def nop(self, a):
                    # type: (Any) -> Any
                    a = a; return a
                # Something
            # More
            pass
            """
        self.check(a, b)

    def test_idempotency_long_1arg(self):
        a = """\
            def nop(a  # type: int
                    ):
                pass
            """
        self.unchanged(a)

    def test_idempotency_long_1arg_comma(self):
        a = """\
            def nop(a,  # type: int
                    ):
                pass
            """
        self.unchanged(a)

    def test_idempotency_long_2args_first(self):
        a = """\
            def nop(a,  # type: int
                    b):
                pass
            """
        self.unchanged(a)

    def test_idempotency_long_2args_last(self):
        a = """\
            def nop(a,
                    b  # type: int
                    ):
                pass
            """
        self.unchanged(a)

    def test_idempotency_long_varargs(self):
        a = """\
            def nop(*a  # type: int
                    ):
                pass
            """
        self.unchanged(a)

    def test_idempotency_long_kwargs(self):
        a = """\
            def nop(**a  # type: int
                    ):
                pass
            """
        self.unchanged(a)
