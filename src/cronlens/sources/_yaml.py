"""Small helpers over PyYAML's node API.

Working with nodes rather than loaded objects keeps line numbers for
reporting, and avoids YAML 1.1 turning a bare ``on:`` key into ``True``.
"""

from __future__ import annotations

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

__all__ = ["compose_documents", "error_line", "get", "items", "line_of", "scalar"]


def compose_documents(text: str) -> list[Node]:
    return [doc for doc in yaml.compose_all(text, Loader=yaml.SafeLoader) if doc is not None]


def get(node: Node | None, key: str) -> Node | None:
    """Return the value node for ``key`` in a mapping node, or None."""
    if not isinstance(node, MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == key:
            found: Node = value_node
            return found
    return None


def scalar(node: Node | None) -> str | None:
    """Return a scalar node's text, or None for anything else."""
    if isinstance(node, ScalarNode):
        return str(node.value)
    return None


def items(node: Node | None) -> list[Node]:
    if isinstance(node, SequenceNode):
        return list(node.value)
    return []


def line_of(node: Node) -> int:
    return int(node.start_mark.line) + 1


def error_line(error: yaml.YAMLError) -> int:
    mark = getattr(error, "problem_mark", None) or getattr(error, "context_mark", None)
    return int(mark.line) + 1 if mark is not None else 1
