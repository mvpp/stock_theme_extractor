"""Standalone theme taxonomy tree — no dependency on stock_themes."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from pathlib import Path

import yaml

from themes_api import config

logger = logging.getLogger(__name__)


class ThemeTree:
    """Parent-child hierarchy for canonical themes."""

    def __init__(self, parent_map: dict[str, str | None]):
        self._parent_map = parent_map
        self._children_map: dict[str, list[str]] = defaultdict(list)
        for child, parent in self._parent_map.items():
            if parent is not None:
                self._children_map[parent].append(child)
        self._depth_cache: dict[str, int] = {}

    @classmethod
    def from_yaml(cls, path: Path) -> ThemeTree:
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        parent_map: dict[str, str | None] = {}

        def _walk(node: dict, parent: str | None) -> None:
            for name, children in node.items():
                name = name.strip().lower()
                parent_map[name] = parent
                if isinstance(children, dict) and children:
                    _walk(children, name)

        _walk(data, None)
        return cls(parent_map)

    @classmethod
    def empty(cls) -> ThemeTree:
        return cls({})

    def has_themes(self) -> bool:
        return bool(self._parent_map)

    def __contains__(self, theme: str) -> bool:
        return theme in self._parent_map

    def get_root(self, theme: str) -> str | None:
        if theme not in self._parent_map:
            return None
        current = theme
        while self._parent_map.get(current) is not None:
            current = self._parent_map[current]
        return current

    def get_family(self, theme: str) -> str | None:
        return self.get_root(theme)

    def get_ancestors(self, theme: str) -> list[str]:
        if theme not in self._parent_map:
            return []
        result = []
        current = self._parent_map.get(theme)
        while current is not None:
            result.append(current)
            current = self._parent_map.get(current)
        return result

    def get_descendants(self, theme: str) -> list[str]:
        if theme not in self._parent_map and theme not in self._children_map:
            return []
        result = []
        queue = deque(self._children_map.get(theme, []))
        while queue:
            child = queue.popleft()
            result.append(child)
            queue.extend(self._children_map.get(child, []))
        return result

    def get_siblings(self, theme: str) -> list[str]:
        parent = self._parent_map.get(theme)
        if parent is None and theme in self._parent_map:
            return [t for t, p in self._parent_map.items() if p is None and t != theme]
        if parent is None:
            return []
        return [c for c in self._children_map.get(parent, []) if c != theme]

    def get_depth(self, theme: str) -> int:
        if theme not in self._parent_map:
            return -1
        if theme in self._depth_cache:
            return self._depth_cache[theme]
        depth = 0
        current = theme
        while self._parent_map.get(current) is not None:
            depth += 1
            current = self._parent_map[current]
        self._depth_cache[theme] = depth
        return depth

    def in_same_family(self, a: str, b: str) -> bool:
        root_a = self.get_root(a)
        root_b = self.get_root(b)
        if root_a is None or root_b is None:
            return False
        return root_a == root_b

    def themes_in_tree(self) -> set[str]:
        return set(self._parent_map.keys())


# --- Singleton ---

_tree: ThemeTree | None = None


def get_theme_tree() -> ThemeTree:
    """Get or lazily load the global ThemeTree singleton."""
    global _tree
    if _tree is None:
        taxonomy_path = Path(config.TAXONOMY_YAML_PATH)
        if taxonomy_path.exists():
            _tree = ThemeTree.from_yaml(taxonomy_path)
            logger.info(
                f"Loaded theme tree: {len(_tree._parent_map)} themes, "
                f"{sum(1 for v in _tree._parent_map.values() if v is None)} roots"
            )
        else:
            _tree = ThemeTree.empty()
            logger.debug("No taxonomy.yaml found — using empty theme tree")
    return _tree
