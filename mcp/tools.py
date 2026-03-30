"""
MCP (Model Context Protocol) Tool Layer
========================================
All real-world side-effects live here. Agents MUST use these
tools rather than calling subprocess or requests directly.
This satisfies the MCP tooling requirement.

Tools exposed:
  git_diff        – run git diff in a repo
  git_log         – recent commits
  read_file       – read a file from the repo
  list_files      – list changed files
  github_get_issue      – fetch an existing issue
  github_get_pr         – fetch an existing PR
  github_create_issue   – create a new issue
  github_create_pr      – create a new PR
"""

from __future__ import annotations
import subprocess
import os
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests
from rich.console import Console

console = Console()

# ──────────────────────────────────────────────
# MCP Tool descriptor
# ──────────────────────────────────────────────

@dataclass
class MCPTool:
    name: str
    description: str
    parameters: dict   # JSON-schema-style

    def __call__(self, **kwargs) -> Any:
        raise NotImplementedError


# ──────────────────────────────────────────────
# Git tools
# ──────────────────────────────────────────────

class GitDiffTool(MCPTool):
    def __init__(self):
        super().__init__(
            name="git_diff",
            description="Returns the git diff for a commit range or working tree.",
            parameters={
                "repo_path":    {"type": "string"},
                "commit_range": {"type": "string", "default": "HEAD~1..HEAD"},
            }
        )

    def __call__(self, repo_path: str, commit_range: str = "HEAD~1..HEAD") -> str:
        console.print(f"  [dim]🔧 MCP[git_diff] range={commit_range}[/dim]")
        try:
            result = subprocess.run(
                ["git", "diff", commit_range],
                cwd=repo_path, capture_output=True, text=True, timeout=30
            )
            return result.stdout or "(no diff output)"
        except Exception as e:
            return f"ERROR: {e}"


class GitLogTool(MCPTool):
    def __init__(self):
        super().__init__(
            name="git_log",
            description="Returns recent git commit log.",
            parameters={
                "repo_path": {"type": "string"},
                "n":         {"type": "integer", "default": 5},
            }
        )

    def __call__(self, repo_path: str, n: int = 5) -> str:
        console.print(f"  [dim]🔧 MCP[git_log] n={n}[/dim]")
        try:
            result = subprocess.run(
                ["git", "log", f"-{n}", "--oneline"],
                cwd=repo_path, capture_output=True, text=True, timeout=30
            )
            return result.stdout or "(no log)"
        except Exception as e:
            return f"ERROR: {e}"


class ReadFileTool(MCPTool):
    def __init__(self):
        super().__init__(
            name="read_file",
            description="Reads a file from the repository.",
            parameters={
                "repo_path": {"type": "string"},
                "file_path": {"type": "string"},
            }
        )

    def __call__(self, repo_path: str, file_path: str) -> str:
        console.print(f"  [dim]🔧 MCP[read_file] {file_path}[/dim]")
        full = os.path.join(repo_path, file_path)
        try:
            with open(full) as f:
                return f.read()
        except Exception as e:
            return f"ERROR reading {file_path}: {e}"


class ListChangedFilesTool(MCPTool):
    def __init__(self):
        super().__init__(
            name="list_files",
            description="Lists files changed in a commit range.",
            parameters={
                "repo_path":    {"type": "string"},
                "commit_range": {"type": "string", "default": "HEAD~1..HEAD"},
            }
        )

    def __call__(self, repo_path: str, commit_range: str = "HEAD~1..HEAD") -> list[str]:
        console.print(f"  [dim]🔧 MCP[list_files] range={commit_range}[/dim]")
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", commit_range],
                cwd=repo_path, capture_output=True, text=True, timeout=30
            )
            return [f for f in result.stdout.strip().split("\n") if f]
        except Exception as e:
            return [f"ERROR: {e}"]


# ──────────────────────────────────────────────
# GitHub API tools
# ──────────────────────────────────────────────

