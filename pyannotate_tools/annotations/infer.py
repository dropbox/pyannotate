"""Infer an annotation from a set of concrete runtime type signatures.

The main entry point is 'infer_annotation'.
"""

from typing import Dict, Iterable, List, Optional, Set, Tuple

from pyannotate_tools.annotations.parse import parse_type_comment
from pyannotate_tools.annotations.types import (
    AbstractType,
    AnyType,
    ARG_POS,
    Argument,
    ClassType,
    is_optional,
    TupleType,
    UnionType,
    NoReturnType,
)

IGNORED_ITEMS = {
    'unittest.mock.Mock',
    'unittest.mock.MagicMock',
    'mock.mock.Mock',
    'mock.mock.MagicMock',
}

class InferError(Exception):
    """Raised if we can't infer a signature for some reason."""


def infer_annotation(type_comments):
    # type: (List[str]) -> Tuple[List[Argument], AbstractType]
    """Given some type comments, return a single inferred signature.

    Args:
        type_comments: Strings of form '(arg1, ... argN) -> ret'

    Returns: Tuple of (argument types and kinds, return type).
    """
    assert type_comments
    args = {}  # type: Dict[int, Set[Argument]]
    returns = set()
    for comment in type_comments:
        arg_types, return_type = parse_type_comment(comment)
        for i, arg_type in enumerate(arg_types):
            args.setdefault(i, set()).add(arg_type)
        returns.add(return_type)
    combined_args = []
    for i in sorted(args):
        arg_infos = list(args[i])
        kind = argument_kind(arg_infos)
        if kind is None:
            raise InferError('Ambiguous argument kinds:\n' + '\n'.join(type_comments))
        types = [arg.type for arg in arg_infos]
        combined = combine_types(types)
        if kind != ARG_POS and (len(str(combined)) > 120 or isinstance(combined, UnionType)):
            # Avoid some noise.
            combined = AnyType()
        combined_args.append(Argument(combined, kind))
    combined_return = combine_types(returns)
    return combined_args, combined_return


def argument_kind(args):
    # type: (List[Argument]) -> Optional[str]
    """Return the kind of an argument, based on one or more descriptions of the argument.

    Return None if every item does not have the same kind.
    """
    kinds = set(arg.kind for arg in args)
    if len(kinds) != 1:
        return None
    return kinds.pop()


def combine_types(types):
    # type: (Iterable[AbstractType]) -> AbstractType
    """Given some types, return a combined and simplified type.

    For example, if given 'int' and 'List[int]', return Union[int, List[int]]. If given
    'int' and 'int', return just 'int'.
    """
    items = simplify_types(types)
    if len(items) == 1:
        return items[0]
    else:
        return UnionType(items)


def simplify_types(types):
    # type: (Iterable[AbstractType]) -> List[AbstractType]
    """Given some types, give simplified types representing the union of types."""
    flattened = flatten_types(types)
    items = filter_ignored_items(flattened)
    items = [simplify_recursive(item) for item in items]
    items = merge_items(items)
    items = dedupe_types(items)
    # We have to remove reundant items after everything has been simplified and
    # merged as this simplification may be what makes items redundant.
    items = remove_redundant_items(items)
    if len(items) > 3:
        return [AnyType()]
    else:
        return items


def simplify_recursive(typ):
    # type: (AbstractType) -> AbstractType
    """Simplify all components of a type."""
    if isinstance(typ, UnionType):
        return combine_types(typ.items)
    elif isinstance(typ, ClassType):
        simplified = ClassType(typ.name, [simplify_recursive(arg) for arg in typ.args])
        args = simplified.args
        if (simplified.name == 'Dict' and len(args) == 2
                and isinstance(args[0], ClassType) and args[0].name in ('str', 'Text')
                and isinstance(args[1], UnionType) and not is_optional(args[1])):
            # Looks like a potential case for TypedDict, which we don't properly support yet.
            return ClassType('Dict', [args[0], AnyType()])
        return simplified
    elif isinstance(typ, TupleType):
        return TupleType([simplify_recursive(item) for item in typ.items])
    return typ


def flatten_types(types):
    # type: (Iterable[AbstractType]) -> List[AbstractType]
    flattened = []
    for item in types:
        if not isinstance(item, UnionType):
            flattened.append(item)
        else:
            flattened.extend(flatten_types(item.items))
    return flattened


def dedupe_types(types):
    # type: (Iterable[AbstractType]) -> List[AbstractType]
    return sorted(set(types), key=lambda t: str(t))

def filter_ignored_items(items):
     # type: (List[AbstractType]) -> List[AbstractType]
    result = [item for item in items
              if not isinstance(item, ClassType) or
              item.name not in IGNORED_ITEMS]
    return result or [AnyType()]

def remove_redundant_items(items):
    # type: (List[AbstractType]) -> List[AbstractType]
    """Filter out redundant union items."""
    result = []
    for item in items:
        for other in items:
            if item is not other and is_redundant_union_item(item, other):
                break
        else:
            result.append(item)
    return result


def is_redundant_union_item(first, other):
    # type: (AbstractType, AbstractType) -> bool
    """If union has both items, is the first one redundant?

    For example, if first is 'str' and the other is 'Text', return True.

    If items are equal, return False.
    """
    if isinstance(first, ClassType) and isinstance(other, ClassType):
        if first.name == 'str' and other.name == 'Text':
            return True
        elif first.name == 'bool' and other.name == 'int':
            return True
        elif first.name == 'int' and other.name == 'float':
            return True
        elif (first.name in ('List', 'Dict', 'Set') and
                  other.name == first.name):
            if not first.args and other.args:
                return True
            elif len(first.args) == len(other.args) and first.args:
                result = all(first_arg == other_arg or other_arg == AnyType()
                             for first_arg, other_arg
                             in zip(first.args, other.args))
                return result

    return False


def merge_items(items):
    # type: (List[AbstractType]) -> List[AbstractType]
    """Merge union items that can be merged."""
    result = []
    while items:
        item = items.pop()
        merged = None
        for i, other in enumerate(items):
            merged = merged_type(item, other)
            if merged:
                break
        if merged:
            del items[i]
            items.append(merged)
        else:
            result.append(item)
    return list(reversed(result))


def merged_type(t, s):
    # type: (AbstractType, AbstractType) -> Optional[AbstractType]
    """Return merged type if two items can be merged in to a different, more general type.

    Return None if merging is not possible.
    """
    if isinstance(t, TupleType) and isinstance(s, TupleType):
        if len(t.items) == len(s.items):
            return TupleType([combine_types([ti, si]) for ti, si in zip(t.items, s.items)])
        all_items = t.items + s.items
        if all_items and all(item == all_items[0] for item in all_items[1:]):
            # Merge multiple compatible fixed-length tuples into a variable-length tuple type.
            return ClassType('Tuple', [all_items[0]])
    elif (isinstance(t, TupleType) and isinstance(s, ClassType) and s.name == 'Tuple'
          and len(s.args) == 1):
        if all(item == s.args[0] for item in t.items):
            # Merge fixed-length tuple and variable-length tuple.
            return s
    elif isinstance(s, TupleType) and isinstance(t, ClassType) and t.name == 'Tuple':
        return merged_type(s, t)
    elif isinstance(s, NoReturnType):
        return t
    elif isinstance(t, NoReturnType):
        return s
    elif isinstance(s, AnyType):
        # This seems to be usually desirable, since Anys tend to come from unknown types.
        return t
    elif isinstance(t, AnyType):
        # Similar to above.
        return s
    return None
