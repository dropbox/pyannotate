"""Fixer that inserts mypy annotations from json file into code.

This fixer consumes json from TYPE_COLLECTION_JSON env variable in the following format:

[
    {
        "path": "/Users/svorobev/src/client/build_number/__init__.py",
        "func_name": "is_test",
        "arg_types": ["int", "str"],
        "ret_type": "Any"
    },
    ...
]

(The old format with "type_comment" instead of "arg_types" and
"ret_type" is also still supported.)
"""

from __future__ import print_function

import json  # noqa
import os
import re

from lib2to3.fixer_util import syms, touch_import
from lib2to3.pgen2 import token
from lib2to3.pytree import Base, Leaf, Node
from typing import __all__ as typing_all  # type: ignore
from typing import Any, Dict, List, Optional, Tuple
try:
    from typing import Text
except ImportError:
    # In Python 3.5.1 stdlib, typing.py does not define Text
    Text = str  # type: ignore

from .fix_annotate import FixAnnotate

# Taken from mypy codebase:
# https://github.com/python/mypy/blob/745d300b8304c3dcf601477762bf9d70b9a4619c/mypy/main.py#L503

PY_EXTENSIONS = ['.pyi', '.py']

def crawl_up(arg):
    # type: (str) -> Tuple[str, str]
    """Given a .py[i] filename, return (root directory, module).
    We crawl up the path until we find a directory without
    __init__.py[i], or until we run out of path components.
    """
    dir, mod = os.path.split(arg)
    mod = strip_py(mod) or mod
    while dir and get_init_file(dir):
        dir, base = os.path.split(dir)
        if not base:
            break
        if mod == '__init__' or not mod:
            mod = base
        else:
            mod = base + '.' + mod
    return dir, mod

def strip_py(arg):
    # type: (str) -> Optional[str]
    """Strip a trailing .py or .pyi suffix.
    Return None if no such suffix is found.
    """
    for ext in PY_EXTENSIONS:
        if arg.endswith(ext):
            return arg[:-len(ext)]
    return None

def get_init_file(dir):
    # type: (str) -> Optional[str]
    """Check whether a directory contains a file named __init__.py[i].
    If so, return the file's name (with dir prefixed).  If not, return
    None.
    This prefers .pyi over .py (because of the ordering of PY_EXTENSIONS).
    """
    for ext in PY_EXTENSIONS:
        f = os.path.join(dir, '__init__' + ext)
        if os.path.isfile(f):
            return f
    return None

def get_funcname(name, node):
    # type: (Leaf, Node) -> Text
    """Get function name by the following rules:

    - function -> function_name
    - instance method -> ClassName.function_name
    """
    funcname = name.value
    if node.parent and node.parent.parent:
        grand = node.parent.parent
        if grand.type == syms.classdef:
            grandname = grand.children[1]
            assert grandname.type == token.NAME, repr(name)
            assert isinstance(grandname, Leaf)  # Same as previous, for mypy
            funcname = grandname.value + '.' + funcname
    return funcname

def count_args(node, results):
    # type: (Node, Dict[str, Base]) -> Tuple[int, bool, bool, bool]
    """Count arguments and check for self and *args, **kwds.

    Return (selfish, count, star, starstar) where:
    - count is total number of args (including *args, **kwds)
    - selfish is True if the initial arg is named 'self' or 'cls'
    - star is True iff *args is found
    - starstar is True iff **kwds is found
    """
    count = 0
    selfish = False
    star = False
    starstar = False
    args = results.get('args')
    if isinstance(args, Node):
        children = args.children
    elif isinstance(args, Leaf):
        children = [args]
    else:
        children = []
    # Interpret children according to the following grammar:
    # (('*'|'**')? NAME ['=' expr] ','?)*
    skip = False
    previous_token_is_star = False
    for child in children:
        if skip:
            skip = False
        elif isinstance(child, Leaf):
            # A single '*' indicates the rest of the arguments are keyword only
            # and shouldn't be counted as a `*`.
            if child.type == token.STAR:
                previous_token_is_star = True
            elif child.type == token.DOUBLESTAR:
                starstar = True
            elif child.type == token.NAME:
                if count == 0:
                    if child.value in ('self', 'cls'):
                        selfish = True
                count += 1
                if previous_token_is_star:
                    star = True
            elif child.type == token.EQUAL:
                skip = True
            if child.type != token.STAR:
                previous_token_is_star = False
    return count, selfish, star, starstar

