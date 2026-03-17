"""Hierarchical theme taxonomy tree for family-aware confidence pooling."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from pathlib import Path

import yaml

from stock_themes.taxonomy.themes import ALL_THEMES

logger = logging.getLogger(__name__)


class ThemeTree:
    """Parent-child hierarchy for canonical themes.

    Internal representation: flat parent_map where each theme maps to its
    parent (or None for roots).

    Example:
        "deep learning" -> "machine learning" -> "artificial intelligence" -> None
    """

    def __init__(self, parent_map: dict[str, str | None]):
        self._parent_map = parent_map
        # Build children map from parent map
        self._children_map: dict[str, list[str]] = defaultdict(list)
        for child, parent in self._parent_map.items():
            if parent is not None:
                self._children_map[parent].append(child)
        # Cache depths
        self._depth_cache: dict[str, int] = {}

    @classmethod
    def from_yaml(cls, path: Path) -> ThemeTree:
        """Load hierarchy from a YAML file.

        YAML format: nested dicts where keys are theme names and leaf nodes
        have empty dict {} as value.

        Example:
            artificial intelligence:
              generative ai:
                large language models: {}
              machine learning: {}
        """
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

        # Validate: warn about themes not in canonical taxonomy
        unknown = set(parent_map.keys()) - ALL_THEMES
        if unknown:
            logger.debug(
                f"ThemeTree: {len(unknown)} themes in taxonomy.yaml not in "
                f"ALL_THEMES (will still work for tree ops): "
                f"{sorted(unknown)[:10]}"
            )

        return cls(parent_map)

    @classmethod
    def empty(cls) -> ThemeTree:
        """Return a no-op tree with no themes."""
        return cls({})

    def has_themes(self) -> bool:
        """True if the tree has any themes defined."""
        return bool(self._parent_map)

    def __contains__(self, theme: str) -> bool:
        return theme in self._parent_map

    def get_root(self, theme: str) -> str | None:
        """Walk up the tree to find the root ancestor. Returns None if not in tree."""
        if theme not in self._parent_map:
            return None
        current = theme
        while self._parent_map.get(current) is not None:
            current = self._parent_map[current]
        return current

    def get_family(self, theme: str) -> str | None:
        """Alias for get_root — returns the family name (root ancestor)."""
        return self.get_root(theme)

    def get_ancestors(self, theme: str) -> list[str]:
        """Return [parent, grandparent, ..., root]. Empty if not in tree or is root."""
        if theme not in self._parent_map:
            return []
        result = []
        current = self._parent_map.get(theme)
        while current is not None:
            result.append(current)
            current = self._parent_map.get(current)
        return result

    def get_descendants(self, theme: str) -> list[str]:
        """Return all children, grandchildren, etc. via BFS. Empty if leaf or not in tree."""
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
        """Return themes sharing the same parent (excluding self)."""
        parent = self._parent_map.get(theme)
        if parent is None and theme in self._parent_map:
            # Root node — siblings are other roots
            return [t for t, p in self._parent_map.items() if p is None and t != theme]
        if parent is None:
            return []
        return [c for c in self._children_map.get(parent, []) if c != theme]

    def get_depth(self, theme: str) -> int:
        """Return depth: 0 for root, 1 for child of root, etc. -1 if not in tree."""
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
        """True if a and b share the same root ancestor."""
        root_a = self.get_root(a)
        root_b = self.get_root(b)
        if root_a is None or root_b is None:
            return False
        return root_a == root_b

    def themes_in_tree(self) -> set[str]:
        """All themes present in the hierarchy."""
        return set(self._parent_map.keys())


# --- Singleton ---

_tree: ThemeTree | None = None


def get_theme_tree() -> ThemeTree:
    """Get or lazily load the global ThemeTree singleton."""
    global _tree
    if _tree is None:
        # taxonomy.yaml lives in stock_themes/ (parent of taxonomy/)
        taxonomy_path = Path(__file__).parent.parent / "taxonomy.yaml"
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
