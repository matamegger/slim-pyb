import re
from dataclasses import replace
from typing import Optional

from astparser.model import Module, Method as AstMethod, Field as AstField
from bindinggenerator import primitive_names
from bindinggenerator.generator import PythonBindingFileGenerator, ElementArranger, AstTypeConverter
from bindinggenerator.model import SystemMethod, SystemField, Parameter, System, Import


class SystemGenerator:
    __INITIALIZER_METHOD_NAME_REGEX = "(.*)_initialize"
    __STEP_METHOD_NAME_REGEX = "(.*)_step"
    __TERMINATOR_METHOD_NAME_REGEX = "(.*)_terminate"
    __LIFE_CYCLE_METHOD_NAME_REGEXES = [
        __INITIALIZER_METHOD_NAME_REGEX,
        __STEP_METHOD_NAME_REGEX,
        __TERMINATOR_METHOD_NAME_REGEX
    ]
    __OUTPUTS_FIELD_REGEX_PATTERN = "{0}_Y"
    __OUTPUTS_NAME = "outputs"
    __INPUTS_FIELD_REGEX_PATTERN = "{0}_U"
    __INPUTS_NAME = "inputs"
    __SIGNALS_FIELD_REGEX_PATTERN = "{0}_B"
    __SIGNALS_NAME = "signals"
    __CONTINUOUS_STATE_FIELD_REGEX_PATTERN = "{0}_X"
    __REAL_TIME_MODEL_FIELD_REGEX_PATTERN = "{0}_M"

    def generate(
            self,
            module: Module,
            name: str,
            binary_basename: str,
            binding_file_generator: PythonBindingFileGenerator = PythonBindingFileGenerator(),
            element_arranger: ElementArranger = ElementArranger()
    ):
        ast_type_converter = AstTypeConverter()
        methods = module.methods
        life_cycle_methods = self._filter_life_cycle_methods(methods)
        simulink_system_name = self.__get_life_cycle_method_name_prefix(life_cycle_methods[0].name)
        if simulink_system_name is None:
            simulink_system_name = ""

        system_methods = [
            SystemMethod(
                name=method.name.removeprefix(f"{simulink_system_name}_"),
                return_type=ast_type_converter.convert(method.return_type),
                parameter=[Parameter(name=param.name, type=ast_type_converter.convert(param.type))
                           for param in method.parameter],
                name_in_library=method.name
            )
            for method in life_cycle_methods]

        system_fields = self._get_system_fields(module.fields, simulink_system_name, ast_type_converter)

        # Generate bindings file
        binding_file = binding_file_generator.generate(module, "bindings", ast_type_converter)
        arranged_elements = element_arranger.arrange(binding_file.elements, primitive_names)
        binding_file = replace(binding_file, elements=arranged_elements)

        return System(
            name=name,
            binary_basename=binary_basename,
            imports=[Import(None, imports=["ctypes"]), Import(None, imports=["os"]),
                     Import(None, imports=["platform"])],
            methods=system_methods,
            fields=system_fields,
            bindingFiles=[binding_file]
        )

    def _get_system_fields(
            self,
            fields: list[AstField],
            simulink_system_name: str,
            ast_type_converter: AstTypeConverter) -> list[SystemField]:
        return [
            self._process_field(field, simulink_system_name, ast_type_converter)
            for field in fields
        ]

    def _process_field(
            self,
            ast_field: AstField,
            simulink_system_name: str,
            ast_type_converter: AstTypeConverter
    ) -> SystemField:
        name = ast_field.name
        if self.__is_outputs(simulink_system_name, ast_field):
            name = self.__OUTPUTS_NAME
        elif self.__is_inputs(simulink_system_name, ast_field):
            name = self.__INPUTS_NAME
        elif self.__is_signals(simulink_system_name, ast_field):
            name = self.__SIGNALS_NAME

        return SystemField(
            name=name,
            type=ast_type_converter.convert(ast_field.type),
            name_in_library=ast_field.name
        )

    def __is_outputs(self, simulink_system_name: str, ast_field: AstField) -> bool:
        return re.fullmatch(
            self.__OUTPUTS_FIELD_REGEX_PATTERN.format(simulink_system_name),
            ast_field.name
        ) is not None

    def __is_inputs(self, simulink_system_name: str, ast_field: AstField) -> bool:
        return re.fullmatch(
            self.__INPUTS_FIELD_REGEX_PATTERN.format(simulink_system_name),
            ast_field.name
        ) is not None

    def __is_signals(self, simulink_system_name: str, ast_field: AstField) -> bool:
        return re.fullmatch(
            self.__SIGNALS_FIELD_REGEX_PATTERN.format(simulink_system_name),
            ast_field.name
        ) is not None

    def _filter_life_cycle_methods(self, methods: list[AstMethod]) -> list[AstMethod]:
        return [method for method in methods if self.__is_life_cycle_method_name(method.name)]

    def _filter_none_life_cycle_methods(self, methods: list[AstMethod]) -> list[AstMethod]:
        return [method for method in methods if not self.__is_life_cycle_method_name(method.name)]

    def __is_life_cycle_method_name(self, name: str) -> bool:
        return self.__get_life_cycle_method_name_prefix(name) is not None

    def __get_life_cycle_method_name_prefix(self, name: str) -> Optional[str]:
        for regex in self.__LIFE_CYCLE_METHOD_NAME_REGEXES:
            match = re.fullmatch(regex, name)
            if match is not None:
                return match.group(1)
        return None
