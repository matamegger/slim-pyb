from dataclasses import replace

from astparser import get_base_type_name, Type, get_base_type, FunctionType, InlineDeclaration
from astparser.model import Module, Struct, Enum, TypeDefinition, Union, Container


class ModuleCleaner:
    externally_known_type_name: list[str] = []

    def remove_not_used_elements(self, module: Module) -> Module:
        needed_type_names: set[str] = set[str]()
        known_type_names: set[str] = set[str]()

        containers: list[Container] = []
        enums: list[Enum] = []
        type_definitions: list[TypeDefinition] = []

        types = self._get_field_types(module) + self._get_method_types(module)
        base_types = self._get_list_of_base_type_names(types)
        needed_type_names = needed_type_names.union(base_types)
        previous_needed_type_names: set[str] = set[str]()

        while len(needed_type_names) > 0:
            if needed_type_names == previous_needed_type_names:
                raise Exception("Loop detected while cleaning up module")
            previous_needed_type_names = needed_type_names.copy()

            new_container = self._find_needed_container(module.container, needed_type_names)
            new_enums = self._find_needed_enums(module.enums, needed_type_names)
            new_type_definitions = self._find_needed_type_definitions(module.type_definitions, needed_type_names)

            containers.extend(new_container)
            enums.extend(new_enums)
            type_definitions.extend(new_type_definitions)

            found_names = self._get_name_of_elements(new_container, new_enums, new_type_definitions)
            known_type_names = known_type_names.union(found_names)

            referenced_names = self._get_referenced_type_names(new_container, new_type_definitions)
            left_needed_type_names = needed_type_names.difference(found_names)

            needed_type_names = left_needed_type_names.union(referenced_names).difference(known_type_names)
            needed_type_names = needed_type_names.difference(self.externally_known_type_name)

        return replace(module,
                       container=containers,
                       enums=enums,
                       type_definitions=type_definitions)

    @staticmethod
    def _get_name_of_elements(
            containers: list[Container],
            enums: list[Enum],
            type_definitions: list[TypeDefinition]
    ) -> list[str]:
        return [container.name for container in containers] + \
               [enum.name for enum in enums] + \
               [type_definition.name for type_definition in type_definitions]

    def _get_referenced_type_names(self, containers: list[Container], type_definitions: list[TypeDefinition]) -> set[str]:
        referenced_base_types = [get_base_type(typ)
                                 for container in containers
                                 for typ in self._get_referenced_types(container)]
        referenced_base_types += [get_base_type(type_definition.for_type)
                                  for type_definition in type_definitions]

        referenced_function_types = self._get_function_types(referenced_base_types)
        while len(referenced_function_types) > 0:
            function_referenced_base_types = self._get_referenced_base_types(referenced_function_types)
            referenced_function_types = self._get_function_types(function_referenced_base_types)
            referenced_base_types += function_referenced_base_types

        return set([get_base_type_name(typ)
                    for typ in referenced_base_types
                    if not isinstance(typ, FunctionType)])

    @staticmethod
    def _get_function_types(types: list[Type]) -> list[FunctionType]:
        return [typ for typ in types if isinstance(typ, FunctionType)]

    @staticmethod
    def _get_referenced_base_types(function_types: list[FunctionType]) -> list[Type]:
        return [get_base_type(param.type)
                for function_type in function_types
                for param in function_type.params]

    @staticmethod
    def _find_needed_container(all_container: list[Container], needed_type_names: set[str]) -> list[Container]:
        return [container for container in all_container if container.name in needed_type_names]

    @staticmethod
    def _find_needed_enums(all_enums: list[Enum], needed_type_names: set[str]) -> list[Enum]:
        return [enum for enum in all_enums if enum.name in needed_type_names]

    @staticmethod
    def _find_needed_type_definitions(
            all_type_definitions: list[TypeDefinition],
            needed_type_names: set[str]
    ) -> list[TypeDefinition]:
        return [type_definition
                for type_definition in all_type_definitions if type_definition.name in needed_type_names]

    @staticmethod
    def _get_referenced_types_of_union(union: Union) -> list[Type]:
        return [property.type for property in union.properties]

    @staticmethod
    def _get_referenced_types(container: Container) -> list[Type]:
        inner_container_names = [inner_container.name for inner_container in container.inner_containers]
        types: list[Type] = [property.type
                             for property in container.properties
                             if not isinstance(get_base_type(property.type), InlineDeclaration)
                             or get_base_type_name(property.type) not in inner_container_names]
        for inner_container in container.inner_containers:
            types.extend(ModuleCleaner._get_referenced_types(inner_container))
        return types

    @staticmethod
    def _get_field_types(module: Module) -> list[Type]:
        return [field.type for field in module.fields]

    @staticmethod
    def _get_method_types(module: Module) -> list[Type]:
        types: list[Type] = []
        for method in module.methods:
            types.append(method.return_type)
            types += [parameter.type for parameter in method.parameter]
        return types

    @staticmethod
    def _get_list_of_base_type_names(types: list[Type]) -> list[str]:
        return [get_base_type_name(typ) for typ in types]
