from typing import Annotated, ClassVar

from pydantic import BaseModel, Field
from pytest import raises

from pydantic_meta_kit import (
    BaseMeta,
    InheritValue,
    MetaRules,
    WithMeta,
)
from pydantic_meta_kit.exceptions import PydanticMetaKitException


def test_meta_add_with_none():

    class SomeMeta(BaseMeta):
        abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
        number: int

    a = SomeMeta(number=1, abstract=True)

    result: SomeMeta = a & None

    assert result.number == 1
    assert result.abstract is False


def test_meta_add_with_type_mismatch():

    class SomeMeta(BaseMeta):
        number: int

    class OtherMeta(BaseMeta):
        number: int

    a = SomeMeta(number=1)
    b = OtherMeta(number=2)

    with raises(PydanticMetaKitException):
        a & b  # type: ignore


def test_meta_initialised_directly_vals():
    """
    Test that an instance records the keys that were instantiated directly
    on the model
    """

    class SomeMeta(BaseMeta):
        number: Annotated[int, MetaRules.INHERIT_OR_OVERRIDE] = 1

    a = SomeMeta()
    b = SomeMeta(number=1)

    assert a._initialised_directly == set()
    assert b._initialised_directly == set(["number"])


def test_meta_basic_combine():

    class SomeMeta(BaseMeta):
        number: Annotated[int, MetaRules.INHERIT_OR_OVERRIDE] = 1
        number_two: int = 2

    a = SomeMeta()
    b = SomeMeta()

    result: SomeMeta = a & b
    assert result.number == 1
    assert result.number_two == 2

    a = SomeMeta(number=3)
    b = SomeMeta()

    result: SomeMeta = a & b
    assert result.number == 3
    assert result.number_two == 2


def test_meta_combine_without_default_value_on_field():
    class SomeMeta(BaseMeta):
        number: int | InheritValue = InheritValue.AS_DEFAULT

    a = SomeMeta(number=1)
    b = SomeMeta()

    result: SomeMeta = a & b
    assert result.number == 1

    a = SomeMeta()
    b = SomeMeta()

    result: SomeMeta = a & b
    assert result.number is InheritValue.AS_DEFAULT


def test_meta_errors_when_do_not_inherit_has_no_default():
    with raises(PydanticMetaKitException):

        class SomeMeta(BaseMeta):
            abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT]


def test_do_not_inherit_accepts_a_default_factory():
    class SomeMeta(BaseMeta):
        names: Annotated[list[str], MetaRules.DO_NOT_INHERIT] = Field(
            default_factory=list
        )

    class Root(WithMeta[SomeMeta]):
        _meta = SomeMeta(names=["root"])

    class Child(Root):
        pass

    class Own(Root):
        _meta = SomeMeta(names=["own"])

    assert Root._meta.names == ["root"]
    # not inherited: the child has the default, made afresh (not the parent's list)
    assert Child._meta.names == []
    assert Child._meta.names is not Root._meta.names
    assert Own._meta.names == ["own"]


def test_do_not_inherit_with_a_mutable_factory_value_is_not_shared_between_classes():
    class SomeMeta(BaseMeta):
        names: Annotated[list[str], MetaRules.DO_NOT_INHERIT] = Field(
            default_factory=list
        )

    class Root(WithMeta[SomeMeta]):
        pass

    class A(Root):
        pass

    class B(Root):
        pass

    assert A._meta.names is not B._meta.names


def test_meta_combine_with_revert_to_default():
    class SomeMeta(BaseMeta):
        abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False

    a = SomeMeta(abstract=True)
    b = SomeMeta()

    result: SomeMeta = a & b
    assert result.abstract is False

    a = SomeMeta(abstract=True)
    b = SomeMeta()

    c = SomeMeta(abstract=True)

    result = a & b & c

    assert result.abstract is True

    a = SomeMeta(abstract=True)
    result = a & None

    assert result.abstract is False


def test_meta_accumulate_must_be_iterable():
    with raises(PydanticMetaKitException):

        class SomeMeta(BaseMeta):
            things: Annotated[int, MetaRules.ACCUMULATE]


def test_meta_accumulate_with_list():
    class SomeMeta(BaseMeta):
        things: Annotated[list, MetaRules.ACCUMULATE] = Field(default_factory=list)

    a = SomeMeta(things=["one"])
    b = SomeMeta(things=["two"])

    result = a & b
    assert result.things == ["one", "two"]

    c = SomeMeta(things=["three"])

    result = a & b & c
    assert result.things == ["one", "two", "three"]


def test_meta_accumulate_with_set():
    class SomeMeta(BaseMeta):
        things: Annotated[set, MetaRules.ACCUMULATE] = Field(default_factory=set)

    a = SomeMeta(things={"one"})
    b = SomeMeta(things={"two"})

    result = a & b
    assert result.things == {"one", "two"}


