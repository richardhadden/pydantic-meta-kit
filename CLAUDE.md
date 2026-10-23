# CLAUDE.md

## What this project is

`pydantic-meta-kit` is a small library (Python >=3.14, Pydantic >=2.12) for putting a Django-style `_meta` object on a Pydantic class hierarchy. Subclasses get a correctly merged `_meta` automatically, without having to declare one. Each field in the meta class carries a rule that says how it behaves under inheritance. See `README.md` for user-facing examples.

Public API (`pydantic_meta_kit/__init__.py`): `BaseMeta`, `MetaRules`, `InheritValue`, `WithMeta`. Everything lives in `pydantic_meta_kit/meta.py`. `exceptions.py` has `PydanticMetaKitException`.

## Intended behaviour

### `MetaRules` (put in `Annotated[...]` on a `BaseMeta` field)
- `INHERIT_OR_OVERRIDE` (default, no annotation needed): use the child's value if it was set explicitly, otherwise the parent's.
- `DO_NOT_INHERIT`: the child never takes the parent's value. It gets its own explicit value or the field default. A default or `default_factory` is required.
- `ACCUMULATE`: values from parent and child are combined (list: concatenated, set: unioned, dict: child keys override parent keys). The field must be iterable and have a `default_factory`.

### `InheritValue.AS_DEFAULT`
A singleton sentinel for fields typed `T | InheritValue`. It lets a child's `_meta` omit the field, and Pydantic won't demand a value. If no class anywhere in the hierarchy ever supplies a real value, class creation must raise.

### `BaseMeta`
- Frozen Pydantic model with `arbitrary_types_allowed`.
- Records which fields were passed explicitly in `__init__` (`_initialised_directly`). This is how "set explicitly" is told apart from "defaulted".
- `__pydantic_init_subclass__` validates the rule annotations when a meta class is defined, and raises `PydanticMetaKitException` for a `DO_NOT_INHERIT` field with no default or an `ACCUMULATE` field that is not iterable.
- `parent & child` (`__and__`) is the merge operation. It returns a new instance of the same type. `child` may be `None`, which means "no own meta: inherit everything inheritable and reset the rest". Merging different meta types raises.

### Custom attribute key
`BaseMeta.meta_key` (default `"_meta"`, must be an identifier starting with `_`) names the class attribute the meta lives on. Several `WithMeta[...]` mixins with different keys can be combined on one class; two metas with the same key on one class raise. Pydantic turns an unannotated `_foo = X` into a private attribute, so `WithMeta` moves such meta objects back to plain class attributes. A `ClassVar` annotation is still nicer for editors.

### `WithMeta[MetaClass]`
Mixin used as `class Entity(Root, WithMeta[MyMeta])`. In `__pydantic_init_subclass__`, every subclass ends up with a resolved class attribute (per key, below shown for `_meta`):
- No own `_meta` and no parent `_meta`: try `MetaClass()` with all defaults, otherwise raise.
- No own `_meta`, parent has one: `parent._meta & None`.
- Own `_meta` and parent has one: `parent._meta & own`.
- Own `_meta` and no parent: use it as is.
- An own `_meta` of the wrong type raises. After resolution, any field still holding `InheritValue` raises.

## Layout and commands

- `pydantic_meta_kit/meta.py`: all logic.
- `tests/test_meta.py`: pytest suite covering the merge rules, initialisation errors and the class-level behaviour.
- Dependencies are managed with uv (`uv.lock`). Run the tests with `uv run pytest`.

## Fixed bugs (keep covered by tests)

- `_meta_class` was global state on `WithMeta`; now per-class `_meta_classes` (key -> meta class).
- Merging used the farthest ancestor's meta (`[-1]`), dropping intermediate overrides; now the nearest parent's (already merged).
- `dict` accumulation raised on overlapping keys; accumulated values were shared between metas (now copied).
- `_get_field_rule` choked on other `Annotated` metadata; explicit `InheritValue` on a child now counts as "not set".
- Merging used `model_dump()`, turning nested models into dicts; now reads attributes. "Explicitly set" now uses `model_fields_set` (works with `model_validate`).
- Aliased meta fields were never merged (merged values are keyed by field name but the model only accepted aliases); `BaseMeta` now sets `validate_by_name`.
- The `WithMeta` docstring example had an impossible MRO (`BaseModel` listed before `WithMeta[...]`; `WithMeta` is already a `BaseModel`). List `WithMeta[...]` before any `BaseModel`-only base.
- Parametrised generics (`Entity[int]`) keep the origin's meta instead of resetting `DO_NOT_INHERIT` fields.

## Still open

- Not yet supported (README "Would be nice"): non-Pydantic classes, and custom callable merge rules.

## Working conventions

- Keep the library small and dependency-light (Pydantic only).
- Any behaviour change needs a test in `tests/test_meta.py`. Add one that reproduces the bug before fixing it.
- Keep the README in sync with behaviour changes.
- Match the existing style: modern generics syntax (`class X[T]`), type hints everywhere, and docstrings on public classes.
