import inspect
from collections.abc import Iterable
from enum import Enum
from typing import Any, ClassVar, cast

from pydantic import BaseModel, PrivateAttr, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefinedType

from pydantic_meta_kit.exceptions import PydanticMetaKitException


class MetaRules(Enum):
    DO_NOT_INHERIT = 0
    """Do not inherit this value; instead reset to default when inherited"""
    ACCUMULATE = 1
    """Accumulate values from list, set or dict through inheritance"""
    INHERIT_OR_OVERRIDE = 2
    """Follow normal inheritance procedure"""


def get_field_rule(field: FieldInfo) -> MetaRules:
    """Extracts the correct `META_RULE` from a field definition"""
    if field.metadata:
        return field.metadata[0]
    else:
        return MetaRules.INHERIT_OR_OVERRIDE


class InheritValueMetaclass(type):
    """Metaclass for INHERIT_VALUE, adding a property to the class that
    returns a singleton instance of itself, so that this works correctly:

    `number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT`
    """

    @property
    def AS_DEFAULT(cls):
        """Use `INHERIT_VALUE` as default value"""
        if not hasattr(cls, "_singleton_instance"):
            cls._singleton_instance = cls()
        return cls._singleton_instance


class InheritValue(metaclass=InheritValueMetaclass):
    """Type marker for field that does not need to be declared on a `_meta` object,
    but must be inherited from a parent's `_meta`.

    `INHERIT_VALUE.AS_DEFAULT` must be used as the default value.

    Usage:

    ```
    class SomeMeta(BaseMeta):
        number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT
    ```
    """

    pass


def _merge_fields[T: list | set | dict](
    field_type: type[T], left: T, right: T | None
) -> T:
    """Utility to merge lists, sets, dicts correctly"""
    if right is None:
        return left

    elif field_type is dict and type(left) is dict and type(right) is dict:
        return field_type(**left, **right)
    else:
        return field_type([*left, *right])


def _generate_initialisation_error_message(
    cls_name: str, do_not_inherits_invalid: list[str], accumulations_invalid: list[str]
) -> str:
    """Utility to generate nice initialisation error message"""

    error_msg = f"Error with <{cls_name}>: "

    if do_not_inherits_invalid:
        error_msg += (
            f"field{'s' if len(do_not_inherits_invalid) > 1 else ''} {', '.join(f"'{f}'" for f in do_not_inherits_invalid)} "
            f"{'are' if len(do_not_inherits_invalid) > 1 else 'is'} annotated with "
            f"META_RULES.DO_NOT_INHERIT but do{'' if len(do_not_inherits_invalid) > 1 else 'es'} not provide a default value "
            "or default_factory"
        )
    if do_not_inherits_invalid and accumulations_invalid:
        error_msg += "; "
    if accumulations_invalid:
        error_msg += (
            f"field{'s' if len(accumulations_invalid) > 1 else ''} {', '.join(f"'{f}'" for f in accumulations_invalid)} "
            f"{'are' if len(accumulations_invalid) > 1 else 'is'} annotated with "
            f"META_RULES.ACCUMULATE but {'are' if len(accumulations_invalid) > 1 else 'is'} not of type Iterable"
        )
    return error_msg


class BaseMeta(BaseModel):
    """
    Class to be inherited for defining your own `_meta` objects.

    Usage:

    ```
    class SomeMeta(BaseMeta):
        abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
        things: Annotated[list[str], META_RULES.ACCUMULATE] = Field(
            default_factory=list
        )
        number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT
    ```
    """

    model_config = {"arbitrary_types_allowed": True, "frozen": True}

    _initialised_directly: set[str] = PrivateAttr(default_factory=set)

    @classmethod
    def __pydantic_init_subclass__(cls, **_):
        cls.run_initialisation_checks()

    @classmethod
    def run_initialisation_checks(cls):
        do_not_inherits_invalid: list[str] = []
        accumulations_invalid: list[str] = []
        for field_name, model_field in cls.model_fields.items():
            # Checks that all fields that are DO_NOT_INHERIT provide a default value
            if get_field_rule(model_field) == MetaRules.DO_NOT_INHERIT and (
                isinstance(model_field.default, PydanticUndefinedType)
                or isinstance(
                    model_field.get_default(call_default_factory=True),
                    PydanticUndefinedType,
                )
            ):
                do_not_inherits_invalid.append(field_name)

            # Checks that fields that are ACCUMULATE are of type Iterable
            if get_field_rule(model_field) == MetaRules.ACCUMULATE and (
                (
                    inspect.isclass(model_field.annotation)
                    and not issubclass(model_field.annotation, Iterable)
                )
                or not isinstance(
                    model_field.get_default(call_default_factory=True), Iterable
                )
            ):
                accumulations_invalid.append(field_name)

        if do_not_inherits_invalid or accumulations_invalid:
            raise PydanticMetaKitException(
                _generate_initialisation_error_message(
                    cls.__name__, do_not_inherits_invalid, accumulations_invalid
                )
            )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Keep track of whether keys have been explicitly provided in instantiation
        self._initialised_directly.update(kwargs.keys())

    def __and__[T: BaseMeta](self: T, child: T | None) -> T:

        # Check self and child have same time, for sanity
        if child and type(self) is not type(child):
            raise PydanticMetaKitException(
                "Cannot merge two Meta objects of different types"
            )

        left_dict: dict[str, Any] = self.model_dump()
        if child is None:
            right_dict = {}
        else:
            right_dict: dict[str, Any] = child.model_dump()

        merged_dict: dict[str, Any] = {}

        for field_name, model_field in self.__class__.model_fields.items():
            field_rule: MetaRules = get_field_rule(model_field)

            # If field should be accumulated, use the _merge_field function
            # to do it
            if field_rule == MetaRules.ACCUMULATE:
                merged_dict[field_name] = _merge_fields(
                    field_type=type(model_field.get_default(call_default_factory=True)),
                    left=left_dict[field_name],
                    right=right_dict.get(field_name, None),
                )

            # A field defined explicitly on a meta object should be used
            elif child and field_name in child._initialised_directly:
                merged_dict[field_name] = right_dict[field_name]

            # A field not defined explicitly and that can inherit
            # should inherit
            elif (
                not child or field_name not in child._initialised_directly
            ) and field_rule != MetaRules.DO_NOT_INHERIT:
                merged_dict[field_name] = left_dict[field_name]

        # Pile everything into a new meta object and return
        return self.__class__(**merged_dict)