def test_meta_accumulate_with_dict():
    class SomeMeta(BaseMeta):
        things: Annotated[dict, MetaRules.ACCUMULATE] = Field(default_factory=dict)

    a = SomeMeta(things={"one": "one"})
    b = SomeMeta(things={"two": "two"})

    result = a & b
    assert result.things == {"one": "one", "two": "two"}


def test_meta_on_class_raises_error_if_no_meta_found_or_cannot_be_instantiated_with_defaults():
    with raises(PydanticMetaKitException):

        class SomeMeta(BaseMeta):
            something: int

        class Root(BaseModel):
            pass

        class ArbitraryMixin:
            pass

        class Entity(Root, ArbitraryMixin, WithMeta[SomeMeta]):
            pass

        class Animal(Entity):
            name: str


def test_meta_on_class_raises_error_if_inherit_field_is_not_declared_somewhere():
    with raises(PydanticMetaKitException):

        class SomeMeta(BaseMeta):
            abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
            things: Annotated[list, MetaRules.ACCUMULATE] = Field(default_factory=list)
            number: int | InheritValue = InheritValue.AS_DEFAULT

        class Root(BaseModel):
            pass

        class ArbitraryMixin:
            pass

        class Entity(Root, ArbitraryMixin, WithMeta[SomeMeta]):
            _meta = SomeMeta(abstract=True, things=["one"])

        class Animal(Entity):
            _meta = SomeMeta()
            name: str


def test_meta_on_class_is_right_type():
    with raises(PydanticMetaKitException):

        class SomeMeta(BaseMeta):
            abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
            things: Annotated[list, MetaRules.ACCUMULATE] = Field(default_factory=list)
            number: int | InheritValue = InheritValue.AS_DEFAULT

        class Bullshit(BaseMeta):
            pass

        class Root(BaseModel):
            pass

        class ArbitraryMixin:
            pass

        class Entity(Root, ArbitraryMixin, WithMeta[SomeMeta]):
            _meta = SomeMeta(
                abstract=True,
                things=["one"],
                number=1,
            )

        class Animal(Entity):
            _meta = Bullshit()
            name: str


def test_meta_on_class():
    class SomeMeta(BaseMeta):
        abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
        things: Annotated[list[str], MetaRules.ACCUMULATE] = Field(default_factory=list)
        number: int | InheritValue = InheritValue.AS_DEFAULT

    class Root(BaseModel):
        pass

    class ArbitraryMixin:
        pass

    class Entity(Root, ArbitraryMixin, WithMeta[SomeMeta]):
        _meta: ClassVar[SomeMeta] = SomeMeta(
            abstract=True,
            things=["one"],
            number=1,
        )

    class Animal(Entity):
        _meta = SomeMeta()
        name: str

    class AnimalTwo(Entity):
        _meta = SomeMeta(things=["two"], abstract=True)
        name: str

    assert Entity._meta.abstract is True
    assert Entity._meta.things == ["one"]
    assert Entity._meta.number == 1

    assert Animal._meta.abstract is False
    assert Animal._meta.things == ["one"]
    assert Animal._meta.number == 1

    assert AnimalTwo._meta.things == ["one", "two"]
    assert AnimalTwo._meta.abstract is True
    assert AnimalTwo._meta.number == 1

    class Cat(Animal):
        pass

    assert Cat._meta.abstract is False
    assert Cat._meta.things == ["one"]


class _BaseOptions(BaseMeta):
    abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
    things: Annotated[list[str], MetaRules.ACCUMULATE] = Field(default_factory=list)
    number: int | InheritValue = InheritValue.AS_DEFAULT


def test_meta_inherits_from_nearest_parent_not_root():
    class Entity(WithMeta[_BaseOptions]):
        _meta = _BaseOptions(things=["a"], number=1)

    class Animal(Entity):
        _meta = _BaseOptions(things=["b"], number=2)

    class Cat(Animal):
        pass

    assert Cat._meta.number == 2
    assert Cat._meta.things == ["a", "b"]


def test_meta_different_hierarchies_do_not_clobber_each_other():
    class MetaOne(BaseMeta):
        one: int = 1

    class MetaTwo(BaseMeta):
        two: int = 2

    class A(WithMeta[MetaOne]):
        pass

    class B(WithMeta[MetaTwo]):
        pass

    class A2(A):
        _meta = MetaOne(one=5)

    assert A._meta.one == 1
    assert A2._meta.one == 5
    assert B._meta.two == 2

    with raises(PydanticMetaKitException):

        class A3(A):
            _meta = MetaTwo()


def test_dict_accumulate_overrides_overlapping_keys():
    class DictMeta(BaseMeta):
        things: Annotated[dict[str, int], MetaRules.ACCUMULATE] = Field(
            default_factory=dict
        )

    result = DictMeta(things={"a": 1, "b": 1}) & DictMeta(things={"b": 2, "c": 3})
    assert result.things == {"a": 1, "b": 2, "c": 3}


