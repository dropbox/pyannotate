"""Internal representation of type objects."""

from typing import NamedTuple, Optional, Sequence


class AbstractType(object):
    """Abstract base class for types."""


class ClassType(AbstractType):
    """A class type, potentially generic (int, List[str], None, ...)"""

    def __init__(self, name, args=None):
        # type: (str, Optional[Sequence[AbstractType]]) -> None
        self.name = name
        if args:
            self.args = tuple(args)
        else:
            self.args = ()

    def __repr__(self):
        # type: () -> str
        if self.name == 'Tuple' and len(self.args) == 1:
            return 'Tuple[%s, ...]' % self.args[0]
        elif self.args:
            return '%s[%s]' % (self.name, ', '.join(str(arg) for arg in self.args))
        else:
            return self.name

    def __eq__(self, other):
        # type: (object) -> bool
        return isinstance(other, ClassType) and self.name == other.name and self.args == other.args

    def __hash__(self):
        # type: () -> int
        return hash((self.name, self.args))


class AnyType(AbstractType):
    """The type Any"""

    def __repr__(self):
        # type: () -> str
        return 'Any'

    def __eq__(self, other):
        # type: (object) -> bool
        return isinstance(other, AnyType)

    def __hash__(self):
        # type: () -> int
        return hash('Any')


class NoReturnType(AbstractType):
    """The type mypy_extensions.NoReturn"""

    def __repr__(self):
        # type: () -> str
        return 'mypy_extensions.NoReturn'

    def __eq__(self, other):
        # type: (object) -> bool
        return isinstance(other, NoReturnType)

    def __hash__(self):
        # type: () -> int
        return hash('NoReturn')


class TupleType(AbstractType):
    """Fixed-length tuple Tuple[x, ..., y]"""

    def __init__(self, items):
        # type: (Sequence[AbstractType]) -> None
        self.items = tuple(items)

    def __repr__(self):
        # type: () -> str
        if not self.items:
            return 'Tuple[()]'  # Special case
        return 'Tuple[%s]' % ', '.join(str(item) for item in self.items)

    def __eq__(self, other):
        # type: (object) -> bool
        return isinstance(other, TupleType) and self.items == other.items

    def __hash__(self):
        # type: () -> int
        return hash(('tuple', self.items))


class UnionType(AbstractType):
    """Union[x, ..., y]"""

    def __init__(self, items):
        # type: (Sequence[AbstractType]) -> None
        self.items = tuple(items)

    def __repr__(self):
        # type: () -> str
        items = self.items
        if len(items) == 2:
            if is_none(items[0]):
                return 'Optional[%s]' % items[1]
            elif is_none(items[1]):
                return 'Optional[%s]' % items[0]
        return 'Union[%s]' % ', '.join(str(item) for item in items)

    def __eq__(self, other):
        # type: (object) -> bool
        return isinstance(other, UnionType) and set(self.items) == set(other.items)

    def __hash__(self):
        # type: () -> int
        return hash(('union', self.items))


# Argument kind
ARG_POS = 'ARG_POS'  # Normal
ARG_STAR = 'ARG_STAR'  # *args
ARG_STARSTAR = 'ARG_STARSTAR'  # **kwargs

# Description of an argument in a signature. The kind is one of ARG_*.
Argument = NamedTuple('Argument', [('type', AbstractType), ('kind', str)])


def is_none(t):
    # type: (AbstractType) -> bool
    return isinstance(t, ClassType) and t.name == 'None'


def is_optional(t):
    # type: (AbstractType) -> bool
    return (isinstance(t, UnionType)
            and len(t.items) == 2
            and any(item == ClassType('None') for item in t.items))
