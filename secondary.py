import os.path
import sys
from dataclasses import dataclass, field, replace
from typing import Optional

from pycparser import c_ast, parse_file
from pycparser.c_ast import FuncDecl, Node, Decl, TypeDecl, IdentifierType, Typename, PtrDecl, ArrayDecl, \
    Typedef, Constant

from pybindingwriter import Module, ModuleField, ModuleFunction

input_file = os.path.expanduser(sys.argv[1])
ast = parse_file(input_file,
                 use_cpp=True,
                 cpp_path="clang",
                 cpp_args=['-E', '-Ifake_libc_include', '-D_Atomic(x)=x', '-D_Bool=int', '-D__extension__=',
                           '-U__STDC__'])


# print(type(ast.ext[0].coord))


@dataclass(frozen=True)
class Type:
    name: str
    constant: bool


@dataclass(frozen=True)
class VoidType(Type):
    name: str = field(init=False, default="void")
    constant: bool = field(init=False, default=False)


@dataclass(frozen=True)
class Pointer(Type):
    name: str = field(init=False, default="Pointer")
    type: Type


@dataclass(frozen=True)
class Array(Type):
    name: str = field(init=False, default="Array")
    constant: bool = field(init=False, default=False)
    type: Type
    size: int


@dataclass(frozen=True)
class Alias(Type):
    alias: Type
    constant: bool = field(init=False, default=False)


@dataclass
class Field:
    name: str
    type: Type


@dataclass(frozen=True)
class Struct(Type):
    fields: list[Field]


@dataclass(frozen=True)
class EnumEntry:
    name: str
    value: Optional[int]


@dataclass(frozen=True)
class Enum(Type):
    entries: list[EnumEntry]


@dataclass
class Method:
    name: str
    returnType: Type
    # we do not handle arguments, just keep track if we would actually need them
    hasArguments: bool


@dataclass
class ModelStructure:
    fields: list[Field]
    methods: list[Method]


def parse_enum(ast_enum: c_ast.Enum, declaration_name: Optional[str], is_constant: bool) -> Enum:
    entries: list[EnumEntry] = []
    for entry in ast_enum.values.enumerators:
        value = None
        if isinstance(entry.value, Constant):
            value = entry.value.value
        elif entry.value is None:
            pass
        else:
            raise Exception("Unexpected enum value")
        entries.append(EnumEntry(name=entry.name, value=value))

    name = ast_enum.name
    if name is None:
        name = declaration_name
    if name is None: raise Exception("No name for enum")

    return Enum(
        name=name,
        entries=entries,
        constant=is_constant
    )


def parse_struct(ast_struct: c_ast.Struct, declaration_name: Optional[str], is_constant: bool) -> Optional[Struct]:
    if ast_struct.decls is None:
        return None
    fields: list[Field] = []
    for declaration in ast_struct.decls:
        fields.append(Field(name=declaration.name, type=parse_type(declaration.type)))

    name = ast_struct.name
    if name is None:
        name = declaration_name
    if name is None: raise Exception("No name for struct")

    return Struct(
        name=name,
        fields=fields,
        constant=is_constant
    )


def parse_type(node: Node) -> Optional[Type]:
    if isinstance(node, FuncDecl):
        return parse_type(node.type)
    elif isinstance(node, TypeDecl):
        if isinstance(node.type, IdentifierType):
            type_name = ' '.join(node.type.names)
            if type_name == "void":
                return VoidType()
            else:
                return Type(type_name, 'const' in node.quals)
        elif isinstance(node.type, c_ast.Struct):
            struct = parse_struct(node.type, node.declname, 'const' in node.quals)
            if struct is None:
                return Type(node.type.name, 'const' in node.quals)
            else:
                return struct
        elif isinstance(node.type, c_ast.Enum):
            return parse_enum(node.type, node.declname, 'const' in node.quals)
        else:
            raise Exception(f"Unexpected subtype of TypeDecl {type(node.type)}{node.type}")
    elif isinstance(node, PtrDecl):
        return Pointer(type=parse_type(node.type), constant='const' in node.quals)
    elif isinstance(node, ArrayDecl):
        return Array(
            size=node.dim.value,
            type=parse_type(node.type)
        )
    elif isinstance(node, Typename):
        return parse_type(node.type)
    elif isinstance(node, c_ast.Struct):
        return parse_struct(node, None, False)
    else:
        raise Exception(f"Unhandled state when resolving type: {type(node)}:{node}")


