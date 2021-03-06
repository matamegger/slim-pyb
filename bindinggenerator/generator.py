from dataclasses import replace
from typing import Callable, TypeVar, Union

import bindinggenerator.model
from astparser.model import Module, TypeDefinition, Struct, Enum, Property, Union as AstParserUnion, Container
from astparser.types import *
from bindinggenerator.model import BindingFile, CtypeContainer, CtypeContainerDefinition, CtypeContainerDeclaration, \
    CtypeContainerType, CtypeContainerElement, CtypeContainerProperty, CtypeFieldType, NamedCtypeFieldType, \
    SplittableElement, CtypeFieldPointer, CtypeFieldTypeArray, CtypeFieldFunctionPointer, Enum as EnumElement, \
    EnumEntry as EnumElementEntry, Definition, Import, Element, get_base_type_names
from topologicalsort import Node, TopologicalSorter, CircularDependency, Sorted


def _get_name_of_type(typ: CtypeFieldType) -> Optional[str]:
    if isinstance(typ, NamedCtypeFieldType):
        return typ.name
    else:
        return None


class PythonCodeElementGraphCreator:
    already_resolved_dependencies: set[str] = set()

    def create(self, elements: list[Element]) -> list[Node]:
        return [self._create_node(element, elements) for element in elements]

    @staticmethod
    def _get_elements_by_name(name: str, elements: list[Element]) -> list[Element]:
        return list(filter(lambda it: it.name == name, elements))

    def _get_recursive_direct_dependencies(self, element: Element, elements: list[Element]):
        if isinstance(element, CtypeContainerElement):
            return [self._mark_as_direct_dependency_name(element.name)]
        elif isinstance(element, bindinggenerator.model.Enum):
            return []
        elif isinstance(element, Definition):
            direct_dependency = _get_name_of_type(element.for_type)
            dependencies = [element.name]
            if direct_dependency is not None:
                found = self._get_elements_by_name(direct_dependency, elements)
                if len(found) == 0:
                    if direct_dependency not in self.already_resolved_dependencies:
                        raise Exception("Missing dependency already when building the graph")
                    else:
                        # print(f"No element for {direct_dependency}, but it is already resolved")
                        pass
                else:
                    dependencies += self._get_recursive_direct_dependencies(found[0], elements)

            return dependencies
        else:
            raise Exception("Unhandled case")

    def _create_node(
            self,
            element: Element,
            elements: list[Element]
    ) -> Node:
        if isinstance(element, Definition):
            return Node(
                keys=[element.name],
                dependencies=get_base_type_names(element.for_type),
                data=element
            )
        elif isinstance(element, CtypeContainerDefinition):
            keys = [self._mark_as_direct_dependency_name(element.name)]
            dependencies = self._get_dependencies(element)
            direct_dependencies = self._get_direct_ctype_dependencies(element)
            dependencies = [dependency
                            for dependency in dependencies
                            if dependency not in direct_dependencies and
                            dependency not in self.already_resolved_dependencies]
            dependencies += [d
                             for dependency in direct_dependencies
                             for element in self._get_elements_by_name(dependency, elements)
                             for d in self._get_recursive_direct_dependencies(element, elements)]
            if not isinstance(element, CtypeContainer):
                dependencies.append(element.name)
            else:
                keys.append(element.name)
            return Node(
                keys=keys,
                dependencies=list(set(dependencies)),
                data=element
            )
        elif isinstance(element, CtypeContainerDeclaration):
            return Node(
                keys=[element.name],
                dependencies=[],
                data=element
            )
        elif isinstance(element, bindinggenerator.model.Enum):
            return Node(
                keys=[element.name],
                dependencies=[],
                data=element
            )
        else:
            raise Exception(f"Unhandled element type {element}")

    @staticmethod
    def _mark_as_direct_dependency_name(regular_name: str) -> str:
        return f"__{regular_name}__complete"

    @staticmethod
    def _get_direct_ctype_dependencies(declaration: CtypeContainerDefinition) -> list[str]:
        return [_get_name_of_type(field.type) for field in declaration.properties
                if _get_name_of_type(field.type) is not None]

    @staticmethod
    def _get_dependencies(declaration: Union[CtypeContainerDefinition]) -> list[str]:
        return [type_name
                for field in declaration.properties
                for type_name in get_base_type_names(field.type)]


class ElementArranger:
    def arrange(
            self,
            elements: list[Element],
            external_dependency_names: list[str],
            resolve_circular_dependencies: bool = True
    ) -> list[Element]:
        sorter = TopologicalSorter()
        graph_creator = PythonCodeElementGraphCreator()
        resolved_dependencies = set(external_dependency_names)
        sorter.ignore_names = resolved_dependencies
        graph_creator.already_resolved_dependencies = resolved_dependencies
        graph = graph_creator.create(elements)

        sorted_nodes: list[Node] = []
        splits = 0
        additional_elements = 0
        while True:
            sorter_result = sorter.sort(graph)
            newly_sorted_nodes = self._flatten(sorter_result.sorted_list)
            sorted_nodes += newly_sorted_nodes
            if isinstance(sorter_result, CircularDependency):
                if not resolve_circular_dependencies:
                    raise Exception("Circular dependency detected")
                new_elements: list[Element] = [node.data for node in sorter_result.remaining_graph]
                before = len(new_elements)
                new_elements = self._split_one_element(new_elements)
                splits += 1
                additional_elements += len(new_elements) - before
                resolved_dependencies = resolved_dependencies.union(self._flatten([node.keys
                                                                                   for node in newly_sorted_nodes]))
                sorter.ignore_names = resolved_dependencies
                graph_creator.already_resolved_dependencies = resolved_dependencies
                graph = graph_creator.create(new_elements)
            elif isinstance(sorter_result, Sorted):
                break

        ordered_elements = [node.data for node in sorted_nodes]

        if len(ordered_elements) != len(elements) + additional_elements:
            raise Exception("Error while sorting elements had " +
                            f"{len(elements) + additional_elements} but now are {len(ordered_elements)}")
        return ordered_elements

    T = TypeVar('T')

    @staticmethod
    def _flatten(list_in_list: list[list[T]]) -> list[T]:
        return [item for sublist in list_in_list for item in sublist]

    def _split_one_element(self, elements: list[Element]) -> list[Element]:
        splittable_elements = [element for element in elements if isinstance(element, SplittableElement)]
        not_splittable_elements = [element for element in elements if not isinstance(element, SplittableElement)]

        if len(splittable_elements) == 0:
            raise Exception("No element to split")

        return not_splittable_elements + splittable_elements[0].split() + splittable_elements[1:]


