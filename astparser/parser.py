import os
import sys
from dataclasses import replace
from typing import Callable

from pycparser import parse_file, c_ast
from pycparser.c_ast import Node, Decl, Typedef, TypeDecl, IdentifierType, PtrDecl, ArrayDecl, Constant, \
    EnumeratorList, Enumerator, ParamList, Typename, FuncDecl, FileAST

from astparser.model import *
from astparser.types import *


def _get_declarations(definitions: list[Node]) -> list[Decl]:
    declarations: list[Decl] = []
    for node in definitions:
        if isinstance(node, Decl) and node.name is not None:
            declarations.append(node)
    return declarations


def _identifier_names_to_str(names: list[str]) -> str:
    return " ".join(names)


def _is_constant(node: Node) -> bool:
    return "const" in node.quals


def _parse_array_dimension(array_dimension: Node) -> int:
    if not isinstance(array_dimension, Constant):
        raise Exception(f"Expected Constant but got {type(array_dimension)}")
    if array_dimension.type != "int":
        raise Exception(f"Unexpected type in array dimension constant {array_dimension.type}")
    return array_dimension.value


def _parse_type(node: Node) -> Type:
    if isinstance(node, TypeDecl):
        parsed_type = _parse_type(node.type)
        if isinstance(parsed_type, NamedType):
            parsed_type = NamedType(name=parsed_type.name, constant=_is_constant(node))
        elif isinstance(parsed_type, StructType):
            struct_name = parsed_type.name
            if struct_name is None:
                struct_name = node.declname
            parsed_type = StructType(name=struct_name, constant=_is_constant(node))
        return parsed_type
    elif isinstance(node, IdentifierType):
        name = _identifier_names_to_str(node.names)
        return NamedType(name=name, constant=False)
    elif isinstance(node, PtrDecl):
        parsed_type = _parse_type(node.type)
        return Pointer(of=parsed_type, constant=_is_constant(node))
    elif isinstance(node, ArrayDecl):
        parsed_type = _parse_type(node.type)
        return Array(of=parsed_type, size=_parse_array_dimension(node.dim), constant=False)
    elif isinstance(node, c_ast.Struct):
        return StructType(name=node.name, constant=False)
    elif isinstance(node, c_ast.FuncDecl):
        params: list[FunctionParameter] = []
        if not isinstance(node.args, ParamList):
            raise Exception(f"Unexpected type for function arguments {type(node.args)}")
        for parameter in node.args.params:
            if isinstance(parameter, Typename) or isinstance(parameter, Decl):
                params.append(FunctionParameter(name=parameter.name, type=_parse_type(parameter.type)))
            else:
                raise Exception(f"Unexpected type for parameter in parameter list {parameter}")

        return FunctionType(
            params=params,
            return_type=_parse_type(node.type),
            constant=False
        )
    else:
        raise Exception(f"Unexpected type {type(node)}{node}")


class _StructParser:
    def parse_struct(self, struct: c_ast.Struct) -> Struct:
        return self._parse_struct(struct)

    def parse_structs(self, structs: list[c_ast.Struct]) -> list[Struct]:
        return [self._parse_struct(struct) for struct in structs]

    def _parse_struct(self, node: c_ast.Struct) -> Struct:
        name = node.name
        properties: list[StructProperty] = []
        inner_structs: list[Struct] = []

        property_declarations = node.decls
        if property_declarations is None:
            property_declarations = []
        for declaration in property_declarations:
            if not isinstance(declaration, Decl):
                raise Exception(f"Expected Decl but is {type(declaration)}")
            property = StructProperty(
                name=declaration.name,
                type=_parse_type(declaration.type)
            )
            properties.append(property)
            if isinstance(property.type, StructType):
                ast_struct = self._find_struct(declaration.type)
                if ast_struct is None:
                    raise Exception("Found struct type, but could not find Struct")
                inner_struct = replace(self._parse_struct(ast_struct), name=property.name)
                inner_structs.append(inner_struct)

        return Struct(
            name=name,
            properties=properties,
            inner_structs=inner_structs
        )

    def _find_struct(self, node: Node) -> Optional[c_ast.Struct]:
        if isinstance(node, TypeDecl) or isinstance(node, ArrayDecl) or isinstance(node, PtrDecl):
            return self._find_struct(node.type)
        elif isinstance(node, c_ast.Struct):
            return node
        else:
            return None


