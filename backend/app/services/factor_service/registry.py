"""Minimal factor registry placeholder."""

from __future__ import annotations


class FactorRegistry:
    """Reserve a registry entrypoint for future multi-factor expansion."""

    def __init__(self) -> None:
        self._factor_names: list[str] = []

    def register(self, factor_name: str) -> None:
        if factor_name not in self._factor_names:
            self._factor_names.append(factor_name)

    def list_factor_names(self) -> list[str]:
        return list(self._factor_names)

