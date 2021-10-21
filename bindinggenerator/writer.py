import ctypes
from typing import IO

from bindinggenerator import primitive_names_to_ctypes
from bindinggenerator.model import File, Import, Element, Definition, Enum, CtypeStruct, CtypeStructDefinition, \
    CtypeStructDeclaration, CtypeFieldPointer, CtypeFieldType, NamedCtypeFieldType, CtypeFieldTypeArray, \
    CtypeFieldFunctionPointer, CtypeStructField


class Output:
    def write(self, text: str):
        pass

    def new_line(self):
        pass

    def close(self):
        pass


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

    def get_mapping(self, typ: CtypeFieldType) -> str:
        if isinstance(typ, NamedCtypeFieldType):
            mapping = self.additional_mappings.get(typ.name)
            if mapping is not None:
                return mapping
            mapping = self._primitive_mappings.get(typ.name)
            if mapping is not None:
                return mapping
            return typ.name
        elif isinstance(typ, CtypeFieldPointer):
            if isinstance(typ.of, NamedCtypeFieldType) and typ.of.name == "void":
                return self._void_pointer
            return self._pointer(self.get_mapping(typ.of))
        elif isinstance(typ, CtypeFieldTypeArray):
            return self._array(self.get_mapping(typ.of), typ.size)
        elif isinstance(typ, CtypeFieldFunctionPointer):
            return self._function(
                return_type=self.get_mapping(typ.return_type),
                parameter_types=[self.get_mapping(parameter) for parameter in typ.parameter_types]
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


class FileOutput(Output):
    __file: IO = None

    def __init__(self, file: str):
        self.__file = open(file, "w")

    def write(self, text: str):
        self.__file.write(text)

    def new_line(self):
        self.write("\n")

    def close(self):
        self.__file.close()


class PythonWriter:
    __INDENT = "    "
    __PASS = "pass"
    __IMPORT_PATTERN = "import {1}"
    __IMPORT_WITH_PATH_PATTERN = "from {0} import {1}"
    __DEFINITION_PATTERN = "{0} = {1}"
    __ENUM_DECLARATION_PATTER = "class {0}(Enum):"
    __ENUM_ENTRY_PATTERN = "{0} = {1}"
    __STRUCT_DECLARATION_PATTERN = "class {0}(ctypes.Structure):"
    __STRUCT_FIELD_ASSIGNMENT_START = "_fields_ = ["
    __STRUCT_FIELD_OR_SLOTS_ASSIGNMENT_END = "]"
    __STRUCT_FIELD_PATTERN = "('{0}', {1})"
    __STRUCT_SLOTS_ASSIGNMENT_START = "__slots__ = ["
    __STRUCT_SLOT_PATTERN = "'{0}'"

    _mapper: CtypesMapper = None

    def __init__(self, ctypes_mapper: CtypesMapper):
        self._mapper = ctypes_mapper

    def write(self, file: File, output: Output):
        for imprt in file.imports:
            output.write(self._convert_to_text(imprt))
            output.new_line()

        for element in file.elements:
            self._write(element, output)
            output.new_line()

    def _convert_to_text(self, imprt: Import) -> str:
        pattern = self.__IMPORT_PATTERN
        if imprt.path is not None:
            pattern = self.__IMPORT_WITH_PATH_PATTERN
        return pattern.format(imprt.path, ", ".join(imprt.imports))

    def _write(self, element: Element, output: Output):
        if isinstance(element, Definition):
            output.write(self.__DEFINITION_PATTERN.format(element.name, self.__mapping(element.for_type)))
            output.new_line()
        elif isinstance(element, Enum):
            output.write(self.__ENUM_DECLARATION_PATTER.format(element.name))
            output.new_line()
            for entry in element.entries:
                output.write(self.__INDENT + self.__ENUM_ENTRY_PATTERN.format(entry.name, entry.value))
                output.new_line()
        elif isinstance(element, CtypeStruct):
            output.write(self.__STRUCT_DECLARATION_PATTERN.format(element.name))
            output.new_line()
            output.new_line()
            self.__write_struct_declaration(element, False, output, 1)
        elif isinstance(element, CtypeStructDefinition):
            output.write(self.__STRUCT_DECLARATION_PATTERN.format(element.name))
            output.new_line()
            output.write(self.__INDENT)
            output.write(self.__PASS)
        elif isinstance(element, CtypeStructDeclaration):
            self.__write_struct_declaration(element, True, output, 0)
        else:
            raise Exception(f"Unhandled element {element}")

    def __write_struct_declaration(self, declaration: CtypeStructDeclaration, with_class_name: bool, output: Output,
                                   indent: int):
        self.__write_struct_declaration_slots(declaration, with_class_name, output, indent)
        output.new_line()
        self.__write_struct_declaration_fields(declaration, with_class_name, output, indent)

    def __write_struct_declaration_slots(
            self,
            declaration: CtypeStructDeclaration,
            with_class_name: bool,
            output: Output, indent: int
    ):
        self.__write_indent(output, indent)
        if with_class_name:
            output.write(declaration.name)
            output.write(".")
        output.write(self.__STRUCT_SLOTS_ASSIGNMENT_START)
        output.new_line()
        indent = indent + 1
        for field in declaration.fields[:-1]:
            self.__write_struct_declaration_slot(field, output, indent)
            output.write(",")
            output.new_line()
        self.__write_struct_declaration_slot(declaration.fields[-1], output, indent)
        output.new_line()
        indent -= 1
        self.__write_indent(output, indent)
        output.write(self.__STRUCT_FIELD_OR_SLOTS_ASSIGNMENT_END)
        output.new_line()

    def __write_struct_declaration_fields(
            self,
            declaration: CtypeStructDeclaration,
            with_class_name: bool,
            output: Output, indent: int
    ):
        self.__write_indent(output, indent)
        if with_class_name:
            output.write(declaration.name)
            output.write(".")
        output.write(self.__STRUCT_FIELD_ASSIGNMENT_START)
        output.new_line()
        indent = indent + 1
        for field in declaration.fields[:-1]:
            self.__write_struct_declaration_field(field, output, indent)
            output.write(",")
            output.new_line()
        self.__write_struct_declaration_field(declaration.fields[-1], output, indent)
        output.new_line()
        indent -= 1
        self.__write_indent(output, indent)
        output.write(self.__STRUCT_FIELD_OR_SLOTS_ASSIGNMENT_END)
        output.new_line()

    def __write_struct_declaration_slot(self, field: CtypeStructField, output: Output, indent: int):
        self.__write_indent(output, indent)
        output.write(self.__STRUCT_SLOT_PATTERN.format(field.name))

    def __write_struct_declaration_field(self, field: CtypeStructField, output: Output, indent: int):
        self.__write_indent(output, indent)
        output.write(self.__STRUCT_FIELD_PATTERN.format(field.name, self.__mapping(field.type)))

    def __write_indent(self, output: Output, count: int):
        for i in range(count):
            output.write(self.__INDENT)

    def __mapping(self, typ: CtypeFieldType) -> str:
        return self._mapper.get_mapping(typ)
