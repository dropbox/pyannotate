import unittest

from pyannotate_tools.annotations.types import AnyType, ClassType, TupleType, UnionType


class TestTypes(unittest.TestCase):
    def test_instance_str(self):
        # type: () -> None
        assert str(ClassType('int')) == 'int'
        assert str(ClassType('List', [ClassType('int')])) == 'List[int]'
        assert str(ClassType('Dict', [ClassType('int'),
                                     ClassType('str')])) == 'Dict[int, str]'

    def test_any_type_str(self):
        # type: () -> None
        assert str(AnyType()) == 'Any'

    def test_tuple_type_str(self):
        # type: () -> None
        assert str(TupleType([ClassType('int')])) == 'Tuple[int]'
        assert str(TupleType([ClassType('int'),
                              ClassType('str')])) == 'Tuple[int, str]'
        assert str(TupleType([])) == 'Tuple[()]'

    def test_union_type_str(Self):
        # type: () -> None
        assert str(UnionType([ClassType('int'), ClassType('str')])) == 'Union[int, str]'

    def test_optional(Self):
        # type: () -> None
        assert str(UnionType([ClassType('str'), ClassType('None')])) == 'Optional[str]'
        assert str(UnionType([ClassType('None'), ClassType('str')])) == 'Optional[str]'
        assert str(UnionType([ClassType('None'), ClassType('str'),
                              ClassType('int')])) == 'Union[None, str, int]'

    def test_uniform_tuple_str(self):
        # type: () -> None
        assert str(ClassType('Tuple', [ClassType('int')])) == 'Tuple[int, ...]'
