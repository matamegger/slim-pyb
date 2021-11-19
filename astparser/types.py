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
class StructType(Type):
    name: str


@dataclass(frozen=True)
class UnionType(Type):
    name: str


@dataclass(frozen=True)
class FunctionParameter:
    name: Optional[str]
    type: Type


@dataclass(frozen=True)
class FunctionType(Type):
    params: list[FunctionParameter]
    return_type: Type