class WithMeta[T: BaseMeta](BaseModel):
    """
    Mixin that creates a `_meta` `ClassVar` attribute, of type `BaseMeta`, on a Pydantic `BaseModel` type.

    All subclasses may or may not define their own `_meta` attribute. This class ensures that
    `_meta` attributes on subclasses inherit the correct values from their parent class's `_meta`,
    following the rules defined in your `BaseMeta` class.

    Usage:

    ```
    class MyMeta(BaseMeta):
        abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
        things: Annotated[list[int], META_RULES.ACCUMULATE] = Field(default_factory=list)
        number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT

    class Entity(BaseModel, WithMeta[MyMeta]):
        _meta = MyMeta(abstract=True, things=[1, 2, 3], number=1)

    class Thing(Entity):
        _meta = MyMeta(number=2, things=[4])
    ```

    `Thing._meta.abtract == False` (not inherited)
    `Thing._meta.number == 2` (overridden)
    `Thing._meta.things == [1, 2, 3, 4]` (accumulated)
    """

    _meta: ClassVar[T]  # type: ignore
    _meta_class: ClassVar[type[T]]  # type: ignore

    @classmethod
    def __pydantic_init_subclass__(cls, **_) -> None:

        # Is the (sub)class being initialised *this* class?
        initialising_class_is_this = (
            cls.__pydantic_generic_metadata__["origin"] is __class__  # type: ignore
        )

        # If initialising *this* class, set the type of BaseMeta for the object;
        # Note that actualising a the generic WithMeta[T] with any actual BaseMeta class
        # means that these are in fact two classes, and there is no overriding
        if initialising_class_is_this:
            __class__._meta_class = cls.__pydantic_generic_metadata__["args"][0]  # type: ignore

        if initialising_class_is_this:
            return

        # Does the class being initialised have its own "_meta" object (rather than inheriting)?
        has_own_meta: bool = "_meta" in cls.__dict__

        # Extract the meta_class that we are going to use
        meta_class: type[BaseMeta] = cast(type[BaseMeta], cls._meta_class)

        if has_own_meta and not isinstance(cls.__dict__["_meta"], meta_class):
            raise PydanticMetaKitException(
                f"<{cls.__name__}>: _meta attribute must be of type {meta_class.__name__}, not {type(cls.__dict__['_meta']).__name__}"
            )

        # Get a list of parent classes for cls
        parent_classes: list[type] = []
        for c in cls.mro():
            if c is not cls:
                parent_classes.append(c)

        # Get the meta classes for parent classes
        parents_metas = []
        for parent in parent_classes:
            if (parent_meta := parent.__dict__.get("_meta"), None) and isinstance(
                parent_meta, BaseMeta
            ):
                parents_metas.append(parent_meta)

        # If no _meta is found anywhere, see if it can be instantiated just using
        # defaults, otherwise raise an error
        if not has_own_meta and not parents_metas:
            try:
                cls._meta = meta_class()  # type: ignore

            except ValidationError:
                raise PydanticMetaKitException(
                    f"<{cls.__name__}>: a _meta field with instance of type {meta_class.__name__} must "
                    "be declared somewhere in the model hierarchy, or have all-default arguments"
                )

        # If no _meta on cls, but parent meta, merge last parent meta with None to reset
        # non-heritable defaults
        elif not has_own_meta and parents_metas:
            cls._meta = parents_metas[-1] & None

        # If cls has its own meta, merge the fields from the parent meta that
        # are not on this cls's meta
        elif has_own_meta and parents_metas:
            cls._meta = parents_metas[-1] & cls.__dict__["_meta"]

        # We're good because it does!
        elif has_own_meta:
            pass

        # Check there are no INHERIT_VALUE fields that somewhere in the chain
        # have not actually been able to inherit a value
        for k, v in cls._meta.model_dump().items():
            if isinstance(v, InheritValue):
                raise PydanticMetaKitException(
                    f"<{cls.__name__}>: field '{k}' of _meta instance can inherit a value, "
                    "but this is never declared in the object hierarchy"
                )