class AstTypeConverter:
    type_remapping_map: dict[str, str] = {}

    def convert(self, typ: Type) -> CtypeFieldType:
        if isinstance(typ, InlineDeclaration) or isinstance(typ, NamedType):
            name = typ.name
            if name in self.type_remapping_map:
                name = self.type_remapping_map[name]
            return NamedCtypeFieldType(
                name=name
            )
        elif isinstance(typ, Pointer):
            # We do not need to wrap the function in a pointer
            # as it is always a function pointer
            # TODO actually this is a design flaw in the parser !?
            if isinstance(typ.of, FunctionType):
                return CtypeFieldFunctionPointer(
                    return_type=self.convert(typ.of.return_type),
                    parameter_types=[self.convert(parameter.type) for parameter in typ.of.params]
                )
            return CtypeFieldPointer(
                of=self.convert(typ.of)
            )
        elif isinstance(typ, Array):
            return CtypeFieldTypeArray(
                of=self.convert(typ.of),
                size=typ.size
            )
        else:
            raise Exception(f"Unhandled type {typ}")


class PythonBindingFileGenerator:
    __type_converter: AstTypeConverter

    def generate(self, module: Module, name: str, type_converter: AstTypeConverter) -> BindingFile:
        self.__type_converter = type_converter
        imports = [
            Import(None, ["ctypes"]),
            Import("enum", ["Enum"])
        ]
        enum_type_definitions = self._create_primitive_type_definitions_for_enums(module.enums)
        elements = [self._create_element_from_type_definition(type_definition)
                    for type_definition in enum_type_definitions]
        type_converter.type_remapping_map = {enum.name: self._ctypes_enum_name(enum) for enum in module.enums}
        elements += [self._create_element_from_type_definition(type_definition)
                     for type_definition in module.type_definitions]
        elements += [self._create_element_from_enum(enum) for enum in module.enums]

        containers = [self._add_container_name_prefix_to_inner_container(container) for container in module.container]
        containers += [inner_container for container in containers for inner_container in container.inner_containers]
        elements += [self._create_element_from_container(container) for container in containers]

        return BindingFile(
            name=f"{name}.py",
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
        return self.__type_converter.convert(typ)

    def __add_prefix_to_struct_base_type(self, typ: Type, prefix: str, condition: Callable[[str], bool]) -> Type:
        if isinstance(typ, InlineDeclaration):
            name = typ.name
            if condition(name):
                name = prefix + name
            return replace(typ, name=name)
        elif isinstance(typ, NamedType):
            return typ
        elif isinstance(typ, Pointer) or isinstance(typ, Array):
            of = self.__add_prefix_to_struct_base_type(typ.of, prefix, condition)
            return replace(typ, of=of)
        elif isinstance(typ, FunctionType):
            return typ
        else:
            raise Exception(f"Unhandled type {typ}")

    def _add_container_name_prefix_to_inner_container(self, container: Container) -> Container:
        old_inner_container_names: list[str] = [inner_struct.name for inner_struct in container.inner_containers]
        inner_containers: list[Container] = []
        for inner_container in container.inner_containers:
            inner_container = replace(inner_container, name=f"{container.name}_{inner_container.name}")
            inner_containers.append(self._add_container_name_prefix_to_inner_container(inner_container))

        properties: list[Property] = []
        for property in container.properties:
            new_property_type = self.__add_prefix_to_struct_base_type(
                property.type,
                f"{container.name}_",
                lambda it: it in old_inner_container_names
            )
            properties.append(replace(property, type=new_property_type))

        return replace(container, inner_containers=inner_containers, properties=properties)

    def _create_element_from_container(self, container: Container) -> Element:
        container_type = self.__get_container_type(container)
        return CtypeContainer(
            name=container.name,
            properties=[CtypeContainerProperty(name=property.name, type=self._convert_type(property.type))
                        for property in container.properties],
            container_type=container_type
        )

    def __get_container_type(self, container: Container) -> CtypeContainerType:
        if isinstance(container, Struct):
            return CtypeContainerType.STRUCT
        if isinstance(container, AstParserUnion):
            return CtypeContainerType.UNION
        raise Exception(f"Unknown container type: {type(container)}")

    @staticmethod
    def _create_element_from_enum(enum: Enum) -> EnumElement:
        return EnumElement(
            name=enum.name,
            entries=[EnumElementEntry(name=entry.name, value=entry.value) for entry in enum.entries]
        )

    def _create_element_from_type_definition(self, type_definition: TypeDefinition) -> Definition:
        return Definition(
            name=type_definition.name,
            for_type=self._convert_type(type_definition.for_type)
        )
