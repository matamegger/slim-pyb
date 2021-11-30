from dataclasses import replace

from astparser import get_base_type_name, Type, InlineStructType, get_base_type, FunctionType, InlineUnionType, \
    InlineDeclaration
from astparser.model import Module, Struct, Enum, TypeDefinition, Union


class ModuleCleaner:
    externally_known_type_name: list[str] = []

    def remove_not_used_elements(self, module: Module) -> Module:
        needed_type_names: set[str] = set[str]()
        known_type_names: set[str] = set[str]()

        structs: list[Struct] = []
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

            new_structs = self._find_needed_structs(module.structs, needed_type_names)
            new_enums = self._find_needed_enums(module.enums, needed_type_names)
            new_type_definitions = self._find_needed_type_definitions(module.type_definitions, needed_type_names)

            structs.extend(new_structs)
            enums.extend(new_enums)
            type_definitions.extend(new_type_definitions)

            found_names = self._get_name_of_elements(new_structs, new_enums, new_type_definitions)
            known_type_names = known_type_names.union(found_names)

            referenced_names = self._get_referenced_type_names(new_structs, new_type_definitions)
            left_needed_type_names = needed_type_names.difference(found_names)

            needed_type_names = left_needed_type_names.union(referenced_names).difference(known_type_names)
            needed_type_names = needed_type_names.difference(self.externally_known_type_name)

        return replace(module,
                       structs=structs,
                       enums=enums,
                       type_definitions=type_definitions)

    @staticmethod
    def _get_name_of_elements(
            structs: list[Struct],
            enums: list[Enum],
            type_definitions: list[TypeDefinition]
    ) -> list[str]:
        return [struct.name for struct in structs] + \
               [enum.name for enum in enums] + \
               [type_definition.name for type_definition in type_definitions]

    def _get_referenced_type_names(self, structs: list[Struct], type_definitions: list[TypeDefinition]) -> set[str]:
        referenced_base_types = [get_base_type(typ)
                                 for struct in structs
                                 for typ in self._get_referenced_types(struct)]
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
    def _find_needed_structs(all_structs: list[Struct], needed_type_names: set[str]) -> list[Struct]:
        return [struct for struct in all_structs if struct.name in needed_type_names]

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
    def _get_referenced_types(struct: Struct) -> list[Type]:
        inner_struct_names = [inner_struct.name for inner_struct in struct.inner_structs]
        inner_union_names = [inner_union.name for inner_union in struct.inner_unions]
        inner_type_names = inner_struct_names + inner_union_names
        types: list[Type] = [property.type
                             for property in struct.properties
                             if not isinstance(get_base_type(property.type), InlineDeclaration)
                                  or get_base_type_name(property.type) not in inner_type_names]
        for inner_struct in struct.inner_structs:
            types.extend(ModuleCleaner._get_referenced_types(inner_struct))
        for inner_union in struct.inner_unions:
            types.extend(ModuleCleaner._get_referenced_types_of_union(inner_union))
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
