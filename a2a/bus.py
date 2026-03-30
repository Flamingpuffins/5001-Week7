"""
A2A (Agent-to-Agent) Communication Bus
Implements the A2A protocol pattern for this assignment.

Each agent registers on the bus. Agents communicate by sending
structured messages to named peers. The bus routes, logs, and
delivers messages, producing a full audit trail.
"""

from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from rich.console import Console

console = Console()


@dataclass
class A2AMessage:
    """Structured message passed between agents."""
    sender:    str
    recipient: str
    task:      str
    payload:   Dict[str, Any]
    message_id: str = field(default_factory=lambda: f"msg-{int(time.time()*1000)}")
    timestamp:  float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "sender":     self.sender,
            "recipient":  self.recipient,
            "task":       self.task,
            "timestamp":  self.timestamp,
            "payload":    self.payload,
        }


class AgentBus:
    """
    Central A2A bus. Agents register here and communicate
    exclusively through this bus — no direct agent references.

    This satisfies the A2A protocol requirement: agents are
    decoupled and communicate via structured messages only.
    """

    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._log: list[A2AMessage] = []

    def register(self, name: str, agent) -> None:
        agent.name = name
        agent.bus  = self
        self._agents[name] = agent
        console.print(f"  [dim]🔌 A2A: '{name}' registered on bus[/dim]")

    async def send(self, recipient: str, payload: dict,
                   sender: str = "orchestrator") -> Any:
        """Route a message to a named agent and return its response."""
        if recipient not in self._agents:
            raise ValueError(f"Unknown agent: {recipient}")

        msg = A2AMessage(
            sender=sender,
            recipient=recipient,
            task=payload.get("task", "unknown"),
            payload=payload,
        )
        self._log.append(msg)

        console.print(
            f"\n[dim]📨 A2A [{msg.message_id}] "
            f"{msg.sender} → {msg.recipient} "
            f"(task={msg.task})[/dim]"
        )

        agent = self._agents[recipient]
        return await agent.handle(msg)

    def get_log(self) -> list[dict]:
        return [m.to_dict() for m in self._log]

    def print_trace(self) -> None:
        """Print full A2A message trace for the session."""
        console.print("\n[bold]A2A Message Trace:[/bold]")
        for m in self._log:
            console.print(
                f"  [cyan]{m.message_id}[/cyan]  "
                f"[yellow]{m.sender}[/yellow] → [green]{m.recipient}[/green]  "
                f"task=[bold]{m.task}[/bold]"
            )
