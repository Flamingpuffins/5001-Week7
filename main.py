#!/usr/bin/env python3
"""
GitHub Repository Agent - Week 7 Assignment
Implements: MCP for tooling, A2A for agent-to-agent communication
Patterns: Planning, Tool Use, Reflection, Multi-Agent
"""

import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from a2a.bus import AgentBus
from agents.reviewer import ReviewerAgent
from agents.planner import PlannerAgent
from agents.writer import WriterAgent
from agents.gatekeeper import GatekeeperAgent

console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold cyan]GitHub Repository Agent[/bold cyan]\n"
        "[dim]Week 7: MCP + A2A Agentic Protocols[/dim]\n"
        "[dim]Patterns: Planning · Tool Use · Reflection · Multi-Agent[/dim]",
        border_style="cyan"
    ))


def print_menu():
    console.print("\n[bold]What would you like to do?[/bold]")
    console.print("  [cyan]1[/cyan]  Review recent changes (git diff)")
    console.print("  [cyan]2[/cyan]  Draft and create a GitHub Issue")
    console.print("  [cyan]3[/cyan]  Draft and create a GitHub PR")
    console.print("  [cyan]4[/cyan]  Improve an existing Issue or PR")
    console.print("  [cyan]q[/cyan]  Quit\n")


async def run_task(task_id: str, **kwargs):
    """Spin up agents and route a task through the A2A bus."""
    bus = AgentBus()

    reviewer   = ReviewerAgent(bus)
    planner    = PlannerAgent(bus)
    writer     = WriterAgent(bus)
    gatekeeper = GatekeeperAgent(bus)

    bus.register("reviewer",   reviewer)
    bus.register("planner",    planner)
    bus.register("writer",     writer)
    bus.register("gatekeeper", gatekeeper)

    # Kick off the pipeline — Reviewer always goes first
    result = await bus.send("reviewer", {
        "task": task_id,
        **kwargs
    })
    return result


async def main():
    print_banner()

    # Config
    repo_path = Prompt.ask(
        "[bold]Repo path[/bold]",
        default="./sample_repo"
    )
    github_repo = Prompt.ask(
        "[bold]GitHub repo[/bold] (owner/repo)",
        default="myuser/my-repo"
    )
    github_token = Prompt.ask(
        "[bold]GitHub PAT[/bold]",
        password=True
    )

    config = {
        "repo_path":    repo_path,
        "github_repo":  github_repo,
        "github_token": github_token,
    }

    while True:
        print_menu()
        choice = Prompt.ask("[bold cyan]Choice[/bold cyan]").strip().lower()

        if choice == "q":
            console.print("\n[dim]Goodbye.[/dim]\n")
            break

        elif choice == "1":
            commit_range = Prompt.ask(
                "Commit range",
                default="HEAD~1..HEAD"
            )
            await run_task("review_changes",
                           commit_range=commit_range, **config)

        elif choice == "2":
            instruction = Prompt.ask(
                "Describe the issue",
                default="Create an issue for missing input validation in login API."
            )
            await run_task("create_issue",
                           instruction=instruction, **config)

        elif choice == "3":
            instruction = Prompt.ask(
                "Describe the PR",
                default="Create a PR to refactor duplicated pricing logic."
            )
            await run_task("create_pr",
                           instruction=instruction, **config)

        elif choice == "4":
            item_type = Prompt.ask("Type", choices=["issue", "pr"])
            item_number = Prompt.ask(f"{'Issue' if item_type=='issue' else 'PR'} number")
            await run_task("improve_item",
                           item_type=item_type,
                           item_number=int(item_number),
                           **config)

        else:
            console.print("[red]Unknown option.[/red]")


if __name__ == "__main__":
    asyncio.run(main())
