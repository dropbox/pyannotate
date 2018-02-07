import unittest

from typing import List, Tuple

from pyannotate_tools.annotations.infer import (
    flatten_types,
    infer_annotation,
    merge_items,
    remove_redundant_items,
)
from pyannotate_tools.annotations.types import (
    AbstractType,
    AnyType,
    ARG_POS,
    ARG_STAR,
    ClassType,
    TupleType,
    UnionType,
    NoReturnType,
)


class TestInfer(unittest.TestCase):
    def test_simple(self):
        # type: () -> None
        self.assert_infer(['(int) -> str'], ([(ClassType('int'), ARG_POS)],
                                             ClassType('str')))

    def test_infer_union_arg(self):
        # type: () -> None
        self.assert_infer(['(int) -> None',
                           '(str) -> None'],
                           ([(UnionType([ClassType('int'),
                                         ClassType('str')]), ARG_POS)],
                            ClassType('None')))

    def test_infer_union_return(self):
        # type: () -> None
        self.assert_infer(['() -> int',
                           '() -> str'],
                           ([],
                            UnionType([ClassType('int'), ClassType('str')])))

    def test_star_arg(self):
        # type: () -> None
        self.assert_infer(['(int) -> None',
                           '(int, *bool) -> None'],
                           ([(ClassType('int'), ARG_POS),
                             (ClassType('bool'), ARG_STAR)],
                            ClassType('None')))

    def test_merge_unions(self):
        # type: () -> None
        self.assert_infer(['(Union[int, str]) -> None',
                           '(Union[str, None]) -> None'],
                           ([(UnionType([ClassType('int'),
                                         ClassType('str'),
                                         ClassType('None')]), ARG_POS)],
                            ClassType('None')))

    def test_remove_redundant_union_item(self):
        # type: () -> None
        self.assert_infer(['(str) -> None',
                           '(unicode) -> None'],
                           ([(ClassType('Text'), ARG_POS)],
                            ClassType('None')))

    def test_remove_redundant_dict_item(self):
        # type: () -> None
        self.assert_infer(['(Dict[str, Any]) -> None',
                           '(Dict[str, str]) -> None'],
                           ([(ClassType('Dict', [ClassType('str'), AnyType()]), ARG_POS)],
                            ClassType('None')))

    def test_remove_redundant_dict_item_when_simplified(self):
        # type: () -> None
        self.assert_infer(['(Dict[str, Any]) -> None',
                            '(Dict[str, Union[str, List, Dict, int]]) -> None'],
                            ([(ClassType('Dict', [ClassType('str'), AnyType()]), ARG_POS)],
                            ClassType('None')))

    def test_simplify_list_item_types(self):
        # type: () -> None
        self.assert_infer(['(List[Union[bool, int]]) -> None'],
                          ([(ClassType('List', [ClassType('int')]), ARG_POS)],
                            ClassType('None')))

    def test_simplify_potential_typed_dict(self):
        # type: () -> None
        # Fall back to Dict[x, Any] in case of a complex Dict type.
        self.assert_infer(['(Dict[str, Union[int, str]]) -> Any'],
                          ([(ClassType('Dict', [ClassType('str'), AnyType()]), ARG_POS)],
                           AnyType()))
        self.assert_infer(['(Dict[Text, Union[int, str]]) -> Any'],
                          ([(ClassType('Dict', [ClassType('Text'), AnyType()]), ARG_POS)],
                           AnyType()))
        # Not a potential TypedDict so ordinary simplification applies.
        self.assert_infer(['(Dict[str, Union[str, Text]]) -> Any'],
                          ([(ClassType('Dict', [ClassType('str'), ClassType('Text')]), ARG_POS)],
                           AnyType()))
        self.assert_infer(['(Dict[str, Union[int, None]]) -> Any'],
                          ([(ClassType('Dict', [ClassType('str'),
                                                UnionType([ClassType('int'),
                                                           ClassType('None')])]), ARG_POS)],
                           AnyType()))

    def test_simplify_multiple_empty_collections(self):
        # type: () -> None
        self.assert_infer(['() -> Tuple[List, List[x]]',
                           '() -> Tuple[List, List]'],
                           ([],
                            TupleType([ClassType('List'), ClassType('List', [ClassType('x')])])))

    def assert_infer(self, comments, expected):
        # type: (List[str], Tuple[List[Tuple[AbstractType, str]], AbstractType]) -> None
        actual = infer_annotation(comments)
        assert actual == expected

    def test_infer_ignore_mock(self):
        # type: () -> None
        self.assert_infer(['(mock.mock.Mock) -> None',
                           '(str) -> None'],
                           ([(ClassType('str'), ARG_POS)],
                            ClassType('None')))

    def test_infer_ignore_mock_fallback_to_any(self):
        # type: () -> None
        self.assert_infer(['(mock.mock.Mock) -> str',
                           '(mock.mock.Mock) -> int'],
                           ([(AnyType(), ARG_POS)],
                            UnionType([ClassType('str'), ClassType('int')])))

