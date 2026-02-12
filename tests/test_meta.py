from typing import Annotated

from pydantic import BaseModel, Field
from pytest import raises

from pydantic_meta_kit.exceptions import PydanticMetaKitException
from pydantic_meta_kit.meta import (
    INHERIT_VALUE,
    META_RULES,
    BaseMeta,
    WithMeta,
)


def test_meta_add_with_none():

    class SomeMeta(BaseMeta):
        abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
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
        number: Annotated[int, META_RULES.REPLACE_IF_NOT_DEFAULT] = 1

    a = SomeMeta()
    b = SomeMeta(number=1)

    assert a._initialised_directly == set()
    assert b._initialised_directly == set(["number"])


def test_meta_basic_combine():

    class SomeMeta(BaseMeta):
        number: Annotated[int, META_RULES.REPLACE_IF_NOT_DEFAULT] = 1
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
        number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT

    a = SomeMeta(number=1)
    b = SomeMeta()

    result: SomeMeta = a & b
    assert result.number == 1

    a = SomeMeta()
    b = SomeMeta()

    result: SomeMeta = a & b
    assert result.number is INHERIT_VALUE.AS_DEFAULT


def test_meta_errors_when_do_not_inherit_has_no_default():
    with raises(PydanticMetaKitException):

        class SomeMeta(BaseMeta):
            abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT]


def test_meta_combine_with_revert_to_default():
    class SomeMeta(BaseMeta):
        abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False

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
            things: Annotated[int, META_RULES.ACCUMULATE]


def test_meta_accumulate_with_list():
    class SomeMeta(BaseMeta):
        things: Annotated[list, META_RULES.ACCUMULATE] = Field(default_factory=list)

    a = SomeMeta(things=["one"])
    b = SomeMeta(things=["two"])

    result = a & b
    assert result.things == ["one", "two"]

    c = SomeMeta(things=["three"])

    result = a & b & c
    assert result.things == ["one", "two", "three"]


def test_meta_accumulate_with_set():
    class SomeMeta(BaseMeta):
        things: Annotated[set, META_RULES.ACCUMULATE] = Field(default_factory=set)

    a = SomeMeta(things={"one"})
    b = SomeMeta(things={"two"})

    result = a & b
    assert result.things == {"one", "two"}


def test_meta_accumulate_with_dict():
    class SomeMeta(BaseMeta):
        things: Annotated[dict, META_RULES.ACCUMULATE] = Field(default_factory=dict)

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
            abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
            things: Annotated[list, META_RULES.ACCUMULATE] = Field(default_factory=list)
            number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT

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
            abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
            things: Annotated[list, META_RULES.ACCUMULATE] = Field(default_factory=list)
            number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT

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
        abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
        things: Annotated[list[str], META_RULES.ACCUMULATE] = Field(
            default_factory=list
        )
        number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT

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
