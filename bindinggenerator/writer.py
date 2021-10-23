import ctypes
import os.path
from typing import IO

from bindinggenerator import primitive_names_to_ctypes
from bindinggenerator.model import BindingFile, Import, Element, Definition, Enum, CtypeStruct, CtypeStructDefinition, \
    CtypeStructDeclaration, CtypeFieldPointer, CtypeFieldType, NamedCtypeFieldType, CtypeFieldTypeArray, \
    CtypeFieldFunctionPointer, CtypeStructField, System, SystemMethod, SystemField


class Output:
    def write(self, text: str):
        pass

    def new_line(self):
        pass

    def close(self):
        pass


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


class IndentableOutput(Output):
    __output: Output
    __needs_indent: bool = False
    indent_pattern: str
    __indent_depth: int = 0

    def __init__(self, output: Output, indent: str):
        self.__output = output
        self.indent_pattern = indent

    def indent(self, by: int = 1):
        self.__indent_depth += by

    def deindent(self, by: int = 1):
        self.__indent_depth -= by

    def set_indent(self, indent: int):
        self.__indent_depth = indent

    def get_indent(self) -> int:
        return self.__indent_depth

    def reset_indent(self):
        self.__indent_depth = 0

    def write(self, text: str):
        if self.__needs_indent:
            self._do_indent()
            self.__needs_indent = False
        self.__output.write(text)

    def new_line(self):
        self.__output.new_line()
        self.__needs_indent = True

    def close(self):
        self.__output.close()

    def _do_indent(self):
        for x in range(self.__indent_depth):
            self.__output.write(self.indent_pattern)


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


class BaseWriter:
    _INDENT = "    "
    _IMPORT_PATTERN = "import {1}"
    _IMPORT_WITH_PATH_PATTERN = "from {0} import {1}"

    _mapper: CtypesMapper = None

    def __init__(self, ctypes_mapper: CtypesMapper):
        self._mapper = ctypes_mapper

    def _write_import(self, imprt: Import, output: Output):
        pattern = self._IMPORT_PATTERN
        if imprt.path is not None:
            pattern = self._IMPORT_WITH_PATH_PATTERN
        output.write(pattern.format(imprt.path, ", ".join(imprt.imports)))
        output.new_line()

    def _write_indent(self, output: Output, count: int):
        for i in range(count):
            output.write(self._INDENT)


class PythonBindingWriter(BaseWriter):
    __PASS = "pass"
    __DEFINITION_PATTERN = "{0} = {1}"
    __ENUM_DECLARATION_PATTER = "class {0}(Enum):"
    __ENUM_ENTRY_PATTERN = "{0} = {1}"
    __STRUCT_DECLARATION_PATTERN = "class {0}(ctypes.Structure):"
    __STRUCT_FIELD_ASSIGNMENT_START = "_fields_ = ["
    __STRUCT_FIELD_OR_SLOTS_ASSIGNMENT_END = "]"
    __STRUCT_FIELD_PATTERN = "('{0}', {1})"
    __STRUCT_SLOTS_ASSIGNMENT_START = "__slots__ = ["
    __STRUCT_SLOT_PATTERN = "'{0}'"

    def write(self, file: BindingFile, output: Output):
        for imprt in file.imports:
            self._write_import(imprt, output)

        for element in file.elements:
            self._write(element, output)
            output.new_line()

    def _write(self, element: Element, output: Output):
        if isinstance(element, Definition):
            output.write(self.__DEFINITION_PATTERN.format(element.name, self.__mapping(element.for_type)))
            output.new_line()
        elif isinstance(element, Enum):
            output.write(self.__ENUM_DECLARATION_PATTER.format(element.name))
            output.new_line()
            for entry in element.entries:
                output.write(self._INDENT + self.__ENUM_ENTRY_PATTERN.format(entry.name, entry.value))
                output.new_line()
        elif isinstance(element, CtypeStruct):
            output.write(self.__STRUCT_DECLARATION_PATTERN.format(element.name))
            output.new_line()
            output.new_line()
            self.__write_struct_declaration(element, False, output, 1)
        elif isinstance(element, CtypeStructDefinition):
            output.write(self.__STRUCT_DECLARATION_PATTERN.format(element.name))
            output.new_line()
            output.write(self._INDENT)
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
        self._write_indent(output, indent)
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
        self._write_indent(output, indent)
        output.write(self.__STRUCT_FIELD_OR_SLOTS_ASSIGNMENT_END)
        output.new_line()

    def __write_struct_declaration_fields(
            self,
            declaration: CtypeStructDeclaration,
            with_class_name: bool,
            output: Output, indent: int
    ):
        self._write_indent(output, indent)
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
        self._write_indent(output, indent)
        output.write(self.__STRUCT_FIELD_OR_SLOTS_ASSIGNMENT_END)
        output.new_line()

    def __write_struct_declaration_slot(self, field: CtypeStructField, output: Output, indent: int):
        self._write_indent(output, indent)
        output.write(self.__STRUCT_SLOT_PATTERN.format(field.name))

    def __write_struct_declaration_field(self, field: CtypeStructField, output: Output, indent: int):
        self._write_indent(output, indent)
        output.write(self.__STRUCT_FIELD_PATTERN.format(field.name, self.__mapping(field.type)))

    def __mapping(self, typ: CtypeFieldType) -> str:
        return self._mapper.get_mapping(typ)


