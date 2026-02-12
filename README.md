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
```

You would like to define a `_meta` attribute on the classes to store some miscellaneous configuration data.

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
from pydantic_meta_kit import BaseMeta, META_RULES, INHERIT_VALUE

class MyMeta(BaseMeta):
    abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
    things: Annotated[list[str], META_RULES.ACCUMULATE] = Field(
        default_factory=list
    )
    number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT
```

Then, inherit from `WithMeta` generic, i.e. `WithMeta[<YourMetaClass>]`:

```python
from pydantic import BaseModel

class Root(BaseModel):
    """If you have some Root object doing some other global things, it
    doesn't need to inherit from `WithMeta`!
    """
    pass

class Entity(Root, WithMeta[MyMeta]):
    _meta = MyMeta(abstract=True, things=["a", "b"], number=1)

class Animal(Entity):
    _meta = MyMeta(number=2)

class Cat(Animal):
    _meta = MyMeta(abstract=True, things=["c", "d"])


Entity._meta.abstract == True
Entity._meta.things = ["a", "b"]
Entity._meta.number = 1

Animal._meta.abstract == False # <- Does not inherit; reset to default
Animal._meta.things == ["a", "b"] # <- Inherited from Entity._meta
Animal._meta.number == 2 # <- Value overridden

Cat._meta.abstract == True # <- Explicitly set to True
Cat._meta.things == ["a", "b", "c", "d"] # <- Values accumulated
Cat._meta.number == 2 # <- Inherited from Animal._meta
```

Note that type annotations are `Annotated` with additional `META_RULES` to determine how inheritance will work.

### MetaRules rules

The `META_RULES` enum defines three rules for how inheritance should work.

- `DO_NOT_INHERIT`: The value will be reset to the default, which must be provided.
    - In the above example, `abstract` will be reset to `False` by inheriting classes, unless explicitly set to `True` 
- `ACCUMULATE`: With a `list`, `set`, or `dict`, accumulate (or override in the case of dict) previous values into one big `list`, `set` or `dict`.
- `INHERIT_OR_OVERRIDE`: The default behaviour (use is optional). If a value is not set on an inheriting class, it will use the parent class's value.

The `INHERIT_VALUE` type and `INHERIT_VALUE.AS_DEFAULT` exist to make an argument optional on a child class's `_meta`. Otherwise, Pydantic will demand that you provide a value. i.e.

```python
number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT
```
does not need to be provided in all the subclasses. Whereas just `number: int` will obviously be demanded by Pydantic when you try to initialise a child class's `_meta`.
