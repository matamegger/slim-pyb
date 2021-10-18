from astparser.types import Type, NamedType, Pointer, StructType, Array


def get_base_type_name(typ: Type) -> str:
    if isinstance(typ, NamedType):
        return typ.name
    elif isinstance(typ, Pointer):
        return get_base_type_name(typ)
    elif isinstance(typ, StructType):
        return typ.name
    elif isinstance(typ, Array):
        return get_base_type_name(typ.of)
    else:
        raise Exception("Unhandled case")