def test_merge_does_not_share_mutable_values():
    parent = _BaseOptions(things=["a"])
    child = parent & None
    assert child.things == ["a"]
    assert child.things is not parent.things


def test_extra_annotated_metadata_does_not_break_rule_detection():
    class SomeMeta(BaseMeta):
        things: Annotated[list[str], Field(max_length=5), MetaRules.ACCUMULATE] = Field(
            default_factory=list
        )
        name: Annotated[str, Field(min_length=1)] = "x"

    result = SomeMeta(things=["a"]) & SomeMeta(things=["b"])
    assert result.things == ["a", "b"]


def test_inherit_value_set_explicitly_on_child_still_inherits():
    parent = _BaseOptions(number=3)
    child = _BaseOptions(number=InheritValue.AS_DEFAULT)
    assert (parent & child).number == 3


def test_nested_model_values_are_not_dumped_to_dicts():
    class Inner(BaseModel):
        x: int = 1

    class SomeMeta(BaseMeta):
        inner: Inner = Inner()

    assert isinstance((SomeMeta(inner=Inner(x=2)) & None).inner, Inner)


def test_meta_set_via_model_validate_counts_as_explicit():
    meta = _BaseOptions.model_validate({"number": 4})
    assert meta._initialised_directly == {"number"}


def test_parametrised_generic_model_keeps_meta():
    class Entity[X](WithMeta[_BaseOptions]):
        value: X
        _meta = _BaseOptions(abstract=True, number=1)

    class Concrete(Entity[int]):
        pass

    assert Entity[int]._meta.abstract is True
    assert Concrete._meta.abstract is False


def test_custom_meta_key():
    class InterfaceMeta(BaseMeta):
        meta_key = "_interface_meta"
        methods: Annotated[list[str], MetaRules.ACCUMULATE] = Field(
            default_factory=list
        )

    class Entity(WithMeta[InterfaceMeta]):
        _interface_meta = InterfaceMeta(methods=["a"])  # unannotated

    class Animal(Entity):
        _interface_meta = InterfaceMeta(methods=["b"])

    class Cat(Animal):
        pass

    assert Entity._interface_meta.methods == ["a"]
    assert Animal._interface_meta.methods == ["a", "b"]
    assert Cat._interface_meta.methods == ["a", "b"]
    assert not hasattr(Cat, "_meta")
    assert Cat.__private_attributes__ == {}
    Cat()  # instances still construct


def test_multiple_metas_on_one_class():
    class InterfaceMeta(BaseMeta):
        meta_key = "_interface_meta"
        methods: Annotated[list[str], MetaRules.ACCUMULATE] = Field(
            default_factory=list
        )

    class Entity(WithMeta[_BaseOptions], WithMeta[InterfaceMeta]):
        _meta: ClassVar[_BaseOptions] = _BaseOptions(number=1, things=["x"])
        _interface_meta: ClassVar[InterfaceMeta] = InterfaceMeta(methods=["a"])

    class Animal(Entity):
        _interface_meta = InterfaceMeta(methods=["b"])

    class Cat(Animal):
        _meta = _BaseOptions(things=["y"])

    assert Cat._meta.number == 1
    assert Cat._meta.things == ["x", "y"]
    assert Cat._interface_meta.methods == ["a", "b"]
    assert Animal._meta.things == ["x"]


def test_duplicate_meta_keys_raise():
    class Other(BaseMeta):
        pass

    with raises(PydanticMetaKitException):

        class Entity(WithMeta[_BaseOptions], WithMeta[Other]):
            pass


def test_invalid_meta_key_raises():
    with raises(PydanticMetaKitException):

        class BadMeta(BaseMeta):
            meta_key = "meta"


def test_aliased_fields_are_merged():
    class AliasMeta(BaseMeta):
        number: int = Field(default=0, alias="num")
        things: Annotated[list[int], MetaRules.ACCUMULATE] = Field(
            default_factory=list, alias="items"
        )

    class Entity(WithMeta[AliasMeta]):
        _meta = AliasMeta(num=1, items=[1])

    class Animal(Entity):
        _meta = AliasMeta(num=2)

    class Cat(Animal):
        pass

    assert AliasMeta(num=5)._initialised_directly == {"number"}
    assert Animal._meta.number == 2
    assert Animal._meta.things == [1]
    assert Cat._meta.number == 2
    assert Cat._meta.things == [1]


def test_docstring_example_runs():
    class MyMeta(BaseMeta):
        abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
        things: Annotated[list[int], MetaRules.ACCUMULATE] = Field(default_factory=list)
        number: int | InheritValue = InheritValue.AS_DEFAULT

    class Entity(WithMeta[MyMeta]):
        _meta = MyMeta(abstract=True, things=[1, 2, 3], number=1)

    class Thing(Entity):
        _meta = MyMeta(number=2, things=[4])

    assert Thing._meta.abstract is False
    assert Thing._meta.number == 2
    assert Thing._meta.things == [1, 2, 3, 4]
