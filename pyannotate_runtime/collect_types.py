"""
This module enables runtime type collection.
Collected information can be used to automatically generate
mypy annotation for the executed code paths.

It uses python profiler callback to examine frames and record
type info about arguments and return type.

For the module consumer, the workflow looks like that:
1) call init_types_collection() from the main thread once
2) call resume() to start the type collection
3) call pause() to stop the type collection
4) call dump_stats(file_name) to dump all collected info to the file as json

You can repeat resume() / pause() as many times as you want.

The module is based on Tony's 2016 prototype D219371.
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
)

import collections
import inspect
import json
import opcode
import os
import sys
import threading
from inspect import ArgInfo
from threading import Thread

from mypy_extensions import TypedDict
from six import iteritems
from six.moves import range
from six.moves.queue import Queue  # type: ignore  # No library stub yet
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Set,
    Sized,
    Tuple,
    TypeVar,
    Union,
)
from contextlib import contextmanager

# pylint: disable=invalid-name

CO_GENERATOR = inspect.CO_GENERATOR  # type: ignore


def _my_hash(arg_list):
    # type: (List[Any]) -> int
    """Simple helper hash function"""
    res = 0
    for arg in arg_list:
        res = res * 31 + hash(arg)
    return res


# JSON object representing the collected data for a single function/method
FunctionData = TypedDict('FunctionData', {'path': str,
                                          'line': int,
                                          'func_name': str,
                                          'type_comments': List[str],
                                          'samples': int})


class UnknownType(object):
    pass


class NoReturnType(object):
    pass


class TypeWasIncomparable(object):
    pass


class FakeIterator(Iterable[Any], Sized):
    """
    Container for iterator values.

    Note that FakeIterator([a, b, c]) is akin to list([a, b, c]); this
    is turned into IteratorType by resolve_type().
    """

    def __init__(self, values):
        # type: (List[Any]) -> None
        self.values = values

    def __iter__(self):
        # type: () -> Iterator[Any]
        for v in self.values:
            yield v

    def __len__(self):
        # type: () -> int
        return len(self.values)


_NONE_TYPE = type(None)
InternalType = Union['DictType', 'ListType', 'TupleType', 'SetType', 'IteratorType', 'type']


class DictType(object):
    """
    Internal representation of Dict type.
    """

    def __init__(self, key_type, val_type):
        # type: (TentativeType, TentativeType) -> None
        self.key_type = key_type
        self.val_type = val_type

    def __repr__(self):
        # type: () -> str
        if repr(self.key_type) == 'None':
            # We didn't see any values, so we don't know what's inside
            return 'Dict'
        else:
            return 'Dict[%s, %s]' % (repr(self.key_type), repr(self.val_type))

    def __hash__(self):
        # type: () -> int
        return hash(self.key_type) if self.key_type else 0

    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, DictType):
            return False

        return self.val_type == other.val_type and self.key_type == other.key_type

    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)


class ListType(object):
    """
    Internal representation of List type.
    """

    def __init__(self, val_type):
        # type: (TentativeType) -> None
        self.val_type = val_type

    def __repr__(self):
        # type: () -> str
        if repr(self.val_type) == 'None':
            # We didn't see any values, so we don't know what's inside
            return 'List'
        else:
            return 'List[%s]' % (repr(self.val_type))

    def __hash__(self):
        # type: () -> int
        return hash(self.val_type) if self.val_type else 0

    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, ListType):
            return False

        return self.val_type == other.val_type

    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)


class SetType(object):
    """
    Internal representation of Set type.
    """

    def __init__(self, val_type):
        # type: (TentativeType) -> None
        self.val_type = val_type

    def __repr__(self):
        # type: () -> str
        if repr(self.val_type) == 'None':
            # We didn't see any values, so we don't know what's inside
            return 'Set'
        else:
            return 'Set[%s]' % (repr(self.val_type))

    def __hash__(self):
        # type: () -> int
        return hash(self.val_type) if self.val_type else 0

    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, SetType):
            return False

        return self.val_type == other.val_type

    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)


class IteratorType(object):
    """
    Internal representation of Iterator type.
    """

    def __init__(self, val_type):
        # type: (TentativeType) -> None
        self.val_type = val_type

    def __repr__(self):
        # type: () -> str
        if repr(self.val_type) == 'None':
            # We didn't see any values, so we don't know what's inside
            return 'Iterator'
        else:
            return 'Iterator[%s]' % (repr(self.val_type))

    def __hash__(self):
        # type: () -> int
        return hash(self.val_type) if self.val_type else 0

    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, IteratorType):
            return False

        return self.val_type == other.val_type

    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)


class TupleType(object):
    """
    Internal representation of Tuple type.
    """

    def __init__(self, val_types):
        #  type: (List[InternalType]) -> None
        self.val_types = val_types

    def __repr__(self):
        # type: () -> str
        return 'Tuple[%s]' % ', '.join([name_from_type(vt) for vt in self.val_types])

    def __hash__(self):
        # type: () -> int
        return _my_hash(self.val_types)

    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, TupleType):
            return False

        if len(self.val_types) != len(other.val_types):
            return False

        for i, v in enumerate(self.val_types):
            if v != other.val_types[i]:
                return False

        return True

    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)


class TentativeType(object):
    """
    This class serves as internal representation of type for a type collection process.
    It can be merged with another instance of TentativeType to build up a broader sample.
    """

    def __init__(self):
        # type: () -> None
        self.types_hashable = set()  # type: Set[InternalType]
        self.types = []  # type: List[InternalType]

    def __hash__(self):
        # type: () -> int

        # These objects not immutable because there was a _large_ perf impact to being immutable.
        # Having a hash on a mutable object is dangerous, but is was much faster.
        # If you do change it, you need to
        # (a) pull it out of the set/table
        # (b) change it,
        # (c) stuff it back in
        return _my_hash([self.types, len(self.types_hashable)]) if self.types else 0

    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, TentativeType):
            return False

        if self.types_hashable != other.types_hashable:
            return False

        if len(self.types) != len(other.types):
            return False

        for i in self.types:
            if i not in other.types:
                return False

        return True

    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)

    def add(self, type):
        # type: (InternalType) -> None
        """
        Add type to the runtime type samples.
        """
        try:
            if isinstance(type, SetType):
                if EMPTY_SET_TYPE in self.types_hashable:
                    self.types_hashable.remove(EMPTY_SET_TYPE)
            elif isinstance(type, ListType):
                if EMPTY_LIST_TYPE in self.types_hashable:
                    self.types_hashable.remove(EMPTY_LIST_TYPE)
            elif isinstance(type, IteratorType):
                if EMPTY_ITERATOR_TYPE in self.types_hashable:
                    self.types_hashable.remove(EMPTY_ITERATOR_TYPE)
            elif isinstance(type, DictType):
                if EMPTY_DICT_TYPE in self.types_hashable:
                    self.types_hashable.remove(EMPTY_DICT_TYPE)
                for item in self.types_hashable:
                    if isinstance(item, DictType):
                        if item.key_type == type.key_type:
                            item.val_type.merge(type.val_type)
                            return
            self.types_hashable.add(type)

        except (TypeError, AttributeError):
            try:
                if type not in self.types:
                    self.types.append(type)
            except AttributeError:
                if TypeWasIncomparable not in self.types:
                    self.types.append(TypeWasIncomparable)

    def merge(self, other):
        # type: (TentativeType) -> None
        """
        Merge two TentativeType instances
        """
        for hashables in other.types_hashable:
            self.add(hashables)
        for non_hashbles in other.types:
            self.add(non_hashbles)

    def __repr__(self):
        # type: () -> str
        if (len(self.types) + len(self.types_hashable) == 0) or (
                len(self.types_hashable) == 1 and _NONE_TYPE in self.types_hashable):
            return 'None'
        else:
            type_format = '%s'
            filtered_types = self.types + [i for i in self.types_hashable if i != _NONE_TYPE]
            if _NONE_TYPE in self.types_hashable:
                type_format = 'Optional[%s]'
            if len(filtered_types) == 1:
                return type_format % name_from_type(filtered_types[0])
            else:
                # use sorted() for predictable type order in the Union
                return type_format % (
                    'Union[' + ', '.join(sorted([name_from_type(s) for s in filtered_types])) + ']')


FunctionKey = NamedTuple('FunctionKey', [('path', str), ('line', int), ('func_name', str)])

# Inferred types for a function call
ResolvedTypes = NamedTuple('ResolvedTypes',
                           [('pos_args', List[InternalType]),
                            ('varargs', Optional[List[InternalType]])])

# Task queue entry for calling a function with specific argument types
KeyAndTypes = NamedTuple('KeyAndTypes', [('key', FunctionKey), ('types', ResolvedTypes)])

# Task queue entry for returning from a function with a value
KeyAndReturn = NamedTuple('KeyAndReturn', [('key', FunctionKey), ('return_type', InternalType)])

# Combined argument and return types for a single function call
Signature = NamedTuple('Signature', [('args', 'ArgTypes'), ('return_type', InternalType)])


BUILTIN_MODULES = {'__builtin__', 'builtins', 'exceptions'}


def name_from_type(type_):
    # type: (InternalType) -> str
    """
    Helper function to get PEP-484 compatible string representation of our internal types.
    """
    if isinstance(type_, (DictType, ListType, TupleType, SetType, IteratorType)):
        return repr(type_)
    else:
        if type_.__name__ != 'NoneType':
            module = type_.__module__
            if module in BUILTIN_MODULES or module == '<unknown>':
                # Omit module prefix for known built-ins, for convenience. This
                # makes unit tests for this module simpler.
                # Also ignore '<uknown>' modules so pyannotate can parse these types
                return type_.__name__
            else:
                return '%s.%s' % (module, type_.__name__)
        else:
            return 'None'


EMPTY_DICT_TYPE = DictType(TentativeType(), TentativeType())
EMPTY_LIST_TYPE = ListType(TentativeType())
EMPTY_SET_TYPE = SetType(TentativeType())
EMPTY_ITERATOR_TYPE = IteratorType(TentativeType())


# TODO: Make this faster
def get_function_name_from_frame(frame):
    # type: (Any) -> str
    """
    Heuristic to find the class-specified name by @guido

    For instance methods we return "ClassName.method_name"
    For functions we return "function_name"
    """

    def bases_to_mro(cls, bases):
        # type: (type, List[type]) -> List[type]
        """
        Convert __bases__ to __mro__
        """
        mro = [cls]
        for base in bases:
            if base not in mro:
                mro.append(base)
            sub_bases = getattr(base, '__bases__', None)
            if sub_bases:
                sub_bases = [sb for sb in sub_bases if sb not in mro and sb not in bases]
                if sub_bases:
                    mro.extend(bases_to_mro(base, sub_bases))
        return mro

    code = frame.f_code
    # This ought to be aggressively cached with the code object as key.
    funcname = code.co_name
    if code.co_varnames:
        varname = code.co_varnames[0]
        if varname == 'self':
            inst = frame.f_locals.get(varname)
            if inst is not None:
                try:
                    mro = inst.__class__.__mro__
                except AttributeError:
                    mro = None
                else:
                    try:
                        bases = inst.__class__.__bases__
                    except AttributeError:
                        bases = None
                    else:
                        mro = bases_to_mro(inst.__class__, bases)
                if mro:
                    for cls in mro:
                        bare_method = cls.__dict__.get(funcname)
                        if bare_method and getattr(bare_method, '__code__', None) is code:
                            return '%s.%s' % (cls.__name__, funcname)
    return funcname


def resolve_type(arg):
    # type: (object) -> InternalType
    """
    Resolve object to one of our internal collection types or generic built-in type.

    Args:
        arg: object to resolve
    """
    arg_type = type(arg)
    if arg_type == list:
        assert isinstance(arg, list)  # this line helps mypy figure out types
        sample = arg[:min(4, len(arg))]
        tentative_type = TentativeType()
        for sample_item in sample:
            tentative_type.add(resolve_type(sample_item))
        return ListType(tentative_type)
    elif arg_type == set:
        assert isinstance(arg, set)  # this line helps mypy figure out types
        sample = []
        iterator = iter(arg)
        for i in range(0, min(4, len(arg))):
            sample.append(next(iterator))
        tentative_type = TentativeType()
        for sample_item in sample:
            tentative_type.add(resolve_type(sample_item))
        return SetType(tentative_type)
    elif arg_type == FakeIterator:
        assert isinstance(arg, FakeIterator)  # this line helps mypy figure out types
        sample = []
        iterator = iter(arg)
        for i in range(0, min(4, len(arg))):
            sample.append(next(iterator))
        tentative_type = TentativeType()
        for sample_item in sample:
            tentative_type.add(resolve_type(sample_item))
        return IteratorType(tentative_type)
    elif arg_type == tuple:
        assert isinstance(arg, tuple)  # this line helps mypy figure out types
        sample = list(arg[:min(10, len(arg))])
        return TupleType([resolve_type(sample_item) for sample_item in sample])
    elif arg_type == dict:
        assert isinstance(arg, dict)  # this line helps mypy figure out types
        key_tt = TentativeType()
        val_tt = TentativeType()
        for i, (k, v) in enumerate(iteritems(arg)):
            if i > 4:
                break
            key_tt.add(resolve_type(k))
            val_tt.add(resolve_type(v))
        return DictType(key_tt, val_tt)
    else:
        return type(arg)


def prep_args(arg_info):
    # type: (ArgInfo) -> ResolvedTypes
    """
    Resolve types from ArgInfo
    """

    # pull out any varargs declarations
    filtered_args = [a for a in arg_info.args if getattr(arg_info, 'varargs', None) != a]

    # we don't care about self/cls first params (perhaps we can test if it's an instance/class method another way?)
    if filtered_args and (filtered_args[0] in ('self', 'cls')):
        filtered_args = filtered_args[1:]

    pos_args = []  # type: List[InternalType]
    if filtered_args:
        for arg in filtered_args:
            if isinstance(arg, str) and arg in arg_info.locals:
                # here we know that return type will be of type "type"
                resolved_type = resolve_type(arg_info.locals[arg])
                pos_args.append(resolved_type)
            else:
                pos_args.append(type(UnknownType()))

    varargs = None  # type: Optional[List[InternalType]]
    if arg_info.varargs:
        varargs_tuple = arg_info.locals[arg_info.varargs]
        # It's unclear what all the possible values for 'varargs_tuple' are,
        # so perform a defensive type check since we don't want to crash here.
        if isinstance(varargs_tuple, tuple):
            varargs = [resolve_type(arg) for arg in varargs_tuple[:4]]

    return ResolvedTypes(pos_args=pos_args, varargs=varargs)


class ArgTypes(object):
    """
    Internal representation of argument types in a single call
    """

    def __init__(self, resolved_types):
        # type: (ResolvedTypes) -> None
        self.pos_args = [TentativeType() for _ in range(len(resolved_types.pos_args))]
        if resolved_types.pos_args:
            for i, arg in enumerate(resolved_types.pos_args):
                self.pos_args[i].add(arg)

        self.varargs = None  # type: Optional[TentativeType]
        if resolved_types.varargs:
            self.varargs = TentativeType()
            for arg in resolved_types.varargs:
                self.varargs.add(arg)

    def __repr__(self):
        # type: () -> str
        return str({'pos_args': self.pos_args, 'varargs': self.varargs})

    def __hash__(self):
        # type: () -> int
        return _my_hash(self.pos_args) + hash(self.varargs)

    def __eq__(self, other):
        # type: (object) -> bool
        return (isinstance(other, ArgTypes)
                and other.pos_args == self.pos_args and other.varargs == self.varargs)

    def __ne__(self, other):
        # type: (object) -> bool
        return not self.__eq__(other)


# Collect at most this many type comments for each function.
MAX_ITEMS_PER_FUNCTION = 8

# The most recent argument types collected for each function. Once we encounter
# a corresponding return event, an item will be flushed and moved to
# 'collected_comments'.
collected_args = {}  # type: Dict[FunctionKey, ArgTypes]

# Collected unique type comments for each function, of form '(arg, ...) -> ret'.
# There at most MAX_ITEMS_PER_FUNCTION items.
collected_signatures = {}  # type: Dict[FunctionKey, Set[Tuple[ArgTypes, InternalType]]]

# Number of samples collected per function (we also count ones ignored after reaching
# the maximum comment count per function).
num_samples = {}  # type: Dict[FunctionKey, int]


def _make_type_comment(args_info, return_type):
    # type: (ArgTypes, InternalType) -> str
    """Generate a type comment of form '(arg, ...) -> ret'."""
    if not args_info.pos_args:
        args_string = ''
    else:
        args_string = ', '.join([repr(t) for t in args_info.pos_args])
    if args_info.varargs:
        varargs = '*%s' % repr(args_info.varargs)
        if args_string:
            args_string += ', %s' % varargs
        else:
            args_string = varargs
    return_name = name_from_type(return_type)
    return '(%s) -> %s' % (args_string, return_name)


def _flush_signature(key, return_type):
    # type: (FunctionKey, InternalType) -> None
    """Store signature for a function.

    Assume that argument types have been stored previously to
    'collected_args'. As the 'return_type' argument provides the return
    type, we now have a complete signature.

    As a side effect, removes the argument types for the function from
    'collected_args'.
    """
    signatures = collected_signatures.setdefault(key, set())
    args_info = collected_args.pop(key)
    if len(signatures) < MAX_ITEMS_PER_FUNCTION:
        signatures.add((args_info, return_type))
    num_samples[key] = num_samples.get(key, 0) + 1


def type_consumer():
    # type: () -> None
    """
    Infinite loop of the type consumer thread.
    It gets types to process from the task query.
    """

    # we are not interested in profiling type_consumer itself
    # but we start it before any other thread
    while True:
        item = _task_queue.get()
        if isinstance(item, KeyAndTypes):
            if item.key in collected_args:
                # Previous call didn't get a corresponding return, perhaps because we
                # stopped collecting types in the middle of a call or because of
                # a recursive function.
                _flush_signature(item.key, UnknownType)
            collected_args[item.key] = ArgTypes(item.types)
        else:
            assert isinstance(item, KeyAndReturn)
            if item.key in collected_args:
                _flush_signature(item.key, item.return_type)
        _task_queue.task_done()


_task_queue = Queue()  # type: Queue[Union[KeyAndTypes, KeyAndReturn]]
_consumer_thread = Thread(target=type_consumer)
_consumer_thread.daemon = True
_consumer_thread.start()

running = False

TOP_DIR = os.path.join(os.getcwd(), '')     # current dir with trailing slash
TOP_DIR_DOT = os.path.join(TOP_DIR, '.')
TOP_DIR_LEN = len(TOP_DIR)


def _make_sampling_sequence(n):
    # type: (int) -> List[int]
    """
    Return a list containing the proposed call event sampling sequence.

    Return events are paired with call events and not counted separately.

    This is 0, 1, 2, ..., 4 plus 50, 100, 150, 200, etc.

    The total list size is n.
    """
    seq = list(range(5))
    i = 50
    while len(seq) < n:
        seq.append(i)
        i += 50
    return seq


# We pre-compute the sampling sequence since 'x in <set>' is faster.
MAX_SAMPLES_PER_FUNC = 500
sampling_sequence = frozenset(_make_sampling_sequence(MAX_SAMPLES_PER_FUNC))
LAST_SAMPLE = max(sampling_sequence)

# Array of counters indexed by ID of code object.
sampling_counters = {}  # type: Dict[int, Optional[int]]
# IDs of code objects for which the previous event was a call (awaiting return).
call_pending = set()  # type: Set[int]


@contextmanager
def collect():
    # type: () -> Iterator[None]
    resume()
    try:
        yield
    finally:
        pause()


def pause():
    # type: () -> None
    """
    Pause the type collection
    """
    global running  # pylint: disable=global-statement
    running = False
    _task_queue.join()


def resume():
    # type: () -> None
    """
    Resume the type collection
    """
    global running  # pylint: disable=global-statement
    running = True
    sampling_counters.clear()


def default_filter_filename(filename):
    # type: (Optional[str]) -> Optional[str]
    """Default filter for filenames.

    Returns either a normalized filename or None.
    You can pass your own filter to init_types_collection().
    """
    if filename is None:
        return None
    elif filename.startswith(TOP_DIR):
        if filename.startswith(TOP_DIR_DOT):
            # Skip subdirectories starting with dot (e.g. .vagrant).
            return None
        else:
            # Strip current directory and following slashes.
            return filename[TOP_DIR_LEN:].lstrip(os.sep)
    elif filename.startswith(os.sep):
        # Skip absolute paths not under current directory.
        return None
    else:
        return filename


_filter_filename = default_filter_filename  # type: Callable[[Optional[str]], Optional[str]]


if sys.version_info[0] == 2:
    RETURN_VALUE_OPCODE = chr(opcode.opmap['RETURN_VALUE'])
    YIELD_VALUE_OPCODE = chr(opcode.opmap['YIELD_VALUE'])
else:
    RETURN_VALUE_OPCODE = opcode.opmap['RETURN_VALUE']
    YIELD_VALUE_OPCODE = opcode.opmap['YIELD_VALUE']


def _trace_dispatch(frame, event, arg):
    # type: (Any, str, Optional[Any]) -> None
    """
    This is the main hook passed to setprofile().
    It implement python profiler interface.

    Arguments are described in https://docs.python.org/2/library/sys.html#sys.settrace
    """
    # Bail if we're not tracing.
    if not running:
        return

    # Get counter for this code object.  Bail if we don't care about this function.
    # An explicit None is stored in the table when we no longer care.
    code = frame.f_code
    key = id(code)
    n = sampling_counters.get(key, 0)
    if n is None:
        return

    if event == 'call':
        # Bump counter and bail depending on sampling sequence.
        sampling_counters[key] = n + 1
        # Each function gets traced at most MAX_SAMPLES_PER_FUNC times per run.
        # NOTE: There's a race condition if two threads call the same function.
        # I don't think we should care, so what if it gets probed an extra time.
        if n not in sampling_sequence:
            if n > LAST_SAMPLE:
                sampling_counters[key] = None  # We're no longer interested in this function.
            call_pending.discard(key)  # Avoid getting events out of sync
            return
        # Mark that we are looking for a return from this code object.
        call_pending.add(key)
    elif event == 'return':
        if key not in call_pending:
            # No pending call event -- ignore this event. We only collect
            # return events when we know the corresponding call event.
            return
        call_pending.remove(key)
    else:
        # Ignore other events, such as c_call and c_return.
        return

    # Track calls under current directory only.
    filename = _filter_filename(code.co_filename)
    if filename:
        func_name = get_function_name_from_frame(frame)
        if not func_name or func_name[0] == '<':
            # Could be a lambda or a comprehension; we're not interested.
            sampling_counters[key] = None
        else:
            function_key = FunctionKey(filename, code.co_firstlineno, func_name)
            if event == 'call':
                # TODO(guido): Make this faster
                arg_info = inspect.getargvalues(frame)  # type: ArgInfo
                resolved_types = prep_args(arg_info)
                _task_queue.put(KeyAndTypes(function_key, resolved_types))
            elif event == 'return':
                # This event is also triggered if a function yields or raises an exception.
                # We can tell the difference by looking at the bytecode.
                # (We don't get here for C functions so the bytecode always exists.)
                last_opcode = code.co_code[frame.f_lasti]
                if last_opcode == RETURN_VALUE_OPCODE:
                    if code.co_flags & CO_GENERATOR:
                        # Return from a generator.
                        t = resolve_type(FakeIterator([]))
                    else:
                        t = resolve_type(arg)
                elif last_opcode == YIELD_VALUE_OPCODE:
                    # Yield from a generator.
                    # TODO: Unify generators -- currently each YIELD is turned into
                    # a separate call, so a function yielding ints and strs will be
                    # typed as Union[Iterator[int], Iterator[str]] -- this should be
                    # Iterator[Union[int, str]].
                    t = resolve_type(FakeIterator([arg]))
                else:
                    # This branch is also taken when returning from a generator.
                    # TODO: returning non-trivial values from generators, per PEP 380;
                    # and async def / await stuff.
                    t = NoReturnType
                _task_queue.put(KeyAndReturn(function_key, t))
    else:
        sampling_counters[key] = None  # We're not interested in this function.


T = TypeVar('T')


def _filter_types(types_dict):
    # type: (Dict[FunctionKey, T]) -> Dict[FunctionKey, T]
    """Filter type info before dumping it to the file."""

    def exclude(k):
        # type: (FunctionKey) -> bool
        """Exclude filter"""
        return k.path.startswith('<') or k.func_name == '<module>'

    return {k: v for k, v in iteritems(types_dict) if not exclude(k)}


def _dump_impl():
    # type: () -> List[FunctionData]
    """Internal implementation for dump_stats and dumps_stats"""
    filtered_signatures = _filter_types(collected_signatures)
    sorted_by_file = sorted(iteritems(filtered_signatures),
                            key=(lambda p: (p[0].path, p[0].line, p[0].func_name)))
    res = []  # type: List[FunctionData]
    for function_key, signatures in sorted_by_file:
        comments = [_make_type_comment(args, ret_type) for args, ret_type in signatures]
        res.append(
            {
                'path': function_key.path,
                'line': function_key.line,
                'func_name': function_key.func_name,
                'type_comments': comments,
                'samples': num_samples.get(function_key, 0),
            }
        )
    return res


def dump_stats(filename):
    # type: (str) -> None
    """
    Write collected information to file.

    Args:
        filename: absolute filename
    """
    res = _dump_impl()
    f = open(filename, 'w')
    json.dump(res, f, indent=4)
    f.close()


def dumps_stats():
    # type: () -> str
    """
    Return collected information as a json string.
    """
    res = _dump_impl()
    return json.dumps(res, indent=4)


def init_types_collection(filter_filename=default_filter_filename):
    # type: (Callable[[Optional[str]], Optional[str]]) -> None
    """
    Setup profiler hooks to enable type collection.
    Call this one time from the main thread.

    The optional argument is a filter that maps a filename (from
    code.co_filename) to either a normalized filename or None.
    For the default filter see default_filter_filename().
    """
    global _filter_filename
    _filter_filename = filter_filename
    sys.setprofile(_trace_dispatch)
    threading.setprofile(_trace_dispatch)


def stop_types_collection():
    # type: () -> None
    """
    Remove profiler hooks.
    """
    sys.setprofile(None)
    threading.setprofile(None)  # type: ignore
