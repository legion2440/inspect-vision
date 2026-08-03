from __future__ import annotations

import json

from scripts.validate_architecture import _check_javascript_imports, _check_python_imports


def test_backend_python_imports_follow_dependency_graph() -> None:
    with open("module-map.json", encoding="utf-8") as module_map_file:
        module_map = json.load(module_map_file)
    with open("dependency-graph.json", encoding="utf-8") as graph_file:
        graph = json.load(graph_file)
    errors: list[str] = []

    _check_python_imports(module_map, graph, errors)
    _check_javascript_imports(module_map, graph, errors)

    assert errors == []
