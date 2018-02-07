"""Parse type annotations collected at runtime by collect_types and dumped as JSON.

Parse JSON data and also parse type comment strings into type objects.

The collect_types tool is in pyannotate_runtime/collect_types.py.
"""

import json
import re
import sys

from typing import Any, List, Mapping, Set, Tuple
try:
    from typing import Text
except ImportError:
    # In Python 3.5.1 stdlib, typing.py does not define Text
    Text = str  # type: ignore
from mypy_extensions import NoReturn, TypedDict

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

PY2 = sys.version_info < (3,)


# Rules for replacing some type names that aren't valid Python names or that
# are otherwise invalid.
TYPE_FIXUPS = {
    # The dictionary-* names come from Python 2 `__class__.__name__` values
    # from `dict.iterkeys()`, etc. Python 3 uses valid names.
    'dictionary-keyiterator': 'Iterator',
    'dictionary-valueiterator': 'Iterator',
    'dictionary-itemiterator': 'Iterator',
    'pyannotate_runtime.collect_types.UnknownType': 'Any',
    'pyannotate_runtime.collect_types.NoReturnType': 'mypy_extensions.NoReturn',
    'function': 'Callable',
    'functools.partial': 'Callable',
    'long': 'int',
    'unicode': 'Text',
    'generator': 'Iterator',
    'listiterator': 'Iterator',
    'instancemethod': 'Callable',
    'itertools.imap': 'Iterator',
    'operator.methodcaller': 'Callable',
    'method': 'Callable',
    'method-wrapper': 'Callable',
    'mappingproxy': 'Mapping',
    'file': 'IO[bytes]',
    'instance': 'Any',
    'collections.defaultdict': 'Dict',
}


# Input JSON data entry
RawEntry = TypedDict('RawEntry', {'path': Text,
                                  'line': int,
                                  'func_name': Text,
                                  'type_comments': List[Text],
                                  'samples': int})


class FunctionInfo(object):
    """Deserialized raw runtime information for a single function (based on RawEntry)"""

    def __init__(self, path, line, func_name, type_comments, samples):
        # type: (str, int, str, List[str], int) -> None
        self.path = path
        self.line = line
        self.func_name = func_name
        self.type_comments = type_comments
        self.samples = samples


class ParseError(Exception):
    """Raised on any type comment parse error.

    The 'comment' attribute contains the comment that produced the error.
    """

    def __init__(self, comment):
        # type: (str) -> None
        super(ParseError, self).__init__('Invalid type comment: %s' % comment)
        self.comment = comment


def parse_json(path):
    # type: (str) -> List[FunctionInfo]
    """Deserialize a JSON file containing runtime collected types.

    The input JSON is expected to to have a list of RawEntry items.
    """
    with open(path) as f:
        data = json.load(f)  # type: List[RawEntry]
    result = []

    def assert_type(value, typ):
        # type: (object, type) -> None
        assert isinstance(value, typ), '%s: Unexpected type %r' % (path, type(value).__name__)

    def assert_dict_item(dictionary, key, typ):
        # type: (Mapping[Any, Any], str, type) -> None
        assert key in dictionary, '%s: Missing dictionary key %r' % (path, key)
        value = dictionary[key]
        assert isinstance(value, typ), '%s: Unexpected type %r for key %r' % (
            path, type(value).__name__, key)

    assert_type(data, list)
    for item in data:
        assert_type(item, dict)
        assert_dict_item(item, 'path', Text)
        assert_dict_item(item, 'line', int)
        assert_dict_item(item, 'func_name', Text)
        assert_dict_item(item, 'type_comments', list)
        for comment in item['type_comments']:
            assert_type(comment, Text)
        assert_type(item['samples'], int)
        info = FunctionInfo(encode(item['path']),
                            item['line'],
                            encode(item['func_name']),
                            [encode(comment) for comment in item['type_comments']],
                            item['samples'])
        result.append(info)
    return result


class Token(object):
    """Abstract base class for tokens used for parsing type comments"""
    text = ''


class DottedName(Token):
    """An identifier token, such as 'List', 'int' or 'package.name'"""

    def __init__(self, text):
        # type: (str) -> None
        self.text = text

    def __repr__(self):
        # type: () -> str
        return 'DottedName(%s)' % self.text


class Separator(Token):
    """A separator or punctuator token such as '(', '[' or '->'"""

    def __init__(self, text):
        # type: (str) -> None
        self.text = text

    def __repr__(self):
        # type: () -> str
        return self.text


class End(Token):
    """A token representing the end of a type comment"""

    def __repr__(self):
        # type: () -> str
        return 'End()'