class FixAnnotateJson(FixAnnotate):

    needed_imports = None

    def add_import(self, mod, name):
        if mod == self.current_module():
            return
        if self.needed_imports is None:
            self.needed_imports = set()
        self.needed_imports.add((mod, name))

    def patch_imports(self, types, node):
        if self.needed_imports:
            for mod, name in sorted(self.needed_imports):
                touch_import(mod, name, node)
        self.needed_imports = None

    def current_module(self):
        # TODO: cache this?
        filename = self.filename
        if filename.endswith('.py'):
            filename = filename[:-3]
        parts = filename.split(os.sep)
        if parts[-1] == '__init__':
            del parts[-1]
        if parts[0] == '.':
            del parts[0]
        return '.'.join(parts)

    def make_annotation(self, node, results):
        name = results['name']
        assert isinstance(name, Leaf), repr(name)
        assert name.type == token.NAME, repr(name)
        funcname = get_funcname(name, node)
        res = self.get_annotation_from_stub(node, results, funcname)
        return res

    stub_json_file = os.getenv('TYPE_COLLECTION_JSON')
    # JSON data for the current file
    stub_json = None  # type: List[Dict[str, Any]]

    @classmethod
    def init_stub_json_from_data(cls, data, filename):
        cls.stub_json = data
        cls.top_dir, _ = crawl_up(os.path.abspath(filename))

    def init_stub_json(self):
        with open(self.__class__.stub_json_file) as f:
            data = json.load(f)
        self.__class__.init_stub_json_from_data(data, self.filename)

    def get_annotation_from_stub(self, node, results, funcname):
        if not self.__class__.stub_json:
            self.init_stub_json()
        data = self.__class__.stub_json
        # We are using relative paths in the JSON.
        items = [it for it in data
                 if it['func_name'] == funcname and
                    (os.path.join(self.__class__.top_dir, it['path']) ==
                     os.path.abspath(self.filename))]
        if len(items) > 1:
            # this can happen, because of
            # 1) nested functions
            # 2) method decorators
            # as a cheap and dirty solution we just return the nearest one by the line number
            # (keep the commented-out log_message call in case we need to come back to this)
            ## self.log_message("%s:%d: duplicate signatures for %s (at lines %s)" %
            ##                  (items[0]['path'], node.get_lineno(), items[0]['func_name'],
            ##                   ", ".join(str(it['line']) for it in items)))
            items.sort(key=lambda it: abs(node.get_lineno() - it['line']))
        if items:
            it = items[0]
            # If the line number is too far off, the source probably drifted
            # since the trace was collected; it's better to skip this node.
            # (Allow some drift, since decorators also cause an offset.)
            if abs(node.get_lineno() - it['line']) >= 5:
                self.log_message("%s:%d: '%s' signature from line %d too far away -- skipping" %
                                 (self.filename, node.get_lineno(), it['func_name'], it['line']))
                return None
            if 'signature' in it:
                sig = it['signature']
                arg_types = sig['arg_types']
                # Passes 1-2 don't always understand *args or **kwds,
                # so add '*Any' or '**Any' at the end if needed.
                count, selfish, star, starstar = count_args(node, results)
                for arg_type in arg_types:
                    if arg_type.startswith('**'):
                        starstar = False
                    elif arg_type.startswith('*'):
                        star = False
                if star:
                    arg_types.append('*Any')
                if starstar:
                    arg_types.append('**Any')
                # Pass 1 omits the first arg iff it's named 'self' or 'cls',
                # even if it's not a method, so insert `Any` as needed
                # (but only if it's not actually a method).
                if selfish and len(arg_types) == count - 1:
                    if self.is_method(node):
                        count -= 1  # Leave out the type for 'self' or 'cls'
                    else:
                        arg_types.insert(0, 'Any')
                # If after those adjustments the count is still off,
                # print a warning and skip this node.
                if len(arg_types) != count:
                    self.log_message("%s:%d: source has %d args, annotation has %d -- skipping" %
                                     (self.filename, node.get_lineno(), count, len(arg_types)))
                    return None
                ret_type = sig['return_type']
                arg_types = [self.update_type_names(arg_type) for arg_type in arg_types]
                # Avoid common error "No return value expected"
                if ret_type == 'None' and self.has_return_exprs(node):
                    ret_type = 'Optional[Any]'
                # Special case for generators.
                if (self.is_generator(node) and
                    not (ret_type == 'Iterator' or ret_type.startswith('Iterator['))):
                    if ret_type.startswith('Optional['):
                        assert ret_type[-1] == ']'
                        ret_type = ret_type[9:-1]
                    ret_type = 'Iterator[%s]' % ret_type
                ret_type = self.update_type_names(ret_type)
                return arg_types, ret_type
        return None

    def update_type_names(self, type_str):
        # Replace e.g. `List[pkg.mod.SomeClass]` with
        # `List[SomeClass]` and remember to import it.
        return re.sub(r'[\w.]+', self.type_updater, type_str)

    def type_updater(self, match):
        # Replace `pkg.mod.SomeClass` with `SomeClass`
        # and remember to import it.
        word = match.group()
        if '.' not in word:
            # Assume it's either builtin or from `typing`
            if word in typing_all:
                self.add_import('typing', word)
            return word
        mod, name = word.rsplit('.', 1)
        self.add_import(mod, name)
        return name
