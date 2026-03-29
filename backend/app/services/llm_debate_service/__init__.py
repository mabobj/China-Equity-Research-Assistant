"""LLM debate service package.

Runtime assembly must import concrete submodules directly instead of relying on
package-level re-exports. This keeps dependency wiring explicit and avoids
accidental circular imports during app startup.
"""

__all__: list[str] = []
