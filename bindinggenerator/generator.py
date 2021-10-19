import ctypes
from dataclasses import replace

from astparser import get_base_type_name
from astparser.model import Module, TypeDefinition, Struct, Enum
from astparser.types import *
from bindinggenerator.model import Enum as EnumElement, EnumEntry as EnumElementEntry, Definition, Import
from bindinggenerator.model import File, CtypeStruct, CtypeStructField, CtypeFieldType, NamedCtypeFieldType, \
    CtypeFieldPointer, CtypeFieldTypeArray, CtypeFieldFunctionPointer

primitive_names_to_ctypes = {
    "byte": ctypes.c_byte,
    "char": ctypes.c_char,
    "signed char": ctypes.c_char,
    "short": ctypes.c_short,
    "int": ctypes.c_int,
    "unsigned": ctypes.c_int,
    "int8": ctypes.c_int8,
    "int16": ctypes.c_int16,
    "int32": ctypes.c_int32,
    "int64": ctypes.c_int64,
    "long": ctypes.c_long,
    "long int": ctypes.c_long,
    "long long": ctypes.c_longlong,
    "float": ctypes.c_float,
    "double": ctypes.c_double,
    "long double": ctypes.c_longdouble,
    "unsigned byte": ctypes.c_ubyte,
    "unsigned char": ctypes.c_ubyte,
    "unsigned short": ctypes.c_ushort,
    "unsigned int": ctypes.c_uint,
    "unsigned int8": ctypes.c_uint8,
    "unsigned int16": ctypes.c_uint16,
    "unsigned int32": ctypes.c_uint32,
    "unsigned int64": ctypes.c_uint64,
    "unsigned long": ctypes.c_ulong,
    "unsigned long long": ctypes.c_ulonglong,
    "size_t": ctypes.c_size_t,
    "ptrdiff_t": ctypes.c_ssize_t,
    "void": None
}

primitive_names = set([k for k, v in primitive_names_to_ctypes.items()])


def _ctype_to_string(ctype) -> str:
    if ctype is None:
        return "None"
    return f"ctypes.{ctype.__name__}"


class CtypesMapper:
    _POINTER_PATTERN = """ctypes.POINTER({0})"""
    _ARRAY_PATTERN = """({0}*{1})"""
    _FUNCTION_PATTERN = """ctypes.CFUNCTYPE({0}, {1})"""
    _primitive_mappings: dict[str, str] = {k: _ctype_to_string(v) for k, v in primitive_names_to_ctypes.items()}
    _void_pointer = _ctype_to_string(ctypes.c_void_p)

    additional_mappings: dict[str, str] = {}

    def has_primitive_base(self, typ: Type) -> bool:
        return self.is_primitive_type_name(get_base_type_name(typ))

    def is_primitive_type_name(self, name: str) -> bool:
        return name in self._primitive_mappings

    def get_mapping(self, typ: Type) -> str:
        if isinstance(typ, NamedType):
            mapping = self.additional_mappings.get(typ.name)
            if mapping is not None:
                return mapping
            mapping = self._primitive_mappings.get(typ.name)
            if mapping is not None:
                return mapping
            return typ.name
        elif isinstance(typ, Pointer):
            if isinstance(typ.of, NamedType) and typ.of.name == "void":
                return self._void_pointer
            elif isinstance(typ.of, FunctionType):
                # We do not need to wrap the function in a pointer
                # as it is always a function pointer
                return self.get_mapping(typ.of)
            return self._pointer(self.get_mapping(typ.of))
        elif isinstance(typ, StructType):
            mapping = self.additional_mappings.get(typ.name)
            if mapping is not None:
                return mapping
            return typ.name
        elif isinstance(typ, Array):
            return self._array(self.get_mapping(typ.of), typ.size)
        elif isinstance(typ, FunctionType):
            return self._function(
                return_type=self.get_mapping(typ.return_type),
                parameter_types=[self.get_mapping(parameter.type) for parameter in typ.params]
            )
        else:
            raise Exception(f"Unhandled case {typ}")

    @staticmethod
    def _array(of: str, size: int):
        return CtypesMapper._ARRAY_PATTERN.format(of, size)

    @staticmethod
    def _pointer(of: str) -> str:
        return CtypesMapper._POINTER_PATTERN.format(of)

    @staticmethod
    def _function(return_type: str, parameter_types: list[str]) -> str:
        return CtypesMapper._FUNCTION_PATTERN.format(return_type, ", ".join(parameter_types))


