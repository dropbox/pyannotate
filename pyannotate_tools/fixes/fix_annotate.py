"""Fixer that inserts mypy annotations into all methods.

This transforms e.g.

  def foo(self, bar, baz=12):
      return bar + baz

into a type annotated version:

	  def foo(self, bar, baz=12):
	      # type: (Any, int) -> Any            # noqa: F821
	      return bar + baz

or (when setting options['annotation_style'] to 'py3'):

	  def foo(self, bar : Any, baz : int = 12) -> Any:
	      return bar + baz


It does not do type inference but it recognizes some basic default
argument values such as numbers and strings (and assumes their type
implies the argument type).

It also uses some basic heuristics to decide whether to ignore the
first argument:

  - always if it's named 'self'
  - if there's a @classmethod decorator

Finally, it knows that __init__() is supposed to return None.
"""

from __future__ import print_function

import os
import re

from lib2to3.fixer_base import BaseFix
from lib2to3.fixer_util import syms, touch_import, find_indentation
from lib2to3.patcomp import compile_pattern
from lib2to3.pgen2 import token
from lib2to3.pytree import Leaf, Node


class FixAnnotate(BaseFix):

    # This fixer is compatible with the bottom matcher.
    BM_compatible = True

    # This fixer shouldn't run by default.
    explicit = True

    # The pattern to match.
    PATTERN = """
              funcdef< 'def' name=any parameters=parameters< '(' [args=any] rpar=')' > ':' suite=any+ >
              """

    _maxfixes = os.getenv('MAXFIXES')
    counter = None if not _maxfixes else int(_maxfixes)

    def transform(self, node, results):
        if FixAnnotate.counter is not None:
            if FixAnnotate.counter <= 0:
                return

        # Check if there's already a long-form annotation for some argument.
        parameters = results.get('parameters')
        if parameters is not None:
            for ch in parameters.pre_order():
                if ch.prefix.lstrip().startswith('# type:'):
                    return
        args = results.get('args')
        if args is not None:
            for ch in args.pre_order():
                if ch.prefix.lstrip().startswith('# type:'):
                    return

        children = results['suite'][0].children

        # NOTE: I've reverse-engineered the structure of the parse tree.
        # It's always a list of nodes, the first of which contains the
        # entire suite.  Its children seem to be:
        #
        #   [0] NEWLINE
        #   [1] INDENT
        #   [2...n-2] statements (the first may be a docstring)
        #   [n-1] DEDENT
        #
        # Comments before the suite are part of the INDENT's prefix.
        #
        # "Compact" functions (e.g. "def foo(x, y): return max(x, y)")
        # have a different structure (no NEWLINE, INDENT, or DEDENT).

        # Check if there's already an annotation.
        for ch in children:
            if ch.prefix.lstrip().startswith('# type:'):
                return  # There's already a # type: comment here; don't change anything.

        # Python 3 style return annotation are already skipped by the pattern

        ### Python 3 style argument annotation structure
        #
        # Structure of the arguments tokens for one positional argument without default value :
        # + LPAR '('
        # + NAME_NODE_OR_LEAF arg1
        # + RPAR ')'
        #
        # NAME_NODE_OR_LEAF is either:
        # 1. Just a leaf with value NAME
        # 2. A node with children: NAME, ':", node expr or value leaf
        #
        # Structure of the arguments tokens for one args with default value or multiple
        # args, with or without default value, and/or with extra arguments :
        # + LPAR '('
        # + node
        #   [
        #     + NAME_NODE_OR_LEAF
        #      [
        #        + EQUAL '='
        #        + node expr or value leaf
        #      ]
        #    (
        #        + COMMA ','
        #        + NAME_NODE_OR_LEAF positional argn
        #      [
        #        + EQUAL '='
        #        + node expr or value leaf
        #      ]
        #    )*
        #   ]
        #   [
        #     + STAR '*'
        #     [
        #     + NAME_NODE_OR_LEAF positional star argument name
        #     ]
        #   ]
        #   [
        #     + COMMA ','
        #     + DOUBLESTAR '**'
        #     + NAME_NODE_OR_LEAF positional keyword argument name
        #   ]
        # + RPAR ')'

        # Let's skip Python 3 argument annotations
        it = iter(args.children) if args else iter([])
        for ch in it:
            if ch.type == token.STAR:
                # *arg part
                ch = next(it)
                if ch.type == token.COMMA:
                    continue
            elif ch.type == token.DOUBLESTAR:
                # *arg part
                ch = next(it)
            if ch.type > 256:
                # this is a node, therefore an annotation
                assert ch.children[0].type == token.NAME
                return
            try:
                ch = next(it)
                if ch.type == token.COLON:
                    # this is an annotation
                    return
                elif ch.type == token.EQUAL:
                    ch = next(it)
                    ch = next(it)
                assert ch.type == token.COMMA
                continue
            except StopIteration:
                break

        # Compute the annotation
        annot = self.make_annotation(node, results)
        if annot is None:
            return
        argtypes, restype = annot

        if self.options['annotation_style'] == 'py3':
            self.add_py3_annot(argtypes, restype, node, results)
        else:
            self.add_py2_annot(argtypes, restype, node, results)

        # Common to py2 and py3 style annotations:
        if FixAnnotate.counter is not None:
            FixAnnotate.counter -= 1

        # Also add 'from typing import Any' at the top if needed.
        self.patch_imports(argtypes + [restype], node)

    def add_py3_annot(self, argtypes, restype, node, results):
        args = results.get('args')

        argleaves = []
        if args is None:
            # function with 0 arguments
            it = iter([])
        elif len(args.children) == 0:
            # function with 1 argument
            it = iter([args])
        else:
            # function with multiple arguments or 1 arg with default value
            it = iter(args.children)

        for ch in it:
            argstyle = 'name'
            if ch.type == token.STAR:
                # *arg part
                argstyle = 'star'
                ch = next(it)
                if ch.type == token.COMMA:
                    continue
            elif ch.type == token.DOUBLESTAR:
                # *arg part
                argstyle = 'keyword'
                ch = next(it)
            assert ch.type == token.NAME
            argleaves.append((argstyle, ch))
            try:
                ch = next(it)
                if ch.type == token.EQUAL:
                    ch = next(it)
                    ch = next(it)
                assert ch.type == token.COMMA
                continue
            except StopIteration:
                break

        # when self or cls is not annotated, argleaves == argtypes+1
        argleaves = argleaves[len(argleaves) - len(argtypes):]

        for ch_withstyle, chtype in zip(argleaves, argtypes):
            style, ch = ch_withstyle
            if style == 'star':
                assert chtype[0] == '*'
                assert chtype[1] != '*'
                chtype = chtype[1:]
            elif style == 'keyword':
                assert chtype[0:2] == '**'
                assert chtype[2] != '*'
                chtype = chtype[2:]
            ch.value = '%s: %s' % (ch.value, chtype)

            # put spaces around the equal sign
            if ch.next_sibling and ch.next_sibling.type == token.EQUAL:
                nextch = ch.next_sibling
                if not nextch.prefix[:1].isspace():
                    nextch.prefix = ' ' + nextch.prefix
                nextch = nextch.next_sibling
                assert nextch != None
                if not nextch.prefix[:1].isspace():
                    nextch.prefix = ' ' + nextch.prefix

        # Add return annotation
        rpar = results['rpar']
        rpar.value = '%s -> %s' % (rpar.value, restype)

        rpar.changed()

    def add_py2_annot(self, argtypes, restype, node, results):
        children = results['suite'][0].children

        # Insert '# type: {annot}' comment.
        # For reference, see lib2to3/fixes/fix_tuple_params.py in stdlib.
        if len(children) >= 1 and children[0].type != token.NEWLINE:
            # one liner function
            if children[0].prefix.strip() == '':
                children[0].prefix = ''
                children.insert(0, Leaf(token.NEWLINE, '\n'))
                children.insert(
                    1, Leaf(token.INDENT, find_indentation(node) + '    '))
                children.append(Leaf(token.DEDENT, ''))
        if len(children) >= 2 and children[1].type == token.INDENT:
            degen_str = '(...) -> %s' % restype
            short_str = '(%s) -> %s' % (', '.join(argtypes), restype)
            if (len(short_str) > 64 or len(argtypes) > 5) and len(short_str) > len(degen_str):
                self.insert_long_form(node, results, argtypes)
                annot_str = degen_str
            else:
                annot_str = short_str
            children[1].prefix = '%s# type: %s\n%s' % (children[1].value, annot_str,
                                                       children[1].prefix)
            children[1].changed()
        else:
            self.log_message("%s:%d: cannot insert annotation for one-line function" %
                             (self.filename, node.get_lineno()))

    def insert_long_form(self, node, results, argtypes):
        argtypes = list(argtypes)  # We destroy it
        args = results['args']
        if isinstance(args, Node):
            children = args.children
        elif isinstance(args, Leaf):
            children = [args]
        else:
            children = []
        # Interpret children according to the following grammar:
        # (('*'|'**')? NAME ['=' expr] ','?)*
        flag = False  # Set when the next leaf should get a type prefix
        indent = ''  # Will be set by the first child

        def set_prefix(child):
            if argtypes:
                arg = argtypes.pop(0).lstrip('*')
            else:
                arg = 'Any'  # Somehow there aren't enough args
            if not arg:
                # Skip self (look for 'check_self' below)
                prefix = child.prefix.rstrip()
            else:
                prefix = '  # type: ' + arg
                old_prefix = child.prefix.strip()
                if old_prefix:
                    assert old_prefix.startswith('#')
                    prefix += '  ' + old_prefix
            child.prefix = prefix + '\n' + indent

        check_self = self.is_method(node)
        for child in children:
            if check_self and isinstance(child, Leaf) and child.type == token.NAME:
                check_self = False
                if child.value in ('self', 'cls'):
                    argtypes.insert(0, '')
            if not indent:
                indent = ' ' * child.column
            if isinstance(child, Leaf) and child.value == ',':
                flag = True
            elif isinstance(child, Leaf) and flag:
                set_prefix(child)
                flag = False
        need_comma = len(children) >= 1 and children[-1].type != token.COMMA
        if need_comma and len(children) >= 2:
            if (children[-1].type == token.NAME and
                    (children[-2].type in (token.STAR, token.DOUBLESTAR))):
                need_comma = False
        if need_comma:
            children.append(Leaf(token.COMMA, u","))
        # Find the ')' and insert a prefix before it too.
        parameters = args.parent
        close_paren = parameters.children[-1]
        assert close_paren.type == token.RPAR, close_paren
        set_prefix(close_paren)
        assert not argtypes, argtypes

    def patch_imports(self, types, node):
        for typ in types:
            if 'Any' in typ:
                touch_import('typing', 'Any', node)
                break

    def make_annotation(self, node, results):
        name = results['name']
        assert isinstance(name, Leaf), repr(name)
        assert name.type == token.NAME, repr(name)
        decorators = self.get_decorators(node)
        is_method = self.is_method(node)
        if name.value == '__init__' or not self.has_return_exprs(node):
            restype = 'None'
        else:
            restype = 'Any'
        args = results.get('args')
        argtypes = []
        if isinstance(args, Node):
            children = args.children
        elif isinstance(args, Leaf):
            children = [args]
        else:
            children = []
        # Interpret children according to the following grammar:
        # (('*'|'**')? NAME ['=' expr] ','?)*
        stars = inferred_type = ''
        in_default = False
        at_start = True
        for child in children:
            if isinstance(child, Leaf):
                if child.value in ('*', '**'):
                    stars += child.value
                elif child.type == token.NAME and not in_default:
                    if not is_method or not at_start or 'staticmethod' in decorators:
                        inferred_type = 'Any'
                    else:
                        # Always skip the first argument if it's named 'self'.
                        # Always skip the first argument of a class method.
                        if child.value == 'self' or 'classmethod' in decorators:
                            pass
                        else:
                            inferred_type = 'Any'
                elif child.value == '=':
                    in_default = True
                elif in_default and child.value != ',':
                    if child.type == token.NUMBER:
                        if re.match(r'\d+[lL]?$', child.value):
                            inferred_type = 'int'
                        else:
                            inferred_type = 'float'  # TODO: complex?
                    elif child.type == token.STRING:
                        if child.value.startswith(('u', 'U')):
                            inferred_type = 'unicode'
                        else:
                            inferred_type = 'str'
                    elif child.type == token.NAME and child.value in ('True', 'False'):
                        inferred_type = 'bool'
                elif child.value == ',':
                    if inferred_type:
                        argtypes.append(stars + inferred_type)
                    # Reset
                    stars = inferred_type = ''
                    in_default = False
                    at_start = False
        if inferred_type:
            argtypes.append(stars + inferred_type)
        return argtypes, restype

    # The parse tree has a different shape when there is a single
    # decorator vs. when there are multiple decorators.
    DECORATED = "decorated< (d=decorator | decorators< dd=decorator+ >) funcdef >"
    decorated = compile_pattern(DECORATED)

    def get_decorators(self, node):
        """Return a list of decorators found on a function definition.

        This is a list of strings; only simple decorators
        (e.g. @staticmethod) are returned.

        If the function is undecorated or only non-simple decorators
        are found, return [].
        """
        if node.parent is None:
            return []
        results = {}
        if not self.decorated.match(node.parent, results):
            return []
        decorators = results.get('dd') or [results['d']]
        decs = []
        for d in decorators:
            for child in d.children:
                if isinstance(child, Leaf) and child.type == token.NAME:
                    decs.append(child.value)
        return decs

    def is_method(self, node):
        """Return whether the node occurs (directly) inside a class."""
        node = node.parent
        while node is not None:
            if node.type == syms.classdef:
                return True
            if node.type == syms.funcdef:
                return False
            node = node.parent
        return False

    RETURN_EXPR = "return_stmt< 'return' any >"
    return_expr = compile_pattern(RETURN_EXPR)

    def has_return_exprs(self, node):
        """Traverse the tree below node looking for 'return expr'.

        Return True if at least 'return expr' is found, False if not.
        (If both 'return' and 'return expr' are found, return True.)
        """
        results = {}
        if self.return_expr.match(node, results):
            return True
        for child in node.children:
            if child.type not in (syms.funcdef, syms.classdef):
                if self.has_return_exprs(child):
                    return True
        return False

    YIELD_EXPR = "yield_expr< 'yield' [any] >"
    yield_expr = compile_pattern(YIELD_EXPR)

    def is_generator(self, node):
        """Traverse the tree below node looking for 'yield [expr]'."""
        results = {}
        if self.yield_expr.match(node, results):
            return True
        for child in node.children:
            if child.type not in (syms.funcdef, syms.classdef):
                if self.is_generator(child):
                    return True
        return False
