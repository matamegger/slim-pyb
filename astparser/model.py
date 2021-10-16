from dataclasses import dataclass
from typing import Optional

from astparser.types import Type


@dataclass(frozen=True)
class StructProperty:
    name: str
    type: Type


@dataclass(frozen=True)
class Struct:
    name: Optional[str]
    properties: list[StructProperty]
    inner_structs: list['Struct']


@dataclass(frozen=True)
class EnumEntry:
    name: str
    value: Optional[int]


@dataclass(frozen=True)
class Enum:
    name: Optional[str]
    entries: list[EnumEntry]


@dataclass(frozen=True)
class TypeDefinition:
    name: str
    for_type: Type
