from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

AgentNode = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ForgePlugin:
    name: str
    capabilities: tuple[str, ...]
    required_env: tuple[str, ...] = ()
    approval_policy: str = "required"
    enabled_by_default: bool = True
    node_builder: Callable[[], AgentNode] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def register_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "plugin": self.name,
                "capabilities": list(self.capabilities),
                "required_env": list(self.required_env),
                "approval_policy": self.approval_policy,
                "enabled_by_default": self.enabled_by_default,
            }
        ]
