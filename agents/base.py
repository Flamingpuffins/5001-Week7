from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from mcp.tools import mcp

if TYPE_CHECKING:
    from a2a.bus import A2AMessage, AgentBus


class BaseAgent(ABC):
    def __init__(self, bus):
        self.bus = bus
        self.name = "unnamed"
        self.mcp = mcp

    async def send(self, recipient: str, payload: dict) -> Any:
        payload["_from"] = self.name
        return await self.bus.send(recipient, payload, sender=self.name)

    @abstractmethod
    async def handle(self, msg) -> Any: ...
