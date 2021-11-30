import os
import sys
from dataclasses import replace
from typing import Callable, Any

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
        elif isinstance(parsed_type, InlineDeclaration):
            inline_declaration_name = parsed_type.name
            if inline_declaration_name is None:
                inline_declaration_name = node.declname
            parsed_type = replace(parsed_type, name=inline_declaration_name, constant=_is_constant(node))
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
        return InlineStructType(name=node.name, constant=False)
    elif isinstance(node, c_ast.Union):
        return InlineUnionType(name=node.name, constant=False)
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

class _ContainerParser:
    __container_types: dict[type, (type, type)] = {}

    def register_container(self, typ: type, output_type:type, c_ast_type: type):
        self.__container_types[typ] = (output_type, c_ast_type)

    def can_parse_type(self, c_ast_type: type) -> bool:
        return len(self._find_output_types_for_input(c_ast_type)) > 0

    def _find_output_types_for_input(self, c_ast_type: type) -> list[type]:
        return [tuple[0] for typ, tuple in self.__container_types.items() if tuple[1] == c_ast_type]

    def _get_registered_c_ast_type(self, typ: type) -> Optional[type]:
        entry = self.__container_types[typ]
        if entry is None:
            return None
        return entry[1]

    def parse(self, c_ast_container) -> Container:
        return self._parse(c_ast_container)

    def parse_multiple(self, c_ast_containers: list) -> list[Container]:
        return [self._parse(c_ast_container) for c_ast_container in c_ast_containers]

    def _parse(self, node) -> Container:
        node_type = type(node)
        matching_types = self._find_output_types_for_input(node_type)
        if len(matching_types) == 0:
            raise Exception(f"You try to parse a not registered c_ast type {node_type}")
        elif len(matching_types) != 1:
            raise Exception(f"You registered too many types for the input type {node_type}")

        output_type = matching_types[0]

        name = node.name
        properties: list[Property] = []
        inner_containers: list[Container] = []

        property_declarations = node.decls
        if property_declarations is None:
            property_declarations = []
        for declaration in property_declarations:
            if not isinstance(declaration, Decl):
                raise Exception(f"Expected Decl but is {type(declaration)}")
            property = Property(
                name=declaration.name,
                type=_parse_type(declaration.type)
            )
            properties.append(property)
            if isinstance(property.type, InlineDeclaration):
                ast_type = self._get_registered_c_ast_type(type(property.type))
                if ast_type is None:
                    raise Exception(f"No mapping for {type(property.type)} registered")
                ast_container = self._find_ast_concept(declaration.type, ast_type)
                if ast_container is None:
                    raise Exception(f"Found {type(property.type)}, but could not find {ast_type}")
                inner_container = replace(self._parse(ast_container), name=property.name)
                inner_containers.append(inner_container)

        return output_type(
            name=name,
            properties=properties,
            inner_containers=inner_containers
        )

    def _find_ast_concept(self, node: Node, ast_type: type) -> Optional[Any]:
        if isinstance(node, TypeDecl) or isinstance(node, ArrayDecl) or isinstance(node, PtrDecl):
            return self._find_ast_concept(node.type, ast_type)
        elif isinstance(node, ast_type):
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
    containers: list[Container]
    enums: list[Enum]


@dataclass(frozen=True)
class _AstInterface:
    fields: list[Field]
    methods: list[Method]


class _TypdefParser:
    def __init__(self, container_parser: _ContainerParser):
        self._container_parser = container_parser

    def parse_typedefs(self, typedefs: list[Typedef]) -> _AstElements:
        type_definitions: list[TypeDefinition] = []
        containers: list[Container] = []
        enums: list[Enum] = []

        for typedef in typedefs:
            if isinstance(typedef.type, TypeDecl):
                type_definition = self._parse_type_definition(typedef.type)
                if type_definition is not None:
                    type_definitions.append(type_definition)

                container = self._parse_container(typedef.type)
                if container is not None:
                    containers.append(container)
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
            containers=containers,
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

    def _parse_container(self, typedecl: TypeDecl) -> Optional[Container]:
        if self._container_parser.can_parse_type(type(typedecl.type)) and typedecl.type.decls is not None:
            container = self._container_parser.parse(typedecl.type)
            if container.name is None:
                container = replace(container, name=typedecl.declname)
            return container
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
        #TODO implement
        pass


class AstParser:
    origin_file_filter: Optional[Callable[[str], bool]] = None
    _container_parser: _ContainerParser

    def __init__(self):
        self._container_parser = _ContainerParser()
        self._container_parser.register_container(InlineStructType, Struct, c_ast.Struct)
        self._container_parser.register_container(InlineUnionType, Union, c_ast.Union)

    def parse(self, ast: FileAST) -> Module:
        definitions = self._filter_by_file(ast, self.origin_file_filter)
        # main_definitions = list(filter(lambda it: input_file == it.coord.file, definitions))
        declarations = self._get_top_level_declarations(definitions)
        unnamed_declarations = self._get_unnamed_top_level_declarations(declarations)
        named_declarations = self._get_named_top_level_declarations(declarations)
        typedefs = self._get_top_level_typedefs(definitions)

        containers = self._parse_unnamed_top_level_declarations(unnamed_declarations)
        ast_elements = _TypdefParser(self._container_parser).parse_typedefs(typedefs)
        ast_interface = self._parse_named_top_level_declarations(named_declarations)

        return Module(
            type_definitions=ast_elements.type_definitions,
            container=ast_elements.containers + containers,
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

    def _parse_unnamed_top_level_declarations(self, declarations: list[Decl]) -> list[Container]:
        c_ast_containers = []
        for declaration in declarations:
            if self._container_parser.can_parse_type(type(declaration.type)):
                c_ast_containers.append(declaration.type)
            elif isinstance(declaration.type, c_ast.Enum):
                print("Found an Enum without name that will be ignored.")
            else:
                raise Exception(f"Unexpected type {declaration.type}")
        return self._container_parser.parse_multiple(c_ast_containers)

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
