from dataclasses import dataclass, replace
from typing import Optional


@dataclass
class Node:
    key: str
    dependencies: list[str]
    data: Optional


@dataclass(frozen=True)
class SorterResult:
    sorted_list: list[Node]

@dataclass(frozen=True)
class CircularDependency(SorterResult):
    remaining_graph: list[Node]

@dataclass(frozen=True)
class Sorted(SorterResult):
    pass


class TopologicalSorter:
    def sort(self, graph: list[Node]) -> SorterResult:
        sorted_list: list[Node] = []
        remaining_graph = graph

        while True:
            independent = [node for node in remaining_graph if len(node.dependencies) == 0]
            if len(independent) == 0:
                return CircularDependency(sorted_list, remaining_graph)
            sorted_list += independent
            independent_keys = [node.key for node in independent]
            remaining_graph = [self._remove_nodes_from_dependencies(node, independent_keys)
                               for node in remaining_graph
                               if len(node.dependencies) > 0]
            if len(remaining_graph) == 0:
                break
        if len(graph) != len(sorted_list):
            raise Exception("Something went horribly wrong, we lost some items while sorting them")

        return Sorted(sorted_list)

    @staticmethod
    def _remove_nodes_from_dependencies(node: Node, to_be_removed_dependencies: list[str]) -> Node:
        return replace(node,
                       dependencies=[dependency
                                     for dependency in node.dependencies
                                     if dependency not in to_be_removed_dependencies]
                       )
