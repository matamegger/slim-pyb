from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Type:
    constant: bool


@dataclass(frozen=True)
class NamedType(Type):
    name: str


@dataclass(frozen=True)
class Pointer(Type):
    of: Type


@dataclass(frozen=True)
class Array(Type):
    of: Type
    size: int


@dataclass(frozen=True)
class InlineDeclaration(Type):
    name: str


@dataclass(frozen=True)
class InlineStructType(InlineDeclaration):
    pass


@dataclass(frozen=True)
class InlineUnionType(InlineDeclaration):
    pass


@dataclass(frozen=True)
class FunctionParameter:
    name: Optional[str]
    type: Type


@dataclass(frozen=True)
class FunctionType(Type):
    params: list[FunctionParameter]
    return_type: Type
