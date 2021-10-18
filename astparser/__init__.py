from astparser.types import Type, NamedType, Pointer, StructType, Array, FunctionType


def get_base_type(typ: Type) -> Type:
    if isinstance(typ, NamedType):
        return typ
    elif isinstance(typ, Pointer):
        return get_base_type(typ.of)
    elif isinstance(typ, Array):
        return get_base_type(typ.of)
    elif isinstance(typ, StructType):
        return typ
    elif isinstance(typ, FunctionType):
        return typ
    else:
        raise Exception(f"Unhandled case {typ}")


def get_base_type_name(typ: Type) -> str:
    base_type = get_base_type(typ)
    if isinstance(base_type, NamedType) or isinstance(base_type, StructType):
        return base_type.name
    raise Exception("Can not get base type name")
