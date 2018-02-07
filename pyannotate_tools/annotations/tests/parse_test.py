import os
import tempfile
import unittest

from typing import List, Optional, Tuple

from pyannotate_tools.annotations.parse import parse_json, parse_type_comment, ParseError, tokenize
from pyannotate_tools.annotations.types import (
    AbstractType,
    AnyType,
    ARG_POS,
    ARG_STAR,
    ARG_STARSTAR,
    Argument,
    ClassType,
    TupleType,
    UnionType,
    NoReturnType,
)


class TestParseError(unittest.TestCase):
    def test_str_conversion(self):
        # type: () -> None
        assert str(ParseError('(int -> str')) == 'Invalid type comment: (int -> str'


class TestParseJson(unittest.TestCase):
    def test_parse_json(self):
        # type: () -> None
        data = """
        [
            {
                "path": "pkg/thing.py",
                "line": 422,
                "func_name": "my_function",
                "type_comments": [
                    "(int) -> None",
                    "(str) -> None"
                ],
                "samples": 3
            }
        ]
        """
        f = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(data)
            result = parse_json(f.name)
        finally:
            if f is not None:
                os.remove(f.name)
        assert len(result) == 1
        item = result[0]
        assert item.path == 'pkg/thing.py'
        assert item.line == 422
        assert item.func_name == 'my_function'
        assert item.type_comments == ['(int) -> None',
                                      '(str) -> None']
        assert item.samples == 3


class TestTokenize(unittest.TestCase):
    def test_tokenize(self):
        # type: () -> None
        self.assert_tokenize(
            ' List[int, str] (  )-> *',
            'DottedName(List) [ DottedName(int) , DottedName(str) ] ( ) -> * End()')

    def test_special_cases(self):
        # type: () -> None
        self.assert_tokenize('dictionary-itemiterator',
                             'DottedName(Iterator) End()')
        self.assert_tokenize('dictionary-keyiterator',
                             'DottedName(Iterator) End()')
        self.assert_tokenize('dictionary-valueiterator',
                             'DottedName(Iterator) End()')
        self.assert_tokenize('foo-bar', 'DottedName(Any) End()')
        self.assert_tokenize('pytz.tzfile.Europe/Amsterdam',
                             'DottedName(datetime.tzinfo) End()')

    def assert_tokenize(self, s, expected):
        # type: (str, str) -> None
        tokens = tokenize(s)
        actual = ' '.join(str(t) for t in tokens)
        assert actual == expected


def class_arg(name, args=None):
    # type: (str, Optional[List[AbstractType]]) -> Argument
    return Argument(ClassType(name, args), ARG_POS)


def any_arg():
    # type: () -> Argument
    return Argument(AnyType(), ARG_POS)


def tuple_arg(items):
    # type: (List[AbstractType]) -> Argument
    return Argument(TupleType(items), ARG_POS)



class TestParseTypeComment(unittest.TestCase):
    def test_empty(self):
        # type: () -> None
        self.assert_type_comment('() -> None', ([], ClassType('None')))

    def test_simple_args(self):
        # type: () -> None
        self.assert_type_comment('(int) -> None', ([class_arg('int')], ClassType('None')))
        self.assert_type_comment('(int, str) -> bool', ([class_arg('int'),
                                                         class_arg('str')], ClassType('bool')))

    def test_generic(self):
        # type: () -> None
        self.assert_type_comment('(List[int]) -> Dict[str, bool]',
                                 ([class_arg('List', [ClassType('int')])],
                                  ClassType('Dict', [ClassType('str'), ClassType('bool')])))

    def test_any_and_unknown(self):
        # type: () -> None
        self.assert_type_comment('(Any) -> pyannotate_runtime.collect_types.UnknownType',
                                 ([any_arg()], AnyType()))

    def test_no_return(self):
        # type: () -> None
        self.assert_type_comment('() -> pyannotate_runtime.collect_types.NoReturnType',
                                 ([], NoReturnType()))

    def test_tuple(self):
        # type: () -> None
        self.assert_type_comment('(Tuple[]) -> Any', ([tuple_arg([])], AnyType()))
        self.assert_type_comment('(Tuple[int]) -> Any',
                                 ([tuple_arg([ClassType('int')])], AnyType()))
        self.assert_type_comment('(Tuple[int, str]) -> Any',
                                 ([tuple_arg([ClassType('int'),
                                              ClassType('str')])], AnyType()))

    def test_union(self):
        # type: () -> None
        self.assert_type_comment('(Union[int, str]) -> Any',
                                 ([Argument(UnionType([ClassType('int'),
                                                       ClassType('str')]), ARG_POS)], AnyType()))
        self.assert_type_comment('(Union[int]) -> Any',
                                 ([class_arg('int')], AnyType()))

    def test_optional(self):
        # type: () -> None
        self.assert_type_comment('(Optional[int]) -> Any',
                                 ([Argument(UnionType([ClassType('int'),
                                                       ClassType('None')]), ARG_POS)], AnyType()))

    def test_star_args(self):
        # type: () -> None
        self.assert_type_comment('(*str) -> Any',
                                 ([Argument(ClassType('str'), ARG_STAR)], AnyType()))
        self.assert_type_comment('(int, *str) -> Any',
                                 ([class_arg('int'), Argument(ClassType('str'), ARG_STAR)],
                                  AnyType()))

    def test_star_star_args(self):
        # type: () -> None
        self.assert_type_comment('(**str) -> Any',
                                 ([Argument(ClassType('str'), ARG_STARSTAR)], AnyType()))
        self.assert_type_comment('(int, *str, **bool) -> Any',
                                 ([class_arg('int'),
                                   Argument(ClassType('str'), ARG_STAR),
                                   Argument(ClassType('bool'), ARG_STARSTAR)], AnyType()))

    def test_function(self):
        # type: () -> None
        self.assert_type_comment('(function) -> Any',
                                 ([class_arg('Callable')], AnyType()))

    def test_unicode(self):
        # type: () -> None
        self.assert_type_comment('(unicode) -> Any',
                                 ([class_arg('Text')], AnyType()))

    def test_bad_annotation(self):
        # type: () -> None
        for bad in ['( -> None',
                    '()',
                    ')) -> None',
                    '() -> ',
                    '()->',
                    '() -> None x',
                    'int',
                    'int -> None',
                    '(Union[]) -> None',
                    '(List[int) -> None',
                    '(*int, *str) -> None',
                    '(*int, int) -> None',
                    '(**int, *str) -> None',
                    '(**int, str) -> None',
                    '(**int, **str) -> None']:
            with self.assertRaises(ParseError):
                parse_type_comment(bad)

    def assert_type_comment(self, comment, expected):
        # type: (str, Tuple[List[Argument], AbstractType]) -> None
        actual = parse_type_comment(comment)
        assert actual == expected
