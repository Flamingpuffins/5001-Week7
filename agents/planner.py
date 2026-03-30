"""
PLANNER AGENT
=============
Role: Receive ReviewArtifact and decide the structured action plan.
Implements the Planning pattern explicitly.

Produces a PlanArtifact with:
  - decided action
  - structured plan steps
  - context for Writer
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
from rich.console import Console
from rich.panel import Panel
from anthropic import Anthropic

from agents.base import BaseAgent
from a2a.bus import A2AMessage

console = Console()
client  = Anthropic()


@dataclass
class PlanArtifact:
    action:       str          # create_issue | create_pr | improve_item | no_action
    context:      dict         # all data Writer needs
    plan_steps:   list[str]    # explicit plan steps
    rationale:    str


class PlannerAgent(BaseAgent):

    async def handle(self, msg: A2AMessage) -> Any:
        task     = msg.payload.get("task")
        artifact = msg.payload.get("artifact")   # ReviewArtifact or None
        config   = msg.payload

        console.print(Panel(
            "[bold green]PLANNER AGENT[/bold green]  —  Building action plan...",
            border_style="green"
        ))

        plan = await self._plan(task, artifact, config)

        self._print_plan(plan)

        # Hand off to Writer via A2A
        return await self.send("writer", {
            "task": task,
            "plan": plan,
            **{k: v for k, v in config.items() if k not in ("task", "artifact")},
        })

    async def _plan(self, task: str, artifact, config: dict) -> PlanArtifact:

        if task == "review_changes" and artifact:
            rec = artifact.recommendation
            plan_steps = [
                f"1. Action decided: {rec}",
                "2. Pass diff summary, issues, and reflection to Writer",
                "3. Writer drafts GitHub item",
                "4. Gatekeeper shows draft and requests human approval",
                "5. On approval: create via MCP GitHub tool",
            ]
            return PlanArtifact(
                action=rec,
                context={
                    "summary":        artifact.summary,
                    "issues":         artifact.issues,
                    "diff":           artifact.diff[:3000],
                    "files_changed":  artifact.files_changed,
                    "risk_level":     artifact.risk_level,
                    "change_type":    artifact.change_type,
                    "reflection":     artifact.reflection,
                    "justification":  artifact.justification,
                    "instruction":    config.get("instruction", ""),
                },
                plan_steps=plan_steps,
                rationale=artifact.justification,
            )

        elif task == "create_issue":
            return PlanArtifact(
                action="create_issue",
                context={"instruction": config.get("instruction", "")},
                plan_steps=[
                    "1. Writer receives explicit instruction",
                    "2. Writer drafts Issue with title, description, evidence, acceptance criteria, risk",
                    "3. Gatekeeper shows draft for human approval",
                    "4. On approval: create via MCP",
                ],
                rationale="Explicit user instruction to create issue.",
            )

        elif task == "create_pr":
            return PlanArtifact(
                action="create_pr",
                context={"instruction": config.get("instruction", "")},
                plan_steps=[
                    "1. Writer receives explicit instruction",
                    "2. Writer drafts PR with title, summary, files affected, test plan, risk",
                    "3. Gatekeeper shows draft for human approval",
                    "4. On approval: create via MCP",
                ],
                rationale="Explicit user instruction to create PR.",
            )

        elif task == "improve_item":
            return PlanArtifact(
                action="improve_item",
                context={
                    "item_type":   config.get("item_type"),
                    "item_number": config.get("item_number"),
                },
                plan_steps=[
                    "1. Fetch existing item via MCP[github_get_issue/pr]",
                    "2. Critique: identify unclear/missing information",
                    "3. Suggest improved structured version",
                    "4. Show suggestion to user (no auto-apply)",
                ],
                rationale="User wants to improve an existing issue/PR.",
            )

        return PlanArtifact(
            action="no_action",
            context={},
            plan_steps=["No action required."],
            rationale="Nothing to do.",
        )

    def _print_plan(self, plan: PlanArtifact):
        console.print(f"\n[bold]Action:[/bold] [cyan]{plan.action}[/cyan]")
        console.print(f"[bold]Rationale:[/bold] {plan.rationale[:200]}")
        console.print("[bold]Plan steps:[/bold]")
        for s in plan.plan_steps:
            console.print(f"  [dim]{s}[/dim]")
