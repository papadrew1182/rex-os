"""Process-wide registry of connector adapter classes.

Maps connector_key (e.g. 'procore', 'exxir') to ConnectorAdapter
subclass. Populated at import time by each adapter subpackage via
`register_adapter`. The sync_service and control-plane endpoints look
up an adapter class by key, then instantiate it per account.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from app.services.connectors.base import ConnectorAdapter


class ConnectorRegistry:
    """Keyed registry of adapter classes.

    Not a singleton class — the module-level ``_registry`` is the one
    process-wide instance. ``get_registry()`` returns it. Tests can
    construct their own instance if they want isolation.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, Type["ConnectorAdapter"]] = {}

    def register(self, connector_key: str, adapter_cls: Type["ConnectorAdapter"]) -> None:
        """Register an adapter class under its connector_key."""
        if connector_key in self._by_key and self._by_key[connector_key] is not adapter_cls:
            raise ValueError(
                f"Connector key '{connector_key}' is already registered to "
                f"{self._by_key[connector_key].__name__}; refusing to overwrite "
                f"with {adapter_cls.__name__}"
            )
        self._by_key[connector_key] = adapter_cls

    def get(self, connector_key: str) -> Type["ConnectorAdapter"]:
        try:
            return self._by_key[connector_key]
        except KeyError as exc:
            raise KeyError(
                f"No connector adapter registered for key '{connector_key}'. "
                f"Registered: {sorted(self._by_key.keys())}"
            ) from exc

    def keys(self) -> list[str]:
        return sorted(self._by_key.keys())

    def __contains__(self, key: str) -> bool:
        return key in self._by_key


_registry = ConnectorRegistry()


def get_registry() -> ConnectorRegistry:
    """Return the process-wide connector registry."""
    return _registry


def register_adapter(connector_key: str, adapter_cls: Type["ConnectorAdapter"]) -> None:
    """Module-level convenience wrapper around ``_registry.register``."""
    _registry.register(connector_key, adapter_cls)


__all__ = ["ConnectorRegistry", "get_registry", "register_adapter"]
