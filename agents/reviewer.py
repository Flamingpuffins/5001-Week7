"""
REVIEWER AGENT
==============
Role: Analyze git diff / file content.
Produces a structured ReviewArtifact that downstream agents consume.

Implements:
  - Tool Use pattern (git_diff, list_files, read_file via MCP)
  - Planning pattern (explicit plan before analysis)
  - Reflection pattern (self-critique of findings)
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents.base import BaseAgent
from a2a.bus import A2AMessage
from llm_client import llm

console = Console()


@dataclass
class ReviewArtifact:
    diff:          str
    files_changed: list[str]
    summary:       str
    issues:        list[dict]
    change_type:   str   # feature | bugfix | refactor | docs | chore
    risk_level:    str   # low | medium | high
    recommendation: str  # create_issue | create_pr | no_action
    justification:  str
    reflection:     str  # critic output


class ReviewerAgent(BaseAgent):

    async def handle(self, msg: A2AMessage) -> Any:
        task    = msg.payload.get("task")
        repo    = msg.payload.get("repo_path", ".")
        token   = msg.payload.get("github_token", "")
        grepo   = msg.payload.get("github_repo", "")
        config  = msg.payload

        console.print(Panel(
            "[bold cyan]REVIEWER AGENT[/bold cyan]  —  Analyzing changes...",
            border_style="cyan"
        ))

        if task == "review_changes":
            artifact = await self._review_diff(config)
        elif task in ("create_issue", "create_pr"):
            # Pass through to planner with minimal review context
            artifact = ReviewArtifact(
                diff="(explicit instruction — no diff required)",
                files_changed=[],
                summary=msg.payload.get("instruction", ""),
                issues=[],
                change_type="chore",
                risk_level="low",
                recommendation="create_issue" if task == "create_issue" else "create_pr",
                justification="Explicit user instruction.",
                reflection="No diff to critique.",
            )
        elif task == "improve_item":
            artifact = ReviewArtifact(
                diff="",
                files_changed=[],
                summary="Improving existing item.",
                issues=[],
                change_type="chore",
                risk_level="low",
                recommendation="no_action",
                justification="Improvement task.",
                reflection="",
            )
        else:
            artifact = None

        # ── Hand off to Planner via A2A ──
        return await self.send("planner", {
            "task":     task,
            "artifact": artifact,
            **{k: v for k, v in config.items() if k != "task"},
        })

    async def _review_diff(self, config: dict) -> ReviewArtifact:
        repo         = config.get("repo_path", ".")
        commit_range = config.get("commit_range", "HEAD~1..HEAD")

        # ── PLANNING STEP ──
        console.print("\n[bold yellow]📋 PLAN[/bold yellow]")
        plan_steps = [
            "1. Fetch git diff via MCP[git_diff]",
            "2. List changed files via MCP[list_files]",
            "3. Send diff to LLM for analysis",
            "4. Run Reflection (critic) on findings",
            "5. Produce ReviewArtifact",
        ]
        for s in plan_steps:
            console.print(f"   [dim]{s}[/dim]")

        # ── TOOL USE (MCP) ──
        diff  = self.mcp.call("git_diff",   repo_path=repo, commit_range=commit_range)
        files = self.mcp.call("list_files", repo_path=repo, commit_range=commit_range)

        if not diff.strip() or diff.startswith("ERROR"):
            console.print("[yellow]⚠️  No diff found — using sample diff for demo.[/yellow]")
            diff  = SAMPLE_DIFF
            files = ["src/auth/login.py", "src/pricing/calculator.py"]

        console.print(f"\n[green]✓[/green] Files changed: {files}")

        # ── LLM ANALYSIS ──
        console.print("\n[bold yellow]🤖 LLM Analysis...[/bold yellow]")
        analysis_prompt = f"""You are a senior code reviewer. Analyze this git diff and respond with ONLY valid JSON.

Diff:
{diff[:6000]}

Files changed: {files}

