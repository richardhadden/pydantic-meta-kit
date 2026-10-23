import inspect
from collections.abc import Iterable
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError
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


def _get_field_rule(field: FieldInfo) -> MetaRules:
    """Extracts the correct `META_RULE` from a field definition"""
    for item in field.metadata:
        if isinstance(item, MetaRules):
            return item
    return MetaRules.INHERIT_OR_OVERRIDE


class _InheritValueMetaclass(type):
    """Metaclass for InheritValue, adding a property to the class that
    returns a singleton instance of itself, so that this works correctly:

    `number: int | InheritValue = InheritValue.AS_DEFAULT`
    """

    @property
    def AS_DEFAULT(cls):
        """Use `InheritValue` as default value"""
        if not hasattr(cls, "_singleton_instance"):
            cls._singleton_instance = cls()
        return cls._singleton_instance


class InheritValue(metaclass=_InheritValueMetaclass):
    """Type marker for field that does not need to be declared on a `_meta` object,
    but must be inherited from a parent's `_meta`.

    `InheritValue.AS_DEFAULT` must be used as the default value.

    Usage:

    ```
    class SomeMeta(BaseMeta):
        number: int | InheritValue = InheritValue.AS_DEFAULT
    ```
    """

    pass


def _merge_fields[T: list | set | dict](
    field_type: type[T], left: T, right: T | None
) -> T:
    """Utility to merge lists, sets, dicts correctly"""
    if right is None:
        return field_type(left)

    elif issubclass(field_type, dict):
        return field_type({**left, **right})  # type: ignore
    else:
        return field_type([*left, *right])  # type: ignore


def _generate_initialisation_error_message(
    cls_name: str, do_not_inherits_invalid: list[str], accumulations_invalid: list[str]
) -> str:
    """Utility to generate nice initialisation error message"""

    error_msg = f"Error with <{cls_name}>: "

    if do_not_inherits_invalid:
        error_msg += (
            f"field{'s' if len(do_not_inherits_invalid) > 1 else ''} {', '.join(f"'{f}'" for f in do_not_inherits_invalid)} "
            f"{'are' if len(do_not_inherits_invalid) > 1 else 'is'} annotated with "
            f"MetaRules.DO_NOT_INHERIT but do{'' if len(do_not_inherits_invalid) > 1 else 'es'} not provide a default value "
            "or default_factory"
        )
    if do_not_inherits_invalid and accumulations_invalid:
        error_msg += "; "
    if accumulations_invalid:
        error_msg += (
            f"field{'s' if len(accumulations_invalid) > 1 else ''} {', '.join(f"'{f}'" for f in accumulations_invalid)} "
            f"{'are' if len(accumulations_invalid) > 1 else 'is'} annotated with "
            f"MetaRules.ACCUMULATE but {'are' if len(accumulations_invalid) > 1 else 'is'} not of type Iterable"
        )
    return error_msg


