"""
GATEKEEPER AGENT
================
Role: Safety enforcement + human approval gate.

Responsibilities:
  1. Show the full draft to the user
  2. Check for policy violations
  3. Require explicit human approval
  4. On approval: create via MCP GitHub tools
  5. On rejection: abort cleanly — nothing is created

This is the ONLY agent that calls github_create_issue / github_create_pr.
"""

from __future__ import annotations
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm, Prompt

from agents.base import BaseAgent
from a2a.bus import A2AMessage

console = Console()


class GatekeeperAgent(BaseAgent):

    async def handle(self, msg: A2AMessage) -> Any:
        task   = msg.payload.get("task")
        draft  = msg.payload.get("draft")
        config = msg.payload

        console.print(Panel(
            "[bold red]GATEKEEPER AGENT[/bold red]  —  Safety check & human approval",
            border_style="red"
        ))

        if draft is None:
            console.print("[yellow]No draft received — nothing to approve.[/yellow]")
            return {"status": "no_draft"}

        # Improvement suggestions are shown but never auto-pushed
        if draft.draft_type == "improvement_suggestion":
            self._show_suggestion(draft)
            return {"status": "suggestion_shown"}

        # Policy check
        violations = self._policy_check(draft)
        if violations:
            console.print(Panel(
                "\n".join(f"[red]⚠ {v}[/red]" for v in violations),
                title="[bold red]Policy Violations — BLOCKED[/bold red]",
                border_style="red"
            ))
            return {"status": "blocked", "violations": violations}

        # Show full draft
        self._show_draft(draft)

        # Human approval
        console.print("\n[bold red]⚠  HUMAN APPROVAL REQUIRED[/bold red]")
        console.print("[dim]Review the draft above carefully before approving.[/dim]\n")

        approved = Confirm.ask("[bold]Approve and create on GitHub?[/bold]", default=False)

        if not approved:
            console.print(
                Panel("[yellow]❌ Rejected by user — nothing was created on GitHub.[/yellow]",
                      border_style="yellow")
            )
            return {"status": "rejected"}

        # Create on GitHub via MCP
        result = await self._create(draft, config)
        return result

    def _policy_check(self, draft) -> list[str]:
        """Basic policy checks before showing draft to user."""
        violations = []
        if not draft.title or len(draft.title.strip()) < 5:
            violations.append("Title is too short or empty.")
        if not draft.body or len(draft.body.strip()) < 20:
            violations.append("Body is too short — likely incomplete draft.")
        if "TODO" in draft.title.upper():
            violations.append("Title contains TODO — likely a placeholder.")
        return violations

    def _show_draft(self, draft):
        draft_type_label = "ISSUE" if draft.draft_type == "issue" else "PULL REQUEST"
        console.print(Panel(
            f"[bold]Type:[/bold] {draft_type_label}\n"
            f"[bold]Title:[/bold] {draft.title}\n"
            f"[bold]Labels:[/bold] {', '.join(draft.labels) if draft.labels else 'none'}"
            + (f"\n[bold]Head → Base:[/bold] {draft.head_branch} → {draft.base_branch}"
               if draft.draft_type == "pr" else ""),
            title="[bold]Draft Preview[/bold]",
            border_style="blue"
        ))
        console.print("\n[bold]Body:[/bold]")
        try:
            console.print(Markdown(draft.body))
        except Exception:
            console.print(draft.body)

    def _show_suggestion(self, draft):
        console.print(Panel(
            "[bold]Improvement Suggestion (read-only — not pushed to GitHub)[/bold]",
            border_style="cyan"
        ))
        console.print(f"[bold]Subject:[/bold] {draft.title}\n")
        try:
            console.print(Markdown(draft.body))
        except Exception:
            console.print(draft.body)

    async def _create(self, draft, config: dict) -> dict:
        token = config.get("github_token", "")
        grepo = config.get("github_repo", "")

        if draft.draft_type == "issue":
            console.print("\n[dim]Creating issue via MCP[github_create_issue]...[/dim]")
            result = self.mcp.call(
                "github_create_issue",
                github_repo=grepo,
                github_token=token,
                title=draft.title,
                body=draft.body,
                labels=draft.labels,
            )
            if "error" in result:
                console.print(f"[red]GitHub API error: {result}[/red]")
                return {"status": "error", "detail": result}

            url = result.get("html_url", "")
            console.print(Panel(
                f"[bold green]✅ Issue created![/bold green]\n{url}",
                border_style="green"
            ))
            return {"status": "created", "type": "issue", "url": url, "data": result}

        elif draft.draft_type == "pr":
            console.print("\n[dim]Creating PR via MCP[github_create_pr]...[/dim]")
            result = self.mcp.call(
                "github_create_pr",
                github_repo=grepo,
                github_token=token,
                title=draft.title,
                body=draft.body,
                head=draft.head_branch or "feature/agent-draft",
                base=draft.base_branch,
            )
            if "error" in result:
                console.print(f"[red]GitHub API error: {result}[/red]")
                return {"status": "error", "detail": result}

            url = result.get("html_url", "")
            console.print(Panel(
                f"[bold green]✅ PR created![/bold green]\n{url}",
                border_style="green"
            ))
            return {"status": "created", "type": "pr", "url": url, "data": result}

        return {"status": "unknown_type"}