class _EnumParser:
    @staticmethod
    def get_enumerator_value(enumerator: Enumerator) -> Optional[int]:
        if enumerator.value is None:
            return None
        if not isinstance(enumerator.value, Constant):
            raise Exception(f"Expected Constant but got {type(enumerator.value)}")
        if enumerator.value.type != "int":
            raise Exception(f"Expected int for Constant but got {enumerator.value.type}")
        return int(enumerator.value.value)

    def parse_enum(self, enum: c_ast.Enum) -> Enum:
        return self._parse_enum(enum)

    @staticmethod
    def _parse_enum(enum: c_ast.Enum) -> Enum:
        name = enum.name
        entries: list[EnumEntry] = []
        if not isinstance(enum.values, EnumeratorList):
            raise Exception(f"Expected EnumeratorList but got {type(enum.values)}")
        last_value: int = -1
        for entry in enum.values:
            if not isinstance(entry, Enumerator):
                raise Exception(f"Expected EnumeratorList but got {type(enum.values)}")
            entry_value = _EnumParser.get_enumerator_value(entry)
            if entry_value is None:
                last_value += 1
                entry_value = last_value
            last_value = entry_value
            entries.append(EnumEntry(
                name=entry.name,
                value=entry_value
            ))

        return Enum(
            name=name,
            entries=entries
        )


@dataclass(frozen=True)
class _AstElements:
    type_definitions: list[TypeDefinition]
    structs: list[Struct]
    enums: list[Enum]


@dataclass(frozen=True)
class _AstInterface:
    fields: list[Field]
    methods: list[Method]


class _TypdefParser:
    def parse_typedefs(self, typedefs: list[Typedef]) -> _AstElements:
        type_definitions: list[TypeDefinition] = []
        structs: list[Struct] = []
        enums: list[Enum] = []

        for typedef in typedefs:
            if isinstance(typedef.type, TypeDecl):
                type_definition = self._parse_type_definition(typedef.type)
                if type_definition is not None:
                    type_definitions.append(type_definition)

                struct = self._parse_struct(typedef.type)
                if struct is not None:
                    structs.append(struct)
                    continue

                enum = self._parse_enum(typedef.type)
                if enum is not None:
                    enums.append(enum)
                    continue

                if type_definition is None:
                    raise Exception(f"Unhandled type {typedef.type}")

            else:
                typedef_type = _parse_type(typedef.type)
                if typedef_type is None:
                    raise Exception(f"Unhandled type {typedef.type}")
                type_definitions.append(TypeDefinition(name=typedef.name, for_type=typedef_type))

        return _AstElements(
            type_definitions=type_definitions,
            structs=structs,
            enums=enums
        )

    @staticmethod
    def _parse_type_definition(typedecl: TypeDecl) -> Optional[TypeDefinition]:
        if isinstance(typedecl.type, IdentifierType):
            return TypeDefinition(
                name=typedecl.declname,
                for_type=_parse_type(typedecl.type))
        elif isinstance(typedecl.type, c_ast.Struct) and \
                (typedecl.type.decls is None or typedecl.type.name is not None):
            return TypeDefinition(name=typedecl.declname, for_type=_parse_type(typedecl.type))
        else:
            return None

    @staticmethod
    def _parse_struct(typedecl: TypeDecl) -> Optional[Struct]:
        if isinstance(typedecl.type, c_ast.Struct) and typedecl.type.decls is not None:
            struct = _StructParser().parse_struct(typedecl.type)
            if struct.name is None:
                struct = replace(struct, name=typedecl.declname)
            return struct
        else:
            return None

    @staticmethod
    def _parse_enum(typedecl: TypeDecl) -> Optional[Enum]:
        if isinstance(typedecl.type, c_ast.Enum):
            enum = _EnumParser().parse_enum(typedecl.type)
            if enum.name is None:
                enum = replace(enum, name=typedecl.declname)
            return enum
        else:
            return None

    def _parse_function_pointer(self, typedef: Typedef) -> Optional[str]:
        pass


