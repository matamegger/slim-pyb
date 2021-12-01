from dataclasses import dataclass
from typing import Optional

from astparser.types import Type


@dataclass(frozen=True)
class Property:
    name: str
    type: Type


@dataclass(frozen=True)
class Container:
    name: Optional[str]
    properties: list[Property]
    inner_containers: list['Container']


@dataclass(frozen=True)
class Struct(Container):
    pass


@dataclass(frozen=True)
class Union(Container):
    pass


@dataclass(frozen=True)
class EnumEntry:
    name: str
    value: int


@dataclass(frozen=True)
class Enum:
    name: Optional[str]
    entries: list[EnumEntry]


@dataclass(frozen=True)
class TypeDefinition:
    name: str
    for_type: Type


@dataclass(frozen=True)
class Field:
    name: str
    type: Type


@dataclass(frozen=True)
class MethodParameter:
    name: str
    type: Type


@dataclass(frozen=True)
class Method:
    name: str
    parameter: list[MethodParameter]
    return_type: Type


@dataclass(frozen=True)
class Module:
    type_definitions: list[TypeDefinition]
    container: list[Container]
    enums: list[Enum]
    fields: list[Field]
    methods: list[Method]
