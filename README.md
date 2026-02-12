# Pydantic Meta Kit

A handy library to define "meta" objects on your Pydantic classes and have children of the Pydantic class inherit the right values (according to some rules)

## Why? If:

You have some Pydantic classes:

```python
class Root(BaseModel):
    pass

class Entity(Root):
    pass

class Animal(Entity):
    pass

class Cat(Animal):
    pass

class Ragdoll(Cat):
    pass
```

And you would like to define a `_meta` class attribute on the classes to store and access some miscellaneous configuration data.

You would also like to not have to write a `_meta` attribute on every single class in your hierarchy.

But you would like to *have* `_meta` on every class, and just be able to override a particular option.

And some options shouldn't inherit. (Like the `Meta` class in Django — it keeps all the parent values, but somehow forgets about `Abstract`.) 

And _some_ options (options that are lists) should accumulate.

And, you don't want to have to write loads of logic...

## Then: this is a handy toolkit for defining your own `_meta` objects on your classes

First, define your Meta class:

```python
from typing import Annotated
from pydantic import Field
from pydantic_meta_kit import BaseMeta, MetaRules, InheritValue

class MyMeta(BaseMeta):
    abstract: Annotated[bool, MetaRules.DO_NOT_INHERIT] = False
    things: Annotated[list[str], MetaRules.ACCUMULATE] = Field(default_factory=list)
    number: int | InheritValue = InheritValue.AS_DEFAULT
```

Then, inherit have your top level class inherit from the `WithMeta` generic, i.e. `WithMeta[<YourMetaClass>]`:

```python
from typing import ClassVar

from pydantic import BaseModel
from pydantic_meta_kit import WithMeta

class Root(BaseModel):
    """If you have some Root object doing some other global things, it
    doesn't need to inherit from `WithMeta`!
    """
    pass

class Entity(Root, WithMeta[MyMeta]):
    _meta: ClassVar[MyMeta] = MyMeta(abstract=True, things=["a", "b"], number=1)

class Animal(Entity):
    pass # <- No need to define _meta here

class Cat(Animal):
    _meta = MyMeta(abstract=True, number=2)

class Ragdoll(Cat):
    _meta = MyMeta(things=["c", "d"])




Entity._meta.abstract is True
Entity._meta.things = ["a", "b"]
Entity._meta.number = 1

Animal._meta.abstract is False      # <- Does not inherit; reset to default
Animal._meta.things == ["a", "b"]   # <- Inherited from Entity.things
Animal._meta.number == 1            # <- Inherited from Entity.number

Cat._meta.abstract is True          # <- Explicitly set to True
Cat._meta.things == ["a", "b"]      # <- Inherited from Entity.things
Cat._meta.number == 2               # <- Explicitly set to 2

Ragdoll._meta.abstract is False     # <- Does not inherit; reset to default
Ragdoll._meta.things == ["a", "b", "c", "d"] 
                            # ^- Accumulated from Entity.things + Ragdoll.things
Ragdoll._meta.number == 2          # <- Inherited from Cat.number
```
n.b. `Entity._meta` is annotated with `ClassVar[MyMeta]`. This is not strictly necessary (some other type assigned to `_meta` in a subclass will be caught at runtime) but this provides nice validation in your editor.

Type annotations are `Annotated` with additional `MetaRules` to determine how inheritance will work.

### `MetaRules` rules

The `MetaRules` enum defines three rules for how inheritance should work.

- `DO_NOT_INHERIT`: The value will be reset to the default, which must be provided.
    - In the above example, `abstract` will be reset to `False` by inheriting classes, unless explicitly set to `True` 
- `ACCUMULATE`: With a `list`, `set`, or `dict`, accumulate (or override in the case of dict) previous values into one big `list`, `set` or `dict`.
    - A `default_factory` must be provided, e.g. `Field(default_factory=list)`
- `INHERIT_OR_OVERRIDE`: The default behaviour (use is optional). If a value is not set on an inheriting class, it will use the parent class's value.

The `InheritValue` type and `InheritValue.AS_DEFAULT` exist to make an argument optional on a child class's `_meta`. Otherwise, Pydantic will demand that you provide a value. i.e.

```python
number: int | InheritValue = InheritValue.AS_DEFAULT
```
does not need to be provided in all the subclasses. Whereas just `number: int` will obviously be demanded by Pydantic when you try to initialise a child class's `_meta`, even if you don't need to define it again.


### Would be nice to...

- Have some custom `MetaRule`-type options, passed as a function...