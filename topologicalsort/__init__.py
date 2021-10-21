from dataclasses import dataclass
from typing import Optional


@dataclass
class Node:
    keys: list[str]
    dependencies: list[str]
    data: Optional


@dataclass(frozen=True)
class SorterResult:
    sorted_list: list[list[Node]]


@dataclass(frozen=True)
class CircularDependency(SorterResult):
    remaining_graph: list[Node]


@dataclass(frozen=True)
class Sorted(SorterResult):
    pass


class TopologicalSorter:
    ignore_names: set[str] = set()

    def sort(self, graph: list[Node]) -> SorterResult:
        sorted_list: list[list[Node]] = []
        remaining_graph = graph
        eliminated_dependencies = self.ignore_names.copy()

        while True:
            independent = [node for node in remaining_graph
                           if self._get_filtered_dependency_count(node, eliminated_dependencies) == 0]
            if len(independent) == 0:
                return CircularDependency(sorted_list, remaining_graph)
            sorted_list.append(independent)
            independent_keys = [key for node in independent for key in node.keys]
            remaining_graph = [node
                               for node in remaining_graph
                               if self._get_filtered_dependency_count(node, eliminated_dependencies) > 0]
            eliminated_dependencies.update(independent_keys)

            if len(remaining_graph) == 0:
                break

        sorted_count = 0
        for sub_list in sorted_list:
            sorted_count += len(sub_list)
        if len(graph) != sorted_count:
            raise Exception("Something went horribly wrong, we lost some items while sorting them")

        return Sorted(sorted_list)

    def _get_filtered_dependency_count(self, node: Node, names_to_be_ignored: set[str]) -> int:
        return len(self._filter_dependencies(node.dependencies, names_to_be_ignored))

    @staticmethod
    def _filter_dependencies(dependencies: list[str], names_to_be_ignored: set[str]):
        return [dependency for dependency in dependencies if dependency not in names_to_be_ignored]