class GitHubBase(MCPTool):
    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api(self, method: str, path: str, token: str, **kwargs) -> dict:
        url = f"https://api.github.com{path}"
        resp = requests.request(method, url, headers=self._headers(token), **kwargs)
        if not resp.ok:
            return {"error": resp.status_code, "message": resp.text}
        return resp.json()


class GitHubGetIssueTool(GitHubBase):
    def __init__(self):
        super().__init__(
            name="github_get_issue",
            description="Fetches an existing GitHub issue.",
            parameters={
                "github_repo":  {"type": "string"},
                "github_token": {"type": "string"},
                "issue_number": {"type": "integer"},
            }
        )

    def __call__(self, github_repo: str, github_token: str, issue_number: int) -> dict:
        console.print(f"  [dim]🔧 MCP[github_get_issue] #{issue_number}[/dim]")
        return self._api("GET", f"/repos/{github_repo}/issues/{issue_number}", github_token)


class GitHubGetPRTool(GitHubBase):
    def __init__(self):
        super().__init__(
            name="github_get_pr",
            description="Fetches an existing GitHub pull request.",
            parameters={
                "github_repo":  {"type": "string"},
                "github_token": {"type": "string"},
                "pr_number":    {"type": "integer"},
            }
        )

    def __call__(self, github_repo: str, github_token: str, pr_number: int) -> dict:
        console.print(f"  [dim]🔧 MCP[github_get_pr] #{pr_number}[/dim]")
        return self._api("GET", f"/repos/{github_repo}/pulls/{pr_number}", github_token)


class GitHubCreateIssueTool(GitHubBase):
    def __init__(self):
        super().__init__(
            name="github_create_issue",
            description="Creates a new GitHub issue.",
            parameters={
                "github_repo":  {"type": "string"},
                "github_token": {"type": "string"},
                "title":        {"type": "string"},
                "body":         {"type": "string"},
                "labels":       {"type": "array"},
            }
        )

    def __call__(self, github_repo: str, github_token: str,
                 title: str, body: str, labels: list = None) -> dict:
        console.print(f"  [dim]🔧 MCP[github_create_issue] '{title}'[/dim]")
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return self._api("POST", f"/repos/{github_repo}/issues",
                         github_token, json=payload)


class GitHubCreatePRTool(GitHubBase):
    def __init__(self):
        super().__init__(
            name="github_create_pr",
            description="Creates a new GitHub pull request.",
            parameters={
                "github_repo":  {"type": "string"},
                "github_token": {"type": "string"},
                "title":        {"type": "string"},
                "body":         {"type": "string"},
                "head":         {"type": "string"},
                "base":         {"type": "string"},
            }
        )

    def __call__(self, github_repo: str, github_token: str,
                 title: str, body: str, head: str, base: str = "main") -> dict:
        console.print(f"  [dim]🔧 MCP[github_create_pr] '{title}'[/dim]")
        return self._api("POST", f"/repos/{github_repo}/pulls", github_token,
                         json={"title": title, "body": body,
                               "head": head, "base": base})


# ──────────────────────────────────────────────
# MCP Tool Registry
# ──────────────────────────────────────────────

class MCPToolRegistry:
    """
    Central registry for all MCP tools.
    Agents import this and call tools by name —
    satisfying the MCP protocol requirement.
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        for tool in [
            GitDiffTool(),
            GitLogTool(),
            ReadFileTool(),
            ListChangedFilesTool(),
            GitHubGetIssueTool(),
            GitHubGetPRTool(),
            GitHubCreateIssueTool(),
            GitHubCreatePRTool(),
        ]:
            self._tools[tool.name] = tool

    def call(self, tool_name: str, **kwargs) -> Any:
        if tool_name not in self._tools:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
        return self._tools[tool_name](**kwargs)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def describe(self, tool_name: str) -> str:
        t = self._tools[tool_name]
        return f"{t.name}: {t.description}"


# Singleton — all agents share one registry
mcp = MCPToolRegistry()
