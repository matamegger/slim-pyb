from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CtypeFieldType:
    pass

@dataclass(frozen=True)
class NamedCtypeFieldType(CtypeFieldType):
    name: str


@dataclass(frozen=True)
class CtypeFieldTypeArray(CtypeFieldType):
    of: CtypeFieldType
    size: int


@dataclass(frozen=True)
class CtypeFieldPointer(CtypeFieldType):
    of: CtypeFieldType


@dataclass(frozen=True)
class CtypeFieldFunctionPointer(CtypeFieldType):
    return_type: CtypeFieldType
    parameter_types: list[CtypeFieldType]


@dataclass(frozen=True)
class Import:
    path: Optional[str]
    imports: list[str]


@dataclass(frozen=True)
class Element:
    pass


@dataclass(frozen=True)
class CtypeStructField:
    name: str
    type: CtypeFieldType


@dataclass(frozen=True)
class CtypeStruct(Element):
    name: str
    fields: list[CtypeStructField]


@dataclass(frozen=True)
class EnumEntry(Element):
    name: str
    value: int

@dataclass(frozen=True)
class Definition(Element):
    name: str
    for_type: CtypeFieldType

@dataclass(frozen=True)
class Enum(Element):
    name: str
    entries: list[EnumEntry]


@dataclass(frozen=True)
class File:
    name: str
    imports: list[Import]
    elements: list[Element]