def get_function_arguments(function: FuncDecl) -> list[Field]:
    arguments: list[Field] = []
    for arg in function.args.params:
        type = parse_type(arg)
        if isinstance(type, VoidType):
            return []
        else:
            arguments.append(Field("dummyField", type, False))


fields: list[Field] = []
methods: list[Method] = []
model_declarations = get_declarations(main_definitions)
# print(model_declarations)
for node in model_declarations:
    if isinstance(node.type, FuncDecl):
        methods.append(
            Method(
                name=node.name,
                returnType=parse_type(node.type),
                hasArguments=len(get_function_arguments(node.type)) != 0
            )
        )
    else:
        fields.append(
            Field(
                name=node.name,
                type=parse_type(node.type)
            )
        )

model = ModelStructure(fields, methods)


def get_root_type_name(type: Type) -> str:
    if isinstance(type, Pointer):
        return get_root_type_name(type.type)
    elif isinstance(type, Array):
        return get_root_type_name(type.type)
    elif isinstance(type, VoidType):
        return type.name
    elif isinstance(type, Type):
        return type.name
    else:
        raise Exception(f"Unhandled type {type}")


types: list[Type] = []

for definition in definitions:
    if isinstance(definition, Decl):
        if definition.name is not None:
            continue

        resolved_type = parse_type(definition.type)
        if resolved_type is None:
            raise Exception(f"That is none {definition.type}")

        types.append(resolved_type)

    elif isinstance(definition, Typedef):
        resolved_type = parse_type(definition.type)

        if resolved_type is None:
            raise Exception(f"That is none {definition.type}")

        types.append(
            Alias(
                name=definition.name,
                alias=resolved_type
            )
        )
    else:
        raise Exception(f"aaii {definition}")

clean_types: list[Type] = []


def reduce_alias(alias: Alias) -> Type:
    if alias.name == alias.alias.name:
        return alias.alias
    else:
        return alias


def reduce_irrelevant_aliases(input_list: list[Type]) -> list[Type]:
    def reduce_if_alias(t: Type) -> Type:
        if isinstance(t, Alias):
            return reduce_alias(t)
        else:
            return t

    return [reduce_if_alias(t) for t in input_list]


def _check_only_type_references(t: Type) -> bool:
    if isinstance(t, Pointer) or isinstance(t, Array):
        return _check_only_type_references(t.type)

    return not isinstance(t, Struct) and not isinstance(t, Enum)


def check_only_type_references(model: ModelStructure) -> bool:
    for field in model.fields:
        if not _check_only_type_references(field.type):
            return False

    for method in model.methods:
        if not _check_only_type_references(method.returnType):
            return False

    return True


def assert_only_type_references(model: ModelStructure):
    if not check_only_type_references(model):
        raise Exception(f"Illegal type in model structure: {model}")


types = reduce_irrelevant_aliases(types)

pure_types = list(filter(lambda it: not isinstance(it, Alias), types))
aliases = list[Alias](filter(lambda it: isinstance(it, Alias), types))


def nest_aliases(aliases: list[Alias]) -> list[Alias]:
    new_aliases = []
    for alias in aliases:
        same_name_alias = list(filter(lambda it: it.name == alias.alias.name, aliases))
        if len(same_name_alias) == 0:
            new_aliases.append(alias)
        elif len(same_name_alias) == 1:
            new_aliases.append(replace(alias, alias=same_name_alias[0]))
        else:
            raise Exception("Could not resolve type, too many possibilities")


def add_full_types_to_aliases(aliases: list[Alias], pure_types: list[Type]) -> list[Alias]:
    new_aliases = []
    for alias in aliases:
        same_name_types = list(
            filter(lambda it: not isinstance(it, Alias) and it.name == alias.alias.name, pure_types + aliases)
        )
        if len(same_name_types) == 0:
            new_aliases.append(alias)
        elif len(same_name_types) == 1:
            new_aliases.append(replace(alias, alias=same_name_types[0]))
        else:
            raise Exception("Could not resolve type, too many possibilities")


assert_only_type_references(model)


def _resolve_type(t: Type) -> Type:
    if isinstance(t, Struct) or isinstance(t, Enum) or isinstance(t, Type):
        return t
    elif isinstance(t, Alias):
        return t.alias
    else:
        raise Exception(f"Unhandled type {t}")


def resolve_type_name(name: str) -> Type:
    for t in types:
        if t.name == name:
            return _resolve_type(t)
        elif isinstance(t, Alias):
            if t.alias.name == name:
                return _resolve_type(t.alias)


