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

But you would like to use `_meta` on every class, and just be able to override a particular option.

And some options shouldn't inherit. (Like the `Meta` class in Django — it keeps all the parent values, but somehow forgets about `Abstract`.) 

And _some_ options (options that are lists) should accumulate.


## Then: this is a handy toolkit for defining your own `_meta` objects on your classes

First, define your Meta class:

```python
from pydantic_meta_kit import BaseMeta, META_RULES, INHERIT_VALUE

class MyMeta(BaseMeta):
    abstract: Annotated[bool, META_RULES.DO_NOT_INHERIT] = False
    things: Annotated[list[str], META_RULES.ACCUMULATE] = Field(
        default_factory=list
    )
    number: int | INHERIT_VALUE = INHERIT_VALUE.AS_DEFAULT
```