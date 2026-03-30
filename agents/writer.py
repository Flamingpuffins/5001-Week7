"""
WRITER AGENT
============
Role: Draft GitHub Issues and PRs based on PlanArtifact context.
Uses LLM to generate structured, complete drafts.
Also handles the "improve existing item" task (critique-then-suggest).
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Optional
from rich.console import Console
from rich.panel import Panel

from agents.base import BaseAgent
from a2a.bus import A2AMessage
from llm_client import llm

console = Console()


@dataclass
class DraftArtifact:
    draft_type:  str   # issue | pr | improvement_suggestion
    title:       str
    body:        str
    labels:      list[str]
    head_branch: Optional[str] = None   # PR only
    base_branch: str = "main"


class WriterAgent(BaseAgent):

    async def handle(self, msg: A2AMessage) -> Any:
        task   = msg.payload.get("task")
        plan   = msg.payload.get("plan")
        config = msg.payload

        console.print(Panel(
            "[bold magenta]WRITER AGENT[/bold magenta]  —  Drafting content...",
            border_style="magenta"
        ))

        action = plan.action if plan else task

        if action == "create_issue":
            draft = await self._draft_issue(plan.context, config)
        elif action == "create_pr":
            draft = await self._draft_pr(plan.context, config)
        elif action == "improve_item":
            draft = await self._improve_item(plan.context, config)
        elif action == "no_action":
            console.print("[green]✓ Reviewer determined: no action required.[/green]")
            return {"status": "no_action"}
        else:
            console.print(f"[yellow]Unknown action '{action}' — skipping draft.[/yellow]")
            return {"status": "skipped"}

        return await self.send("gatekeeper", {
            "task":   task,
            "draft":  draft,
            **{k: v for k, v in config.items() if k not in ("task", "plan")},
        })

    async def _draft_issue(self, context: dict, config: dict) -> DraftArtifact:
        instruction = context.get("instruction") or context.get("summary", "")
        issues      = context.get("issues", [])
        diff_snip   = context.get("diff", "")[:2000]
        reflection  = context.get("reflection", "")

        prompt = f"""Draft a GitHub Issue. Respond with ONLY valid JSON, no markdown fences.

Instruction / context:
{instruction}

Issues found in code review:
{json.dumps(issues, indent=2) if issues else "N/A"}

Diff excerpt:
{diff_snip if diff_snip else "N/A"}

Reflection notes:
{reflection if reflection else "N/A"}

Return this exact JSON:
{{
  "title": "clear, specific issue title",
  "body": "## Problem Description\\n...\\n## Evidence\\n...\\n## Acceptance Criteria\\n- [ ] ...\\n## Risk Level\\nlow|medium|high\\n\\n_Drafted by GitHub Agent_",
  "labels": ["bug", "needs-review"]
}}"""

        raw = self._clean_json(llm.chat(prompt, max_tokens=1200))
        try:
            data = json.loads(raw)
        except Exception:
            data = {"title": "Agent-drafted issue", "body": raw, "labels": []}

        return DraftArtifact(
            draft_type="issue",
            title=data.get("title", "Untitled"),
            body=data.get("body", ""),
            labels=data.get("labels", []),
        )

    async def _draft_pr(self, context: dict, config: dict) -> DraftArtifact:
        instruction = context.get("instruction") or context.get("summary", "")
        files       = context.get("files_changed", [])
        risk        = context.get("risk_level", "low")
        reflection  = context.get("reflection", "")

        prompt = f"""Draft a GitHub Pull Request. Respond with ONLY valid JSON, no markdown fences.

Instruction / context:
{instruction}

Files changed: {files}
Risk level: {risk}
Reflection notes: {reflection}

Return this exact JSON:
{{
  "title": "clear PR title",
  "body": "## Summary\\n...\\n## Files Affected\\n...\\n## Behavior Change\\n...\\n## Test Plan\\n- [ ] ...\\n## Risk Level\\nlow|medium|high\\n\\n_Drafted by GitHub Agent_",
  "labels": ["enhancement"],
  "head_branch": "feature/agent-draft"
}}"""

        raw = self._clean_json(llm.chat(prompt, max_tokens=1200))
        try:
            data = json.loads(raw)
        except Exception:
            data = {"title": "Agent-drafted PR", "body": raw,
                    "labels": [], "head_branch": "feature/agent-draft"}

        return DraftArtifact(
            draft_type="pr",
            title=data.get("title", "Untitled PR"),
            body=data.get("body", ""),
            labels=data.get("labels", []),
            head_branch=data.get("head_branch", "feature/agent-draft"),
            base_branch="main",
        )

    async def _improve_item(self, context: dict, config: dict) -> DraftArtifact:
        item_type   = context.get("item_type", "issue")
        item_number = context.get("item_number", 0)
        token       = config.get("github_token", "")
        grepo       = config.get("github_repo", "")

        tool_name = f"github_get_{item_type}"
        kwarg_key = "issue_number" if item_type == "issue" else "pr_number"

        console.print(f"  [dim]Fetching {item_type} #{item_number} via MCP...[/dim]")
        item_data = self.mcp.call(tool_name,
                                  github_repo=grepo,
                                  github_token=token,
                                  **{kwarg_key: item_number})

        if "error" in item_data:
            console.print(f"[red]Could not fetch {item_type}: {item_data}[/red]")
            return DraftArtifact(
                draft_type="improvement_suggestion",
                title="Could not fetch item",
                body=str(item_data),
                labels=[],
            )

        existing_title = item_data.get("title", "")
        existing_body  = item_data.get("body", "")

        prompt = f"""You are a senior engineer reviewing a GitHub {item_type}.

EXISTING TITLE: {existing_title}
EXISTING BODY:
{existing_body[:3000]}

Step 1 - CRITIQUE: Identify unclear language, missing sections, vague acceptance criteria, missing evidence.
Step 2 - IMPROVED VERSION: Rewrite with a structured, complete version.

Respond in this format:
## Critique
[your critique here]

## Improved Title
[new title]

## Improved Body
[full improved body with proper sections]"""

        suggestion = llm.chat(prompt, max_tokens=1500)

        return DraftArtifact(
            draft_type="improvement_suggestion",
            title=f"Improvement suggestion for {item_type} #{item_number}",
            body=suggestion,
            labels=[],
        )

    @staticmethod
    def _clean_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        return text.strip()