class BaseMeta(BaseModel):
    """
    Class to be inherited for defining your own `_meta` objects.

    Usage:

    ```
    class SomeMeta(BaseMeta):
        abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
        things: Annotated[list[str], MetaRules.ACCUMULATE] = Field(
            default_factory=list
        )
        number: int | InheritValue = InheritValue.AS_DEFAULT
    ```
    """

    # `validate_by_name` is needed so that merged values (keyed by field name) are
    # accepted for fields that declare an alias
    model_config = {
        "arbitrary_types_allowed": True,
        "frozen": True,
        "validate_by_name": True,
        "validate_by_alias": True,
    }

    meta_key: ClassVar[str] = "_meta"
    """Name of the class attribute that instances of this meta class are attached
    to by `WithMeta`. Override in a subclass to allow several different metas on
    the same class, e.g. `meta_key = "_interface_meta"`."""

    @property
    def _initialised_directly(self) -> set[str]:
        """Names of fields that were explicitly provided on instantiation"""
        return set(self.model_fields_set)

    @classmethod
    def __pydantic_init_subclass__(cls, **_):
        if not (cls.meta_key.isidentifier() and cls.meta_key.startswith("_")):
            raise PydanticMetaKitException(
                f"Error with <{cls.__name__}>: meta_key '{cls.meta_key}' must be a valid "
                "identifier starting with an underscore"
            )
        cls.run_initialisation_checks()

    @classmethod
    def run_initialisation_checks(cls):
        do_not_inherits_invalid: list[str] = []
        accumulations_invalid: list[str] = []
        for field_name, model_field in cls.model_fields.items():
            # Checks that all fields that are DO_NOT_INHERIT provide a default value
            # (`get_default` runs a `default_factory`; `default` alone is undefined when
            # there is one)
            if _get_field_rule(model_field) == MetaRules.DO_NOT_INHERIT and isinstance(
                model_field.get_default(call_default_factory=True),
                PydanticUndefinedType,
            ):
                do_not_inherits_invalid.append(field_name)

            # Checks that fields that are ACCUMULATE are of type Iterable
            if _get_field_rule(model_field) == MetaRules.ACCUMULATE and (
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

    def __and__[T: BaseMeta](self: T, child: T | None) -> T:
        """Merge this (parent) meta with a child meta according to the field rules,
        returning a new meta object. `child` may be `None`, meaning the child
        declares no meta of its own."""

        # Check self and child have same type, for sanity
        if child is not None and type(self) is not type(child):
            raise PydanticMetaKitException(
                "Cannot merge two Meta objects of different types"
            )

        merged_dict: dict[str, Any] = {}

        for field_name, model_field in type(self).model_fields.items():
            field_rule: MetaRules = _get_field_rule(model_field)
            left = getattr(self, field_name)

            # A field counts as set on the child if it was explicitly provided
            # and is not just the `InheritValue` placeholder
            child_has_value = (
                child is not None
                and field_name in child.model_fields_set
                and not isinstance(getattr(child, field_name), InheritValue)
            )
            right = getattr(child, field_name) if child_has_value else None

            # Accumulated fields are combined
            if field_rule == MetaRules.ACCUMULATE:
                merged_dict[field_name] = _merge_fields(
                    field_type=type(model_field.get_default(call_default_factory=True)),
                    left=left,
                    right=right,
                )

            # A field defined explicitly on the child meta object is used
            elif child_has_value:
                merged_dict[field_name] = right

            # A field not defined explicitly and that can inherit, inherits
            elif field_rule != MetaRules.DO_NOT_INHERIT:
                merged_dict[field_name] = left

        # Pile everything into a new meta object and return
        return type(self)(**merged_dict)


class WithMeta[T: BaseMeta](BaseModel):
    """
    Mixin that creates a `_meta` `ClassVar` attribute, of type `BaseMeta`, on a Pydantic `BaseModel` type.

    All subclasses may or may not define their own `_meta` attribute. This class ensures that
    `_meta` attributes on subclasses inherit the correct values from their parent class's `_meta`,
    following the rules defined in your `BaseMeta` class.

    The attribute name is taken from the `meta_key` of the meta class (default `_meta`), and
    several `WithMeta[...]` mixins with different keys may be combined on one class.

    Usage:

    ```
    class MyMeta(BaseMeta):
        abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
        things: Annotated[list[int], MetaRules.ACCUMULATE] = Field(default_factory=list)
        number: int | InheritValue = InheritValue.AS_DEFAULT

    class Entity(WithMeta[MyMeta]):
        _meta = MyMeta(abstract=True, things=[1, 2, 3], number=1)

    class Thing(Entity):
        _meta = MyMeta(number=2, things=[4])
    ```

    `Thing._meta.abstract == False` (not inherited)
    `Thing._meta.number == 2` (overridden)
    `Thing._meta.things == [1, 2, 3, 4]` (accumulated)

    With a custom key:

    ```
    class InterfaceMeta(BaseMeta):
        meta_key = "_interface_meta"
        ...

    class Entity(WithMeta[MyMeta], WithMeta[InterfaceMeta]):
        _interface_meta: ClassVar[InterfaceMeta] = InterfaceMeta(...)  # annotation optional
    ```
    """

    _meta: ClassVar[T]  # type: ignore
    _meta_classes: ClassVar[dict[str, type[BaseMeta]]] = {}
    """Mapping of attribute name -> meta class for every `WithMeta[...]` in the bases"""

    @classmethod
    def __pydantic_init_subclass__(cls, **_) -> None:
        origin = cls.__pydantic_generic_metadata__["origin"]

        # If initialising a `WithMeta[SomeMeta]` parametrisation, just record the meta class
        # on that (generic-alias) class; there is no overriding to do
        if origin is WithMeta:
            args = cls.__pydantic_generic_metadata__["args"]
            if args and isinstance(args[0], type) and issubclass(args[0], BaseMeta):
                cls._meta_classes = {args[0].meta_key: args[0]}
            return

        # Collect the meta classes of all `WithMeta[...]` parametrisations in the bases
        meta_classes: dict[str, type[BaseMeta]] = {}
        for klass in cls.mro()[1:]:
            for key, meta_class in klass.__dict__.get("_meta_classes", {}).items():
                if meta_classes.setdefault(key, meta_class) is not meta_class:
                    raise PydanticMetaKitException(
                        f"<{cls.__name__}>: meta classes {meta_classes[key].__name__} and "
                        f"{meta_class.__name__} both use the key '{key}'"
                    )
        cls._meta_classes = meta_classes

        # A parametrisation of a generic model (`Entity[int]`) is the same class as far as
        # meta is concerned: copy the metas unchanged rather than "inheriting" them
        if origin is not None and issubclass(origin, WithMeta):
            for key in meta_classes:
                setattr(cls, key, getattr(origin, key))
            return

        for key, meta_class in meta_classes.items():
            cls._resolve_meta(key, meta_class)

    @classmethod
    def _resolve_meta(cls, key: str, meta_class: type[BaseMeta]) -> None:

        # Pydantic treats an unannotated `_name = value` as a private attribute; when it
        # holds a meta object, turn it back into an ordinary class attribute
        private = cls.__private_attributes__.get(key)
        if private is not None and key not in cls.__dict__:
            cls.__private_attributes__.pop(key)
            cls.__class_vars__.add(key)
            setattr(cls, key, private.default)

        # Does the class being initialised have its own meta object (rather than inheriting)?
        has_own_meta: bool = key in cls.__dict__
        own_meta = cls.__dict__.get(key)

        if has_own_meta and not isinstance(own_meta, meta_class):
            raise PydanticMetaKitException(
                f"<{cls.__name__}>: {key} attribute must be of type {meta_class.__name__}, not {type(own_meta).__name__}"
            )

        # The nearest parent's meta has already been merged with all of its ancestors
        parent_meta: BaseMeta | None = None
        for parent in cls.mro()[1:]:
            if isinstance(candidate := parent.__dict__.get(key), BaseMeta):
                parent_meta = candidate
                break

        if parent_meta is None:
            # If no meta is found anywhere, see if it can be instantiated just using
            # defaults, otherwise raise an error
            if not has_own_meta:
                try:
                    setattr(cls, key, meta_class())
                except ValidationError:
                    raise PydanticMetaKitException(
                        f"<{cls.__name__}>: a {key} field with instance of type {meta_class.__name__} must "
                        "be declared somewhere in the model hierarchy, or have all-default arguments"
                    )
        else:
            # Merge with the parent's meta; with no own meta this resets non-heritable fields
            setattr(cls, key, parent_meta & own_meta)

        # Check there are no InheritValue fields that somewhere in the chain
        # have not actually been able to inherit a value
        final_meta: BaseMeta = getattr(cls, key)
        for field_name in type(final_meta).model_fields:
            if isinstance(getattr(final_meta, field_name), InheritValue):
                raise PydanticMetaKitException(
                    f"<{cls.__name__}>: field '{field_name}' of {key} instance can inherit a value, "
                    "but this is never declared in the object hierarchy"
                )