CT = ClassType


class TestRedundantItems(unittest.TestCase):
    def test_cannot_simplify(self):
        # type: () -> None
        for first, second in ((CT('str'), CT('int')),
                              (CT('List', [CT('int')]),
                               CT('List', [CT('str')])),
                              (CT('List'),
                               CT('Set', [CT('int')]))):
            assert remove_redundant_items([first, second]) == [first, second]
            assert remove_redundant_items([second, first]) == [second, first]

    def test_simplify_simple(self):
        # type: () -> None
        for first, second in ((CT('str'), CT('Text')),
                              (CT('bool'), CT('int')),
                              (CT('int'), CT('float'))):
            assert remove_redundant_items([first, second]) == [second]
            assert remove_redundant_items([second, first]) == [second]

    def test_simplify_multiple(self):
        # type: () -> None
        assert remove_redundant_items([CT('Text'), CT('str'), CT('bool'), CT('int'),
                                       CT('X')]) == [CT('Text'), CT('int'), CT('X')]

    def test_simplify_generics(self):
        # type: () -> None
        for first, second in ((CT('List'), CT('List', [CT('Text')])),
                              (CT('Set'), CT('Set', [CT('Text')])),
                              (CT('Dict'), CT('Dict', [CT('str'), CT('int')]))):
            assert remove_redundant_items([first, second]) == [second]


class TestMergeUnionItems(unittest.TestCase):
    def test_cannot_merge(self):
        # type: () -> None
        for first, second in ((CT('str'), CT('Text')),
                              (CT('List', [CT('int')]), CT('List', [CT('str')]))):
            assert merge_items([first, second]) == [first, second]
            assert merge_items([second, first]) == [second, first]
            assert merge_items([first, second, first]) == [first, second, first]

    def test_merge_union_of_same_length_tuples(self):
        # type: () -> None
        assert merge_items([TupleType([CT('str')]),
                            TupleType([CT('int')])]) == [TupleType([UnionType([CT('str'),
                                                                               CT('int')])])]
        assert merge_items([TupleType([CT('str')]),
                            TupleType([CT('Text')])]) == [TupleType([CT('Text')])]

    def test_merge_tuples_with_different_lengths(self):
        # type: () -> None
        assert merge_items([
            TupleType([CT('str')]),
            TupleType([CT('str'), CT('str')])]) == [CT('Tuple', [CT('str')])]
        assert merge_items([
            TupleType([]),
            TupleType([CT('str')]),
            TupleType([CT('str'), CT('str')])]) == [CT('Tuple', [CT('str')])]
        # Don't merge if types aren't identical
        assert merge_items([
            TupleType([CT('str')]),
            TupleType([CT('str'), CT('int')])]) == [TupleType([CT('str')]),
                                                    TupleType([CT('str'), CT('int')])]

    def test_merge_union_containing_no_return(self):
        # type: () -> None
        assert merge_items([CT('int'), NoReturnType()]) == [CT('int')]
        assert merge_items([NoReturnType(), CT('int')]) == [CT('int')]


class TestFlattenTypes(unittest.TestCase):
    def test_nested_tuples(self):
        # type: () -> None
        assert flatten_types([UnionType([UnionType([CT('int'), CT('str')]), CT('X')])]) == [
            CT('int'), CT('str'), CT('X')]