def _dicts_have_common_key(a: dict, b: dict) -> bool:
    for key in a.keys():
        if key in b:
            return True
    return False


class BindingGenerator:
    _TYPE_DEFINITION_PATTER = """{0} = {1}"""
    _STRUCT_PATTERN = """class {0}(ctypes.Structure):
        {1}
        _fields_ = [
{2}
        ]
    """
    _STRUCT_FIELD_PATTERN = "            (\"{0}\", {1})"
    _ENUM_PATTER = """class {0}(Enum):
{1}
     """
    _ENUM_ENTRY_PATTERN = """     {0} = {1}"""
    _MODEL_CLASS_PATTERN = """"""
    _imports: list[str] = [
        "import ctypes",
        "from enum import Enum"
    ]

    def generate(self, module: Module) -> str:
        ctypes_mapper = CtypesMapper()
        enum_type_definitions = self._create_primitive_type_definitions_for_enums(module.enums)
        self._register_additional_mappings_for_enums(ctypes_mapper, module.enums)
        output = "\n".join(self._imports) + "\n\n"
        output += self.generate_structs(module.structs, ctypes_mapper) + "\n\n"
        output += self.generate_enums(module.enums, ctypes_mapper) + "\n\n"
        output += self.generate_type_definitions(
            module.type_definitions + enum_type_definitions,
            ctypes_mapper
        ) + "\n\n"
        return output

    def generate_type_definitions(self, type_definitions: list[TypeDefinition], ctypes_mapper: CtypesMapper) -> str:
        definitions: list[str] = []
        for type_definition in type_definitions:
            definitions.append(self._convert_type_definition(type_definition, ctypes_mapper))
        return '\n'.join(definitions)

    def generate_structs(self, structs: list[Struct], ctypes_mapper: CtypesMapper) -> str:
        structs_strings: list[str] = []
        for struct in structs:
            structs_strings.append(self._convert_struct(struct, ctypes_mapper))
        return '\n'.join(structs_strings)

    def generate_enums(self, enums: list[Enum], ctypes_mapper: CtypesMapper) -> str:
        enum_strings: list[str] = []
        for enum in enums:
            enum_strings.append(self._convert_enum(enum))
        return '\n'.join(enum_strings)

    @staticmethod
    def _ctypes_enum_name(enum: Enum) -> str:
        return f"enum_{enum.name}"

    def _register_additional_mappings_for_enums(self, ctypes_mapper: CtypesMapper, enums: list[Enum]):
        enum_mappings = {enum.name: self._ctypes_enum_name(enum) for enum in enums}
        ctypes_mapper.additional_mappings.update(enum_mappings)

    def _create_primitive_type_definitions_for_enums(self, enums: list[Enum]) -> list[TypeDefinition]:
        return [TypeDefinition(
            name=self._ctypes_enum_name(enum),
            for_type=NamedType(name="int", constant=False)
        ) for enum in enums]

    def _convert_struct(self, struct: Struct, ctypes_mapper: CtypesMapper, name_prefix: str = "") -> str:
        struct_name = name_prefix + struct.name
        output: str = ""
        for inner_struct in struct.inner_structs:
            inner_name_prefix = f"{struct_name}_"
            output += self._convert_struct(inner_struct, ctypes_mapper, inner_name_prefix)
            output += "\n\n"
            ctypes_mapper.additional_mappings[inner_struct.name] = inner_name_prefix + inner_struct.name

        output += self._STRUCT_PATTERN.format(
            struct_name,
            "",
            ", \n".join([self._STRUCT_FIELD_PATTERN.format(
                property.name,
                ctypes_mapper.get_mapping(property.type)
            ) for property in struct.properties])
        )

        for inner_struct in struct.inner_structs:
            del ctypes_mapper.additional_mappings[inner_struct.name]

        return output

    def _convert_enum(self, enum: Enum) -> str:
        output = self._ENUM_PATTER.format(
            enum.name,
            "\n".join([self._ENUM_ENTRY_PATTERN.format(
                entry.name,
                entry.value
            ) for entry in enum.entries])
        )
        return output

    @staticmethod
    def _convert_type_definition(type_definition: TypeDefinition, ctypes_mapper: CtypesMapper) -> str:
        return BindingGenerator._TYPE_DEFINITION_PATTER.format(
            type_definition.name,
            ctypes_mapper.get_mapping(type_definition.for_type)
        )


