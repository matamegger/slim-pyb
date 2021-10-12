import enum
import os.path
import re
import sys
from dataclasses import dataclass, field
from pycparser import c_parser, c_ast, parse_file
from pycparser.c_ast import FileAST, FuncDecl, Node, Decl, TypeDecl, IdentifierType, Typename, PtrDecl, ArrayDecl
from pycparser.plyparser import Coord

input_file = os.path.expanduser(sys.argv[1])
ast = parse_file(input_file,
                 use_cpp=True,
                 cpp_path="clang",
                 cpp_args=['-E', '-Ifake_libc_include', '-D_Atomic(x)=x', '-D_Bool=int', '-D__extension__=',
                           '-U__STDC__'])

print(type(ast.ext[0].coord))

definitions = filter(lambda it: "fake_libc_include" not in it.coord.file, ast.ext)

main_definitions = filter(lambda it: input_file == it.coord.file, definitions)


@dataclass(frozen=True)
class Type:
    name: str
    constant: bool


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
class VoidType(Type):
    name: str = field(init=False, default="Void")
    constant: bool = field(init=False, default=False)


@dataclass
class Field:
    name: str
    type: Type


@dataclass
class Struct:
    fields: list[Field]


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


def get_model_declarations(definitions: list[Node]) -> list[Decl]:
    declarations: list[Decl] = []
    for node in definitions:
        if isinstance(node, Decl) and node.name is not None:
            declarations.append(node)
    return declarations


def resolve_type(node: Node):
    if isinstance(node, FuncDecl):
        return resolve_type(node.type)
    elif isinstance(node, TypeDecl):
        if isinstance(node.type, IdentifierType):
            type_name = node.type.names[0]
            if type_name == "void":
                return VoidType()
            else:
                return Type(type_name, 'const' in node.quals)
        else:
            raise Exception(f"Unexpected subtype of TypeDecl {type(node.type)}{node.type}")
    elif isinstance(node, PtrDecl):
        return Pointer(type=resolve_type(node.type), constant='const' in node.quals)
    elif isinstance(node, ArrayDecl):
        return Array(
            size=node.dim.value,
            type=resolve_type(node.type)
        )
    elif isinstance(node, Typename):
        return resolve_type(node.type)
    else:
        raise Exception(f"Unhandled state when resolving type: {type(node)}:{node}")


def get_function_arguments(function: FuncDecl) -> list[Field]:
    arguments: list[Field] = []
    for arg in function.args.params:
        type = resolve_type(arg)
        if isinstance(type, VoidType):
            return []
        else:
            arguments.append(Field("dummyField", type, False))


fields: list[Field] = []
methods: list[Method] = []
model_declarations = get_model_declarations(main_definitions)
print(model_declarations)
for node in model_declarations:
    if isinstance(node.type, FuncDecl):
        methods.append(
            Method(
                name=node.name,
                returnType=resolve_type(node.type),
                hasArguments=len(get_function_arguments(node.type)) != 0
            )
        )
    else:
        fields.append(
            Field(
                name=node.name,
                type=resolve_type(node.type)
            )
        )

unknown_types = []
structs = []
model = ModelStructure(fields, methods)


def get_root_type_name(type: Type):
    if isinstance(type, Pointer):
        return get_root_type_name(type.type)
    elif isinstance(type, Array):
        return get_root_type_name(type.type)
    elif isinstance(type, VoidType):
        return None
    elif isinstance(type, Type):
        return type.name
    else:
        raise Exception(f"Unhandled type {type}")


primary_types = [type for type in map(lambda it: get_root_type_name(it.type), model.fields) if type is not None]
primary_types = set(primary_types + [type for type in map(lambda it: get_root_type_name(it.returnType), model.methods) if type is not None])

unknown_types += primary_types


