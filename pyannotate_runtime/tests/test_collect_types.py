"""Tests for collect_types"""
from __future__ import (
    absolute_import,
    division,
    print_function,
)

import contextlib
import json
import os
import sched
import time
import unittest
from collections import namedtuple
from threading import Thread

from six import PY2
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)
try:
    from typing import Text
except ImportError:
    # In Python 3.5.1 stdlib, typing.py does not define Text
    Text = str  # type: ignore

from pyannotate_runtime import collect_types

# A bunch of random functions and classes to test out type collection
# Disable a whole bunch of lint warnings for simplicity

# pylint:disable=invalid-name
# pylint:disable=blacklisted-name
# pylint:disable=missing-docstring

FooNamedTuple = namedtuple('FooNamedTuple', 'foo bar')


def print_int(i):
    # type: (Any) -> Any
    print(i)


def noop_dec(a):
    # type: (Any) -> Any
    return a


@noop_dec
class FoosParent(object):
    pass


class FooObject(FoosParent):
    pass


class FooReturn(FoosParent):
    pass


class WorkerClass(object):

    def __init__(self, special_num, foo):
        # type: (Any, Any) -> None
        self._special_num = special_num
        self._foo = foo

    @noop_dec
    def do_work(self, i, haz):
        # type: (Any, Any) -> Any
        print_int(i)
        return EOFError()

    @classmethod
    def do_work_clsmthd(cls, i, haz=None):
        # type: (Any, Any) -> Any
        print_int(i)
        return EOFError()


class EventfulHappenings(object):

    def __init__(self):
        # type: () -> None
        self.handlers = []  # type: Any

    def add_handler(self, handler):
        # type: (Any) -> Any
        self.handlers.append(handler)

    def something_happened(self, a, b):
        # type: (Any, Any) -> Any
        for h in self.handlers:
            h(a, b)
        return 1999


def i_care_about_whats_happening(y, z):
    # type: (Any, Any) -> Any
    print_int(y)
    print(z)
    return FooReturn()


def takes_different_lists(l):
    # type: (Any) -> Any
    pass


def takes_int_lists(l):
    # type: (Any) -> Any
    pass


def takes_int_float_lists(l):
    # type: (Any) -> Any
    pass


def takes_int_to_str_dict(d):
    # type: (Any) -> Any
    pass


def takes_int_to_multiple_val_dict(d):
    # type: (Any) -> Any
    pass


def recursive_dict(d):
    # type: (Any) -> Any
    pass


def empty_then_not_dict(d):
    # type: (Any) -> Any
    return d


def empty_then_not_list(l):
    # type: (Any) -> Any
    pass


def tuple_verify(t):
    # type: (Any) -> Any
    return t


def problematic_dup(uni, bol):
    # type: (Text, bool) -> Tuple[Dict[Text, Union[List, int, Text]],bytes]
    return {u"foo": [], u"bart": u'ads', u"bax": 23}, b'str'


def two_dict_comprehensions():
    # type: () -> Dict[int, Dict[Tuple[int, int], int]]
    d = {1: {1: 2}}
    return {
        i: {
            (i, k): l
            for k, l in j.items()
        }
        for i, j in d.items()
    }


class TestBaseClass(unittest.TestCase):

    def setUp(self):
        # type: () -> None
        super(TestBaseClass, self).setUp()
        # Stats in the same format as the generated JSON.
        self.stats = []  # type: List[collect_types.FunctionData]

    def tearDown(self):
        # type: () -> None
        collect_types.stop_types_collection()

    def load_stats(self):
        # type: () -> None
        self.stats = json.loads(collect_types.dumps_stats())

    @contextlib.contextmanager
    def collecting_types(self):
        # type: () -> Iterator[None]
        collect_types.collected_args = {}
        collect_types.collected_signatures = {}
        collect_types.num_samples = {}
        collect_types.sampling_counters = {}
        collect_types.call_pending = set()
        collect_types.resume()
        yield None
        collect_types.pause()
        self.load_stats()

    def assert_type_comments(self, func_name, comments):
        # type: (str, List[str]) -> None
        """Assert that we generated expected comment for the func_name function in self.stats"""
        stat_items = [item for item in self.stats if item.get('func_name') == func_name]
        if not comments and not stat_items:
            # If we expect no comments, it's okay if nothing was collected.
            return
        assert len(stat_items) == 1
        item = stat_items[0]
        if set(item['type_comments']) != set(comments):
            print('Actual:')
            for comment in sorted(item['type_comments']):
                print('    ' + comment)
            print('Expected:')
            for comment in sorted(comments):
                print('    ' + comment)
            assert set(item['type_comments']) == set(comments)
        assert len(item['type_comments']) == len(comments)
        assert os.path.join(collect_types.TOP_DIR, item['path']) == __file__