class PythonBindingFileGenerator:
    _TYPE_REMAPPING_MAP: dict[str, str] = {}

    def generate(self, module: Module) -> File:
        imports = [
            Import(None, ["ctypes"]),
            Import("enum", ["Enum"])
        ]
        enum_type_definitions = self._create_primitive_type_definitions_for_enums(module.enums)
        elements = [self._create_element_from_type_definition(type_definition)
                    for type_definition in enum_type_definitions]
        self._TYPE_REMAPPING_MAP = {enum.name: self._ctypes_enum_name(enum) for enum in module.enums}
        elements += [self._create_element_from_type_definition(type_definition)
                     for type_definition in module.type_definitions]
        elements += [self._create_element_from_enum(enum) for enum in module.enums]

        elements += [self._create_element_from_struct(
            self._add_struct_name_prefix_to_inner_structs_name(struct)
        )
            for struct in module.structs]

        return File(
            name="binding.py",
            imports=imports,
            elements=elements
        )

    @staticmethod
    def _ctypes_enum_name(enum: Enum) -> str:
        return f"enum_{enum.name}"

    def _create_primitive_type_definitions_for_enums(self, enums: list[Enum]) -> list[TypeDefinition]:
        return [TypeDefinition(
            name=self._ctypes_enum_name(enum),
            for_type=NamedType(name="int", constant=False)
        ) for enum in enums]

    def _convert_type(self, typ: Type) -> CtypeFieldType:
        if isinstance(typ, StructType) or isinstance(typ, NamedType):
            name = typ.name
            if name in self._TYPE_REMAPPING_MAP:
                name = self._TYPE_REMAPPING_MAP[name]
            return NamedCtypeFieldType(
                name=name
            )
        elif isinstance(typ, Pointer):
            # We do not need to wrap the function in a pointer
            # as it is always a function pointer
            # TODO actually this is a design flaw in the parser !?
            if isinstance(typ.of, FunctionType):
                return CtypeFieldFunctionPointer(
                    return_type=self._convert_type(typ.of.return_type),
                    parameter_types=[self._convert_type(parameter.type) for parameter in typ.of.params]
                )
            return CtypeFieldPointer(
                of=self._convert_type(typ.of)
            )
        elif isinstance(typ, Array):
            return CtypeFieldTypeArray(
                of=self._convert_type(typ.of),
                size=typ.size
            )
        else:
            raise Exception(f"Unhandled type {typ}")

    def _add_struct_name_prefix_to_inner_structs_name(self, struct: Struct) -> Struct:
        inner_structs: list[Struct] = []
        for inner_struct in struct.inner_structs:
            inner_struct = replace(inner_struct, name=f"{struct.name}_{inner_struct.name}")
            inner_structs.append(self._add_struct_name_prefix_to_inner_structs_name(inner_struct))

        return replace(struct, inner_structs=inner_structs)

    def _create_element_from_struct(self, struct: Struct) -> CtypeStruct:
        return CtypeStruct(
            name=struct.name,
            fields=[CtypeStructField(name=property.name, type=self._convert_type(property.type))
                    for property in struct.properties]
        )

    def _create_element_from_enum(self, enum: Enum) -> EnumElement:
        return EnumElement(
            name=enum.name,
            entries=[EnumElementEntry(name=entry.name, value=entry.value) for entry in enum.entries]
        )

    def _create_element_from_type_definition(self, type_definition: TypeDefinition) -> Definition:
        return Definition(
            name=type_definition.name,
            for_type=self._convert_type(type_definition.for_type)
        )