Return this exact JSON structure:
{{
  "summary": "one sentence summary",
  "issues": [
    {{"title": "...", "description": "...", "evidence": "...", "severity": "low|medium|high"}}
  ],
  "change_type": "feature|bugfix|refactor|docs|chore",
  "risk_level": "low|medium|high",
  "recommendation": "create_issue|create_pr|no_action",
  "justification": "why this recommendation, with evidence from diff"
}}"""

        raw = llm.chat(analysis_prompt, max_tokens=1500)
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "summary": raw[:200],
                "issues": [],
                "change_type": "chore",
                "risk_level": "low",
                "recommendation": "no_action",
                "justification": "Could not parse LLM output.",
            }

        # ── REFLECTION (CRITIC) ──
        console.print("\n[bold yellow]🔍 REFLECTION — Critic checking findings...[/bold yellow]")
        reflection = await self._reflect(data, diff)

        self._print_review(data, files, reflection)

        return ReviewArtifact(
            diff=diff,
            files_changed=files,
            summary=data.get("summary", ""),
            issues=data.get("issues", []),
            change_type=data.get("change_type", "chore"),
            risk_level=data.get("risk_level", "low"),
            recommendation=data.get("recommendation", "no_action"),
            justification=data.get("justification", ""),
            reflection=reflection,
        )

    async def _reflect(self, analysis: dict, diff: str) -> str:
        """
        REFLECTION PATTERN — critic checks analysis for:
          - Unsupported claims
          - Missing evidence
          - Missing test mentions
          - Policy violations
        """
        critic_prompt = f"""You are a critic reviewing a code analysis. Check for:
1. Unsupported claims (not backed by diff)
2. Missing evidence
3. No mention of test coverage
4. Vague or unactionable findings

Analysis to critique:
{json.dumps(analysis, indent=2)}

Diff snippet:
{diff[:2000]}

Respond in 2-4 sentences: what is well-supported, what is missing or weak."""

        return llm.chat(critic_prompt, max_tokens=400)

    def _print_review(self, data: dict, files: list, reflection: str):
        # Issues table
        if data.get("issues"):
            t = Table(title="Issues Found", border_style="yellow")
            t.add_column("Title", style="bold")
            t.add_column("Severity")
            t.add_column("Evidence")
            for iss in data["issues"]:
                sev   = iss.get("severity", "?")
                color = {"high": "red", "medium": "yellow", "low": "green"}.get(sev, "white")
                t.add_row(
                    iss.get("title", ""),
                    f"[{color}]{sev}[/{color}]",
                    iss.get("evidence", "")[:80]
                )
            console.print(t)

        console.print(f"\n[bold]Change type:[/bold] {data.get('change_type')}")
        console.print(f"[bold]Risk:[/bold]        {data.get('risk_level')}")
        console.print(f"[bold]Recommendation:[/bold] {data.get('recommendation')}")
        console.print(f"[bold]Justification:[/bold]  {data.get('justification', '')[:300]}")
        console.print(Panel(
            f"[italic]{reflection}[/italic]",
            title="[bold]Reflection Artifact[/bold]",
            border_style="magenta"
        ))


# ── Fallback sample diff for demo / testing ──
SAMPLE_DIFF = """\
diff --git a/src/auth/login.py b/src/auth/login.py
index a1b2c3..d4e5f6 100644
--- a/src/auth/login.py
+++ b/src/auth/login.py
@@ -10,6 +10,12 @@ def login(username, password):
     user = db.find_user(username)
+    # TODO: add input validation
     if user and user.password == password:
         return generate_token(user)
-    return None
+    return {"error": "invalid credentials"}

diff --git a/src/pricing/calculator.py b/src/pricing/calculator.py
index 111..222 100644
--- a/src/pricing/calculator.py
+++ b/src/pricing/calculator.py
@@ -5,8 +5,8 @@ def calculate_price(item):
-    discount = item.price * 0.1
-    return item.price - discount
+    # duplicated from cart.py
+    discount = item.price * 0.1
+    final = item.price - discount
+    return final
"""