def tokenize(s):
    # type: (str) -> List[Token]
    """Translate a type comment into a list of tokens."""
    original = s
    tokens = []  # type: List[Token]
    while True:
        if not s:
            tokens.append(End())
            return tokens
        elif s[0] == ' ':
            s = s[1:]
        elif s[0] in '()[],*':
            tokens.append(Separator(s[0]))
            s = s[1:]
        elif s[:2] == '->':
            tokens.append(Separator('->'))
            s = s[2:]
        else:
            m = re.match(r'[-\w]+( *\. *[-/\w]*)*', s)
            if not m:
                raise ParseError(original)
            fullname = m.group(0)
            fullname = fullname.replace(' ', '')
            if fullname in TYPE_FIXUPS:
                fullname = TYPE_FIXUPS[fullname]
            # pytz creates classes with the name of the timezone being used:
            # https://github.com/stub42/pytz/blob/f55399cddbef67c56db1b83e0939ecc1e276cf42/src/pytz/tzfile.py#L120-L123
            # This causes pyannotates to crash as it's invalid to have a class
            # name with a `/` in it (e.g. "pytz.tzfile.America/Los_Angeles")
            if fullname.startswith('pytz.tzfile.'):
                fullname = 'datetime.tzinfo'
            if '-' in fullname or '/' in fullname:
                # Not a valid Python name; there are many places that
                # generate these, so we just substitute Any rather
                # than crashing.
                fullname = 'Any'
            tokens.append(DottedName(fullname))
            s = s[len(m.group(0)):]


def parse_type_comment(comment):
    # type: (str) -> Tuple[List[Argument], AbstractType]
    """Parse a type comment of form '(arg1, ..., argN) -> ret'."""
    return Parser(comment).parse()


class Parser(object):
    """Implementation of the type comment parser"""

    def __init__(self, comment):
        # type: (str) -> None
        self.comment = comment
        self.tokens = tokenize(comment)
        self.i = 0

    def parse(self):
        # type: () -> Tuple[List[Argument], AbstractType]
        self.expect('(')
        arg_types = []  # type: List[Argument]
        stars_seen = set()  # type: Set[str]
        while self.lookup() != ')':
            if self.lookup() == '*':
                self.expect('*')
                if self.lookup() == '*':
                    if '**' in stars_seen:
                        self.fail()
                    self.expect('*')
                    star_star = True
                else:
                    if stars_seen:
                        self.fail()
                    star_star = False
                arg_type = self.parse_type()
                if star_star:
                    arg_types.append(Argument(arg_type, ARG_STARSTAR))
                    stars_seen.add('**')
                else:
                    arg_types.append(Argument(arg_type, ARG_STAR))
                    stars_seen.add('*')
            else:
                if stars_seen:
                    self.fail()
                arg_type = self.parse_type()
                arg_types.append(Argument(arg_type, ARG_POS))
            if self.lookup() == ',':
                self.expect(',')
            elif self.lookup() == ')':
                break
        self.expect(')')
        self.expect('->')
        ret_type = self.parse_type()
        if not isinstance(self.next(), End):
            self.fail()
        return arg_types, ret_type

    def parse_type_list(self):
        # type: () -> List[AbstractType]
        types = []
        while self.lookup() not in (')', ']'):
            typ = self.parse_type()
            types.append(typ)
            if self.lookup() == ',':
                self.expect(',')
            elif self.lookup() not in (')', ']'):
                self.fail()
        return types

    def parse_type(self):
        # type: () -> AbstractType
        t = self.next()
        if not isinstance(t, DottedName):
            self.fail()
        if t.text == 'Any':
            return AnyType()
        elif t.text == 'mypy_extensions.NoReturn':
            return NoReturnType()
        elif t.text == 'Tuple':
            self.expect('[')
            args = self.parse_type_list()
            self.expect(']')
            return TupleType(args)
        elif t.text == 'Union':
            self.expect('[')
            items = self.parse_type_list()
            self.expect(']')
            if len(items) == 1:
                return items[0]
            elif len(items) == 0:
                self.fail()
            else:
                return UnionType(items)
        else:
            if self.lookup() == '[':
                self.expect('[')
                args = self.parse_type_list()
                self.expect(']')
                if t.text == 'Optional' and len(args) == 1:
                    return UnionType([args[0], ClassType('None')])
                return ClassType(t.text, args)
            else:
                return ClassType(t.text)

    def expect(self, s):
        # type: (str) -> None
        if self.tokens[self.i].text != s:
            self.fail()
        self.i += 1

    def lookup(self):
        # type: () -> str
        return self.tokens[self.i].text

    def next(self):
        # type: () -> Token
        token = self.tokens[self.i]
        self.i += 1
        return token

    def fail(self):
        # type: () -> NoReturn
        raise ParseError(self.comment)


def encode(s):
    # type: (Text) -> str
    if PY2:
        return s.encode('ascii')
    else:
        return s