class SystemWriter(BaseWriter):
    __CLASS_PATTERN = "class {0}:"
    __INIT_METHOD_START_PATTERN = "def __init__(self, model=\"{0}\"):"
    __LOADER_BLOCK_LINES = ["self.model = model",
                            """if platform.system() == "Linux":""",
                            """    self.dll_path = os.path.abspath(f"{model}.so")""",
                            """    self.dll = ctypes.cdll.LoadLibrary(self.dll_path)""",
                            """elif platform.system() == "Darwin":""",
                            """    self.dll_path = os.path.abspath(f"{model}.dylib")""",
                            """    self.dll = ctypes.cdll.LoadLibrary(self.dll_path)""",
                            """elif platform.system() == "Windows":""",
                            """    self.dll_path = os.path.abspath(f"{model}_win64.dll")""",
                            """    self.dll = ctypes.windll.LoadLibrary(self.dll_path)""",
                            """else:""",
                            """    raise Exception("System Not Supported")"""
                            ]
    __METHOD_VAR_INIT_PATTERN = """self.__{0} = getattr(self.dll, "{1}")"""
    __FIELD_VAR_INIT_PATTERN = """self.{0} = {2}.in_dll(self.dll, "{1}")"""
    __METHOD_START_PATTERN = "def {0}(self):"
    __METHOD_CALLING_CMETHOD_CONTENT = "self.__{0}()"

    def write(
            self,
            system: System,
            output_path: str,
            python_bindings_writer: PythonBindingWriter
    ):
        binding_imports = []
        for binding in system.bindingFiles:
            name_without_extension = binding.name[:binding.name.rfind(".")]
            binding_imports.append(Import(name_without_extension, ["*"]))
            output = FileOutput(os.path.join(output_path, binding.name))
            python_bindings_writer.write(binding, output)
            output.close()

        output = IndentableOutput(FileOutput(os.path.join(output_path, f"{system.name.lower()}.py")), self._INDENT)
        self._write_actual_system(system, binding_imports, output)
        output.close()

    def _write_actual_system(self, system: System, binding_imports: list[Import], output: IndentableOutput):
        for imprt in system.imports + binding_imports:
            self._write_import(imprt, output)
        output.new_line()

        self._write_class_start(output, system.name)
        output.indent()
        self._write_init(output, system)
        output.new_line()
        output.deindent()
        self._write_methods(output, system.methods)

    def _write_class_start(self, output: Output, name: str):
        output.write(self.__CLASS_PATTERN.format(name))
        output.new_line()

    def _write_init(self, output: IndentableOutput, system: System):
        output.write(self.__INIT_METHOD_START_PATTERN.format(system.binary_basename))
        output.new_line()
        output.indent()
        self._write_loader_block(output)
        output.new_line()
        output.write("# System method initializers")
        output.new_line()
        self._write_method_initializers(output, system.methods)
        output.new_line()
        output.write("# System field initializers")
        output.new_line()
        self._write_field_initializers(output, system.fields)

    def _write_loader_block(self, output: Output):
        for line in self.__LOADER_BLOCK_LINES:
            output.write(line)
            output.new_line()

    def _write_method_initializers(self, output: Output, methods: list[SystemMethod]):
        for method in methods:
            self._write_method_initializer(output, method)

    def _write_method_initializer(self, output: Output, method: SystemMethod):
        output.write(self.__METHOD_VAR_INIT_PATTERN.format(method.name, method.name_in_library))
        output.new_line()

    def _write_field_initializers(self, output: Output, fields: list[SystemField]):
        for field in fields:
            self._write_field_initializer(output, field)

    def _write_field_initializer(self, output: Output, field: SystemField):
        output.write(self.__FIELD_VAR_INIT_PATTERN.format(
            field.name,
            field.name_in_library,
            self._mapper.get_mapping(field.type)
        ))
        output.new_line()

    def _write_methods(self, output: IndentableOutput, methods: list[SystemMethod]):
        indent = output.get_indent()
        for method in methods:
            self.__write_method(output, method)
            output.new_line()
            output.set_indent(indent)

    def __write_method(self, output: IndentableOutput, method: SystemMethod):
        # TODO we ignore parameters and return types
        output.write(self.__METHOD_START_PATTERN.format(method.name))
        output.new_line()
        output.indent()
        output.write(self.__METHOD_CALLING_CMETHOD_CONTENT.format(method.name))
        output.new_line()
