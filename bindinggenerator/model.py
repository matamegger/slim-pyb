from dataclasses import dataclass
from enum import Enum
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
    name: str


@dataclass(frozen=True)
class CtypeStructField:
    name: str
    type: CtypeFieldType


class CtypeContainerType(Enum):
    STRUCT = 1
    UNION = 2


@dataclass(frozen=True)
class CtypeContainerElement(Element):
    container_type: CtypeContainerType


@dataclass(frozen=True)
class CtypeContainerDefinition(CtypeContainerElement):
    pass


@dataclass(frozen=True)
class CtypeContainerDeclaration(CtypeContainerElement):
    field: list[CtypeStructField]


@dataclass(frozen=True)
class CtypeContainer(CtypeContainerDeclaration, CtypeContainerDefinition): pass


@dataclass(frozen=True)
class CtypeStructDefinition(Element):
    pass


@dataclass(frozen=True)
class CtypeStructDeclaration(Element):
    fields: list[CtypeStructField]


@dataclass(frozen=True)
class CtypeStruct(CtypeStructDefinition, CtypeStructDeclaration):
    pass


@dataclass(frozen=True)
class CtypeUnionDefinition(Element):
    pass


@dataclass(frozen=True)
class CtypeUnionDeclaration(Element):
    fields: list[CtypeStructField]


@dataclass(frozen=True)
class CtypeUnion(CtypeUnionDefinition, CtypeUnionDeclaration):
    pass


@dataclass(frozen=True)
class EnumEntry(Element):
    value: int


@dataclass(frozen=True)
class Definition(Element):
    for_type: CtypeFieldType


@dataclass(frozen=True)
class Enum(Element):
    name: str
    entries: list[EnumEntry]


@dataclass(frozen=True)
class BindingFile:
    name: str
    imports: list[Import]
    elements: list[Element]


@dataclass(frozen=True)
class Parameter:
    name: str
    type: CtypeFieldType


@dataclass(frozen=True)
class SystemMethod:
    name: str
    return_type: CtypeFieldType
    parameter: list[Parameter]
    name_in_library: str


@dataclass(frozen=True)
class SystemField:
    name: str
    type: CtypeFieldType
    name_in_library: str


@dataclass(frozen=True)
class System:
    name: str
    binary_basename: str
    imports: list[Import]
    methods: list[SystemMethod]
    fields: list[SystemField]
    bindingFiles: list[BindingFile]


def get_base_types(typ: CtypeFieldType) -> list[CtypeFieldType]:
    if isinstance(typ, NamedCtypeFieldType):
        return [typ]
    elif isinstance(typ, CtypeFieldTypeArray) or isinstance(typ, CtypeFieldPointer):
        return get_base_types(typ.of)
    elif isinstance(typ, CtypeFieldFunctionPointer):
        types = [typ for parameter_type in typ.parameter_types for typ in get_base_types(parameter_type)]
        types += get_base_types(typ.return_type)
        return types
    else:
        raise Exception("Unsupported type")


def get_base_type_names(typ: CtypeFieldType) -> list[str]:
    base_types = get_base_types(typ)
    base_type_names: list[str] = []
    for base_type in base_types:
        if isinstance(base_type, NamedCtypeFieldType):
            base_type_names.append(base_type.name)
        else:
            raise Exception("Unsupported type")

    return base_type_names