class AstParser:
    origin_file_filter: Optional[Callable[[str], bool]] = None

    def parse(self, ast: FileAST) -> Module:
        definitions = self._filter_by_file(ast, self.origin_file_filter)
        # main_definitions = list(filter(lambda it: input_file == it.coord.file, definitions))
        declarations = self._get_top_level_declarations(definitions)
        unnamed_declarations = self._get_unnamed_top_level_declarations(declarations)
        named_declarations = self._get_named_top_level_declarations(declarations)
        typedefs = self._get_top_level_typedefs(definitions)

        structs = self._parse_unnamed_top_level_declarations(unnamed_declarations)
        ast_elements = _TypdefParser().parse_typedefs(typedefs)
        ast_interface = self._parse_named_top_level_declarations(named_declarations)

        return Module(
            type_definitions=ast_elements.type_definitions,
            structs=ast_elements.structs + structs,
            enums=ast_elements.enums,
            fields=ast_interface.fields,
            methods=ast_interface.methods
        )

    @staticmethod
    def _filter_by_file(ast: FileAST, origin_file_filter: Optional[Callable[[str], bool]]) -> list[Node]:
        return list(filter(lambda it: origin_file_filter(it.coord.file), ast.ext))

    def _parse_named_top_level_declarations(self, declarations: list[Decl]) -> _AstInterface:
        fields: list[Field] = []
        methods: list[Method] = []
        for declaration in declarations:
            field = self._parse_field(declaration)
            if field is not None:
                fields.append(field)
                continue

            method = self._parse_method(declaration)
            if method is not None:
                methods.append(method)
                continue

            raise Exception(f"Unhandled declaration {declaration}")

        return _AstInterface(
            fields=fields,
            methods=methods
        )

    @staticmethod
    def _parse_method(declaration: Decl) -> Optional[Method]:
        if isinstance(declaration.type, FuncDecl):
            function = declaration.type
            params: list[MethodParameter] = []
            if not isinstance(function.args, ParamList):
                raise Exception(f"Unexpected type for function arguments {type(function.args)}")
            for parameter in function.args.params:
                if isinstance(parameter, Typename) or isinstance(parameter, Decl):
                    params.append(MethodParameter(name=parameter.name, type=_parse_type(parameter.type)))
                else:
                    raise Exception(f"Unexpected type for parameter in parameter list {parameter}")

            return Method(
                name=declaration.name,
                parameter=params,
                return_type=_parse_type(function.type)
            )
        else:
            return None

    @staticmethod
    def _parse_field(declaration: Decl) -> Optional[Field]:
        parsed_type = _parse_type(declaration.type)
        if isinstance(parsed_type, FunctionType):
            return None
        return Field(
            name=declaration.name,
            type=parsed_type
        )

    @staticmethod
    def _parse_unnamed_top_level_declarations(declarations: list[Decl]) -> list[Struct]:
        ast_structs = []
        for declaration in declarations:
            if not isinstance(declaration.type, c_ast.Struct):
                raise Exception("Unexpected type {type(d.type)}")
            ast_structs.append(declaration.type)
        return _StructParser().parse_structs(ast_structs)

    @staticmethod
    def _get_unnamed_top_level_declarations(declarations: list[Decl]) -> list[Decl]:
        return [decl for decl in declarations if decl.name is None]

    @staticmethod
    def _get_named_top_level_declarations(declarations: list[Decl]) -> list[Decl]:
        return [decl for decl in declarations if decl.name is not None]

    @staticmethod
    def _get_top_level_declarations(nodes: list[Node]) -> list[Decl]:
        return [node for node in nodes if isinstance(node, Decl)]

    @staticmethod
    def _get_top_level_typedefs(nodes: list[Node]) -> list[Typedef]:
        return [node for node in nodes if isinstance(node, Typedef)]


if __name__ == '__main__':
    input_file = os.path.expanduser(sys.argv[1])
    ast = parse_file(input_file,
                     use_cpp=True,
                     cpp_path="clang",
                     cpp_args=['-E', '-Ifake_libc_include', '-D_Atomic(x)=x', '-D_Bool=int', '-D__extension__=',
                               '-U__STDC__'])
    astParser = AstParser()
    astParser.origin_file_filter = lambda it: "fake_libc_include" not in it
    print(astParser.parse(ast))