type_mapping = {
}


def to_ctypes_type(t: Type):
    if isinstance(t, Pointer):
        return f"ctypes.POINTER({to_ctypes_type(t.type)})"
    elif isinstance(t, Array):
        return f"{to_ctypes_type(t.type)}*{t.size}"
    elif isinstance(t, Type):
        mapping = type_mapping.get(t.name)
        if mapping is None:
            return t.name
        else:
            raise Exception("aiii")
    else:
        raise Exception("Illegal Type")


m = Module(
    "SpringMassSystem",
    [ModuleFunction(method.name, to_ctypes_type(method.returnType), []) for method in model.methods],
    [ModuleField(field.name, to_ctypes_type(field.type)) for field in model.fields]
)

needed_types = set(
    [get_root_type_name(method.returnType) for method in model.methods] + [get_root_type_name(field.type) for field in
                                                                           model.fields])

base_types = {
    "void": None
}
structs = []
enums = []
known_types = []

while len(needed_types) != 0:
    print(needed_types)

    found_types = []
    for a in needed_types:
        if a in base_types:
            continue
        found_type = resolve_type_name(a)
        if found_type is None:
            raise Exception(f"Could not resolve type: {a}")
        found_types.append(found_type)

    needed_types = []

    for f in found_types:
        if isinstance(f, Struct):
            if f not in structs:
                structs.append(f)
            needed_types += filter(lambda it: it not in known_types,
                                   [get_root_type_name(field.type) for field in f.fields])
        elif isinstance(f, Enum):
            if f not in enums:
                enums.append(f)
        elif isinstance(f, Type):
            needed_types.append(f.name)
        else:
            raise Exception(f"a: {f}")

# primary_types = [type for type in map(lambda it: get_root_type_name(it.type), model.fields) if type is not None]
# primary_types = set(
#     primary_types + [type for type in map(lambda it: get_root_type_name(it.returnType), model.methods) if
#                      type is not None])
#
# unknown_types += primary_types
#
# type_definitions = [definition for definition in definitions if isinstance(definition, Typedef)]
# print([definition for definition in definitions if not isinstance(definition, Typedef)])
# def handle_typedef(type_def: Typedef) -> Union[Struct, Alias]:
#     if not isinstance(type_def.type, TypeDecl):
#         raise Exception(f"Unexpected type in Typedef {type(type_def.type)}")
#     if isinstance(type_def.type.type, IdentifierType):
#         return Alias(
#             type_def.type.declname,
#             type_def.type.type.names[0]
#         )
#     if not isinstance(type_def.type.type, c_ast.Struct):
#         raise Exception(f"Unexpected type in TypeDec in Typedef {type(type_def.type.type)}: {type_def}")
#     struct_def = type_def.type.type
#     if struct_def.decls is None and struct_def.name:
#         return Alias(
#             type_def.type.declname,
#             struct_def.name
#         )
#     fields: list[Field] = []
#     for declaration in struct_def.decls:
#         fields.append(
#             Field(
#                 name=declaration.name,
#                 type=resolve_type(declaration.type)
#             )
#         )
#     return Struct(
#         name=type_def.type.declname,
#         fields=fields
#     )
#
# print("Finding all types")
# iteration = 0
# while len(unknown_types) != 0:
#     new_structs = []
#     new_aliases = []
#     print("Looking for")
#     print(unknown_types)
#     for unknown_type in unknown_types:
#         type_definition = list(filter(lambda it: it.name == unknown_type, type_definitions))
#         if len(type_definition) != 1:
#             raise Exception(f"Found {len(type_definition)} of type definitions for {unknown_type}, but expected 1")
#         structOrAlias = handle_typedef(type_definition[0])
#         if isinstance(structOrAlias, Struct):
#             new_structs.append(structOrAlias)
#         else:
#             new_aliases.append(structOrAlias)
#
#     found_types = list(map(lambda it: it.name, new_structs))
#     found_types += list(map(lambda it: it.name, new_aliases))
#     unknown_types = set(filter(lambda it: it not in found_types, unknown_types))
#
#     types_in_structs = set([get_root_type_name(field.type) for struct in new_structs for field in struct.fields])
#
#     unknown_types = unknown_types.union(types_in_structs).union(map(lambda it: it.alias, new_aliases))
#     structs += new_structs
#     aliases += new_aliases
#     print(f"Iteration {iteration} done")
#
#     iteration += 1
#
#
#
# print(definitions)