class TestCollectTypes(TestBaseClass):

    def setUp(self):
        # type: () -> None
        super(TestCollectTypes, self).setUp()
        collect_types.init_types_collection()

    # following type annotations are intentionally use Any,
    # because we are testing runtime type collection

    def foo(self, int_arg, list_arg):
        # type: (Any, Any) -> None
        """foo"""
        self.bar(int_arg, list_arg)

    def bar(self, int_arg, list_arg):
        # type: (Any, Any) -> Any
        """bar"""
        return len(self.baz(list_arg)) + int_arg

    def baz(self, list_arg):
        # type: (Any) -> Any
        """baz"""
        return set([int(s) for s in list_arg])

    def test_type_collection_on_main_thread(self):
        # type: () -> None
        with self.collecting_types():
            self.foo(2, ['1', '2'])
        self.assert_type_comments('TestCollectTypes.foo', ['(int, List[str]) -> None'])
        self.assert_type_comments('TestCollectTypes.bar', ['(int, List[str]) -> int'])
        self.assert_type_comments('TestCollectTypes.baz', ['(List[str]) -> Set[int]'])

    def bar_another_thread(self, int_arg, list_arg):
        # type: (Any, Any) -> Any
        """bar"""
        return len(self.baz_another_thread(list_arg)) + int_arg

    def baz_another_thread(self, list_arg):
        # type: (Any) -> Any
        """baz"""
        return set([int(s) for s in list_arg])

    def test_type_collection_on_another_thread(self):
        # type: () -> None
        with self.collecting_types():
            t = Thread(target=self.bar_another_thread, args=(100, ['1', '2', '3'],))
            t.start()
            t.join()
        self.assert_type_comments('TestCollectTypes.baz_another_thread',
                                  ['(List[str]) -> Set[int]'])

    def test_run_a_bunch_of_tests(self):
        # type: () -> None
        with self.collecting_types():
            to = FooObject()
            wc = WorkerClass(42, to)
            s = sched.scheduler(time.time, time.sleep)
            event_source = EventfulHappenings()
            s.enter(.001, 1, wc.do_work, ([52, 'foo,', 32], FooNamedTuple('ab', 97)))
            s.enter(.002, 1, wc.do_work, ([52, 32], FooNamedTuple('bc', 98)))
            s.enter(.003, 1, wc.do_work_clsmthd, (52, FooNamedTuple('de', 99)))
            s.enter(.004, 1, event_source.add_handler, (i_care_about_whats_happening,))
            s.enter(.005, 1, event_source.add_handler, (lambda a, b: print_int(a),))
            s.enter(.006, 1, event_source.something_happened, (1, 'tada'))
            s.run()

            takes_different_lists([42, 'as', 323, 'a'])
            takes_int_lists([42, 323, 3231])
            takes_int_float_lists([42, 323.2132, 3231])
            takes_int_to_str_dict({2: 'a', 4: 'd'})
            takes_int_to_multiple_val_dict({3: 'a', 4: None, 5: 232})
            recursive_dict({3: {3: 'd'}, 4: {3: 'd'}})

            empty_then_not_dict({})
            empty_then_not_dict({3: {3: 'd'}, 4: {3: 'd'}})
            empty_then_not_list([])
            empty_then_not_list([1, 2])
            empty_then_not_list([1, 2])
            tuple_verify((1, '4'))
            tuple_verify((1, '4'))

            problematic_dup(u'ha', False)
            problematic_dup(u'ha', False)

        # TODO(svorobev): add checks for the rest of the functions
        # print_int,
        self.assert_type_comments(
            'WorkerClass.__init__',
            ['(int, pyannotate_runtime.tests.test_collect_types.FooObject) -> None'])
        self.assert_type_comments(
            'do_work_clsmthd',
            ['(int, pyannotate_runtime.tests.test_collect_types.FooNamedTuple) -> EOFError'])
        # TODO: that could be better
        self.assert_type_comments('takes_different_lists', ['(List[Union[int, str]]) -> None'])

        # TODO: that should work
        # self.assert_type_comment('empty_then_not_dict',
        #                         '(Dict[int, Dict[int, str]]) -> Dict[int, Dict[int, str]]')
        self.assert_type_comments('empty_then_not_list', ['(List[int]) -> None',
                                                          '(List) -> None'])
        if PY2:
            self.assert_type_comments(
                'problematic_dup',
                ['(unicode, bool) -> Tuple[Dict[unicode, Union[List, int, unicode]], str]'])
        else:
            self.assert_type_comments(
                'problematic_dup',
                ['(str, bool) -> Tuple[Dict[str, Union[List, int, str]], bytes]'])

    def test_two_signatures(self):
        # type: () -> None

        def identity(x):
            # type: (Any) -> Any
            return x

        with self.collecting_types():
            identity(1)
            identity('x')
        self.assert_type_comments('identity', ['(int) -> int', '(str) -> str'])

    def test_many_signatures(self):
        # type: () -> None

        def identity2(x):
            # type: (Any) -> Any
            return x

        with self.collecting_types():
            for x in 1, 'x', 2, 'y', slice(1), 1.1, None, False, bytearray(), (), [], set():
                for _ in range(50):
                    identity2(x)
        # We collect at most 8 distinct signatures.
        self.assert_type_comments('identity2', ['(int) -> int',
                                                '(str) -> str',
                                                '(slice) -> slice',
                                                '(float) -> float',
                                                '(None) -> None',
                                                '(bool) -> bool',
                                                '(bytearray) -> bytearray',
                                                '(Tuple[]) -> Tuple[]'])

    def test_default_args(self):
        # type: () -> None

        def func_default(x=0, y=None):
            # type: (Any, Any) -> Any
            return x

        with self.collecting_types():
            func_default()
            func_default('')
            func_default(1.1, True)
        self.assert_type_comments('func_default', ['(int, None) -> int',
                                                   '(str, None) -> str',
                                                   '(float, bool) -> float'])

    def test_keyword_args(self):
        # type: () -> None

        def func_kw(x, y):
            # type: (Any, Any) -> Any
            return x

        with self.collecting_types():
            func_kw(y=1, x='')
            func_kw(**{'x': 1.1, 'y': None})
        self.assert_type_comments('func_kw', ['(str, int) -> str',
                                              '(float, None) -> float'])

    def test_no_return(self):
        # type: () -> None

        def func_always_fail(x):
            # type: (Any) -> Any
            raise ValueError

        def func_sometimes_fail(x):
            # type: (Any) -> Any
            if x == 0:
                raise RuntimeError
            return x

        with self.collecting_types():
            try:
                func_always_fail(1)
            except Exception:
                pass
            try:
                func_always_fail('')
            except Exception:
                pass
            try:
                func_always_fail(1)
            except Exception:
                pass
            try:
                func_sometimes_fail(0)
            except Exception:
                pass
            func_sometimes_fail('')
            try:
                func_sometimes_fail(0)
            except Exception:
                pass
        self.assert_type_comments('func_always_fail', ['(int) -> pyannotate_runtime.collect_types.NoReturnType',
                                                       '(str) -> pyannotate_runtime.collect_types.NoReturnType'])
        self.assert_type_comments('func_sometimes_fail', ['(int) -> pyannotate_runtime.collect_types.NoReturnType',
                                                          '(str) -> str'])

    def test_only_return(self):
        # type: () -> None

        def only_return(x):
            # type: (int) -> str
            collect_types.resume()
            return ''

        only_return(1)
        collect_types.pause()
        self.load_stats()
        # No entry is stored if we only have a return event with no matching call.
        self.assert_type_comments('only_return', [])

    def test_callee_star_args(self):
        # type: () -> None

        def callee_star_args(x, *y):
            # type: (Any, *Any) -> Any
            return 0

        with self.collecting_types():
            callee_star_args(0)
            callee_star_args(1, '')
            callee_star_args(slice(1), 1.1, True)
            callee_star_args(*(False, 1.1, ''))
        self.assert_type_comments('callee_star_args', ['(int) -> int',
                                                       '(int, *str) -> int',
                                                       '(slice, *Union[bool, float]) -> int',
                                                       '(bool, *Union[float, str]) -> int'])

    def test_caller_star_args(self):
        # type: () -> None

        def caller_star_args(x, y=None):
            # type: (Any, Any) -> Any
            return 0

        with self.collecting_types():
            caller_star_args(*(1,))
            caller_star_args(*('', 1.1))
        self.assert_type_comments('caller_star_args', ['(int, None) -> int',
                                                       '(str, float) -> int'])

    def test_star_star_args(self):
        # type: () -> None

        def star_star_args(x, **kw):
            # type: (Any, **Any) -> Any
            return 0

        with self.collecting_types():
            star_star_args(1, y='', z=True)
            star_star_args(**{'x': True, 'a': 1.1})
        self.assert_type_comments('star_star_args', ['(int) -> int',
                                                     '(bool) -> int'])

    def test_fully_qualified_type_name_with_sub_package(self):
        # type: () -> None

        def identity_qualified(x):
            # type: (Any) -> Any
            return x

        with self.collecting_types():
            identity_qualified(collect_types.TentativeType())
        self.assert_type_comments(
            'identity_qualified',
            ['(pyannotate_runtime.collect_types.TentativeType) -> '
             'pyannotate_runtime.collect_types.TentativeType'])

    def test_recursive_function(self):
        # type: () -> None

        def recurse(x):
            # type: (Any) -> Any
            if len(x) == 0:
                return 1.1
            else:
                recurse(x[1:])
                return x[0]

        with self.collecting_types():
            recurse((1, '', True))
        self.assert_type_comments(
            'recurse',
            ['(Tuple[]) -> float',
             '(Tuple[bool]) -> pyannotate_runtime.collect_types.UnknownType',
             '(Tuple[str, bool]) -> pyannotate_runtime.collect_types.UnknownType',
             '(Tuple[int, str, bool]) -> pyannotate_runtime.collect_types.UnknownType'])

    def test_recursive_function_2(self):
        # type: () -> None

        def recurse(x):
            # type: (Any) -> Any
            if x == 0:
                recurse('')
                recurse(1.1)
                return False
            else:
                return x

        with self.collecting_types():
            # The return event for the initial call is mismatched because of
            # the recursive calls, so we'll have to drop the return type.
            recurse(0)
        self.assert_type_comments(
            'recurse',
            ['(str) -> str',
             '(float) -> float',
             '(int) -> pyannotate_runtime.collect_types.UnknownType'])

    def test_ignoring_c_calls(self):
        # type: () -> None

        def func(x):
            # type: (Any) -> Any
            a = [1]
            # Each of these generates a c_call/c_return event pair.
            y = len(a), len(a), len(a), len(a), len(a), len(a), len(a), len(a), len(a), len(a)
            y = len(a), len(a), len(a), len(a), len(a), len(a), len(a), len(a), len(a), len(a)
            str(y)
            return x

        with self.collecting_types():
            func(1)
            func('')
        self.assert_type_comments('func', ['(int) -> int',
                                           '(str) -> str'])

    def test_no_crash_on_nested_dict_comps(self):
        # type: () -> None
        with self.collecting_types():
            two_dict_comprehensions()
        self.assert_type_comments('two_dict_comprehensions',
                                  ['() -> Dict[int, Dict[Tuple[int, int], int]]'])

    def test_skip_lambda(self):
        # type: () -> None
        with self.collecting_types():
            (lambda: None)()
            (lambda x: x)(0)
            (lambda x, y: x+y)(0, 0)
        assert self.stats == []

    def test_unknown_module_types(self):
        # type: () -> None
        def func_with_unknown_module_types(c):
            # type: (Any) -> Any
            return c

        with self.collecting_types():
            ns = {
                '__name__': '<unknown>'
            }   # type: Dict[str, Any]
            exec('class C(object): pass', ns)

            func_with_unknown_module_types(ns['C']())

        self.assert_type_comments('func_with_unknown_module_types', ['(C) -> C'])

    def test_yield_basic(self):
        # type: () -> None
        def gen(n, a):
            for i in range(n):
                yield a

        with self.collecting_types():
            list(gen(10, 'x'))

        self.assert_type_comments('gen', ['(int, str) -> Iterator[str]'])

    def test_yield_various(self):
        # type: () -> None
        def gen(n, a, b):
            for i in range(n):
                yield a
                yield b

        with self.collecting_types():
            list(gen(10, 'x', 1))
            list(gen(0, 0, 0))

        # TODO: This should really return Iterator[Union[int, str]]
        self.assert_type_comments('gen', ['(int, str, int) -> Iterator[int]',
                                          '(int, str, int) -> Iterator[str]'])

    def test_yield_empty(self):
        # type: () -> None
        def gen():
            if False:
                yield

        with self.collecting_types():
            list(gen())

        self.assert_type_comments('gen', ['() -> Iterator'])


def foo(arg):
    # type: (Any) -> Any
    return [arg]


class TestInitWithFilter(TestBaseClass):

    def always_foo(self, filename):
        # type: (Optional[str]) -> Optional[str]
        return 'foo.py'

    def always_none(self, filename):
        # type: (Optional[str]) -> Optional[str]
        return None

    def test_init_with_filter(self):
        # type: () -> None
        collect_types.init_types_collection(self.always_foo)
        with self.collecting_types():
            foo(42)
        assert len(self.stats) == 1
        assert self.stats[0]['path'] == 'foo.py'

    def test_init_with_none_filter(self):
        # type: () -> None
        collect_types.init_types_collection(self.always_none)
        with self.collecting_types():
            foo(42)
        assert self.stats == []
